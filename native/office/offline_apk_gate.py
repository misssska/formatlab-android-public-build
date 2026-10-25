#!/usr/bin/env python3
"""Fail-closed offline Android Office APK audit; not proof of document fidelity."""
from __future__ import annotations
import argparse,hashlib,json,re,shutil,subprocess,sys,zipfile
from pathlib import Path,PurePosixPath

PACKAGE_ID='hu.formatlab.android'
LIB='lib/arm64-v8a/liblo-native-code.so'
REQUIRED=(
    'AndroidManifest.xml','classes.dex',LIB,
    'assets/program/fundamentalrc','assets/program/bootstraprc',
    'assets/program/unorc','assets/program/versionrc',
    'assets/unpack/program/sofficerc',
    'assets/share/registry/main.xcd',
    'assets/share/registry/res/registry_en-US.xcd',
    'res/raw/license.txt','res/raw/notice.txt')
MAX_ENTRIES=30000
MAX_TOTAL_UNCOMPRESSED=3*1024**3
MAX_FILE_UNCOMPRESSED=1024**3
MAX_COMPRESSION_RATIO=500
PERMISSION=re.compile(r"(?:uses-permission|uses-permission-sdk-\d+):\s+name='([^']+)'",re.I)
BADGING=re.compile(r"\bpackage:\s+name='([^']+)'",re.I)

def elf_arm64_header(buffer:bytes)->bool:
    return (len(buffer)>=20 and buffer[:6]==b'\x7fELF\x02\x01'
            and int.from_bytes(buffer[16:18],'little')==3
            and int.from_bytes(buffer[18:20],'little')==183)

def scan_entries(infos:list[zipfile.ZipInfo])->tuple[set[str],list[str]]:
    seen=set()
    failures=[]
    total=0
    if len(infos)>MAX_ENTRIES:failures.append('ZIP_TOO_MANY_ENTRIES')
    for info in infos:
        path=info.filename
        p=PurePosixPath(path)
        if (path.startswith('/') or '\\' in path or '\x00' in path
                or '//' in path or '/./' in path or path.startswith('./')
                or any(x in ('..','') for x in p.parts)):
            failures.append('UNSAFE_ZIP_ENTRY')
        if path in seen:failures.append('DUPLICATE_ZIP_ENTRY')
        seen.add(path)
        mode=(info.external_attr>>16)&0o170000
        if mode==0o120000:failures.append('ZIP_SYMLINK_ENTRY')
        if info.file_size>MAX_FILE_UNCOMPRESSED:failures.append('ZIP_OVERSIZE_ENTRY')
        total+=info.file_size
        if info.file_size and info.file_size/max(info.compress_size,1)>MAX_COMPRESSION_RATIO:
            failures.append('ZIP_EXCESSIVE_COMPRESSION_RATIO')
    if total>MAX_TOTAL_UNCOMPRESSED:failures.append('ZIP_TOTAL_TOO_LARGE')
    return seen,sorted(set(failures))

def assess_metadata(names:set[str],*,package:str,permissions:list[str],
                    elf_header:bytes,lib_size:int)->dict:
    reasons=[]
    if package!=PACKAGE_ID:reasons.append('WRONG_APPLICATION_ID')
    if permissions:reasons.append('UNEXPECTED_ANDROID_PERMISSIONS')
    missing=[x for x in REQUIRED if x not in names]
    if missing:reasons.append('REQUIRED_RUNTIME_ASSETS_MISSING')
    fonts=[x for x in names if x.startswith('assets/unpack/user/fonts/')
           and x.lower().endswith(('.ttf','.otf'))]
    if not fonts:reasons.append('BUNDLED_FONTS_MISSING')
    if not elf_arm64_header(elf_header) or not 1000000<=lib_size<=1024**3:
        reasons.append('NATIVE_ENGINE_NOT_ARM64_ELF_SHARED')
    return {'status':'PACKAGE_STATIC_PASS' if not reasons else 'BLOCKED',
            'issues':reasons,'package':package,'permissions':permissions,
            'missing_assets':missing,'bundled_font_count':len(fonts),
            'lib_bytes':lib_size,'docx_pdf_fidelity_proved':False,
            'airplane_mode_device_tested':False,'public_release_approved':False}

def sdk_aapt(apk:Path,aapt:str|Path|None,*,runner=subprocess.run)->tuple[str,list[str]]:
    if not aapt:raise ValueError('AAPT_REQUIRED')
    exe=Path(aapt)
    if not exe.is_file():
        found=shutil.which(str(aapt))
        if not found:raise ValueError('AAPT_NOT_FOUND')
        exe=Path(found)
    def call(*args):
        try:
            res=runner([str(exe),'dump',*args,str(apk)],check=False,timeout=30,
                       capture_output=True,text=True)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise ValueError('AAPT_EXECUTION_FAILED') from exc
        if res.returncode:raise ValueError('AAPT_REJECTED_APK')
        return res.stdout
    badging=call('badging')
    perms=call('permissions')
    match=BADGING.search(badging)
    if not match:raise ValueError('PACKAGE_NAME_NOT_DECODED')
    return match.group(1),sorted(set(PERMISSION.findall(perms)))

def inspect_apk(apk:Path,*,aapt:str|Path|None)->dict:
    apk=Path(apk)
    base={'status':'BLOCKED','issues':[],'apk':apk.name,
          'docx_pdf_fidelity_proved':False,'airplane_mode_device_tested':False,
          'public_release_approved':False}
    if not apk.is_file() or apk.is_symlink():
        base['issues']=['APK_MISSING_OR_SYMLINK'];return base
    size=apk.stat().st_size
    if size<1024 or size>3*1024**3:
        base['issues']=['APK_SIZE_OUT_OF_RANGE'];return base
    try:
        with zipfile.ZipFile(apk) as z:
            names,errors=scan_entries(z.infolist())
            if errors:
                base['issues']=errors;return base
            info=z.getinfo(LIB) if LIB in names else None
            if info is None:
                header=b'';lib_size=0
            else:
                with z.open(info) as f:header=f.read(64)
                lib_size=info.file_size
    except (OSError,ValueError,zipfile.BadZipFile,RuntimeError,KeyError):
        base['issues']=['APK_ZIP_INVALID'];return base
    try:
        package,permissions=sdk_aapt(apk,aapt)
    except ValueError as exc:
        base['issues']=[str(exc)];return base
    result=assess_metadata(names,package=package,permissions=permissions,
                           elf_header=header,lib_size=lib_size)
    sha=hashlib.sha256()
    with apk.open('rb') as f:
        for chunk in iter(lambda:f.read(1024**2),b''):sha.update(chunk)
    result.update(apk=apk.name,apk_bytes=size,sha256=sha.hexdigest())
    return result

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('apk',type=Path)
    p.add_argument('--aapt',type=Path,required=True)
    p.add_argument('--report',type=Path)
    args=p.parse_args()
    result=inspect_apk(args.apk,aapt=args.aapt)
    document=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(document,encoding='utf-8')
    print(document,end='')
    return 0 if result['status']=='PACKAGE_STATIC_PASS' else 2

if __name__=='__main__':sys.exit(main())
