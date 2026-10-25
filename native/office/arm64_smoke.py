#!/usr/bin/env python3
"""Cross-compile one harmless ARM64 Android shared library to prove NDK toolchain.

This is NOT a LibreOfficeKit engine or Android converter. Produces no APK.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

NDK_PIN='27.2.12479018'
AARCH64_MACHINE=183

def smoke(ndk:Path, *, api_level:int=24, run=subprocess.run) -> dict:
    ndk = Path(ndk).resolve()
    props = ndk/'source.properties'
    if not props.is_file() or not re.search(rf'^Pkg.Revision\s*=\s*{re.escape(NDK_PIN)}\s*$',
                                            props.read_text(errors='replace'), re.M):
        raise ValueError('NDK_PIN_MISMATCH')
    if not 23<=api_level<=35:
        raise ValueError('ANDROID_API_OUT_OF_RANGE')
    clang=ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin'/f'aarch64-linux-android{api_level}-clang'
    if not clang.is_file():
        raise ValueError('ARM64_CLANG_NOT_FOUND')
    with tempfile.TemporaryDirectory(prefix='formatlab-arm64-') as tmp:
        root=Path(tmp); src=root/'smoke.c'; out=root/'libformatlab_smoke.so'
        src.write_text('int formatlab_arm64_smoke(void) { return 42; }\n',encoding='utf-8')
        try:
            result=run([str(clang), '-shared','-fPIC','-Wl,--no-undefined',
                        '-o',str(out),str(src)], check=False, timeout=90,
                        capture_output=True, text=True)
        except (OSError,subprocess.TimeoutExpired) as ex:
            raise RuntimeError('CROSS_COMPILER_FAILED_TO_START') from ex
        if result.returncode or not out.is_file():
            raise RuntimeError('CROSS_COMPILE_FAILED '+result.stderr[-400:])
        elf=out.read_bytes()[:20]
        if len(elf)<20 or elf[:4]!=b'\x7fELF' or elf[4]!=2 or elf[5]!=1:
            raise RuntimeError('OUTPUT_NOT_ELF64_LE')
        kind=int.from_bytes(elf[16:18], 'little')
        machine=int.from_bytes(elf[18:20], 'little')
        if (kind,machine)!=(3,AARCH64_MACHINE):
            raise RuntimeError('OUTPUT_NOT_AARCH64_SHARED')
        return {'status':'PASS','ndk_revision':NDK_PIN,'abi':'arm64-v8a',
                'android_api_level':api_level,'elf_type':kind,'elf_machine':machine,
                'elf_bytes':out.stat().st_size, 'lo_engine_built':False,
                'apk_built':False}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ndk',type=Path)
    parser.add_argument('--api-level',type=int,default=24)
    args=parser.parse_args(argv)
    try:
        result=smoke(args.ndk,api_level=args.api_level)
        code=0
    except (ValueError,RuntimeError) as e:
        result={'status':'BLOCKED','reason':str(e),'lo_engine_built':False,'apk_built':False};code=2
    print(json.dumps(result,indent=2))
    return code

if __name__=='__main__':sys.exit(main())
