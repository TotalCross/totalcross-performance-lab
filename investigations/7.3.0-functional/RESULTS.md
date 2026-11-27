# Campaign Results

The campaign has executed a partial Android API 36 runtime investigation
(I03), which reproduced a native crash in the official 7.3.0 package. Linux
runtime cases remain unexecuted because the frozen-master build has not yet
completed. The authoritative case and platform statuses are in
`test-matrix.json`.

## Imported historical evidence

- **Windows Win32/I386 ownership:** PASS in TotalCross Actions run
  [45907759163](https://github.com/TotalCross/totalcross/actions/runs/45907759163).
  Historical A, historical B, and corrected source `94af2b8b653cad509994b5ccf3dbb60ac28ef920`
  started on one Windows runner. The corrected I386 runtime passed the existing
  ownership smoke. This was verified during the priority correction and is not
  a campaign execution.
- **Windows AMD64 startup:** PREEXISTING / OUT_OF_SCOPE. No campaign execution.
- JavaSE, macOS ARM64, and Android ARM64 PR #567 claims: import pending source,
  artifact, assertion, and provenance review.

## Campaign execution

- **I03, Android API 36 ARM64 AVD:** FAIL. The exact customer APK and a
  diagnostic build each crashed during denied and grant-in-place permission
  flows with SIGSEGVs in the native Skia/GLES surface-change path. The
  pregranted trace control created and deleted the test directory without a
  crash. Four tombstones were captured. This confirms the reported failure for
  the official 7.3.0 package on this API 36 emulator; it does not establish the
  root cause or corrected-candidate behavior. See
  `reports/I03-android-api36.md` and `evidence/I03/`.

No production source was changed. The remaining I03 APIs and lifecycle
scenarios, frozen-master Linux runtime matrix, and other campaign cases remain
pending.
