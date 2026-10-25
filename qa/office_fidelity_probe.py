#!/usr/bin/env python3
"""FormatLab offline DOCX->PDF fidelity probe. Purely local, never sends files.

REVIEW_REQUIRED is never a professional PASS. On-device acceptance still required.
Requires PyMuPDF; Pillow is needed when a visual reference is supplied.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile, BadZipFile

W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_BYTES=40*1024*1024
MAX_DOC_XML_BYTES=12*1024*1024
MAX_PAGE_RENDER_PIXELS=5_000_000
MAX_TOTAL_RENDER_PIXELS=60_000_000

def words(s):
    return re.findall(r"[^\W_]+",s.casefold(),re.UNICODE)

def docx_structure(path):
    if not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise ValueError("DOCX absent or >40MB")
    try:
        with ZipFile(path) as z:
            items=z.infolist()
            if len(items)>3000 or sum(e.file_size for e in items)>180*1024*1024:
                raise ValueError("DOCX resource limit exceeded")
            if any(".." in e.filename.split("/") for e in items):
                raise ValueError("Unsafe DOCX path")
            document_parts=[e for e in items if e.filename=="word/document.xml"]
            if len(document_parts)!=1:
                raise ValueError("Missing or duplicate document.xml")
            if document_parts[0].file_size>MAX_DOC_XML_BYTES:
                raise ValueError("DOCX document XML too large")
            raw=z.read(document_parts[0])
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ValueError("DOCX DTD/entity declarations not allowed")
            root=ET.fromstring(raw)
            fs=[n for n in z.namelist() if n.startswith("word/media/") and not n.endswith("/")]
            fonts=set()
            for node in root.iter(W+"rFonts"):
                fonts.update(v for k,v in node.attrib.items() if k.endswith(("}ascii","}hAnsi","}eastAsia","}cs")))
            txt=" ".join((e.text or "") for e in root.iter(W+"t"))
            return {"media_files":len(fs),"table_nodes":len(list(root.iter(W+"tbl"))),
                    "drawing_nodes":len(list(root.iter(W+"drawing"))),
                    "fonts":sorted(fonts),"words":words(txt)}
    except BadZipFile as e:
        raise ValueError("Invalid DOCX ZIP") from e

def pdf_structure(path):
    import fitz
    if not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise ValueError("PDF absent or >40MB")
    with fitz.open(path) as doc:
        if not doc.is_pdf or doc.is_encrypted or len(doc)>200:
            raise ValueError("Invalid, protected or over-limit PDF")
        images=set()
        fonts=set()
        drawings=[]
        txt=[]
        for p in doc:
            images.update(x[0] for x in p.get_images(full=True))
            drawings.append(len(p.get_drawings()))
            txt.append(p.get_text())
            fonts.update(str(f[3]) for f in p.get_fonts(full=True) if len(f)>=4)
        return {"pages":len(doc),"embedded_images":len(images),
                "fonts":sorted(fonts),"drawing_operations":drawings,
                "words":words("\n".join(txt))}

def compare_visual(output,reference):
    import fitz
    from PIL import Image,ImageChops,ImageStat
    with fitz.open(output) as o,fitz.open(reference) as r:
        if len(o)!=len(r): return {"status":"SKIPPED_PAGE_MISMATCH"}
        if len(o)>24: return {"status":"SKIPPED_OVER_24_PAGES"}
        pages=[]
        total_pixels=0
        for i in range(len(o)):
            if abs(o[i].rect.width-r[i].rect.width)>1 or abs(o[i].rect.height-r[i].rect.height)>1:
                pages.append({"page":i+1,"status":"PAGE_GEOMETRY_MISMATCH"});continue
            # Check untrusted page geometry BEFORE bitmap allocation at 72 DPI.
            width=max(1,int(o[i].rect.width+0.9999))
            height=max(1,int(o[i].rect.height+0.9999))
            pixels=width*height
            if pixels>MAX_PAGE_RENDER_PIXELS or total_pixels+pixels>MAX_TOTAL_RENDER_PIXELS:
                pages.append({"page":i+1,"status":"SKIPPED_RENDER_PIXEL_LIMIT"});continue
            total_pixels+=pixels
            a=o[i].get_pixmap(colorspace=fitz.csGRAY,alpha=False)
            b=r[i].get_pixmap(colorspace=fitz.csGRAY,alpha=False)
            if (a.width,a.height)!=(b.width,b.height):
                pages.append({"page":i+1,"status":"RASTER_SIZE_MISMATCH"});continue
            x=Image.frombytes("L",(a.width,a.height),a.samples)
            y=Image.frombytes("L",(b.width,b.height),b.samples)
            value=ImageStat.Stat(ImageChops.difference(x,y)).mean[0]/255
            pages.append({"page":i+1,"mean_absolute_pixel_difference":round(value,5)})
        return {"status":"MEASURED_NOT_PASS","pages":pages}

def audit(src,out,ref=None):
    d=docx_structure(src)
    p=pdf_structure(out)
    reference=pdf_structure(ref) if ref else None
    failures=[]
    warnings=[]
    if d["media_files"]>0 and p["embedded_images"]==0:
        failures.append("ALL_EMBEDDED_DOCX_MEDIA_MISSING")
    if reference and p["pages"]!=reference["pages"]:
        failures.append("PAGE_COUNT_MISMATCH")
    if d["table_nodes"] and not any(p["drawing_operations"]):
        warnings.append("TABLES_WITH_NO_PDF_VECTOR_DRAWING")
    overlap=sum((Counter(d["words"]) & Counter(p["words"])).values())/max(1,len(d["words"]))
    # A mostly empty PDF is a failed conversion, not a soft warning.
    # Leave moderate extractable-text differences for manual review.
    if d["words"] and overlap<.60:
        failures.append("SEVERE_TEXT_LOSS")
    elif d["words"] and overlap<.92:
        warnings.append("LOW_TEXT_OVERLAP")
    elif not d["words"]:
        warnings.append("NO_EXTRACTABLE_SOURCE_TEXT")
    if reference and len(p["fonts"])<len(reference["fonts"]):
        warnings.append("FONT_RESOURCE_REDUCTION")
    for v in (d,p):
        v.pop("words",None)
    if reference: reference.pop("words",None)
    return {"status":"FAIL" if failures else "REVIEW_REQUIRED",
            "hard_failures":failures,"review_warnings":warnings,
            "source":d,"output":p,"reference":reference,
            "word_overlap":round(overlap,4),
            "visual":compare_visual(out,ref) if ref else {"status":"NO_REFERENCE"},
            "note":"No automated result alone establishes professional fidelity."}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("docx",type=Path)
    ap.add_argument("pdf",type=Path)
    ap.add_argument("--reference-pdf",type=Path)
    ap.add_argument("--report",type=Path)
    ap.add_argument("--strict",action="store_true")
    a=ap.parse_args()
    try:
        r=audit(a.docx,a.pdf,a.reference_pdf)
        s=json.dumps(r,indent=2,ensure_ascii=False)
        if a.report:
            a.report.parent.mkdir(parents=True,exist_ok=True)
            a.report.write_text(s+"\n",encoding="utf8")
        print(s)
        return 2 if a.strict and r["status"]=="FAIL" else 0
    except Exception as e:
        print("INVALID_EVIDENCE:",str(e),file=sys.stderr)
        return 3

if __name__=="__main__": sys.exit(main())
