# FormatLab: professional, fully offline quality gate (2026-10-21)

## Release rules
- ALL conversion is on the Android device, without runtime network or third-party app.
- A valid output file is not proof of fidelity. Every format pair must have an explicit, tested quality contract.
- No silent loss of text, pages, pictures, charts, tables, transparency, frames, fonts, colors, data types, metadata or tracks. Inherently lossy modes require explicit choice and warnings.
- Mark each pairing PASS (tested), LIMITED (clearly advertised subset), EXPERIMENTAL (not certified) or UNSUPPORTED. Never market LIMITED as professional.
- Preserve regressions proven in v0.2.1/v0.3; run CI plus real-device airplane-mode acceptance.
- User-submitted sample files remain private: do not put them in the public repository without explicit consent.

## P0: DOCX to PDF is NOT layout-faithful
User-provided benchmark analyzed locally, 2026-10-21:
- DOCX is 8 pages in LibreOffice reference rendering; v0.3 PDF has 10 pages.
- DOCX contains 4 embedded media objects and 5 table objects; v0.3 PDF has no embedded bitmap images and drops styled tables.
- PDF sampled pages use DroidSansMono only. Fonts, bullets, line wrapping, formatting, pictures, table colors and layout disappear.
- Root cause confirmed in v0.3 source: OfflineDocuments.java extracts the DOCX text and generates PDF from it. A full document layout renderer is required, not a formatting tweak.
- LibreOffice reference is not guaranteed pixel-identical to Word if fonts/rendering differ.

## Format-specific acceptance contracts
- Office DOCX/PDF/XLSX/PPTX: preserve visible media, table relationships/merge, styles, headings, hyperlinks, lists, page geometry and sheet formulas or declare intentional semantic losses. DOCX to TXT stays explicitly text-only. PDF to editable DOCX must distinguish editable-content vs layout-fidelity modes; an arbitrary PDF cannot always be converted into an identically formatted editable document.
- Images: dimension/EXIF orientation, ICC color, alpha, depth, animation, metadata and selected quality. Alpha to JPEG requires user-selected background and loss warning. Independent decode and compare.
- PDF: all/page range, DPI, dimensions, rotation, page boxes and annotations/bookmarks when promised, resource guardrails and optional *real* local OCR. Never silently export only the first page.
- SVG and plotter: trace is an approximation, not magical vector recovery; test coordinate units (mm), scaling, smooth paths, duplicates, node counts, toolpath continuity and machine-safe geometry.
- Audio/video: codec-container compatibility, track fidelity, frame rate/resolution, video/audio sync and subtitles when advertised; AAC from MP4 is extraction only until genuine transcode exists.
- JSON/CSV/TXT/ZIP: charsets, quotes, delimiters, null/numbers, newlines and nesting; type-loss warnings for CSV; CRC/path traversal/zip bomb handling.

## Regression and release tests
For every input→output pair: fixture sets cover normal, complex, extreme but accepted, Unicode, malformed, and unsupported input. Independently parse output; compare semantic objects, pages and images against references. Render and compare visual pages with calibrated metrics and manual review. Track run time, memory, crash, cancellation, cleanup, license and platform ABI. Test offline on real phones without Wi-Fi or mobile data.

Current DOCX benchmark fails until images and tables persist, typography and page breaks are close to reference, and concrete device-level evidence proves it. This issue is a BLOCKER for marketing DOCX→PDF as professional.

## Roadmap
1. P0: label quality modes honestly; build public synthetic fixtures; keep real user docs private.
2. P0: replace flattened text-to-PDF with a genuine local document layout engine. Investigate Android LibreOfficeKit/Collabora native integration, including size, NDK, fonts, RAM, packaging and license. Commercial Aspose.Words Android is only a separately evaluated alternative with an appropriate fully offline paid license.
3. P1: certify PDF, image, SVG/CNC, structured formats independently against representative fixtures. Preserve existing functionality.
4. P2: extend fully offline office/media/OCR only where viable, with independent fidelity evidence.
5. No stable release until automated gates and human real-device review PASS.

Research sources: https://github.com/LibreOffice/core/blob/master/android/README.md ; https://www.collaboraoffice.org/post/build-code-android/ ; https://releases.aspose.com/words/androidjava/ ; https://docs.aspose.com/words/java/licensing/ ; https://www.ffmpeg.org/legal.html

**This document records a quality target, not a claim that the current Android v0.3 meets it.**
