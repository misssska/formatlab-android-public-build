# FormatLab P0 — LibreOfficeKit ARM64 source/toolchain qualification

**Milestone P0a: source and toolchain verification only. No native Office engine or new Android APK.**

## Pins

- LibreOffice/core commit: `f2820323446ae210668dcb6422ddcd55ce939dc2`
- Android target: `arm64-v8a`
- Upstream distro config: `LibreOfficeAndroidAarch64.conf`
- Android NDK: `27.2.12479018`
- Android API for sample library: 24
- GitHub Actions: `.github/workflows/native-office-arm64-source-smoke.yml`

The upstream pinned commit was checked to contain `android/README.md`, `distro-configs/LibreOfficeAndroidAarch64.conf`, and `include/LibreOfficeKit/LibreOfficeKit.h`. The current LibreOffice recipe differs from older Collabora Android NDK 23 documentation; do not mix these two version sets.

## Automated checks

1. Negative unit tests for mismatched source commit / NDK / ABI / dangerous assumptions.
2. Sparse checkout of exact LibreOffice upstream commit in disposable runner space.
3. Read-only source identity and Android distro/ABI checks.
4. Autogen input **preview only**, not applied or configured.
5. Cross compile small C library with actual Android ARM64 compiler.
6. Reject ELF that is not little-endian, 64-bit AArch64 shared object.

These tests do **not** build `liblo-native-code.so`, invoke LibreOfficeKit, produce a PDF, or build an Android APK. A successful job must not close the DOCX→PDF P0 issue.

## Local Linux/WSL commands

```bash
python3 -m unittest discover -s native/office -p 'test_*.py' -v
python3 native/office/preflight.py
python3 native/office/engine_source_gate.py /path/to/libreoffice-core \
  --sdk "$ANDROID_SDK_ROOT" --ndk "$ANDROID_SDK_ROOT/ndk/27.2.12479018"
python3 native/office/arm64_smoke.py "$ANDROID_SDK_ROOT/ndk/27.2.12479018"
```

Run real LibreOffice native builds only in a separate, disposable WSL project directory after checking disk and RAM, dependencies, licensing, and approval. Never write to an existing Milan Code workspace.

## Outstanding quality gates

- [ ] Compile full pinned `liblo-native-code.so` and package required fonts/bootstrap assets.
- [ ] JNI wrapper executes synthetic DOCX→PDF without the INTERNET Android permission.
- [ ] Verify images, merged/nested tables, typography, layout, links, Unicode and page count against a reference.
- [ ] Verify on actual Android phone with airplane mode; benchmark RAM, CPU, startup, cancellations and crashes.
- [ ] Document MPL/third-party/font license obligations; keep v0.3 APK available for rollback.
- [ ] Integrate only after offline correctness, fidelity and v0.3 regression testing.

See [P0 issue](../../issues/1), [Office ADR](../../docs/ADR-0001_OFFLINE_OFFICE_ENGINE.md) and [quality-gate policy](../../docs/QUALITY_GATE_OFFLINE.md).

Upstream: https://github.com/LibreOffice/core/tree/f2820323446ae210668dcb6422ddcd55ce939dc2/android
