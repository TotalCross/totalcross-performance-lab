# Campaign Results

The campaign remains in progress. I01-B and I02 Linux runtime evidence from
hosted Actions run 45949849457 is consolidated in the reports, result matrix,
and provenance record. I03 priority API runs are recorded for Android API 29,
30, 35, and 36; API 30 lifecycle follow-ups are also recorded. I04 is now
inconclusive on API 30; I05 shutdown findings remain pending.

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
- **I03 API 30 lifecycle follow-up:** Rotating while the all-files Settings
  page was open and returning without changing authorization reproduced the
  common Skia/GLES SIGSEGV. A separate pregranted customer-app control survived
  background/foreground and 90-degree rotation; a diagnostic worker-screen
  variant crashed on foreground surface reinitialization. Repeated permission
  requests remain NOT_RUN because the first denied transition already crashes
  and no corrected candidate is available.
- **I04, Android API 30 ARM64:** INCONCLUSIVE. Normal app-private writes,
  invalid-mode exceptions, failed-open handling, granted external writes, and
  ten barrier-released 8 MiB write/close pairs completed without the reported
  `fwrite` abort. The denied Settings return did not complete, and the race
  probe did not observe overlap inside `fwrite`. A separate I05 shutdown probe
  aborted during file I/O, but its missing native stack does not identify
  `File.writeBytes` as the call site.
- **I06 Windows Win32/I386:** PASS for the Windows target; overall I06 remains
  pending its required Linux x86_64 validation.
- **I01-B, Linux x86_64:** official 7.3.0 and frozen master failed before
  startup on all four tested path forms, including short paths. Official 7.2.2
  is inconclusive as a realpath control: three cases failed in dynamic loading;
  its long path failed in the launcher. Root cause remains open.
- **I02, Linux x86_64:** frozen master aborted before the unmodified probe.
  With the test-only startup shim, 8/9 cases passed; a valid indexed PNG was
  rejected during construction. Other platforms remain untested.

No production source was changed. I03 repeated requests and corrected-candidate
validation remain explicitly unrun; I05 is the next Android investigation.
I06/I07, I08/I09/I10, I11, remaining provenance, and the final report remain
pending.
