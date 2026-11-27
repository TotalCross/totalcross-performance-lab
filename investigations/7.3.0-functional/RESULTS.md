# Campaign Results

The campaign remains in progress. I01-B and I02 Linux runtime evidence from
hosted Actions run 45949849457 is consolidated in the reports, result matrix,
and provenance record. I03 priority API runs are recorded for Android API 29,
30, 35, and 36; API 30 lifecycle follow-ups are also recorded. I04 is
inconclusive on API 30. I05 recorded one destroyed-mutex abort during shutdown
in ten clean file-I/O cycles; the native stack and mutex owner remain unknown.
I08 completed its official/candidate filesystem matrix on Android API 29, 30,
35, and 36, including a separate foreign-file permission control.

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

## Completed campaign image validation

- **I06 persistent image ownership:** PASS for the production Windows
  Win32/I386 target. Linux x86_64 baseline and corrected ownership probes also
  completed all seven stages: the baseline recorded 6,046 mismatches and the
  corrected candidate recorded zero. Linux used the test-only realpath shim
  because the unmodified runtime aborts before application startup. A bundled
  red JPEG control replaced the tiny PNG after both Linux probes failed in the
  decoder at native drawing. The Linux result is conditional; normal Linux
  startup and the PNG decoder failure remain separately tracked. See the
  [Linux report](reports/I06-linux-ownership.md).
- **I07 `Image(String)` fallback:** PASS on Windows Win32/I386, Linux x86_64,
  macOS ARM64, and Android API 36 ARM64. All four platforms reported 16 cases
  and zero failures. Linux used the realpath shim and skipped its inaccessible
  device path; macOS skipped its read-only device path. Windows and Android
  had no skips. The Android activity exit code is unavailable from the local
  runner, but its completion marker and no-crash state were observed. See the
  [I07 report](reports/I07-image-string-fallback.md).

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
- **I05, Android API 30 ARM64:** FAIL under one of ten clean file-I/O shutdown
  cycles with `FORTIFY: pthread_mutex_lock called on a destroyed mutex`, then
  SIGABRT on `Thread-2`. Ten normal-exit and ten SQLite-shutdown controls, one
  foreground active-worker exit, and one exit after a successful storage
  permission grant completed without the same abort. The exact mutex owner and
  failure stack were not captured. The report proposes an update to existing
  issue #432; no remote issue was edited.
- **I06 Linux x86_64:** Conditional ownership validation completed in hosted
  run 45989644203. The unmodified startup abort remains INCOMPLETE under
  I01-B; the shimmed baseline and candidate assertions passed as recorded in
  [the Linux I06 record](evidence/I06/linux-x86_64-45989644203.json).
- **I07 hosted platforms:** Windows I386, Linux x86_64, and macOS ARM64 all
  completed in hosted run 45989644203. Their full case results, artifacts, and
  compact markers are under `evidence/I07/`. The local API 36 Android record is
  [here](evidence/I07/android-api36-arm64.json).
- **I08, Android API 29/30/35/36 ARM64:** PASS for filesystem CRUD on private,
  app-specific external, and app-created shared paths for official 7.3.0 and
  candidate 94af. The separate host-seeded foreign file passed after candidate
  API 29 permission grant; API 30 requested READ only, while APIs 35/36 denied
  foreign access without a legacy prompt. App-created shared-path success is
  not treated as foreign-file authorization. See the
  [I08 report](reports/I08-android-storage.md) and
  [machine evidence](evidence/I08/android-storage-matrix.json).
- **I01-B, Linux x86_64:** official 7.3.0 and frozen master failed before
  startup on all four tested path forms, including short paths. Official 7.2.2
  is inconclusive as a realpath control: three cases failed in dynamic loading;
  its long path failed in the launcher. Root cause remains open.
- **I02, Linux x86_64:** frozen master aborted before the unmodified probe.
  With the test-only startup shim, 8/9 cases passed; a valid indexed PNG was
  rejected during construction. Other platforms remain untested.

No production source was changed. I03 repeated requests and corrected-candidate
validation remain explicitly unrun. I09/I10, I11, remaining provenance, and the
final report remain pending.
