"""Safe source-overlay tests; no Android SDK or real native library needed."""
from __future__ import annotations
import hashlib,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from assemble_runtime_overlay import assemble,verify_archive,GateError,PINNED_KIT,SOURCE_UPSTREAM,ROOT,OVERLAY_JAVA

class RuntimeOverlayTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir=Path(tmp.name)
        self.archive=self.dir/'v03.zip'
        self.upstream=self.dir/'upstream'
        self.overlay=self.dir/'overlay'
        self.overlay.mkdir()
        self.out=self.dir/'out'
        for name in OVERLAY_JAVA:
            (self.overlay/name).write_text(
                'package hu.formatlab.android; class '+name[:-5]+' {}\n')
        for name in PINNED_KIT:
            p=self.upstream/SOURCE_UPSTREAM/name
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(
                ('package org.libreoffice.kit; import android.app.Activity; '
                 'class LibreOfficeKit { void init(Activity activity) { '
                 'activity.getApplication().getCacheDir(); '
                 'activity.getApplication().getPackageResourcePath(); } }')
                if name=='LibreOfficeKit.java'
                else 'package org.libreoffice.kit; class '+name[:-5]+' {}\n')

    def fixture(self,*,bad_internet=False,bad_main=False,duplicate=False,traversal=False):
        src={
            f'{ROOT}/app/build.gradle':'plugins { id "com.android.application" }',
            f'{ROOT}/app/src/main/java/hu/formatlab/android/MainActivity.java':
                'package wrong.pkg;' if bad_main else 'package hu.formatlab.android; class MainActivity {}',
            f'{ROOT}/app/src/main/AndroidManifest.xml':
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                'android.permission.INTERNET="true"><application></application></manifest>'
                if bad_internet else '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                'package="hu.formatlab.android"><application></application></manifest>'
        }
        if traversal:src[f'{ROOT}/../injected.txt']='escape'
        with zipfile.ZipFile(self.archive,'w') as z:
            for k,v in src.items():z.writestr(k,v)
            if duplicate:z.writestr(f'{ROOT}/app/build.gradle','duplicate')
        return hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def test_happy_overlay_reports_not_native(self):
        sha=self.fixture()
        r=assemble(self.archive,self.upstream,self.overlay,self.out,expected_sha=sha)
        self.assertEqual(r['status'],'SOURCE_OVERLAY_ASSEMBLED')
        self.assertFalse(r['native_lib_bundled'])
        self.assertFalse(r['feature_exposed_in_ui'])
        self.assertEqual(len(r['sources']),len(PINNED_KIT)+len(OVERLAY_JAVA))
        self.assertTrue((self.out/'FORMATLAB_OFFICE_OVERLAY_EVIDENCE.json').is_file())
        self.assertTrue(r['separate_process_service_declared'])
        self.assertTrue(r['upstream_context_adapter_pinned'])
        manifest=(self.out/'app/src/main/AndroidManifest.xml').read_text()
        self.assertIn('android:process=":office"',manifest)
        self.assertIn('android:exported="false"',manifest)
        lib=(self.out/'app/src/main/java/org/libreoffice/kit/LibreOfficeKit.java').read_text()
        self.assertIn('init(Context activity)',lib)
        self.assertNotIn('init(Activity activity)',lib)

    def test_untrusted_upstream_adapter_signature_blocks(self):
        sha=self.fixture()
        lib=self.upstream/SOURCE_UPSTREAM/'LibreOfficeKit.java'
        lib.write_text('package org.libreoffice.kit; class LibreOfficeKit {}')
        with self.assertRaisesRegex(GateError,'UPSTREAM_CONTEXT_ADAPTER_PATTERN_CHANGED'):
            assemble(self.archive,self.upstream,self.overlay,self.out,expected_sha=sha)
        self.assertFalse(self.out.exists())

    def test_missing_service_source_blocks(self):
        sha=self.fixture()
        (self.overlay/'FormatLabOfficeService.java').unlink()
        with self.assertRaisesRegex(GateError,'OVERLAY_SOURCE_MISSING'):
            assemble(self.archive,self.upstream,self.overlay,self.out,expected_sha=sha)
        self.assertFalse(self.out.exists())

    def test_client_timeout_bound_and_cancelled_on_finish(self):
        client = (Path(__file__).parent/'android/hu/formatlab/android/FormatLabOfficeProcessClient.java').read_text()
        self.assertIn('FormatLabOfficeService.MAX_SECONDS + 20L', client)
        self.assertIn('main.postDelayed(timeout, CLIENT_TIMEOUT_MS)', client)
        self.assertIn('main.removeCallbacks(timeout)', client)
        self.assertIn('OFFICE_CLIENT_TIMEOUT', client)
        self.assertIn('if (finished) return;', client)
        self.assertIn('context.unbindService(connection)', client)

    def test_docx_zip_path_and_pdf_trailer_guards(self):
        converter = (Path(__file__).parent/'android/hu/formatlab/android/FormatLabOfflineOfficeConverter.java').read_text()
        for guard in ('name.startsWith("./")', 'name.contains("//")',
                      'name.endsWith("/.")', 'name.indexOf((char) 0) >= 0'):
            self.assertIn(guard, converter)
        self.assertIn('new RandomAccessFile(file, "r")', converter)
        self.assertIn('PDF end marker missing', converter)
        self.assertIn("tail[i + 4] == 'F'", converter)
        self.assertIn('MAX_PDF_BYTES', converter)

    def test_stale_private_cache_cleanup_is_narrowly_scoped(self):
        converter = (Path(__file__).parent/'android/hu/formatlab/android/FormatLabOfflineOfficeConverter.java').read_text()
        self.assertIn('TEMP_RETENTION_MS = 24L * 60L * 60L * 1000L', converter)
        self.assertIn('cleanupStaleTempFiles(workDir)', converter)
        self.assertIn('name.startsWith("office-in-")', converter)
        self.assertIn('name.startsWith("office-out-")', converter)
        self.assertIn('candidate.lastModified() < cutoff', converter)

    def test_archive_hash_mismatch_fails(self):
        self.fixture()
        with self.assertRaisesRegex(GateError,'SHA256'):verify_archive(self.archive)

    def test_traversal_archive_fails(self):
        sha=self.fixture(traversal=True)
        with self.assertRaisesRegex(GateError,'UNSAFE_SOURCE_ZIP'):
            verify_archive(self.archive,expected_sha=sha)

    def test_duplicate_archive_entry_fails(self):
        sha=self.fixture(duplicate=True)
        with self.assertRaisesRegex(GateError,'DUPLICATE_SOURCE_ZIP'):
            verify_archive(self.archive,expected_sha=sha)

    def test_normalized_source_zip_path_rejected(self):
        self.fixture()
        with zipfile.ZipFile(self.archive, 'a') as z:
            z.writestr(f'{ROOT}/app/./extra.txt', 'alias')
        sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaisesRegex(GateError, 'UNSAFE_SOURCE_ZIP'):
            verify_archive(self.archive, expected_sha=sha)

    def test_missing_upstream_file_fails_cleanup(self):
        sha=self.fixture()
        (self.upstream/SOURCE_UPSTREAM/PINNED_KIT[0]).unlink()
        with self.assertRaisesRegex(GateError,'UPSTREAM_KIT_SOURCE_MISSING'):
            assemble(self.archive,self.upstream,self.overlay,self.out,expected_sha=sha)
        self.assertFalse(self.out.exists())

    def test_internet_permission_fails_cleanup(self):
        sha=self.fixture(bad_internet=True)
        with self.assertRaisesRegex(GateError,'INTERNET_PERMISSION_FORBIDDEN'):
            assemble(self.archive,self.upstream,self.overlay,self.out,expected_sha=sha)
        self.assertFalse(self.out.exists())

    def test_wrong_main_package_fails(self):
        sha=self.fixture(bad_main=True)
        with self.assertRaisesRegex(GateError,'UNEXPECTED_APP_PACKAGE'):
            assemble(self.archive,self.upstream,self.overlay,self.out,expected_sha=sha)

    def test_existing_output_blocks_without_changes(self):
        sha=self.fixture()
        self.out.mkdir()
        marker=self.out/'keep';marker.write_text('preserved')
        with self.assertRaisesRegex(GateError,'OUTPUT_MUST_BE_EMPTY'):
            assemble(self.archive,self.upstream,self.overlay,self.out,expected_sha=sha)
        self.assertEqual(marker.read_text(),'preserved')

    def test_missing_source_archive_fails(self):
        with self.assertRaisesRegex(GateError,'SOURCE_ARCHIVE_MISSING'):
            verify_archive(self.dir/'missing.zip',expected_sha='bad')

    def test_zip_symlink_denied(self):
        self.fixture()
        with zipfile.ZipFile(self.archive,'a') as z:
            i=zipfile.ZipInfo(f'{ROOT}/evil')
            i.external_attr=(0o120777<<16)
            z.writestr(i,'link')
        sha=hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaisesRegex(GateError,'UNSAFE_SOURCE_ZIP'):
            verify_archive(self.archive,expected_sha=sha)

    def test_real_service_single_terminal_response_guard(self):
        """Regression gate: worker success/error and watchdog share one completion latch."""
        source = (Path(__file__).parent/'android/hu/formatlab/android/FormatLabOfficeService.java').read_text()
        self.assertIn('AtomicBoolean completed = new AtomicBoolean(false)', source)
        self.assertEqual(source.count('completed.compareAndSet(false, true)'), 4)
        self.assertIn('if (!completed.compareAndSet(false, true)) return;', source)
        self.assertIn('Process.killProcess(Process.myPid())', source)
        self.assertIn('mainHandler.removeCallbacks(watchdog)', source)

if __name__=='__main__':unittest.main()
