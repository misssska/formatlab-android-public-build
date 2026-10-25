# FormatLab P0e — real offline Office golden corpus

**Reference tool qualified on desktop Linux. Native Android conversion and device acceptance are NOT qualified.**

## Purpose

Five synthetic DOCX input cases are generated from scratch, with no private documents:
1. Styled text and Hungarian diacritics
2. Merged and nested tables
3. Three generated color images
4. Three explicit pages with Unicode examples
5. Header, footer and body markers

Local LibreOffice headless converts each DOCX to PDF. Each reference is audited
for text markers, page count, embedded images, table fixture structure and
source-word loss. The suite writes SHA-256 digests for every DOCX and PDF and
rejects reference-file tampering.

The candidate checker then compares any future **on-device** PDF against
its generated reference: extracted words, images, pagination and a bounded
72-DPI grayscale visual difference. Skipped or invalid visual comparisons
are FAIL. The default visual mean absolute difference threshold is 0.055,
which may be tuned only with documented device/font evidence. Genuine app
execution is NOT inferred from files named as Android candidate results.

## Reproduce on Linux/WSL

Prerequisites: LibreOffice Writer, Python 3.11+, python-docx, Pillow, PyMuPDF.

\`\`\`bash
python -m unittest discover -s qa -p test_offline_reference_suite.py -v
python qa/offline_reference_suite.py --output /tmp/formatlab-office-golden
\`\`\`

This produces:
- \`synthetic_docx/*.docx\`
- \`reference_pdf/*.pdf\`
- \`suite-report.json\`, including immutable content hashes.

After converting the **same five DOCX documents** offline on the actual
Android device, place PDF outputs named \`styled_text.pdf\`,
\`tables_nested.pdf\`, \`embedded_images.pdf\`, \`pagination_unicode.pdf\`,
\`header_footer.pdf\` in one local candidate directory and run:

\`\`\`bash
python qa/offline_android_fidelity_acceptance.py \
  --suite /tmp/formatlab-office-golden \
  --candidate-dir /tmp/formatlab-android-candidates \
  --report /tmp/formatlab-android-fidelity-report.json
\`\`\`

Exit code:
- 0: **CANDIDATE_STATIC_PASS**, not proof of a genuine device run.
- 2: measured difference / missing content or candidate failures.
- 3: invalid/tampered reference or configuration.

Do not upload private DOCX files. Avoid publishing personal names or sensitive
data in logs. For a real device acceptance report, record separately the
exact APK hash, Android model/OS/ABI, airplane mode, app-generated file path,
crashes, conversion time and peak memory. A reliable device run must be
witnessed, not claimed merely because two PDFs match.

## Status

Local development proved: 5/5 LibreOffice references PASS and 7/7
regression tests PASS, including detection of image stripping and tampering.
GitHub CI evidence is separate; consult the latest workflow run.

Still blocked: JNI integration of compiled LibreOfficeKit into FormatLab,
on-device DOCX rendering, offline airplane-mode proof, and public release.
Preserve v0.3 debug APK as rollback.
