"""Synthetic tests. A static APK PASS is not a real DOCX/PDF quality pass."""
import tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from offline_apk_gate import (
    REQUIRED,LIB,PACKAGE_ID,scan_entries,assess_metadata,
    elf_arm64_header,sdk_aapt,inspect_apk)

ELF=b'\x7fELF\x02\x01'+bytes(10)+(3).to_bytes(2,'little')+(183).to_bytes(2,'little')+bytes(44)

def complete_names():
    return set(REQUIRED)|{'assets/unpack/user/fonts/LiberationSans-Regular.ttf'}

class StaticPackageGateTests(unittest.TestCase):
    def valid(self,**kwargs):
        args={'names':complete_names(),'package':PACKAGE_ID,'permissions':[],
              'elf_header':ELF,'lib_size':3000000}
        args.update(kwargs)
        return assess_metadata(**args)

    def test_valid_static_package_never_claims_document_fidelity(self):
        r=self.valid()
        self.assertEqual(r['status'],'PACKAGE_STATIC_PASS')
        self.assertFalse(r['docx_pdf_fidelity_proved'])
        self.assertFalse(r['airplane_mode_device_tested'])
        self.assertFalse(r['public_release_approved'])

    def test_wrong_app_id_rejected(self):
        self.assertIn('WRONG_APPLICATION_ID',self.valid(package='org.libreoffice')['issues'])

    def test_internet_permission_rejected(self):
        r=self.valid(permissions=['android.permission.INTERNET'])
        self.assertIn('UNEXPECTED_ANDROID_PERMISSIONS',r['issues'])

    def test_missing_bootstrap_rejected(self):
        r=self.valid(names=complete_names()-{'assets/program/fundamentalrc'})
        self.assertIn('REQUIRED_RUNTIME_ASSETS_MISSING',r['issues'])

    def test_missing_font_rejected(self):
        self.assertIn('BUNDLED_FONTS_MISSING',self.valid(names=set(REQUIRED))['issues'])

    def test_missing_engine_rejected(self):
        r=self.valid(names=complete_names()-{LIB},lib_size=0)
        self.assertIn('NATIVE_ENGINE_NOT_ARM64_ELF_SHARED',r['issues'])

    def test_wrong_elf_abi_rejected(self):
        wrong=b'\x7fELF\x02\x01'+bytes(10)+(3).to_bytes(2,'little')+(62).to_bytes(2,'little')
        self.assertFalse(elf_arm64_header(wrong))
        self.assertIn('NATIVE_ENGINE_NOT_ARM64_ELF_SHARED',self.valid(elf_header=wrong)['issues'])

    def test_duplicate_archive_entry_rejected(self):
        self.assertIn('DUPLICATE_ZIP_ENTRY',scan_entries([zipfile.ZipInfo('x'),zipfile.ZipInfo('x')])[1])

    def test_path_traversal_archive_entry_rejected(self):
        self.assertIn('UNSAFE_ZIP_ENTRY',scan_entries([zipfile.ZipInfo('../escape')])[1])

    def test_zip_bomb_ratio_rejected(self):
        x=zipfile.ZipInfo('huge');x.file_size=600000;x.compress_size=8
        self.assertIn('ZIP_EXCESSIVE_COMPRESSION_RATIO',scan_entries([x])[1])

    def test_symlink_rejected(self):
        x=zipfile.ZipInfo('assets/evil');x.external_attr=(0o120777<<16)
        self.assertIn('ZIP_SYMLINK_ENTRY',scan_entries([x])[1])

    def test_aapt_extracts_verified_package_and_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'aapt';binary.write_text('fake')
            def fake_run(argv,**kwargs):
                out="package: name='hu.formatlab.android' versionCode='4'" if 'badging' in argv else "uses-permission: name='android.permission.INTERNET'"
                return SimpleNamespace(returncode=0,stdout=out)
            pkg,perms=sdk_aapt(Path(d)/'app.apk',binary,runner=fake_run)
            self.assertEqual(pkg,PACKAGE_ID)
            self.assertEqual(perms,['android.permission.INTERNET'])

    def test_aapt_unavailable_fails_closed(self):
        with patch('offline_apk_gate.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'AAPT_NOT_FOUND'):
                sdk_aapt(Path('fake.apk'),'/definitely/missing/aapt')

    def test_invalid_zip_rejected_before_aapt(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'app.apk';apk.write_bytes(b'bad'*500)
            self.assertIn('APK_ZIP_INVALID',inspect_apk(apk,aapt='ignored')['issues'])

    def test_real_zip_and_mocked_aapt_static_pass_not_fidelity(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'complete-but-not-working.apk'
            with zipfile.ZipFile(apk,'w',compression=zipfile.ZIP_STORED) as z:
                for name in complete_names():
                    z.writestr(name,ELF+bytes(1100000) if name==LIB else b'test asset')
            with patch('offline_apk_gate.sdk_aapt',return_value=(PACKAGE_ID,[])):
                result=inspect_apk(apk,aapt='mock')
            self.assertEqual(result['status'],'PACKAGE_STATIC_PASS')
            self.assertFalse(result['docx_pdf_fidelity_proved'])
            self.assertEqual(len(result['sha256']),64)

    def test_missing_library_real_zip_reports_missing_not_exception(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'missing-lib.apk'
            with zipfile.ZipFile(apk,'w',compression=zipfile.ZIP_STORED) as z:
                for name in complete_names()-{LIB}:z.writestr(name,b'test')
                z.writestr('padding.bin',bytes(1800))
            with patch('offline_apk_gate.sdk_aapt',return_value=(PACKAGE_ID,[])):
                result=inspect_apk(apk,aapt='mock')
            self.assertEqual(result['status'],'BLOCKED')
            self.assertIn('REQUIRED_RUNTIME_ASSETS_MISSING',result['issues'])
            self.assertIn('NATIVE_ENGINE_NOT_ARM64_ELF_SHARED',result['issues'])

    def test_actual_synthetic_zip_without_native_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'fake.apk'
            with zipfile.ZipFile(apk,'w') as z:
                z.writestr('assets/program/bootstraprc','[Bootstrap]')
                z.writestr('assets/unpack/user/fonts/font.ttf','dummy')
            r=inspect_apk(apk,aapt='ignored')
            self.assertNotEqual(r['status'],'PACKAGE_STATIC_PASS')

if __name__=='__main__':unittest.main()
