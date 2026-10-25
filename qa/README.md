# FormatLab P0 offline Office fidelity gate

This public directory stores an offline diagnostic script and synthetic-only tests. It includes **no uploaded private user documents**.

## Run

```bash
python -m pip install PyMuPDF==1.26.7 Pillow==12.0.0 python-docx==1.2.0
cd qa
python -m unittest -v test_office_fidelity_probe.py
python office_fidelity_probe.py INPUT.docx OUTPUT.pdf --reference-pdf REFERENCE.pdf --report PRIVATE_RESULT.json --strict
```

- Exit 2 / `FAIL`: structural regression detected, e.g. all media missing, page count differs from reference, or **less than 60% source-word overlap**.
- Exit 0 / `REVIEW_REQUIRED`: no automated hard failure; manual visual inspection and **real Android airplane-mode** testing still required.
- Exit 3: invalid evidence.

**This is not a DOCX conversion engine.** The native LibreOfficeKit Android implementation remains pending. Do not commit actual user documents or generated private report JSON to this public repo.

[Architecture decision](../docs/ADR-0001_OFFLINE_OFFICE_ENGINE.md) · [P0 tracking issue](../issues/1)

## Conservative guardrails

- `word/document.xml` must exist exactly once and its declared uncompressed size must be at most 12 MiB. DTD / entity declarations are rejected. This is a **diagnostic-tool limit**, not an Android app input-limit change.
- PDF reference images are rendered only within 5 million pixels per page and 60 million pixels across the comparison. Oversized pages are reported as `SKIPPED_RENDER_PIXEL_LIMIT`; a skip is **not** a quality PASS.
- Source-to-PDF word overlap below 60% is a hard `SEVERE_TEXT_LOSS` failure; overlap from 60% to below 92% remains a review warning. This extraction-based heuristic can be affected by fonts, ligatures, OCR and multilingual tokenization; it is **not** a document-fidelity certification.
- `REVIEW_REQUIRED` always means further evidence is needed. Neither matching reference bitmaps nor a successful unit test proves the Android converter preserves editable content, tables, pages, fonts, or image fidelity.
- The GitHub pull-request quality workflow runs synthetic fixtures only. Never commit user-provided DOCX/PDF samples or private report JSON.

