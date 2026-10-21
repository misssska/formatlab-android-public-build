# FormatLab — Fully Offline, No-Paid-SDK Native Office Engine Build Track

Status: **P0 / build-host preflight complete; native Android renderer NOT yet built**.
Updated: 2026-10-21.

## Non-negotiable product contract

1. All conversions, previews, and exports operate with airplane mode enabled.
2. No server, online converter, trial watermark, paid SDK, license subscription or usage fee.
3. Native engines and fonts bundled with the application; no requirement to install Collabora, LibreOffice, Word or another Android app.
4. Actual format fidelity, not just a valid output file. Complex synthetic DOCX benchmark includes 4 media images, merged/nested tables, fonts, colored graphics, lists, page breaks and Unicode.
5. No unsupported conversions disguised as successful ones. Non-fidelity-preserving target modes must clearly declare losses or refuse conversion.
6. Preserve known-good v0.3 APK while developing an independent feature branch/new build.

## Selected technology

- **First candidate:** LibreOfficeKit source + native Android renderer. It is free/open source and can package its actual document-layout core as a native library. Official Android builds use bundled liblo-native-code.so.
- **Second candidate:** Collabora Office Android source (based on the LibreOffice engine). Use only a license-compliant local build, not a separate installed app or online server.
- **Excluded** for this project: commercial Aspose SDKs (even though they can work offline with paid licensing), external paid cloud APIs, online conversion, and trial-watermarked SDKs.
- LibreOffice is primarily MPL 2.0, with other covered upstream dependencies; all third-party license/notice and source-availability obligations require a documented audit before redistribution, especially if a public Android APK is monetized with ads.
- These are not drop-in Gradle dependencies. Android NDK/C++ building, font resources, file access and Java/JNI integration are substantial development tasks.

## Version lock / host environment

Selected candidate snapshot (research only, **not yet compiled**):

- Source: https://github.com/LibreOffice/core
- Git commit: `f2820323446ae210668dcb6422ddcd55ce939dc2` (2026-10-21).
- Upstream current baseline: Android **NDK 27**, SDK tools **30.0.3** (core README). Collabora's older Android guide mentions NDK 23; do NOT mix recipes across branches without verification.
- First target architecture: **arm64-v8a**.
- Build host: Linux or WSL2; recommended >=16 GiB available RAM and >=50 GiB free disk as conservative planning allowances, not proven minimal requirements.
- Android package currently has no INTERNET permission; this must remain true.

### Step 1: harmless local preflight

```bash
python3 native/office/preflight.py
```

The script **never installs packages, reads private documents, downloads source, or changes files**. It prints a JSON status with missing build prerequisites. `READY_FOR_CONFIGURE_ONLY` is not a compiled engine and must never be treated as build PASS.

### Step 2: source checkout (after preflight, with explicit operator authorization)

```bash
git clone --filter=blob:none https://github.com/LibreOffice/core.git libreoffice-core
git -C libreoffice-core checkout f2820323446ae210668dcb6422ddcd55ce939dc2
git -C libreoffice-core rev-parse HEAD
```

Before configuring verify actual Android distro files in that checked-out revision and verify NDK compatibility. Do not blindly use the older NDK 23 Collabora recipe for modern LibreOffice NDK 27. Use a separate disposable WSL directory; do not modify or delete existing desktop projects.

### Step 3: native POC acceptance (pending)

- Build arm64-native engine and package its full bootstrap data/assets/fonts legally.
- JNI bridge exports synthetic DOCX -> PDF to a temporary local file without network.
- Inspect ABI, APK size, cold/warm conversion time, RAM, crash/recovery and filenames.
- Auto QA compares to genuine LibreOffice golden PDF: image count, text overlap, page count, fonts and visible tables; visual comparison and real Android device review mandatory.
- Fail closed if native assets/bootstrap absent (no fallback to DOCX-text-only PDF marketed as professional).
- Never commit private user-provided samples into this public repository.
- Only after success integrate to FormatLab and preserve tested PDF/image/ZIP/CSV/Android share functions.

## Existing evidence

- Android v0.3 APK is **functional**, but DOCX->PDF fidelity is **FAIL**.
- On local Linux, free LibreOffice converted the private benchmark to an 8-page PDF that retained 4 images and 7 embedded font-resource names. The existing Android v0.3 output is 10 pages and retains no embedded images.
- A reproducible Linux-only reference converter is checked in at [qa/libreoffice_reference.py](../../qa/libreoffice_reference.py). It is a benchmark tool **not** a phone implementation.
- Synthetic tests are checked in at [qa/test_libreoffice_reference.py](../../qa/test_libreoffice_reference.py) and have run locally successfully.
- Exact GitHub Actions success, if applicable, must be verified in the run logs rather than inferred from the workflow file.

## Primary vendor documents

- LibreOffice official Android README: https://github.com/LibreOffice/core/blob/master/android/README.md
- LibreOffice build toolchain baseline: https://github.com/LibreOffice/core/blob/master/README.md
- LibreOffice redistribution/licenses: https://www.libreoffice.org/licenses/
- Collabora Android Linux native build: https://www.collaboraoffice.org/post/build-code-android/
