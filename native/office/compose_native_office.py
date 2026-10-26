#!/usr/bin/env python3
"""P0g: assemble an unshipped FormatLab Android source tree with verified LibreOffice assets.

Inputs MUST include a real upstream LibreOffice reference APK, an attested native
ARM64 library directory, and exact P0c evidence. No download, shell, APK signing
or release occurs here. Production UI remains disabled until device acceptance.
"""
from __future__ import annotations
import argparse,hashlib,json,re,shutil,sys,zipfile
from pathlib import Path

from assemble_runtime_overlay import assemble,GateError,ORIGINAL_SHA256
from offline_apk_gate import (REQUIRED,REQUIRED_NATIVE_LIBS,PACKAGE_ID,
                              elf_arm64_header,scan_entries)

SOURCE_SHA='f2820323446ae210668dcb6422ddcd55ce939dc2'
REQUIRED_ASSETS=tuple(x for x in REQUIRED if x.startswith('assets/'))
REQUIRED_LICENSES=('res/raw/license.txt','res/raw/notice.txt')
MAX_UPSTREAM_APK=3*1024**3
MAX_COPY_BYTES=3*1024**3

def hash_file(path:Path)->str:
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def elf_gnu_build_id(stream)->str|None:
    """Read the linker GNU build-id from a little-endian ELF64 PT_NOTE segment.

    A stripped Android APK library may differ byte-for-byte from the unstripped
    library in P0c's native-libs directory; matching build IDs are evidence
    that the linker produced the same object. Fail closed if notes are absent.
    """
    stream.seek(0)
    header=stream.read(64)
    if not elf_arm64_header(header):
        return None
    phoff=int.from_bytes(header[32:40],'little')
    phsize=int.from_bytes(header[54:56],'little')
    phnum=int.from_bytes(header[56:58],'little')
    if phoff<64 or phoff>1024*1024 or phsize<56 or phsize>256 or phnum>256:
        return None
    for i in range(phnum):
        stream.seek(phoff+i*phsize)
        ph=stream.read(phsize)
        if len(ph)!=phsize or int.from_bytes(ph[0:4],'little')!=4:
            continue
        noteoff=int.from_bytes(ph[8:16],'little')
        notesize=int.from_bytes(ph[32:40],'little')
        if noteoff<64 or notesize>1024*1024 or notesize<16:
            continue
        stream.seek(noteoff)
        blob=stream.read(notesize)
        p=0
        while p+12<=len(blob):
            namelen=int.from_bytes(blob[p:p+4],'little')
            datalen=int.from_bytes(blob[p+4:p+8],'little')
            note_type=int.from_bytes(blob[p+8:p+12],'little')
            p+=12
            name_end=p+namelen
            data_start=p+((namelen+3)//4)*4
            data_end=data_start+datalen
            next_note=data_start+((datalen+3)//4)*4
            if namelen>128 or datalen>128 or next_note>len(blob):
                break
            if blob[p:name_end]==b'GNU\x00' and note_type==3 and datalen>=16:
                return blob[data_start:data_end].hex()
            p=next_note
    return None

def verified_upstream(reference_apk:Path)->dict:
    reference_apk=Path(reference_apk)
    if not reference_apk.is_file() or reference_apk.is_symlink():
        raise GateError('UPSTREAM_REFERENCE_APK_MISSING')
    if not 1024<reference_apk.stat().st_size<MAX_UPSTREAM_APK:
        raise GateError('UPSTREAM_REFERENCE_APK_SIZE_INVALID')
    try:
        with zipfile.ZipFile(reference_apk) as z:
            names,issues=scan_entries(z.infolist())
            if issues:raise GateError('UNSAFE_UPSTREAM_APK:'+','.join(issues))
            necessary=REQUIRED_ASSETS+REQUIRED_LICENSES+REQUIRED_NATIVE_LIBS
            absent=[x for x in necessary if x not in names]
            if absent:raise GateError('UPSTREAM_RUNTIME_PARTS_MISSING:'+','.join(absent[:8]))
            fonts=[x for x in names if x.startswith('assets/unpack/user/fonts/')
                   and x.lower().endswith(('.ttf','.otf'))]
            if not fonts:raise GateError('UPSTREAM_BUNDLED_FONTS_MISSING')
            if 'assets/unpack/etc/fonts/fonts.conf' not in names:
                raise GateError('UPSTREAM_FONTCONFIG_MISSING')
            total_assets=sum(i.file_size for i in z.infolist() if i.filename.startswith('assets/'))
            if total_assets>MAX_COPY_BYTES:raise GateError('UPSTREAM_ASSETS_EXCEED_LIMIT')
            for n in REQUIRED_NATIVE_LIBS:
                info=z.getinfo(n)
                with z.open(n) as f:header=f.read(64)
                if not elf_arm64_header(header):
                    raise GateError('UPSTREAM_NATIVE_ABI_INVALID:'+n)
                if info.file_size<(1_000_000 if n.endswith('liblo-native-code.so') else 4096):
                    raise GateError('UPSTREAM_NATIVE_LIB_TOO_SMALL:'+n)
            return {'apk_sha256':hash_file(reference_apk),
                    'reference_assets':sum(1 for n in names if n.startswith('assets/')),
                    'reference_fonts':len(fonts),
                    'native_libs':len(REQUIRED_NATIVE_LIBS)}
    except (OSError,zipfile.BadZipFile,RuntimeError,KeyError) as ex:
        raise GateError('UNREADABLE_UPSTREAM_APK') from ex

def qualify_bundle(reference_apk:Path,libs:Path,evidence:Path)->dict:
    ref=verified_upstream(reference_apk)
    libs=Path(libs)
    if not libs.is_dir() or libs.is_symlink():
        raise GateError('NATIVE_BUNDLE_MISSING')
    try:record=json.loads(Path(evidence).read_text(encoding='utf-8'))
    except (OSError,ValueError) as ex:raise GateError('NATIVE_ATTESTATION_UNREADABLE') from ex
    if (record.get('status')!='NATIVE_BUILD_ATTESTED'
        or record.get('engine_compiled') is not True
        or record.get('pinned_source_commit')!=SOURCE_SHA
        or record.get('engine',{}).get('status')!='PASS'):
        raise GateError('NATIVE_ATTESTATION_NOT_ACCEPTED')
    report_libs={}
    with zipfile.ZipFile(reference_apk) as z:
        for path in REQUIRED_NATIVE_LIBS:
            lib_name=Path(path).name
            native=libs/lib_name
            if not native.is_file() or native.is_symlink():
                raise GateError('NATIVE_BUNDLE_LIBRARY_MISSING:'+lib_name)
            with native.open('rb') as f:header=f.read(64)
            if not elf_arm64_header(header):
                raise GateError('NATIVE_BUNDLE_WRONG_ABI:'+lib_name)
            checksum=hash_file(native)
            with z.open(path) as source:
                reference_hash=hashlib.sha256()
                for part in iter(lambda:source.read(1024*1024),b''):
                    reference_hash.update(part)
            reference_sha=reference_hash.hexdigest()
            comparison='EXACT_SHA256'
            if checksum!=reference_sha:
                # Gradle may strip symbols when making the reference APK.
                # Do not accept a different native library just because it is ELF.
                with native.open('rb') as raw, z.open(path) as packaged:
                    raw_id=elf_gnu_build_id(raw)
                    packaged_id=elf_gnu_build_id(packaged)
                if not raw_id or raw_id!=packaged_id:
                    raise GateError('NATIVE_REFERENCE_MISMATCH:'+lib_name)
                comparison='MATCHING_GNU_BUILD_ID_AFTER_STRIP'
            if lib_name=='liblo-native-code.so' and checksum!=record['engine']['sha256']:
                raise GateError('ENGINE_SHA256_MISMATCH')
            report_libs[lib_name]={'bytes':native.stat().st_size,
                                   'sha256':checksum,
                                   'reference_apk_sha256':reference_sha,
                                   'comparison':comparison}
    ref['libs']=report_libs
    ref['pinned_libreoffice_source']=SOURCE_SHA
    return ref

def compose(source_zip:Path,upstream_tree:Path,java_overlay:Path,
            reference_apk:Path,libs:Path,evidence:Path,destination:Path,
            *,expected_source_sha:str=ORIGINAL_SHA256)->dict:
    destination=Path(destination)
    if destination.exists():raise GateError('DESTINATION_MUST_NOT_EXIST')
    proof=qualify_bundle(reference_apk,libs,evidence)
    # Always build from the pinned source ZIP via existing safe v0.3 assembler.
    result=assemble(source_zip,upstream_tree,java_overlay,destination,
                    expected_sha=expected_source_sha)
    try:
        asset_root=destination/'app/src/main/assets'
        jni_root=destination/'app/src/main/jniLibs/arm64-v8a'
        license_root=destination/'app/src/main/res/raw'
        with zipfile.ZipFile(reference_apk) as z:
            for info in z.infolist():
                if not info.filename.startswith('assets/') or info.is_dir():continue
                relative=Path(info.filename).relative_to('assets')
                target=asset_root/relative
                if target.exists():raise GateError('FORMATLAB_ASSET_COLLISION:'+str(relative))
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as f,target.open('wb') as w:
                    shutil.copyfileobj(f,w,length=1024*1024)
            for resource in REQUIRED_LICENSES:
                dest=license_root/Path(resource).name
                if dest.exists():raise GateError('FORMATLAB_LICENSE_COLLISION')
                dest.parent.mkdir(parents=True,exist_ok=True)
                with z.open(resource) as f,dest.open('wb') as w:
                    shutil.copyfileobj(f,w,length=1024*1024)
        jni_root.mkdir(parents=True,exist_ok=True)
        for path in REQUIRED_NATIVE_LIBS:
            dest=jni_root/Path(path).name
            if dest.exists():raise GateError('FORMATLAB_NATIVE_COLLISION')
            shutil.copyfile(libs/Path(path).name,dest)
        # Pinned upstream fontconfig is app-ID-specific. It cannot be blindly
        # transplanted from org.libreoffice into hu.formatlab.android.
        fonts=(asset_root/'unpack/etc/fonts/fonts.conf')
        configuration=fonts.read_text(encoding='utf-8')
        # Upstream copyUnpackAssets expands @@APPLICATION_ID@@ to its own
        # Android app ID; remap ONLY the well-known fontconfig cache path.
        matches=re.findall(r'/data/data/([A-Za-z0-9_.]+)/fontconfig',configuration)
        if len(matches)!=1 or '@@APPLICATION_ID@@' in configuration:
            raise GateError('FONTCONFIG_APPLICATION_ID_UNVERIFIED')
        configuration=configuration.replace('/data/data/'+matches[0]+'/fontconfig',
                                            '/data/data/'+PACKAGE_ID+'/fontconfig')
        fonts.write_text(configuration,encoding='utf-8')
        result.update(status='NATIVE_OFFICE_SOURCE_COMPOSED_NOT_RELEASED',
                      native_lib_bundled=True,reference_apk_sha256=proof['apk_sha256'],
                      verified_library_count=len(proof['libs']),
                      verified_asset_count=proof['reference_assets'],
                      reference_font_count=proof['reference_fonts'],
                      offline_document_conversion_executed=False,
                      android_apk_built=False,public_release_approved=False)
        (destination/'FORMATLAB_OFFICE_COMPOSE_EVIDENCE.json').write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result
    except Exception:
        shutil.rmtree(destination,ignore_errors=True)
        raise

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source-zip','upstream-tree','java-overlay','reference-apk',
                'native-libs','evidence','destination'):
        p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args()
    try:
        result=compose(a.source_zip,a.upstream_tree,a.java_overlay,
                       a.reference_apk,a.native_libs,a.evidence,a.destination)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (GateError,ValueError,OSError) as ex:
        print('FORMATLAB_OFFLINE_NATIVE_INTEGRATION_BLOCKED:',str(ex),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
