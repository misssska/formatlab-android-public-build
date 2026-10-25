# P0b — Real LibreOffice ARM64 configuration qualification

**Status:** Pending GitHub Actions. This work does not compile the LibreOfficeKit engine, package assets, run JNI, or produce a new APK.

## Baselines
- P0a: [PR #3](../../pull/3) (AArch64 Android ELF smoke, not Office).
- P0b branches off P0a, not main; integration requires reviewing/landing P0a first.
- Pinned LibreOffice SHA: `f2820323446ae210668dcb6422ddcd55ce939dc2`.
- Android NDK: `27.2.12479018`. SDK platform 35; build tools 35.0.0.
- Target distro: `LibreOfficeAndroidAarch64`; Linux x86_64 build host.
- Existing v0.3 Android debug APK and P0 quality limitations remain unchanged.

## What the CI actually does
1. Eight local deterministic tests for resource/failure/opt-in pathways.
2. Installs minimal build-host configure dependencies, Android SDK 35 and exact Android NDK 27.2.
3. Fetches and checks out the complete exact upstream source revision in an ephemeral GitHub runner directory (no source edits committed).
4. Checks available free disk (8 GiB before configuring), pin, host toolchain and SDK.
5. Opts into writing `autogen.input` **only in the disposable checkout**, invokes `./autogen.sh` with 600-second timeout, records blocked/missing requirements.
6. Marks the workflow as failed if the configure step did not complete successfully. The report deliberately records that no engine/APK was built.

Commands to reproduce on a sufficiently provisioned disposable Linux / WSL2 build host:

```bash
# In the FormatLab repository:
python3 -m unittest discover -s native/office -p 'test_configure_probe.py' -v
export FORMATLAB_DISPOSABLE_CHECKOUT=YES
python3 native/office/configure_probe.py /tmp/formatlab-lo-p0b \
  --sdk "${ANDROID_SDK_ROOT}" \
  --ndk "${ANDROID_SDK_ROOT}/ndk/27.2.12479018" \
  --report /tmp/formatlab-p0b-report.json
```

## Important safety and fidelity limitations
- **No compiled LibreOfficeKit** in this milestone, even if `autogen.sh` exits zero.
- **No Android conversion** and no proof of DOCX/PDF formatting fidelity.
- The reference document and private user files are not part of this repository/CI.
- No changes to working Android APK, end-user permissions, monetization, or Office conversion output.
- If configuration fails, treat the exact missing dependencies as next engineering blockers; do not bypass gating by marking known errors PASS.
- Full LO native build should be attempted on a host with adequate disk/RAM using pinned upstream instructions and licensing checks.
