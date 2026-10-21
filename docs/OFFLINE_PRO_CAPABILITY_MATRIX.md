# FormatLab Pro — truthful offline conversion matrix

Status date: 2026-10-21. Product target: **free to use, completely offline Android app, high-quality output**.

**Definitions**
- **HANDSET PASS**: real-phone tests of identified operation have passed, not necessarily general fidelity.
- **LIMITED**: output valid only for documented subset or with losses.
- **P0 BLOCKED**: fidelity failure; cannot be marketed as professional.
- **FUTURE**: candidate engine, not embedded, built or accepted.

| Conversion pair | v0.3 evidence | Professional target / open source candidate | Release condition |
|---|---|---|---|
| PNG↔JPEG/WebP | Handset conversion/save PASS for one PNG→WebP test | preserve dimensions/ICC where possible, EXIF orientation, alpha warnings; Android/possible libvips (LGPL) | independent decode, perceptual/metadata tests per pair |
| BMP/TIFF/ICO | Source unit tests only | Image encoder/decoder integrity, depth, alpha, ICC, multiframe; evaluate libvips build size and licenses | fixtures, ICC/alpha/bit-depth, 64-bit overflow, device |
| PDF→PNG | First page, saved/opened on handset PASS | chosen page ranges/all pages and DPI/resolution/rotation with PdfRenderer/PDFium | all pages, pixel-reference tests, arbitrary file handling |
| PDF→page image ZIP | Source test only, max 20 pages | explicit page range, DPI, progress, resource limits | archival integrity and pages matching |
| DOCX→TXT | Text extraction LIMITED | explicitly text-only, Unicode, tables separated without data smearing | semantic text completeness test |
| DOCX→PDF | **P0 BLOCKED**, source loses pictures/tables/format | LibreOfficeKit/Collabora Android native engine; free, offline, copyright-compliant | rendered layout, pages/images/tables/fonts, performance, device |
| TXT/MD/CSV/JSON→PDF/DOCX | LIMITED, simple text wrapping | structured parser and actual styles/tables where relevant | content/encoding and editable semantics |
| XLSX/PPTX→PDF | UNAVAILABLE | native Office engine | complex formulas/tables/slides/charts preserved |
| scanned PDF→searchable PDF | UNAVAILABLE | on-device Tesseract (Apache-2.0) plus PDF font text-layer processor | multiple language packs, accessibility/OCR accuracy |
| image→SVG | experimental contour/centerline trace | evaluate VTracer (MIT, Rust/WASM), plus separate CAD/CNC metric-vector profile | exact mm output, geometry, reference shape and cut-path verification |
| SVG→PNG/JPEG | LIMITED static sanitized subset | secure SVG renderer, fixed dimensions and alpha controls | adversarial SVG and visual suite |
| MP4(AAC)→M4A | LIMITED track extraction, no re-encode | clarify copy/extraction vs real transcoding | input codec check, track metadata, sample verification |
| video/audio format pairs | UNAVAILABLE | build/test FFmpeg LGPL-only profile; enable GPL-dependent components only after compatibility/legal review | independent decode, A/V sync, audio tracks, fidelity |
| CSV→JSON, ZIP | Individual user handset tests PASS | schema/type/encoding/quoting and ZIP safety checks | reproducibility and malformed input gate |

## Mandatory architecture rules

1. **Free**: no commercial or paid SDK, cloud processing charges, metered license, watermark or subscription for app functions. Build tools can be downloaded during development; end-user conversion cannot access network.
2. **Offline**: APK has no INTERNET permission; format codecs, fonts, language data and layout engine must ship within the app or be declared as an **explicit opt-in offline language pack installed separately** (not a server dependency).
3. **Quality**: valid output never automatically means fidelity. If the format intrinsically discards data (JPG transparency, editable Word from scanned PDF, low-bitrate audio), present deliberate modes and losses. Never imply impossible lossless round-trip.
4. **Legal distribution**: honor MPL/LGPL/Apache/MIT notices/source requirements, copyright and font redistribution. FFmpeg is LGPL by default but GPL/nonfree additions change permitted redistribution; patent licensing is separate.
5. **Platform reality**: LibreOfficeKit is a substantial native Android NDK build, not a Gradle dependency. Current v0.3 306 KB APK cannot become a full office suite with no binary size increase. Report size, RAM, ABI and CPU benchmarks.
6. **Privacy/security**: never put user-provided benchmark documents in public repo; source ZIP audit and Android user confirmation remain release gates.
7. **Shipping**: no beta/full release called professional until real handset airplane-mode tests and independently verified golden fixtures pass. Keep previous APK/release available for rollback.

## Candidate license upstream references

- https://www.libreoffice.org/licenses/
- https://www.collaboraoffice.org/post/build-code-android/
- https://github.com/libvips/libvips
- https://github.com/visioncortex/vtracer
- https://github.com/tesseract-ocr/tessdoc
- https://www.ffmpeg.org/legal.html

**Planning document only; it does not claim any FUTURE engine is already integrated.**
