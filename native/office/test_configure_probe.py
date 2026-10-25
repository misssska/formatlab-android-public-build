"""No network/no LibreOffice required: deterministic P0b configure safety tests."""
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from configure_probe import check, run_probe


class ConfigureProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "core"
        self.sdk = self.root / "sdk"
        self.ndk = self.sdk / "ndk" / "27.2.12479018"
        self.source.mkdir()
        self.ndk.mkdir(parents=True)
        (self.source / "autogen.sh").write_text("#!/bin/sh\nexit 0\n")
        for p in ("platforms/android-35", "build-tools/35.0.0"):
            (self.sdk / p).mkdir(parents=True)
        self.identity = {"status": "PASS", "commit": "f2820323446ae210668dcb6422ddcd55ce939dc2", "issues": []}

    def mocks(self):
        from contextlib import ExitStack
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("configure_probe.inspect", return_value=self.identity))
        stack.enter_context(patch("configure_probe.config_preview", return_value="--with-distro=LibreOfficeAndroidAarch64\n"))
        stack.enter_context(patch("configure_probe.shutil.which", side_effect=lambda name: "/usr/bin/" + name))
        stack.enter_context(patch("configure_probe.shutil.disk_usage", return_value=SimpleNamespace(free=15*(1024**3))))
        return stack

    def test_preflight_pass_not_a_build(self):
        self.mocks()
        r = check(self.source, self.sdk, self.ndk)
        self.assertEqual(r["status"], "READY_FOR_CONFIGURE")
        self.assertFalse(r["office_engine_built"])
        self.assertFalse(r["android_apk_built"])

    def test_missing_android_platform_denied(self):
        self.mocks()
        (self.sdk/"platforms/android-35").rmdir()
        r = check(self.source, self.sdk, self.ndk)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIn("MISSING_ANDROID_SDK_COMPONENT:platforms/android-35", r["blockers"])

    def test_low_disk_blocks(self):
        self.mocks()
        with patch("configure_probe.shutil.disk_usage", return_value=SimpleNamespace(free=2*(1024**3))):
            r = check(self.source, self.sdk, self.ndk)
        self.assertIn("INSUFFICIENT_FREE_DISK", r["blockers"])

    def test_wrong_source_denied(self):
        self.mocks()
        with patch("configure_probe.inspect", return_value={"status":"BLOCKED","commit":"bad","issues":["SOURCE_COMMIT_MISMATCH"]}):
            r = check(self.source, self.sdk, self.ndk)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIn("SOURCE_COMMIT_MISMATCH", r["blockers"])

    def test_no_explicit_disposable_opt_in_denied_without_write(self):
        self.mocks()
        with patch.dict(os.environ, {"FORMATLAB_DISPOSABLE_CHECKOUT": "NO"}):
            r = run_probe(self.source, self.sdk, self.ndk)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertFalse((self.source/"autogen.input").exists())

    def test_configure_success_is_not_native_engine(self):
        self.mocks()
        called = []
        def fake_run(argv, **kw):
            called.append((argv, kw["cwd"]))
            return SimpleNamespace(returncode=0, stdout="configured", stderr="")
        with patch.dict(os.environ, {"FORMATLAB_DISPOSABLE_CHECKOUT": "YES"}):
            r = run_probe(self.source, self.sdk, self.ndk, runner=fake_run)
        self.assertEqual(r["status"], "CONFIGURED_ONLY")
        self.assertTrue((self.source/"autogen.input").exists())
        self.assertEqual(called[0][0], ["perl", "autogen.sh"])
        self.assertFalse(r["office_engine_built"])
        self.assertFalse(r["android_apk_built"])

    def test_nonzero_exit_does_not_become_pass(self):
        self.mocks()
        def fake_run(*a, **kw):
            return SimpleNamespace(returncode=1, stdout="", stderr="missing host deps")
        with patch.dict(os.environ, {"FORMATLAB_DISPOSABLE_CHECKOUT": "YES"}):
            r = run_probe(self.source, self.sdk, self.ndk, runner=fake_run)
        self.assertEqual(r["status"], "FAILED")
        self.assertIn("AUTOGEN_NONZERO_EXIT", r["blockers"])

    def test_unsupported_space_limit_denied(self):
        self.mocks()
        with self.assertRaisesRegex(ValueError, "INVALID_MIN_FREE_SPACE"):
            check(self.source, self.sdk, self.ndk, min_free_gib=0)


if __name__ == "__main__":
    unittest.main()
