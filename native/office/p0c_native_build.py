#!/usr/bin/env python3
"""Bounded actual LibreOffice ARM64 build. Does not integrate FormatLab APK."""
from __future__ import annotations
import argparse, json, os, shutil, signal, subprocess, sys, time
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from engine_source_gate import inspect, config_preview

MIN_DISK_GIB=12
MIN_MEM_GIB=10

def memory_gib(path=Path('/proc/meminfo')):
    try:
        for line in path.read_text().splitlines():
            if line.startswith('MemAvailable:'):
                return int(line.split()[1])/(1024*1024)
    except (OSError, IndexError, ValueError):
        pass
    return None

def disposable(source, root=None):
    if os.environ.get('FORMATLAB_DISPOSABLE_CHECKOUT')!='YES':
        raise ValueError('DISPOSABLE_OPT_IN_REQUIRED')
    if os.environ.get('FORMATLAB_ALLOW_NATIVE_BUILD')!='YES':
        raise ValueError('NATIVE_BUILD_OPT_IN_REQUIRED')
    source=Path(source).resolve(strict=True)
    root=Path(root or os.environ.get('RUNNER_TEMP','/nonexistent')).resolve()
    if source==root or not source.is_relative_to(root):
        raise ValueError('SOURCE_NOT_UNDER_DISPOSABLE_ROOT')
    if source.name!='formatlab-lo-p0c':
        raise ValueError('SOURCE_DIRECTORY_NAME_NOT_PINNED')

def attest_arm64(path, min_bytes=1_000_000):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('ENGINE_MISSING_OR_SYMLINK')
    n=path.stat().st_size
    if n<min_bytes or n>1024**3:
        raise ValueError('ENGINE_SIZE_OUT_OF_RANGE')
    with path.open('rb') as f:
        h=f.read(64)
    if len(h)!=64 or h[:6]!=b'\x7fELF\x02\x01':
        raise ValueError('NOT_ELF64_LITTLE_ENDIAN')
    typ=int.from_bytes(h[16:18],'little')
    machine=int.from_bytes(h[18:20],'little')
    if (typ,machine)!=(3,183):
        raise ValueError('NOT_ARM64_SHARED_OBJECT')
    return {'status':'PASS','abi':'arm64-v8a','elf_machine':183,'size_bytes':n}

def upstream_apks(source):
    """Upstream LibreOffice APK is NOT a FormatLab app."""
    root=Path(source)/'android/app/build/outputs/apk'
    found=[]
    if root.is_dir():
        for p in sorted(root.rglob('*.apk')):
            if p.is_symlink() or not p.is_file():
                continue
            try:
                with ZipFile(p) as z:
                    names=z.namelist()
                    if 'AndroidManifest.xml' in names and any(
                       x.endswith('/arm64-v8a/liblo-native-code.so') for x in names):
                        found.append({'path':str(p.relative_to(source)),'bytes':p.stat().st_size})
            except BadZipFile:
                continue
    return {'upstream_reference_apks':found,'formatlab_apk_built':False}

