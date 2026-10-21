# FormatLab P0 offline Office fidelity gate

This public directory stores an offline diagnostic script and synthetic-only tests. It includes **no uploaded private user documents**.

## Run

```bash
python -m pip install PyMuPDF==1.26.7 Pillow==12.0.0 python-docx==1.2.0
cd qa
python -m unittest -v test_office_fidelity_probe.py
python office_fidelity_probe.py INPUT.docx OUTPUT.pdf --reference-pdf REFERENCE.pdf --report PRIVATE_RESULT.json --strict
```

- Exit 2 / `FAIL`: structural regression detected, e.g. all media missing or page count differs from reference.
- Exit 0 / `REVIEW_REQUIRED`: no automated hard failure; manual visual inspection and **real Android airplane-mode** testing still required.
- Exit 3: invalid evidence.

**This is not a DOCX conversion engine.** The native LibreOfficeKit Android implementation remains pending. Do not commit actual user documents or generated private report JSON to this public repo.

[Architecture decision](../docs/ADR-0001_OFFLINE_OFFICE_ENGINE.md) · [P0 tracking issue](../issues/1)
