#!/usr/bin/env python3
"""Read-only v0.3 source validation + isolated Java overlay assembly for offline Office.

No native lib present or runtime feature exposed in the generated candidate APK.
No release publishing. Intended for CI compilation gate only.
"""
from __future__ import annotations
import argparse,hashlib,json,re,shutil,sys,zipfile
from pathlib import Path,PurePosixPath

ORIGINAL_SHA256='04694a0afbc26ebcbe7dd0c4c265d656acc05497d6d5765980c22e4366c0123b'
ROOT='FormatLab-Android-v0.3'
JAVA_PACKAGE='app/src/main/java/hu/formatlab/android'
KIT_PATH='app/src/main/java/org/libreoffice/kit'
PINNED_KIT=(
 'LibreOfficeKit.java','Office.java','Document.java','DirectBufferAllocator.java'
)
SOURCE_UPSTREAM='android/Bootstrap/src/org/libreoffice/kit'
OVERLAY_JAVA=('FormatLabOfflineOfficeConverter.java','FormatLabOfficeService.java','FormatLabOfficeProcessClient.java')
SERVICE_PROCESS=':office'
MAX_ENTRIES=1000
MAX_INPUT_UNCOMPRESSED=20*1024*1024
MAX_FILE=5*1024*1024

class GateError(ValueError):pass

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as fp:
        for b in iter(lambda:fp.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify_archive(archive:Path,expected_sha:str=ORIGINAL_SHA256)->list[zipfile.ZipInfo]:
    if not archive.is_file() or archive.is_symlink():
        raise GateError('SOURCE_ARCHIVE_MISSING')
    if sha256(archive)!=expected_sha:
        raise GateError('SOURCE_SHA256_MISMATCH')
    try:
        with zipfile.ZipFile(archive) as z:
            items=z.infolist()
            if len(items)>MAX_ENTRIES:raise GateError('TOO_MANY_ZIP_ENTRIES')
            total=0
            seen=set()
            for item in items:
                name=item.filename
                p=PurePosixPath(name)
                if (not name.startswith(ROOT+'/') or name.startswith('/') or
                    '\\' in name or '\x00' in name or
                    any(part=='..' for part in p.parts) or
                    len(set(p.parts))==0 or
                    ((item.external_attr>>16)&0o170000)==0o120000):
                    raise GateError('UNSAFE_SOURCE_ZIP')
                if name in seen:raise GateError('DUPLICATE_SOURCE_ZIP')
                seen.add(name)
                if item.file_size>MAX_FILE:raise GateError('OVERSIZED_SOURCE_ENTRY')
                total+=item.file_size
            if total>MAX_INPUT_UNCOMPRESSED:raise GateError('SOURCE_ZIP_BOMB')
            if z.testzip() is not None:raise GateError('ZIP_CRC_FAILED')
            return items
    except zipfile.BadZipFile as ex:
        raise GateError('CORRUPT_ZIP') from ex

def assemble(archive:Path,upstream:Path,overlay:Path,output:Path,
             *,expected_sha:str=ORIGINAL_SHA256)->dict:
    verify_archive(archive,expected_sha=expected_sha)
    output=Path(output).resolve()
    if output.exists():
        raise GateError('OUTPUT_MUST_BE_EMPTY')
    output.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                relative=PurePosixPath(item.filename).relative_to(ROOT)
                if not relative.parts:continue
                path=output.joinpath(*relative.parts)
                if item.is_dir():
                    path.mkdir(parents=True,exist_ok=True)
                else:
                    path.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(item) as src,path.open('wb') as dest:
                        shutil.copyfileobj(src,dest,length=1024*1024)
        appjava=output/JAVA_PACKAGE
        if not appjava.is_dir() or not (output/'app/build.gradle').exists():
            # Alternative Gradle Kotlin project still has app/build.gradle.kts
            if not appjava.is_dir() or not (output/'app/build.gradle.kts').exists():
                raise GateError('ANDROID_PROJECT_LAYOUT_UNEXPECTED')
        main=appjava/'MainActivity.java'
        if not main.is_file() or 'package hu.formatlab.android;' not in main.read_text(errors='replace'):
            raise GateError('UNEXPECTED_APP_PACKAGE')
        manifest=output/'app/src/main/AndroidManifest.xml'
        if not manifest.is_file():
            raise GateError('MANIFEST_NOT_FOUND')
        data=manifest.read_text(encoding='utf-8')
        if 'android.permission.INTERNET' in data:
            raise GateError('INTERNET_PERMISSION_FORBIDDEN')
        api_dest=output/KIT_PATH
        api_dest.mkdir(parents=True,exist_ok=True)
        copied=[]
        for name in PINNED_KIT:
            src=Path(upstream)/SOURCE_UPSTREAM/name
            if not src.is_file() or 'package org.libreoffice.kit;' not in src.read_text(errors='replace'):
                raise GateError('UPSTREAM_KIT_SOURCE_MISSING:'+name)
            content=src.read_text(encoding='utf-8')
            if name=='LibreOfficeKit.java':
                # Upstream init only uses Context-compatible methods; keep all
                # other pinned JNI declarations byte-for-byte unchanged.
                required=('import android.app.Activity;',
                          'init(Activity activity)',
                          'activity.getApplication().getCacheDir()',
                          'activity.getApplication().getPackageResourcePath()')
                if any(x not in content for x in required):
                    raise GateError('UPSTREAM_CONTEXT_ADAPTER_PATTERN_CHANGED')
                content=content.replace('import android.app.Activity;',
                                        'import android.content.Context;')
                content=content.replace('init(Activity activity)',
                                        'init(Context activity)')
                content=content.replace('activity.getApplication().getCacheDir()',
                                        'activity.getApplicationContext().getCacheDir()')
                content=content.replace('activity.getApplication().getPackageResourcePath()',
                                        'activity.getPackageResourcePath()')
                (api_dest/name).write_text(content,encoding='utf-8')
            else:
                shutil.copyfile(src,api_dest/name)
            copied.append({'path':str((api_dest/name).relative_to(output)),
                           'sha256':sha256(api_dest/name)})
        for name in OVERLAY_JAVA:
            src=Path(overlay)/name
            if not src.is_file() or 'package hu.formatlab.android;' not in src.read_text(errors='replace'):
                raise GateError('OVERLAY_SOURCE_MISSING:'+name)
            target=appjava/name
            if target.exists():raise GateError('ANDROID_OVERLAY_ALREADY_EXISTS')
            shutil.copyfile(src,target)
            copied.append({'path':str(target.relative_to(output)),'sha256':sha256(target)})
        # Non-exported separate-process service, never callable from other apps.
        # Preserve original manifest bytes other than a single inserted service.
        service_element=('        <service android:name="hu.formatlab.android.FormatLabOfficeService"'
                         ' android:process=":office" android:exported="false" />\n')
        if data.count('</application>')!=1 or 'xmlns:android=' not in data:
            raise GateError('ANDROID_APPLICATION_MANIFEST_UNEXPECTED')
        if 'FormatLabOfficeService' in data:
            raise GateError('OFFICE_SERVICE_ALREADY_REGISTERED')
        data=data.replace('</application>',service_element+'</application>')
        manifest.write_text(data,encoding='utf-8')
        result={'status':'SOURCE_OVERLAY_ASSEMBLED','source_sha256':sha256(archive),
                'upstream_kit_version':'f2820323446ae210668dcb6422ddcd55ce939dc2',
                'sources':copied,'native_lib_bundled':False,
                'document_conversion_runtime_tested':False,'feature_exposed_in_ui':False,
                'separate_process_service_declared':True,'native_timeout_watchdog_seconds':180,
                'upstream_context_adapter_pinned':True}
        (output/'FORMATLAB_OFFICE_OVERLAY_EVIDENCE.json').write_text(
            json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return result
    except Exception:
        shutil.rmtree(output,ignore_errors=True)
        raise

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-zip',type=Path,required=True)
    p.add_argument('--upstream',type=Path,required=True)
    p.add_argument('--overlay',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:
        result=assemble(args.source_zip,args.upstream,args.overlay,args.output)
        print(json.dumps(result,indent=2))
        return 0
    except (GateError,OSError,ValueError) as ex:
        print('OFFLINE_OFFICE_OVERLAY_BLOCKED:',str(ex),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
