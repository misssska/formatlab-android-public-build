#!/usr/bin/env python3
"""Read-only pinned LibreOffice source verification and safe configure preview.

Never builds or modifies LibreOffice. A PASS is only a source/configuration gate.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

PINNED_COMMIT = 'f2820323446ae210668dcb6422ddcd55ce939dc2'
DISTRO = 'LibreOfficeAndroidAarch64'
REQUIRED = (
    'autogen.sh', 'README.cross', 'android/README.md',
    'distro-configs/LibreOfficeAndroidAarch64.conf',
    'include/LibreOfficeKit/LibreOfficeKit.h',
)

def inspect(root: Path, *, sha: str | None = None) -> dict:
    root = Path(root).resolve()
    problems: list[str] = []
    if not root.is_dir():
        return {'status': 'BLOCKED', 'reason': 'SOURCE_DIRECTORY_MISSING', 'commit': None, 'missing': list(REQUIRED), 'issues': []}
    if sha is None:
        try:
            sha = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, check=True).stdout.strip()
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            sha = ''
    if sha != PINNED_COMMIT:
        problems.append('SOURCE_COMMIT_MISMATCH')
    missing = [p for p in REQUIRED if not (root/p).is_file()]
    if missing: problems.append('SOURCE_LAYOUT_MISSING')
    conf = root/'distro-configs/LibreOfficeAndroidAarch64.conf'
    if conf.is_file():
        raw = conf.read_text(encoding='utf-8')
        if not re.search(r'^--host=aarch64-linux-android\s*$', raw, re.M):
            problems.append('SOURCE_WRONG_ABI')
    return {'status': 'PASS' if not problems else 'BLOCKED', 'commit': sha,
            'expected_commit': PINNED_COMMIT, 'distro': DISTRO,
            'missing': missing, 'issues': problems,
            'engine_compiled': False, 'android_apk_built': False}

def config_preview(sdk: Path, ndk: Path, *, host='x86_64-unknown-linux-gnu') -> str:
    sdk = Path(sdk).resolve()
    ndk = Path(ndk).resolve()
    for p in (sdk, ndk):
        if not p.is_dir() or '\n' in str(p) or '\r' in str(p):
            raise ValueError('SDK/NDK directory missing or path invalid')
    if not (ndk/'source.properties').is_file():
        raise ValueError('NDK source.properties missing')
    if not re.search(r'^Pkg.Revision\s*=\s*27\.2\.12479018\s*$',
                     (ndk/'source.properties').read_text(errors='replace'), re.M):
        raise ValueError('Exact NDK 27.2.12479018 required')
    if host != 'x86_64-unknown-linux-gnu':
        raise ValueError('Only pinned Linux x86_64 build host supported')
    return (f'--build={host}\n--with-android-sdk={sdk}\n'
            f'--with-android-ndk={ndk}\n--with-distro={DISTRO}\n--enable-sal-log\n')

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('--sdk', type=Path)
    parser.add_argument('--ndk', type=Path)
    args = parser.parse_args(argv)
    result = inspect(args.source_dir)
    if args.sdk or args.ndk:
        if not args.sdk or not args.ndk:
            result.setdefault('issues', []).append('SDK_AND_NDK_MUST_BOTH_BE_PROVIDED')
        else:
            try:
                result['autogen_input_preview'] = config_preview(args.sdk,args.ndk)
            except ValueError as e:
                result.setdefault('issues', []).append('TOOLCHAIN_CONFIG_INVALID: ' + str(e))
    if result['issues']:
        result['status'] = 'BLOCKED'
    print(json.dumps(result,indent=2))
    return 0 if result['status'] == 'PASS' else 2

if __name__=='__main__': sys.exit(main())
