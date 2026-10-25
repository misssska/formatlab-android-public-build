#!/usr/bin/env python3
"""Bounded real Android LibreOffice configure probe, never the full Office build.

Only run in an explicitly disposable upstream checkout: autogen writes generated files.
No native engine, Android APK, or document conversion is produced.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from engine_source_gate import inspect, config_preview

MIN_FREE_GIB = 8
REQUIRED_TOOLS = ("git", "perl", "autoconf", "aclocal", "automake", "pkg-config", "make", "m4")
SDK_PACKAGES = ("platforms/android-35", "build-tools/35.0.0")

def check(source: Path, sdk: Path, ndk: Path, *, min_free_gib: int = MIN_FREE_GIB,
          which=shutil.which, disk=shutil.disk_usage) -> dict:
    source, sdk, ndk = (Path(x).resolve() for x in (source, sdk, ndk))
    identity = inspect(source)
    blockers = list(identity.get("issues", []))
    if identity.get("status") != "PASS":
        blockers.append("SOURCE_PIN_OR_LAYOUT_FAILED")
    if not 4 <= min_free_gib <= 100:
        raise ValueError("INVALID_MIN_FREE_SPACE")
    missing_tools = [x for x in REQUIRED_TOOLS if not which(x)]
    if missing_tools:
        blockers.append("MISSING_CONFIGURE_TOOLS:" + ",".join(missing_tools))
    try:
        options = config_preview(sdk, ndk)
    except ValueError as exc:
        blockers.append("SDK_NDK_INVALID:" + str(exc))
        options = ""
    for package in SDK_PACKAGES:
        if not (sdk/package).is_dir():
            blockers.append("MISSING_ANDROID_SDK_COMPONENT:" + package)
    try:
        free_gib = disk(source).free / (1024 ** 3)
        if free_gib < min_free_gib:
            blockers.append("INSUFFICIENT_FREE_DISK")
    except OSError:
        free_gib = None
        blockers.append("DISK_SPACE_UNKNOWN")
    if not (source / "autogen.sh").is_file():
        blockers.append("AUTOGEN_NOT_FOUND")
    return {"status": "READY_FOR_CONFIGURE" if not blockers else "BLOCKED",
            "blockers": blockers, "source_commit": identity.get("commit"),
            "sdk": str(sdk), "ndk": str(ndk), "free_gib": round(free_gib, 2) if free_gib is not None else None,
            "min_free_gib": min_free_gib, "autogen_options": options,
            "office_engine_built": False, "android_apk_built": False}

def run_probe(source: Path, sdk: Path, ndk: Path, *, timeout: int = 600,
              min_free_gib: int = MIN_FREE_GIB, runner=subprocess.run) -> dict:
    result = check(source, sdk, ndk, min_free_gib=min_free_gib)
    result["configure_attempted"] = False
    if result["status"] != "READY_FOR_CONFIGURE":
        return result
    if not 30 <= timeout <= 1200:
        raise ValueError("INVALID_TIMEOUT")
    source = Path(source).resolve()
    # Mandatory opt-in: the source must be a disposable checkout, never an arbitrary repo.
    if os.environ.get("FORMATLAB_DISPOSABLE_CHECKOUT") != "YES":
        result.update(status="BLOCKED", blockers=["DISPOSABLE_CHECKOUT_OPT_IN_REQUIRED"])
        return result
    (source / "autogen.input").write_text(result["autogen_options"], encoding="utf-8")
    env = os.environ.copy()
    env["ANDROID_SDK_ROOT"] = str(Path(sdk).resolve())
    env["ANDROID_HOME"] = env["ANDROID_SDK_ROOT"]
    result["configure_attempted"] = True
    started = time.monotonic()
    try:
        done = runner(["./autogen.sh"], cwd=str(source), env=env,
                      timeout=timeout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      text=True, errors="replace", check=False)
    except subprocess.TimeoutExpired:
        result.update(status="TIMEOUT", duration_sec=round(time.monotonic()-started, 1),
                      blockers=["AUTOGEN_TIMEOUT"])
        return result
    except OSError as exc:
        result.update(status="FAILED", blockers=["AUTOGEN_EXECUTION_ERROR:" + str(exc)])
        return result
    result["duration_sec"] = round(time.monotonic()-started, 1)
    result["return_code"] = done.returncode
    result["stdout_tail"] = done.stdout[-2500:]
    result["stderr_tail"] = done.stderr[-2500:]
    # An exit 0 is still only a configure result, not a compiled library.
    result["status"] = "CONFIGURED_ONLY" if done.returncode == 0 else "FAILED"
    if done.returncode:
        result["blockers"] = ["AUTOGEN_NONZERO_EXIT"]
    return result

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("--sdk", required=True, type=Path)
    ap.add_argument("--ndk", required=True, type=Path)
    ap.add_argument("--min-free-gib", type=int, default=MIN_FREE_GIB)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--preflight-only", action="store_true")
    args = ap.parse_args()
    try:
        outcome = (check(args.source, args.sdk, args.ndk, min_free_gib=args.min_free_gib)
                   if args.preflight_only else
                   run_probe(args.source, args.sdk, args.ndk, min_free_gib=args.min_free_gib,
                             timeout=args.timeout))
        code = 0 if outcome["status"] in ("CONFIGURED_ONLY", "READY_FOR_CONFIGURE") else 2
    except (OSError, ValueError) as exc:
        outcome = {"status": "BLOCKED", "blockers": [str(exc)],
                   "office_engine_built": False, "android_apk_built": False}
        code = 2
    text = json.dumps(outcome, indent=2, ensure_ascii=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return code

if __name__ == "__main__":
    sys.exit(main())
