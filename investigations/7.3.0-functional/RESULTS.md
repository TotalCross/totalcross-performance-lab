# Campaign Results

The campaign remains in progress. Linux runtime execution has completed in
hosted Actions run 45949849457, but the I01-B and I02 reports and result matrix
still need consolidation from the result artifact. I03 priority API runs are
now recorded for Android API 29, 30, 35, and 36.

## Imported historical evidence

- **Windows Win32/I386 ownership:** PASS in TotalCross Actions run
  [45907759163](https://github.com/TotalCross/totalcross/actions/runs/45907759163).
  Historical A, historical B, and corrected source
  `94af2b8b653cad509994b5ccf3dbb60ac28ef920` started on the same
  `windows-2022` runner. The corrected runtime passed the minimal startup gate
  and the existing ownership smoke against the identical I386 runtime. The
  Actions result artifact digest was verified and compact evidence is retained
  in [the Windows report](reports/I06-windows-win32-ownership.md). This is
  reused hosted evidence, not a duplicate campaign execution. The production
  Windows Win32/I386 correction is functionally validated.
- **Windows AMD64 startup:** PREEXISTING / OUT_OF_SCOPE. No campaign execution.
- JavaSE, macOS ARM64, and Android ARM64 PR #567 claims: imported evidence
  verification remains pending.

## Campaign execution

- **I03, Android API 30, 35, and 36 ARM64 AVDs:** FAIL. The exact customer APK
  and trace build together produced four SIGSEGVs per API across denied and
  grant-in-place permission flows. Pregranted controls remained alive; the
  trace grant-in-place case created and deleted `/sdcard/asd` before crashing.
  The stack is in the Skia/GLES surface-change path; root cause remains open.
- **I03, Android API 29 ARM64 AVD:** Native crash NOT_REPRODUCED in the tested
  denied, grant-in-place, and pregranted flows. The interactive Allow action
  left `WRITE_EXTERNAL_STORAGE` denied and the directory operation failed;
  the explicitly pregranted control succeeded. The permission result is
  tracked separately under I08.
- **I06 Windows Win32/I386:** PASS for the Windows target; overall I06 remains
  pending its required Linux x86_64 validation.
- **I01-B/I02, Linux x86_64:** hosted run 45949849457 completed both jobs and
  uploaded the campaign result artifact. Findings and reports are pending
  result-artifact consolidation.

No production source was changed. I03's corrected candidate, remaining
permission lifecycle scenarios, Linux report consolidation, I04/I05, I06/I07,
I08/I09/I10, I11, provenance completion, and final report remain pending.
