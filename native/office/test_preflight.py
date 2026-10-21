import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from preflight import inspect

class PreflightTests(unittest.TestCase):
    def test_no_sdk_produces_clear_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            r=inspect(env={},tool_lookup=lambda x:'/usr/bin/'+x,root=Path(d))
            self.assertEqual(r['status'],'BLOCKED')
            self.assertTrue(any('SDK' in x for x in r['blockers']))
            self.assertEqual(r['changed_files'],0)

    def test_fake_offline_ndk27_sdk_reports_configurable(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            ndk=p/'sdk'/'ndk'/'27.2.12479018'
            ndk.mkdir(parents=True)
            (ndk/'source.properties').write_text('Pkg.Revision = 27.2.12479018\n')
            with patch('preflight.platform.system',return_value='Linux'):
                r=inspect(env={'ANDROID_SDK_ROOT':str(p/'sdk')},
                          tool_lookup=lambda x:'/usr/bin/'+x,root=p)
            self.assertEqual(r['status'],'READY_FOR_CONFIGURE_ONLY')
            self.assertEqual(r['ndk_version'],'27.2.12479018')

if __name__=='__main__': unittest.main()
