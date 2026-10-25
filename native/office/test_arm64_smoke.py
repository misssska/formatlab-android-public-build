import tempfile
from pathlib import Path
from unittest import TestCase
from arm64_smoke import smoke

class FakeResult:
    returncode=0;stderr=''

class SmokeTests(TestCase):
    def _ndk(self,root):
        ndk=Path(root)/'ndk';compiler=ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';compiler.parent.mkdir(parents=True)
        compiler.write_text('mock');(ndk/'source.properties').write_text('Pkg.Revision = 27.2.12479018\n')
        return ndk
    def test_elf64_arm64_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            ndk=self._ndk(tmp)
            def compile(argv,**kwargs):
                p=Path(argv[argv.index('-o')+1]);p.write_bytes(b'\x7fELF'+bytes([2,1])+bytes(10)+(3).to_bytes(2,'little')+(183).to_bytes(2,'little')+bytes(20))
                return FakeResult()
            self.assertEqual(smoke(ndk,run=compile)['status'],'PASS')
    def test_wrong_machine_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            ndk=self._ndk(tmp)
            def compile(argv,**kwargs):
                Path(argv[argv.index('-o')+1]).write_bytes(b'\x7fELF'+bytes([2,1])+bytes(10)+(3).to_bytes(2,'little')+(62).to_bytes(2,'little')+bytes(20))
                return FakeResult()
            with self.assertRaisesRegex(RuntimeError,'AARCH64'):smoke(ndk,run=compile)
    def test_incorrect_ndk_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            ndk=self._ndk(tmp);(ndk/'source.properties').write_text('Pkg.Revision = 29.0.0\n')
            with self.assertRaisesRegex(ValueError,'NDK_PIN'):smoke(ndk)
    def test_api_range_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            ndk=self._ndk(tmp)
            with self.assertRaisesRegex(ValueError,'API_OUT'):smoke(ndk,api_level=21)
