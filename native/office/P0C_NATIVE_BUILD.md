# FormatLab Android P0c — real LibreOffice ARM64 native build

## Purpose

This milestone attempts **the real upstream LibreOffice Android build** on a disposable Linux GitHub runner — not another compiler toy test. Its accepted binary is the upstream `liblo-native-code.so`, not a FormatLab Android release.

Stacked prerequisites:
- [P0a / PR #3](../../pull/3): source pin, NDK 27, ARM64 cross-compiler PASS.
- [P0b / PR #4](../../pull/4): `perl autogen.sh` with Android ARM64 distro configured successfully ([CI 40177040037](https://github.com/misssska/formatlab-android-public-build/actions/runs/40177040037)).
- P0c: this PR, based on the P0b branch, and NOT merged into `main`.

## What the GitHub CI executes

1. Synthetic safety/regression tests, including **11 new P0c tests**.
2. Installs the real Android SDK 35 and pinned NDK `27.2.12479018`.
3. Checks out the complete pinned LibreOffice/core source at `f2820323446ae210668dcb6422ddcd55ce939dc2`.
4. Runs real Android ARM64 `perl autogen.sh` with the previously verified configuration.
5. With two build jobs, attempts **`make -j2 android`**, bounded to 4,800 seconds. The complete runner is limited to 110 minutes.
6. Accepts a native engine build only when make exits 0 AND `android/jniLibs/arm64-v8a/liblo-native-code.so` is a nonempty ELF64 little-endian AArch64 shared library.
7. Records the make log tail, resource checks and any failure reason. Any absence/timeout/missing library is an explicit failure.

The build is prevented from running on existing Windows/WSL projects or the Milan Code workspace. A specific disposable source path and two explicit CI opt-in environment variables are mandatory. Disk <12 GiB or available memory <10 GiB blocks the build before make. No user files, secrets or private benchmark DOCX files are used.

No native binaries or upstream APKs are published automatically because legal/licensing, binary provenance and device acceptance are not yet approved.

## Acceptance ladder

| Gate | Passing evidence |
|---|---|
| P0a — compiler | Genuine Android ARM64 shared-library smoke PASS |
| P0b — configure | Genuine pinned LibreOffice ARM64 autogen, exit 0 |
| **P0c — native build** | **Real `make android` succeeds + ARM64 `liblo-native-code.so` ELF attestation** |
| P0d — JNI packaging | Offline JNI wrapper, bundled fonts/resources, cancellation, no Internet permission |
| P0e — document fidelity | Complex synthetic DOCX→PDF preserves images, styled/nested tables, fonts, Unicode, pagination; independent oracle PASS |
| P0f — device | Real phone, airplane mode, time/RAM/crash/regression benchmarks and license review |
| Public distribution | Reproducible, signed FormatLab release after all gates PASS |

**WARNING:** Even a successful P0c does not imply a functional FormatLab converter, a proven Android JNI export, or the preservation of Word document formatting. The existing v0.3 APK is preserved as the rollback baseline.

## Reproduce on isolated Linux / WSL2 host

The source folder must be named `formatlab-lo-p0c` and sit under the explicitly permitted temporary root.

```bash
python3 -m unittest discover -s native/office -p 'test_*.py' -v
export FORMATLAB_DISPOSABLE_CHECKOUT=YES
export FORMATLAB_ALLOW_NATIVE_BUILD=YES
export RUNNER_TEMP=/path/to/isolated/temp
python3 native/office/configure_probe.py "$RUNNER_TEMP/formatlab-lo-p0c" \
  --sdk "$ANDROID_SDK_ROOT" \
  --ndk "$ANDROID_SDK_ROOT/ndk/27.2.12479018"
python3 native/office/p0c_native_build.py "$RUNNER_TEMP/formatlab-lo-p0c" \
  --sdk "$ANDROID_SDK_ROOT" \
  --ndk "$ANDROID_SDK_ROOT/ndk/27.2.12479018" \
  --jobs 2 --timeout-sec 4800 \
  --log "$RUNNER_TEMP/native-build.log" \
  --report "$RUNNER_TEMP/native-build.json"
```

## Explicit remaining blockers

- Integrating upstream LibreOfficeKit and its bootstrap data into FormatLab — NOT DONE.
- Actual offline DOCX→PDF export, output and quality comparison, tablet/phone device tests — NOT DONE.
- Native-library dependencies, source-offer / MPL license notices, fonts and redistribution review — NOT DONE.
- Preservation of previously working image/ZIP/CSV sharing flows must be retested after integration.
