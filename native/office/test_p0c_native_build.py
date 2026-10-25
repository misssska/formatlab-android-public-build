"""Synthetic negative tests; they do NOT prove a LibreOfficeKit engine."""
import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from p0c_native_build import attest_arm64, preflight, disposable, memory_gib, upstream_apks, build_stages

class NativeBuildGateTests(unittest.TestCase):
    def test_core_build_must_precede_android_link(self):
        stages=build_stages(2)
        self.assertEqual(stages,[
            ('core_build',['make','-j2','build']),
            ('android_link',['make','-j2','android'])])

    def test_three_workers_supported(self):
        self.assertEqual(build_stages(3)[0][1],['make','-j3','build'])

    def test_four_workers_supported(self):
        self.assertEqual(build_stages(4)[1][1],['make','-j4','android'])

    def test_invalid_parallelism_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'PARALLEL_JOB_LIMIT'):
            build_stages(5)

    def test_valid_arm64_shared_object(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'liblo-native-code.so'
            f.write_bytes(b'\x7fELF\x02\x01'+bytes(10)+(3).to_bytes(2,'little')+(183).to_bytes(2,'little')+bytes(80))
            result=attest_arm64(f,min_bytes=40)
            self.assertEqual(result['abi'],'arm64-v8a')
            self.assertEqual(len(result['sha256']),64)

    def test_x86_elf_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'bad.so'
            f.write_bytes(b'\x7fELF\x02\x01'+bytes(10)+(3).to_bytes(2,'little')+(62).to_bytes(2,'little')+bytes(80))
            with self.assertRaisesRegex(ValueError,'ARM64'):attest_arm64(f,min_bytes=40)

    def test_truncated_binary_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'bad.so';f.write_bytes(b'\x7fELF')
            with self.assertRaises(ValueError):attest_arm64(f,min_bytes=1)

    def test_missing_opt_in_blocks_build(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'formatlab-lo-p0c';src.mkdir()
            with patch.dict(os.environ,{'FORMATLAB_DISPOSABLE_CHECKOUT':'NO','FORMATLAB_ALLOW_NATIVE_BUILD':'NO'}):
                with self.assertRaisesRegex(ValueError,'OPT_IN'):disposable(src,Path(td))

    def test_untrusted_workspace_blocks_build(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'milan-code';src.mkdir()
            with patch.dict(os.environ,{'FORMATLAB_DISPOSABLE_CHECKOUT':'YES','FORMATLAB_ALLOW_NATIVE_BUILD':'YES'}):
                with self.assertRaisesRegex(ValueError,'PINNED'):disposable(src,Path(td))

    def test_external_workspace_blocks_build(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'formatlab-lo-p0c';src.mkdir()
            with patch.dict(os.environ,{'FORMATLAB_DISPOSABLE_CHECKOUT':'YES','FORMATLAB_ALLOW_NATIVE_BUILD':'YES'}):
                with self.assertRaisesRegex(ValueError,'ROOT'):disposable(src,Path(td)/'elsewhere')

    def _preflight(self,src,sdk,ndk,disk=30,mem=20):
        with patch('p0c_native_build.inspect',return_value={'status':'PASS','commit':'pin'}),\
             patch('p0c_native_build.config_preview',return_value='ok'),\
             patch('p0c_native_build.shutil.which',return_value='/usr/bin/make'):
            return preflight(src,sdk,ndk,disk_gib=disk,mem_gib=mem,require_approval=False)

    def test_insufficient_ram_and_disk(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);src=p/'src';src.mkdir()
            r=self._preflight(src,p/'sdk',p/'ndk',disk=1,mem=4)
            self.assertEqual(r['status'],'BLOCKED')
            self.assertIn('DISK_LIMIT',r['blockers'])
            self.assertIn('MEMORY_LIMIT',r['blockers'])
            self.assertFalse(r['engine_compiled'])

    def test_not_configured_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);src=p/'src';src.mkdir()
            r=self._preflight(src,p/'sdk',p/'ndk')
            self.assertIn('UPSTREAM_NOT_CONFIGURED',r['blockers'])

    def test_synthetic_ready_is_not_compiled(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);src=p/'src';src.mkdir()
            (src/'config_host.mk').write_text('ok')
            (src/'Makefile').write_text('ok')
            sdk=p/'sdk';(sdk/'platforms/android-35').mkdir(parents=True)
            r=self._preflight(src,sdk,p/'ndk')
            self.assertEqual(r['status'],'READY_TO_BUILD')
            self.assertFalse(r['engine_compiled'])

    def test_missing_ram_read_is_safe(self):
        self.assertIsNone(memory_gib(Path('/nonexistent/formatlab-p0c-meminfo')))

    def test_no_upstream_apk_not_formatlab_apk(self):
        with tempfile.TemporaryDirectory() as td:
            result=upstream_apks(Path(td))
            self.assertEqual(result['upstream_reference_apks'],[])
            self.assertFalse(result['formatlab_apk_built'])

if __name__=='__main__':unittest.main()
