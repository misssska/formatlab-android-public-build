"""P0g assembly contract tests: synthetic references only, no actual Office build."""
from __future__ import annotations
import hashlib,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch

from compose_native_office import (compose,qualify_bundle,verified_upstream,elf_gnu_build_id,
                                   SOURCE_SHA,REQUIRED_ASSETS,REQUIRED_LICENSES)
from offline_apk_gate import REQUIRED_NATIVE_LIBS
from assemble_runtime_overlay import ROOT,PINNED_KIT,SOURCE_UPSTREAM,GateError

ELF=b'\x7fELF\x02\x01'+bytes(10)+(3).to_bytes(2,'little')+(183).to_bytes(2,'little')+bytes(44)

def elf_with_build_id(build_id:bytes, marker:bytes)->bytes:
    """ELF64 ARM PT_NOTE fixture with stable linker identity but different body."""
    header=bytearray(64)
    header[:6]=b'\x7fELF\x02\x01'
    header[16:18]=(3).to_bytes(2,'little')
    header[18:20]=(183).to_bytes(2,'little')
    header[32:40]=(64).to_bytes(8,'little')
    header[54:56]=(56).to_bytes(2,'little')
    header[56:58]=(1).to_bytes(2,'little')
    android_note=(8).to_bytes(4,'little')+(132).to_bytes(4,'little')+(1).to_bytes(4,'little')+b'Android\x00'+bytes(132)
    gnu_note=(4).to_bytes(4,'little')+len(build_id).to_bytes(4,'little')+(3).to_bytes(4,'little')+b'GNU\x00'+build_id
    note=android_note+gnu_note
    ph=bytearray(56)
    ph[0:4]=(4).to_bytes(4,'little')
    ph[8:16]=(120).to_bytes(8,'little')
    ph[32:40]=len(note).to_bytes(8,'little')
    return bytes(header+ph)+note+marker*8192

class NativePackageComposerTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory(prefix='formatlab-p0g-')
        self.addCleanup(td.cleanup)
        self.root=Path(td.name)
        self.apk=self.root/'reference.apk'
        self.libs=self.root/'libs';self.libs.mkdir()
        self.evidence=self.root/'evidence.json'
        self.upstream=self.root/'source'
        self.overlay=self.root/'overlay';self.overlay.mkdir()
        self.zip=self.root/'v03.zip'
        self.destination=self.root/'composed'
        for name in PINNED_KIT:
            f=self.upstream/SOURCE_UPSTREAM/name
            f.parent.mkdir(parents=True,exist_ok=True)
            if name=='LibreOfficeKit.java':
                f.write_text(
                    'package org.libreoffice.kit; import android.app.Activity; '
                    'class LibreOfficeKit { void init(Activity activity) { '
                    'activity.getApplication().getCacheDir(); '
                    'activity.getApplication().getPackageResourcePath(); } }')
            else:
                f.write_text('package org.libreoffice.kit; class '+name[:-5]+' {}')
        for name in ('FormatLabOfflineOfficeConverter.java',
                     'FormatLabOfficeService.java','FormatLabOfficeProcessClient.java'):
            (self.overlay/name).write_text(
                'package hu.formatlab.android; class '+name[:-5]+' {}')
        with zipfile.ZipFile(self.zip,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr(ROOT+'/app/build.gradle','plugins {}')
            z.writestr(ROOT+'/app/src/main/java/hu/formatlab/android/MainActivity.java',
                       'package hu.formatlab.android; public class MainActivity {}')
            z.writestr(ROOT+'/app/src/main/AndroidManifest.xml',
                       '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                       'package="hu.formatlab.android"><application></application></manifest>')
        self.source_sha=hashlib.sha256(self.zip.read_bytes()).hexdigest()
        self.assets={n:b'fixture' for n in REQUIRED_ASSETS}
        self.assets['assets/unpack/user/fonts/LiberationSans-Regular.ttf']=b'font'
        self.assets['assets/unpack/etc/fonts/fonts.conf']=(
            b'<fontconfig><cachedir>/data/data/org.libreoffice.android/fontconfig</cachedir></fontconfig>'
        )
        for n in REQUIRED_LICENSES:self.assets[n]=b'MPL licensing fixture'
        self.native={}
        for n in REQUIRED_NATIVE_LIBS:
            file=ELF+bytes(1_100_000 if n.endswith('/liblo-native-code.so') else 8192)
            self.native[n]=file
            (self.libs/Path(n).name).write_bytes(file)
        self.write_apk()
        engine_hash=hashlib.sha256(self.native['lib/arm64-v8a/liblo-native-code.so']).hexdigest()
        self.evidence.write_text(json.dumps({'status':'NATIVE_BUILD_ATTESTED',
            'engine_compiled':True,'pinned_source_commit':SOURCE_SHA,
            'engine':{'status':'PASS','sha256':engine_hash}}))

    def write_apk(self):
        with zipfile.ZipFile(self.apk,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr('AndroidManifest.xml',b'fixture')
            for name,payload in {**self.assets,**self.native}.items():
                z.writestr(name,payload)

    def test_complete_provenance_source_composition(self):
        r=compose(self.zip,self.upstream,self.overlay,self.apk,self.libs,self.evidence,
                  self.destination,expected_source_sha=self.source_sha)
        self.assertEqual(r['status'],'NATIVE_OFFICE_SOURCE_COMPOSED_NOT_RELEASED')
        self.assertTrue(r['native_lib_bundled'])
        self.assertFalse(r['android_apk_built'])
        self.assertFalse(r['public_release_approved'])
        self.assertEqual(r['verified_library_count'],len(REQUIRED_NATIVE_LIBS))
        self.assertIn('hu.formatlab.android/fontconfig',
                      (self.destination/'app/src/main/assets/unpack/etc/fonts/fonts.conf').read_text())

    def test_matching_build_id_accepts_stripped_native_pair(self):
        name='lib/arm64-v8a/libnss3.so'
        ident=bytes(range(20))
        staged=elf_with_build_id(ident,b'X')
        packaged=elf_with_build_id(ident,b'Y')
        self.assertNotEqual(hashlib.sha256(staged).digest(),hashlib.sha256(packaged).digest())
        self.assertEqual(elf_gnu_build_id(io.BytesIO(staged)), ident.hex())
        self.native[name]=packaged
        (self.libs/'libnss3.so').write_bytes(staged)
        self.write_apk()
        qualified=qualify_bundle(self.apk,self.libs,self.evidence)
        self.assertEqual(qualified['libs']['libnss3.so']['comparison'],
                         'MATCHING_GNU_BUILD_ID_AFTER_STRIP')

    def test_mismatching_build_id_blocks_stripped_native_pair(self):
        name='lib/arm64-v8a/libnss3.so'
        self.native[name]=elf_with_build_id(bytes(range(20)),b'Y')
        (self.libs/'libnss3.so').write_bytes(elf_with_build_id(bytes(reversed(range(20))),b'X'))
        self.write_apk()
        with self.assertRaisesRegex(GateError,'NATIVE_REFERENCE_MISMATCH:libnss3.so'):
            qualify_bundle(self.apk,self.libs,self.evidence)

    def test_library_mismatch_blocks(self):
        (self.libs/'libnss3.so').write_bytes(ELF+bytes(8192)+b'altered')
        with self.assertRaisesRegex(GateError,'NATIVE_REFERENCE_MISMATCH'):
            qualify_bundle(self.apk,self.libs,self.evidence)

    def test_missing_native_lib_blocks(self):
        (self.libs/'libnss3.so').unlink()
        with self.assertRaisesRegex(GateError,'NATIVE_BUNDLE_LIBRARY_MISSING'):
            qualify_bundle(self.apk,self.libs,self.evidence)

    def test_wrong_source_commit_blocks(self):
        data=json.loads(self.evidence.read_text())
        data['pinned_source_commit']='a'*40
        self.evidence.write_text(json.dumps(data))
        with self.assertRaisesRegex(GateError,'NATIVE_ATTESTATION_NOT_ACCEPTED'):
            qualify_bundle(self.apk,self.libs,self.evidence)

    def test_native_build_not_complete_blocks(self):
        data=json.loads(self.evidence.read_text())
        data['status']='BUILD_TIMEOUT'
        self.evidence.write_text(json.dumps(data))
        with self.assertRaisesRegex(GateError,'NATIVE_ATTESTATION_NOT_ACCEPTED'):
            qualify_bundle(self.apk,self.libs,self.evidence)

    def test_missing_upstream_assets_denied(self):
        del self.assets['assets/program/fundamentalrc']
        self.write_apk()
        with self.assertRaisesRegex(GateError,'UPSTREAM_RUNTIME_PARTS_MISSING'):
            verified_upstream(self.apk)

    def test_fontconfig_source_path_unverifiable_fails_cleanup(self):
        self.assets['assets/unpack/etc/fonts/fonts.conf']=b'<fontconfig><cachedir>unknown</cachedir></fontconfig>'
        self.write_apk()
        with self.assertRaisesRegex(GateError,'FONTCONFIG_APPLICATION_ID_UNVERIFIED'):
            compose(self.zip,self.upstream,self.overlay,self.apk,self.libs,self.evidence,
                    self.destination,expected_source_sha=self.source_sha)
        self.assertFalse(self.destination.exists())

    def test_source_zip_hash_mismatch_denied(self):
        with self.assertRaisesRegex(GateError,'SOURCE_SHA256_MISMATCH'):
            compose(self.zip,self.upstream,self.overlay,self.apk,self.libs,self.evidence,
                    self.destination)

    def test_existing_destination_is_preserved(self):
        self.destination.mkdir()
        marker=self.destination/'KEEP'
        marker.write_text('untouched')
        with self.assertRaisesRegex(GateError,'DESTINATION_MUST_NOT_EXIST'):
            compose(self.zip,self.upstream,self.overlay,self.apk,self.libs,self.evidence,
                    self.destination,expected_source_sha=self.source_sha)
        self.assertEqual(marker.read_text(),'untouched')

    def test_wrong_abi_reference_denied(self):
        n='lib/arm64-v8a/libnss3.so'
        self.native[n]=b'\x7fELF\x02\x01'+bytes(10)+(3).to_bytes(2,'little')+(62).to_bytes(2,'little')+bytes(8192)
        self.write_apk()
        with self.assertRaisesRegex(GateError,'UPSTREAM_NATIVE_ABI_INVALID'):
            verified_upstream(self.apk)

    def test_traversal_zip_reference_denied(self):
        with zipfile.ZipFile(self.apk,'a') as z:z.writestr('../escape',b'bad')
        with self.assertRaisesRegex(GateError,'UNSAFE_UPSTREAM_APK'):
            verified_upstream(self.apk)

if __name__=='__main__':unittest.main()
