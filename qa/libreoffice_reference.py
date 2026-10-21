#!/usr/bin/env python3
"""Offline LibreOffice reference conversion on Linux (NOT an Android engine).

For independent document-fidelity benchmarks only. Requires local LibreOffice
installation; does not send anything to external services or touch user profile.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

MAX_INPUT = 40 * 1024 * 1024
SUPPORTED = {'.docx', '.odt', '.rtf', '.xlsx', '.ods', '.pptx', '.odp'}

def convert(src: Path, dest: Path, *, soffice: str = 'libreoffice', timeout: int = 180) -> dict:
    src = src.resolve()
    dest = dest.resolve()
    if not src.is_file() or src.suffix.casefold() not in SUPPORTED:
        raise ValueError('Unsupported or missing input')
    if src.stat().st_size <= 0 or src.stat().st_size > MAX_INPUT:
        raise ValueError('Input outside 1..40 MiB bound')
    if dest.suffix.lower() != '.pdf':
        raise ValueError('Output file must have .pdf extension')
    if not shutil.which(soffice):
        raise FileNotFoundError(f'LibreOffice binary missing: {soffice}')
    if not 1 <= timeout <= 900:
        raise ValueError('Invalid timeout')
    with tempfile.TemporaryDirectory(prefix='formatlab-lo-ref-') as td:
        root = Path(td)
        inbox = root / ('document' + src.suffix.lower())
        shutil.copyfile(src, inbox)
        profile = root / 'profile'
        outbox = root / 'out'
        outbox.mkdir()
        argv = [soffice, '-env:UserInstallation=' + profile.as_uri(),
                '--headless', '--convert-to', 'pdf', '--outdir', str(outbox), str(inbox)]
        environment = os.environ.copy()
        environment.pop('DISPLAY', None)
        done = subprocess.run(argv, cwd=str(root), env=environment,
                              timeout=timeout, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, errors='replace', check=False)
        artifact = outbox / 'document.pdf'
        if done.returncode != 0 or not artifact.is_file() or artifact.stat().st_size == 0:
            raise RuntimeError(f'LibreOffice conversion failed (exit={done.returncode}): '
                               + (done.stderr or done.stdout)[-500:])
        import fitz
        with fitz.open(artifact) as pdf:
            if not pdf.is_pdf or not len(pdf) or len(pdf)>200 or pdf.is_encrypted:
                raise ValueError('Invalid output PDF')
            stats = {'page_count': len(pdf),
                     'embedded_images': len({info[0] for page in pdf for info in page.get_images(full=True)}),
                     'fonts': sorted({str(f[3]) for page in pdf for f in page.get_fonts(full=True) if len(f)>3})}
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(artifact,dest)
        return {'status':'REFERENCE_CREATED_NOT_ANDROID', 'source_format':src.suffix.lower(),
                'output':str(dest), 'output_bytes':dest.stat().st_size, **stats}

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path)
    ap.add_argument('pdf_output',type=Path)
    ap.add_argument('--soffice',default='libreoffice')
    ap.add_argument('--timeout',type=int,default=180)
    args=ap.parse_args()
    try:
        print(json.dumps(convert(args.input,args.pdf_output,soffice=args.soffice,timeout=args.timeout),
                         ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status':'REFERENCE_FAIL','reason':str(exc)},ensure_ascii=False))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
