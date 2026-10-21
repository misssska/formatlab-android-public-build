#!/usr/bin/env python3
"""Read-only LibreOfficeKit Android build-host preflight. Never installs software."""
from __future__ import annotations
import json, os, platform, re, shutil, sys
from pathlib import Path

TOOLS=('git','make','gcc','g++','clang','javac','python3','pkg-config')

def inspect(env=None,tool_lookup=shutil.which,root=None):
    env=os.environ if env is None else env
    root=Path.cwd() if root is None else Path(root)
    missing=[x for x in TOOLS if not tool_lookup(x)]
    sdk=env.get('ANDROID_SDK_ROOT') or env.get('ANDROID_HOME','')
    sdkpath=Path(sdk) if sdk else None
    ndk=env.get('ANDROID_NDK_ROOT') or env.get('ANDROID_NDK_HOME','')
    if not ndk and sdkpath is not None:
        directory=sdkpath/'ndk'
        if directory.is_dir():
            found=[x for x in directory.iterdir() if x.name.startswith('27.') and x.is_dir()]
            if found: ndk=str(sorted(found,reverse=True)[0])
    ndkpath=Path(ndk) if ndk else None
    rev=''
    if ndkpath and (ndkpath/'source.properties').is_file():
        raw=(ndkpath/'source.properties').read_text(errors='replace')
        match=re.search(r'Pkg.Revision\s*=\s*(\d+(?:\.\d+)+)',raw)
        rev=match.group(1) if match else ''
    try:
        ram=round(int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines()
                          if x.startswith('MemTotal:')))/1024/1024,1)
    except (OSError,StopIteration,ValueError): ram=None
    try: disk=round(shutil.disk_usage(root).free/1024**3,1)
    except OSError: disk=None
    blockers=[];warnings=[]
    if platform.system()!='Linux': blockers.append('Linux/WSL2 build host required')
    if missing: blockers.append('Missing local build tools: '+', '.join(missing))
    if not sdkpath or not sdkpath.is_dir(): blockers.append('ANDROID_SDK_ROOT / ANDROID_HOME missing')
    if not rev.startswith('27.'): blockers.append('Android NDK 27 not found or incompatible')
    if ram is not None and ram<16: warnings.append(f'RAM {ram} GiB < recommended 16 GiB')
    if disk is not None and disk<50: warnings.append(f'Free disk {disk} GiB < recommended 50 GiB')
    return {'status':'READY_FOR_CONFIGURE_ONLY' if not blockers else 'BLOCKED',
            'host_os':platform.system(),'tools_missing':missing,
            'sdk_path':str(sdkpath or ''),'ndk_path':str(ndkpath or ''),'ndk_version':rev,
            'ram_gib':ram,'free_disk_gib':disk,'blockers':blockers,'warnings':warnings,
            'executed_commands':0,'network_calls':0,'changed_files':0}

if __name__=='__main__':
    report=inspect()
    print(json.dumps(report,indent=2,ensure_ascii=False))
    sys.exit(0 if report['status']=='READY_FOR_CONFIGURE_ONLY' else 2)
