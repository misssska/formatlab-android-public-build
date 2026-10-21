"""Synthetic, public-safe regression checks for the fidelity gate itself.

These checks do NOT verify an Android office layout engine or prove document fidelity.
"""
import tempfile
from pathlib import Path
import unittest
import fitz
from PIL import Image,ImageDraw
from docx import Document
from docx.shared import Inches
from office_fidelity_probe import audit,docx_structure,pdf_structure


def fixture(directory):
    root=Path(directory)
    img=root/"synthetic.png"
    bitmap=Image.new("RGB",(150,50),"white")
    painter=ImageDraw.Draw(bitmap)
    painter.ellipse((15,8,70,42),fill="green")
    bitmap.save(img)
    src=root/"synthetic.docx"
    d=Document()
    d.add_heading("Árvíztűrő tükörfúrógép",0)
    r=d.add_paragraph().add_run("Félkövér, színek, többféle font")
    r.bold=True
    t=d.add_table(rows=2,cols=2,style="Table Grid")
    t.cell(0,0).text="Táblázat"
    t.cell(1,0).text="Cella"
    d.add_picture(str(img),width=Inches(2))
    d.save(src)
    bad=root/"flattened.pdf"
    p=fitz.open()
    p.new_page().insert_text((40,50),"Text-only flattening")
    p.save(bad);p.close()
    reference=root/"reference.pdf"
    q=fitz.open()
    page=q.new_page()
    page.insert_text((40,50),"Office layout reference")
    page.insert_image(fitz.Rect(50,75,200,125),filename=str(img))
    q.save(reference);q.close()
    return src,bad,reference


class QualityProbeTests(unittest.TestCase):
    def test_detects_missing_docx_images(self):
        with tempfile.TemporaryDirectory() as temp:
            doc,bad,ref=fixture(temp)
            result=audit(doc,bad,ref)
            self.assertEqual(result["status"],"FAIL")
            self.assertIn("ALL_EMBEDDED_DOCX_MEDIA_MISSING",result["hard_failures"])
            self.assertEqual(result["source"]["table_nodes"],1)

    def test_matching_reference_is_still_not_professional_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            doc,bad,ref=fixture(temp)
            result=audit(doc,ref,ref)
            self.assertEqual(result["status"],"REVIEW_REQUIRED")
            self.assertEqual(result["hard_failures"],[])
            self.assertEqual(result["visual"]["status"],"MEASURED_NOT_PASS")

    def test_invalid_docx_zip_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid=Path(temp)/"broken.docx"
            invalid.write_bytes(b"not DOCX")
            with self.assertRaises(ValueError): docx_structure(invalid)

    def test_invalid_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid=Path(temp)/"broken.pdf"
            invalid.write_bytes(b"not PDF")
            with self.assertRaises(Exception): pdf_structure(invalid)


if __name__=="__main__":
    unittest.main()