def preflight(source,sdk,ndk,*,disk_gib=None,mem_gib=None,require_approval=True,root=None):
    source,sdk,ndk=(Path(p).resolve() for p in (source,sdk,ndk))
    problems=[]
    if require_approval:
        try: disposable(source,root)
        except (OSError,ValueError) as e: problems.append(str(e))
    src=inspect(source)
    if src.get('status')!='PASS': problems.append('SOURCE_PIN_FAILED')
    try: config_preview(sdk,ndk)
    except ValueError as e: problems.append('ANDROID_TOOLCHAIN_INVALID:'+str(e))
    if not (source/'config_host.mk').is_file() or not (source/'Makefile').is_file():
        problems.append('UPSTREAM_NOT_CONFIGURED')
    if not (sdk/'platforms/android-35').is_dir():
        problems.append('ANDROID_35_NOT_INSTALLED')
    if not shutil.which('make'):
        problems.append('MAKE_MISSING')
    try:
        disk_gib=disk_gib if disk_gib is not None else shutil.disk_usage(source).free/(1024**3)
    except OSError: disk_gib=0
    mem_gib=mem_gib if mem_gib is not None else memory_gib()
    if disk_gib<MIN_DISK_GIB: problems.append('DISK_LIMIT')
    if mem_gib is None or mem_gib<MIN_MEM_GIB: problems.append('MEMORY_LIMIT')
    return {'status':'READY_TO_BUILD' if not problems else 'BLOCKED','blockers':problems,
            'disk_available_gib':round(disk_gib,2),
            'mem_available_gib':round(mem_gib,2) if mem_gib is not None else None,
            'pinned_source_commit':src.get('commit'),
            'engine_compiled':False,'formatlab_apk_built':False}

def build(source,sdk,ndk,*,jobs=2,timeout_sec=4800,log=None):
    source=Path(source).resolve()
    if not 1<=jobs<=3: raise ValueError('PARALLEL_JOB_LIMIT')
    if not 120<=timeout_sec<=6000: raise ValueError('TIMEOUT_OUT_OF_RANGE')
    evidence=preflight(source,sdk,ndk)
    evidence['build_attempted']=False
    if evidence['status']!='READY_TO_BUILD': return evidence
    log=Path(log or Path(os.environ.get('RUNNER_TEMP','/tmp'))/'formatlab-p0c-make.log')
    log.parent.mkdir(parents=True,exist_ok=True)
    evidence['build_attempted']=True
    start=time.monotonic()
    try:
        with log.open('wb') as out:
            child=subprocess.Popen(['make',f'-j{jobs}','android'],cwd=source,
                stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,
                start_new_session=True)
            try: code=child.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGKILL)
                    child.wait(timeout=10)
                code=124
    except OSError as e:
        evidence.update(status='BUILD_EXECUTION_ERROR',blockers=[str(e)])
        return evidence
    evidence['duration_sec']=round(time.monotonic()-start,1)
    evidence['make_exit_code']=code
    n=log.stat().st_size
    with log.open('rb') as f:
        f.seek(max(0,n-6000))
        evidence['log_tail']=f.read().decode(errors='replace')[-5500:]
    evidence['log_bytes']=n
    if code:
        evidence.update(status='BUILD_TIMEOUT' if code==124 else 'BUILD_FAILED',
                        blockers=['MAKE_EXIT_NONZERO'])
        return evidence
    try:
        evidence['engine']=attest_arm64(source/'android/jniLibs/arm64-v8a/liblo-native-code.so')
    except ValueError as e:
        evidence.update(status='ENGINE_ATTESTATION_FAILED',blockers=[str(e)])
        return evidence
    evidence.update(upstream_apks(source))
    evidence.update(status='NATIVE_BUILD_ATTESTED',engine_compiled=True)
    return evidence

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--sdk',type=Path,required=True)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=2)
    p.add_argument('--timeout-sec',type=int,default=4800)
    p.add_argument('--log',type=Path)
    p.add_argument('--report',type=Path)
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    try:
        data=preflight(a.source,a.sdk,a.ndk) if a.preflight_only else build(
            a.source,a.sdk,a.ndk,jobs=a.jobs,timeout_sec=a.timeout_sec,log=a.log)
    except (OSError,ValueError) as e:
        data={'status':'BLOCKED','blockers':[str(e)],
              'engine_compiled':False,'formatlab_apk_built':False}
    rendered=json.dumps(data,indent=2,ensure_ascii=False)
    if a.report:
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.write_text(rendered+'\n',encoding='utf-8')
    print(rendered)
    return 0 if data['status'] in ('NATIVE_BUILD_ATTESTED','READY_TO_BUILD') else 2

if __name__=='__main__':sys.exit(main())
