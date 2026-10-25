import tempfile
from pathlib import Path
from unittest import TestCase
from engine_source_gate import inspect,config_preview,PINNED_COMMIT,REQUIRED

class SourceGateTests(TestCase):
    def test_pinned_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in REQUIRED:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('--host=aarch64-linux-android\n' if 'Aarch64.conf' in name else 'placeholder\n')
            self.assertEqual(inspect(root,sha=PINNED_COMMIT)['status'],'PASS')
    def test_wrong_source_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn('SOURCE_COMMIT_MISMATCH',inspect(Path(tmp),sha='0'*40)['issues'])
    def test_wrong_distro_abi_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in REQUIRED:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('--host=arm-linux-androideabi\n')
            self.assertIn('SOURCE_WRONG_ABI',inspect(root,sha=PINNED_COMMIT)['issues'])
    def test_pinned_ndk_autogen_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sdk=root/'sdk';ndk=sdk/'ndk/27.2.12479018'
            ndk.mkdir(parents=True);(ndk/'source.properties').write_text('Pkg.Revision = 27.2.12479018\n')
            s=config_preview(sdk,ndk)
            self.assertIn('--with-distro=LibreOfficeAndroidAarch64',s)
    def test_old_ndk_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ndk=root/'ndk';ndk.mkdir();(ndk/'source.properties').write_text('Pkg.Revision = 26.0.0\n')
            with self.assertRaisesRegex(ValueError,'Exact NDK'):config_preview(root,ndk)
