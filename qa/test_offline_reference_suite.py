"""Offline reference corpus and Android candidate negative tests (synthetic only)."""
import shutil,tempfile,unittest
from pathlib import Path
import fitz
from offline_reference_suite import SPECS,create_corpus,convert_reference,build
from offline_android_fidelity_acceptance import compare,inspect_case

class OfflineQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='formatlab-qa-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_generates_five_synthetic_docx(self):
        corpus=create_corpus(self.root/'corpus')
        self.assertEqual(len(corpus),5)
        self.assertTrue(all(f.stat().st_size>1000 for _,f in corpus))

    def test_embedded_png_has_pixels(self):
        create_corpus(self.root/'corpus')
        files=list((self.root/'corpus'/'generated-images').glob('*.png'))
        self.assertEqual(len(files),3)
        self.assertTrue(all(x.stat().st_size>200 for x in files))

    def test_invalid_timeout_denied(self):
        with self.assertRaisesRegex(ValueError,'INVALID_TIMEOUT'):
            convert_reference(self.root/'no.docx',self.root/'out','none',timeout=9999)

    def test_missing_candidate_fails(self):
        src=create_corpus(self.root/'synthetic_docx')[0]
        result=inspect_case(src[0],self.root,self.root/'empty')
        self.assertEqual(result['result'],'FAIL')

    def test_missing_reference_report_denied(self):
        with self.assertRaisesRegex(ValueError,'REFERENCE_SUITE_REPORT_MISSING'):
            compare(self.root,self.root/'candidate')

    def test_invalid_visual_difference_denied(self):
        with self.assertRaisesRegex(ValueError,'INVALID_VISUAL_DIFF_LIMIT'):
            compare(self.root,self.root,max_mean_diff=.7)

    @unittest.skipUnless(shutil.which('libreoffice'),'LibreOffice headless unavailable')
    def test_full_offline_reference_and_candidate_contract(self):
        suite=self.root/'suite'
        reference=build(suite,soffice=shutil.which('libreoffice'))
        self.assertEqual(reference['status'],'REFERENCE_PASS',reference)
        self.assertEqual(len(reference['cases']),5)
        self.assertFalse(reference['android_fidelity_tested'])
        candidate=self.root/'candidate';candidate.mkdir()
        for spec in SPECS:
            shutil.copyfile(suite/'reference_pdf'/f'{spec.name}.pdf',candidate/f'{spec.name}.pdf')
        same=compare(suite,candidate)
        self.assertEqual(same['status'],'CANDIDATE_STATIC_PASS',same)
        self.assertFalse(same['device_provenance_verified'])
        # Negative: text-only PDF discards images. No false pass.
        filename='embedded_images.pdf'
        source=fitz.open(candidate/filename)
        text_only=fitz.open()
        for page in source:
            dest=text_only.new_page(width=page.rect.width,height=page.rect.height)
            dest.insert_text((30,30),page.get_text()[:1000])
        source.close()
        text_only.save(candidate/filename);text_only.close()
        broken=compare(suite,candidate)
        self.assertEqual(broken['status'],'FAIL')
        image=next(x for x in broken['cases'] if x['case']=='embedded_images')
        self.assertIn('EMBEDDED_IMAGES_LOST',image['blockers'])
        # Reference SHA mismatch must abort (no evidence tampering).
        with (suite/'reference_pdf'/'styled_text.pdf').open('ab') as f:
            f.write(b'\n%test-tamper\n')
        with self.assertRaisesRegex(ValueError,'REFERENCE_SHA256_MISMATCH'):
            compare(suite,candidate)

if __name__=='__main__':unittest.main()
