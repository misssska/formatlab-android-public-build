# FormatLab P0f — offline LibreOfficeKit DOCX→PDF runtime integration

## Implemented in code (not a released converter)

The branch compiles a candidate Java adapter against the real FormatLab Android v0.3 source and the exact pinned upstream LibreOfficeKit Java API.

- FormatLabOfflineOfficeConverter.java: bounded private SAF DOCX input staging (40 MiB), ZIP magic check, serialized native documentLoad/saveAs(pdf) calls, PDF magic/size validation, temporary input cleanup and private output lifecycle.
- Fail closed when liblo-native-code.so, bundled fonts, registry or bootstraps are unavailable. The existing v0.3 APK does not carry the LibreOffice native engine; do not enable or advertise this new code in the user interface.
- assemble_runtime_overlay.py: exact v0.3 ZIP SHA-256, safe archive extraction, pinned upstream Java API sources and isolated Gradle source overlay.
- CI: Gradle 8.10.2, JDK 17, Android SDK 35, v0.3 Python/JS regressions, application identity and zero requested permissions. No new APK is released from this workflow.

## Upstream Java integration (pinned source)

LibreOffice core commit f2820323446ae210668dcb6422ddcd55ce939dc2.

- LibreOfficeKit.init(Activity)
- LibreOfficeKit.getLibreOfficeKitHandle()
- new Office(ByteBuffer), Office.documentLoad(file URI)
- Document.saveAs(file URI, pdf, empty options), Document.destroy()

Convert from a background thread; serialized access to native API. Thread.interrupt does NOT reliably cancel native LibreOffice calls. Native crash containment and isolated process execution are mandatory before enabling this for untrusted files.

## Outstanding acceptance gates

1. Actual liblo-native-code.so from the complete upstream P0c ARM64 build with all runtime dependencies.
2. P0d static package verification on an actually integrated FormatLab APK.
3. P0e golden synthetic PDF comparison on real converter outputs (images, tables, Unicode, pages, headers/footers).
4. Real ARM64 handset airplane-mode and isolated-process tests: cancellation, time, memory, crashes, and prior v0.3 functionality.
5. Source and font license notices, signing, release reproducibility, and legal review.

Existing known debug APK stays as rollback. Compiling this adapter does not prove a working DOCX→PDF engine.
