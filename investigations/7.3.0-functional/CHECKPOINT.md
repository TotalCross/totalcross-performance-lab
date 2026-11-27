# Campaign Checkpoint

## Current state

- Branch: `investigation/totalcross-7.3.0-functional-validation`
- Last completed platform checkpoint: I08 passed on Android API 29/30/35/36
  ARM64 for official 7.3.0 and candidate 94af. I07 passed on Windows I386,
  Linux x86_64 conditionally, macOS ARM64, and Android API 36 ARM64. I06 passed
  on Windows I386 and completed its Linux ownership assertions conditionally.
- Shared Android probe source SHA-256:
  `c65d09b87873db63016ba3a209ac453f49a1cf038c0dbdd88a34bb36581f172b`.
- Base and initial HEAD: `fe23e009fa2fcdbf8c36746cea58b9946a138858`
- Active milestone: 4 — Filesystem and SQLite
- Previous campaign checkpoint: `1a602fa` (native build retry findings)
- Previous evidence checkpoint: `42008b9`
- Production source edits: none

## Frozen references

- TotalCross master at campaign snapshot: `6b915883dd202f6db891990f6c3af26fb645ecc7`
- Ownership implementation: `94af2b8b653cad509994b5ccf3dbb60ac28ef920`
- Ownership PR head: `926e964841ac64dca172a648bce1ffcc6d60d153` (open)
- Windows I386 priority validation: Actions run `45907759163` (startup and
  same-runtime ownership smoke PASS)
- Performance-lab `main` base: `fe23e009fa2fcdbf8c36746cea58b9946a138858`

PR verification found that #545 is merged into an intermediate feature branch,
#565 is stacked on #545, and #538/#539 remain open and stacked. Their current
presence in `master` is not established by those merge flags. GitHub commit
comparison shows #545 and #565 diverge from frozen master at merge base
`61034a7562e7fa43df076dcc38bcd48128605395`; their changed-file sets include
the permission and Image(String) implementation files. GitHub lists a 7.2.2
release, but no 7.3.0 release/tag. The 7.3.0 CI package is pinned by its
workflow artifact and nested package hashes. PR #567's SDK tree is byte-for-byte
equivalent to source commit `94af2b8b653cad509994b5ccf3dbb60ac28ef920`.

## Completed

- Read the campaign request and its priority correction.
- Reverified Actions run `45907759163` against the Win32/I386 priority
  correction. Exact corrected source `94af2b8b653cad509994b5ccf3dbb60ac28ef920`
  built with the production Win32/Release Skia/SDL configuration. The minimal
  probe passed all six markers; the existing ownership smoke then passed all
  seven stages on the same I386 runtime, with two 1,510-control screens,
  `ownersAfterDetach=0`, zero ownership mismatches, and pixel `0xff0000`.
  Historical I386 A/B and corrected I386 were compared on the same
  `windows-2022` runner. The 26,769,105-byte result artifact SHA-256 was
  verified; compact identities and assertions are in
  `evidence/I06/windows-win32-45907759163.json`. No duplicate Windows run or
  AMD64 analysis was needed.
- Created a clean campaign worktree from the exact current performance-lab
  `main` head after confirming the requested branch was absent locally and
  remotely.
- Confirmed the performance-lab main tree has no existing dedicated functional
  workflow; reuse/extension opportunities still need inspection.
- Verified PR #567's complete `TotalCrossSDK/` tree matches the validated
  implementation commit; GitHub reports #545/#565 on diverged stack branches.
- Imported compact historical I01-B and I02 Linux evidence, verified archive
  digests and PNG/JPEG fixture hashes, and kept historical failures distinct
  from the still-unrun frozen-master campaign.
- Verified the 7.2.2 release package and its SDK/Linux VM hashes, the 7.3.0 CI
  package and its SDK/Linux VM hashes, and the 4.6.0 source boundary for I04
  and I05. Both Android cases remain in scope.
- Confirmed local ARM64 AVD acceleration. API 29/30/35/36 Google APIs images are
  installed and were exercised on the M1 Pro GPU renderer. API 24/31 were not
  provisioned.
- Compared the earlier 61034 Linux build with frozen master and found native
  file, SQLite, image, and Android permission changes. Do not reuse its VM for
  current-master evidence; the focused runner must build exact commit 6b915.
