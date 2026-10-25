# FormatLab P0g — verified offline native Office source integration

This is a fail-closed bridge between the original Android v0.3 app and the real LibreOffice ARM64 native engine. The composer produces a source tree, not an approved APK.

## Required authoritative inputs

- P0c evidence with status NATIVE_BUILD_ATTESTED, engine_compiled=true and pinned upstream commit f2820323446ae210668dcb6422dd55ce939dc2.
- All 14 ARM64 native shared libraries from the accepted P0c build.
- Actual upstream LibreOffice Android reference APK built from that same revision, with fonts, registry, bootstrap and license resources.
- The exact FormatLab v0.3 source ZIP pinned to SHA256 04694a0afbc26ebcbe7dd0c4c265d656acc05497d6d5765980c22e4366c0123b.
- Pinned LibreOfficeKit Java API, already verified by P0f.

## Integration and security

The composer compares all native library hashes against the upstream reference APK, checks their ELF64 AArch64 format and verifies the main engine hash against signed-off P0c evidence. It rejects missing files, malicious ZIP entries, giant archives, path traversals, source overlays, and pre-existing outputs. It verifies bootstrap, registry, fonts, notices and licenses.

The upstream fontconfig cache path is remapped only if the exact expected upstream application ID path is recognized. The new path is /data/data/hu.formatlab.android/fontconfig; an unresolved placeholder or unknown configuration is rejected.

## Manual staging command after P0c succeeds

```bash
python3 native/office/compose_native_office.py \
  --source-zip FormatLab-Android-v0.3-offline-source.zip \
  --upstream-tree /path/to/pinned-libreoffice-source \
  --java-overlay native/office/android/hu/formatlab/android \
  --reference-apk /path/to/upstream-libreoffice-reference.apk \
  --native-libs /path/to/p0c/native-libs \
  --evidence /path/to/p0c/build-evidence.json \
  --destination /path/to/disposable/formatlab-office-source
```

Once all real inputs exist, build that Android project with Gradle 8.10.2, Java 17, SDK 35; then run the P0d offline_apk_gate.py against the actual resulting FormatLab APK. A static PASS is still not functional JNI proof. Validate actual offline DOCX-to-PDF, five P0e golden documents, airplane-mode performance and safe process isolation on a real ARM64 phone. Do not publish an APK until all gates and licensing checks pass.

No private documents, native binaries or signing keys are committed to this public repo. The existing v0.3 release and main remain unchanged.
