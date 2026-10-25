# P0d – Offline FormatLab Android APK packaging gate

This gate is for a **future compiled FormatLab APK** bundling LibreOffice.
It will deliberately reject the existing v0.3, which lacks that engine.

## Fail-closed contract

- Exact decoded application ID: hu.formatlab.android (never silently ship
  upstream LibreOffice's reference APK as FormatLab).
- No Android uses-permission at all, including INTERNET and broad storage.
  File access should remain Android SAF based.
- Real ELF64 AArch64 lib/arm64-v8a/liblo-native-code.so of plausible size.
- Bundled runtime files: fundamentalrc, bootstraprc, unorc, versionrc,
  sofficerc; registry main.xcd and locale registry, plus actual fonts.
- Redistribution resources: res/raw/license.txt and res/raw/notice.txt.
- Reject invalid or dangerous ZIP archives (symlinks, duplicate entries,
  traversal, excessive size, decompression ratio, entry count).
- Record APK SHA-256. Missing AAPT binary or undecodable binary manifest BLOCKS.

The expected paths come from the pinned upstream LibreOffice
android/app/build.gradle.kts asset tasks and android/Bootstrap build rules;
adjust only with verified evidence of actual Android packaging layout.

## Run on Linux build host with an actual integrated FormatLab APK

Use SDK 35.0.0 to analyze the actual APK's compiled binary manifest:

    python3 native/office/offline_apk_gate.py /path/to/FormatLab-with-office.apk \
      --aapt "$ANDROID_SDK_ROOT/build-tools/35.0.0/aapt" \
      --report /tmp/formatlab-offline-apk-report.json

Exit code 0 = PACKAGE_STATIC_PASS; exit code 2 = BLOCKED.

**A static package pass is NOT proof** of functional JNI startup,
layout-preserving DOCX→PDF, real offline behavior, memory/time limits,
stable signing, license compliance, or device acceptance. Every report
sets docx_pdf_fidelity_proved=false, airplane_mode_device_tested=false,
public_release_approved=false, even on a static PASS.

## Next substantial milestones

1. Build and verify actual native liblo-native-code.so and its bootstrap data,
   with source and license obligations reviewed.
2. Integrate with FormatLab using an explicitly offline JNI wrapper, cancellation,
   bounded temporary files, safe error reporting and no INTERNET permission.
3. Independently verify synthetic golden DOCX→PDF documents with pictures,
   styled/nested tables, Unicode, page breaks and fonts.
4. Run airplane-mode ARM64 handset tests, performance/crash metrics, and full
   legacy image/ZIP/CSV/SAF save/share regressions.
5. Publish a stable signed release only after all gates pass.

No private user documents, signing keys or sensitive artifacts are checked into
this public repository. This CI runs synthetic ZIP fixtures only.

## Runtime dependency hardening (2026-10-25)

The pinned upstream Android `LibreOfficeKit.NativeLibLoader` explicitly loads
12 NSS/SQLite shared libraries, `libc++_shared.so`, and `liblo-native-code.so`.
The package checker now requires all 14 ARM64 shared objects and verifies
that each starts with an ELF64 AArch64 shared-object header, with a realistic
minimum size. A library name alone is not enough to pass; the check remains
static and cannot prove the libraries will successfully link at runtime.