- Added deterministic PNG fixtures, deployed startup and PNG probes, a
  reusable Linux observation harness, and a branch-push-only Actions workflow.
  The workflow runs I01-B against 7.2.2, the archived 7.3.0 CI package, and
  frozen master on Ubuntu 24.04; I02 runs on frozen master with an unmodified
  attempt before any conditional startup shim.
- Validated campaign configuration and harness contracts, compiled both Java
  probes against the official 7.2.2 SDK, and parsed the workflow plus embedded
  shell, Python, and JSON blocks. Actions runtime execution is still pending.
- First hosted run `45942723832` passed SDK packaging, dependency fetch, and
  native-bridge generation, then stopped during CMake configuration. Frozen
  source `6b915` has no depot-tools ref file, so bootstrap followed the moving
  default branch, whose `deps.yml` lacked the zlib-ng release CMake requires.
  Commit `3394d9b` pins depot-tools to
  `0fd3c98727c87a441bc9c8d2c8dd2b731ef0861a`.
- Second hosted run `45943884053` checked out that pinned revision and fetched
  zlib-ng `2.1.6-r3`, but an empty `ZLIB_NG_RELEASE_TAG` override prevented
  CMake from reading the pinned `deps.yml`. Commit `dc76666` now forwards
  release/repository override variables only when nonempty. Neither run
  reached Linux runtime validation.
- I03 now covers the original denied, grant-in-place, and pregranted customer
  flows on API 29, 30, 35, and 36 with the official 7.3.0 package. API 30/35/36
  each produced four Skia/GLES SIGSEGV tombstones; pregranted controls stayed
  alive. API 29 produced no native crash, but interactive Allow left
  `WRITE_EXTERNAL_STORAGE` denied and the directory operation failed; the
  explicit pregrant passed. Source ordering supports a diagnostic hypothesis,
  not a confirmed root cause. Commit `b7bfd90` contains the consolidated report,
  matrix/provenance updates, sanitized stacks/logs, prompt screenshots, and the
  proposed #563 update.
- Hosted run `45944696531` passed SDK packaging, pinned dependency fetch, native
  bridge generation, and CMake configuration, then failed when the canonical
  Docker build could not access Actions' external Git metadata and the frozen
  source archive lacked `build-provenance.json`. The workflow now writes a
  manifest from the pinned commit/tree before entering Docker; the official
  build-identity script accepted this no-Git manifest in a local fixture.
  Hosted run `45949849457` then completed the frozen-master build and runtime
  jobs.
- Hosted Linux run `45949849457` completed I01-B and I02 on the exact frozen
  master build. Official 7.3.0 and frozen master abort on all four path forms;
  the official 7.2.2 control is inconclusive because three paths fail during
  dynamic loading and the long path fails in the launcher. The conditional
  PNG run passed 8/9 cases; indexed PNG is rejected during construction. The
  result and build-bundle artifact digests and payload hashes were verified;
  reports, machine-readable results, provenance, and issue drafts are recorded.
- The verified Windows Win32/I386 priority result remains PASS; AMD64 remains
  outside campaign scope.
- I03 API 30 follow-ups are now recorded: rotation while All files access
  Settings is open reproduces the Skia/GLES SIGSEGV; a separate pregranted
  customer-app background/foreground plus rotation control passed once; a
  diagnostic worker-screen foreground transition crashed in the same surface
  path. Repeated permission requests remain NOT_RUN because no corrected
  candidate exists and the first denied transition already crashes.
- I04 completed its API 30 ARM64 probe. Normal writes, after-close and
  DONT_OPEN exceptions, failed-open handling, pregranted/recovered external
  writes, and ten barrier-released 8 MiB write/close pairs produced no `fwrite`
  abort. The denied Settings return had no completion marker; actual native
  overlap inside `fwrite` was not proven. I04 is INCONCLUSIVE. The I05 probe
  separately observed one destroyed-mutex abort during file-I/O shutdown, but
  there is no stack to attribute it to I04.
- I05 completed its API 30 ARM64 shutdown probes. One of ten clean file-I/O
  shutdown runs emitted a destroyed-mutex FORTIFY SIGABRT; eight follow-up runs
  did not reproduce. Ten normal exit and ten SQLite controls passed; foreground
  active-worker exit and exit after permission grant passed once. Background/
  foreground shutdown was blocked by the I03 EGL crash before the exit control.
  Native stack and mutex owner remain unknown. Proposed update to issue #432 is
  committed as a draft only.
