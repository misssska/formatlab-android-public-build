# ADR-0001: Professional Office conversion on Android, fully offline
Date: 2026-10-21 | Decision: **LibreOfficeKit/Collabora native POC first; NOT integrated.**

## Requirements
- Convert on-device, with no network, cloud API, or separate office app.
- Fidelity: document images, tables, fonts, page geometry, colors, bullets and hyperlinks.
- Keep accepted v0.3 APK untouched until tested replacement passes quality and Android offline checks.
- Never publish private user DOCX/PDF files in this public repo without explicit consent.

## Evidence
P0 sample: reference DOCX rendered as 8 pages by LibreOffice; v0.3 PDF has 10. Source has 4 media files, 6 OOXML table nodes (including nested tables), Android export 0 embedded images; text coverage is ~95%, but visual layout does not survive. Current DOCX->PDF conversion extracts text and calls Android PdfDocument. This is not a layout renderer.

## Architecture choices
1. LibreOfficeKit/Collabora Android: **selected for a native proof of concept**, because it has a genuine layout engine and PDF export, but native Linux + Android NDK builds are required. Integration, ABI, packaging, font support, size, memory, loading and license compliance must be evaluated; no APK built from it yet.
2. Aspose.Words Android via Java: reserve as a possible commercial SDK alternative after licensing and fully offline operation have been approved. Evaluation inserts a watermark; metered licenses need internet; classic commercial licenses can work offline.
3. WebView docx HTML renderers: may be fast but have not been validated for complex Word formatting. Not a professional replacement without test evidence.
4. External office app/share intent: not acceptable as the permanent integrated solution because it violates no-separate-app requirement.

## Milestone gate
- [x] Identify root cause and objective regression metrics.
- [x] Produce **private, local** reproducible image/page/font report.
- [x] Produce synthetic test suite for quality detector; local results: four unittest PASS, user's current v0.3 output FAIL for missing media/page discrepancy. Test suite artifact prepared independently.
- [ ] Check in independently runnable quality tests to repository, run public CI without using private test data.
- [ ] Build liblo native engine arm64-v8a, pin exact versions and license notices, and embed within FormatLab.
- [ ] Validate DOCX->PDF with synthetic rich DOCX on real Android in airplane mode; no watermark.
- [ ] Privately compare user benchmark, including 8 pages, all images, table geometry/colors, fonts and footnotes; do not upload user assets publicly.
- [ ] Establish real-device performance, peak RAM, APK size, crashes, cancellation, battery.
- [ ] Make a new APK only after acceptance. Preserve v0.3 baseline and other conversion paths.

## Sources
- https://github.com/LibreOffice/core/blob/master/android/README.md
- https://www.collaboraoffice.org/post/build-code-android/
- https://github.com/LibreOffice/core/blob/master/include/LibreOfficeKit/LibreOfficeKit.hxx
- https://docs.aspose.com/words/java/aspose-words-for-android-via-java-supported-platforms/
- https://docs.aspose.com/words/java/licensing/
- https://forum.aspose.com/t/license-for-offline-use/328937