- Hosted run `45978158503` built and paired frozen-master Linux plus corrected
  SDK artifacts. The baseline ownership probe compiled and deployed, then
  aborted before its first application marker with exit 134 and
  `*** buffer overflow detected ***` on Ubuntu 22.04/glibc 2.35. Its VM and
  launcher hashes match the I01-B build whose captured stack is
  `__realpath_chk -> startVM -> executeProgram -> main`. This remains the
  unmodified Linux startup blocker under I01-B. The bundle and initial result
  are indexed in
  `evidence/I06/linux-x86_64-45978158503.json`.
- Added the I07 `Image(String)` probe, cross-platform prepare/run harness, and
  branch-push workflow. It reuses the verified Windows I386 artifacts, the
  Linux frozen-master bundle, and the exact prepared dependency/bridge artifacts
  for the canonical macOS ARM64 build. Hosted run `45989644203` passed the
  Windows I386 and macOS ARM64 jobs and completed Linux I06/I07 conditionally.
- The Linux ownership run completed all seven stages for both SDKs after using
  the test-only realpath shim. The baseline recorded 6,046 ownership
  mismatches; corrected source `94af2b8` recorded zero and passed all
  assertions. Both original PNG draw controls failed in the Linux decoder, so
  the Linux ownership smoke used a bundled red JPEG and validated the native
  render pixel. Evidence is in `evidence/I06/linux-x86_64-45989644203.json`.
- I07 passed all 16 cases on Windows I386, Linux x86_64, macOS ARM64, and
  Android API 36 ARM64. Windows and Android had no skips. Linux used the
  conditional realpath shim and skipped only its inaccessible device path;
  macOS skipped only its read-only device path. The Android API 36 host-GPU run
  identifies the Apple M1 Pro. Full results and compact markers are committed
  under `evidence/I07/`.
- I08 passed all nine filesystem operations on private, app-specific external,
  and app-created shared storage for official 7.3.0 and candidate 94af on API
  29/30/35/36. A host-seeded foreign-file control confirmed candidate API 29
  denial followed by successful permission-granted retry; API 30 requested
  READ only, and APIs 35/36 denied foreign access without a legacy prompt. The
  manifest does not declare MANAGE_EXTERNAL_STORAGE. Results and compact logs
  are in `reports/I08-android-storage.md` and `evidence/I08/`.
- Built the candidate Android release AAB and ran I07 on the hardware-accelerated
  API 36 ARM64 emulator. All 16 reported cases passed, with zero failures,
  skips, or native crashes. The host GPU log identifies the Apple M1 Pro. The
  AAB, deployed APK, SDK jar, runtime library, fixture, and marker-log identities
  are recorded in `evidence/I07/android-api36-arm64.json` and its evidence files.
- Android setup first required the pinned depot-tools bootstrap and generated
  native bridge sources in the isolated exact-source archive. The first probe
  run found a fixture mismatch at the 255-character TCZ boundary; the payload
  was corrected before the recorded passing run.

## Pending investigations

PR #567 historical JavaSE/macOS/Android ownership evidence verification,
I09, I10, I11, remaining provenance, proposed issue updates, and final
consolidation. I03 repeated requests and corrected-candidate validation remain
explicitly unrun because no candidate is available and the first denied
transition already reproduces the crash.

## Next concrete action

Begin I09 with the exact official and candidate Android ARM64 runtimes: cover
private persistence, shared-path permission denial/grant/re-denial, SQLite
error codes, read-only and corrupt controls, and `integrity_check`. I08 is
complete; Linux I06 remains explicitly conditional on the test-only startup
shim. Do not run Windows AMD64.

## Constraints and blockers

- No Windows AMD64 execution or analysis; record it PREEXISTING / OUT_OF_SCOPE.
- No local native Windows, Linux, or macOS execution. Use hosted Actions.
- Android native tests only on local hardware-accelerated ARM64 emulators.
- No production changes, benchmarks, iOS, Android Actions, releases, or PR
  creation. The priority correction authorizes only the narrow diagnostic
  workflow and fixture push to the existing campaign branch.
- Current root TotalCross checkout is unrelated and must remain untouched.
