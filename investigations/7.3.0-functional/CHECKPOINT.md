# Campaign Checkpoint

## Current state

- Branch: `investigation/totalcross-7.3.0-functional-validation`
- Campaign branch tip before the Windows evidence update:
  `fccadcb5897b0c8aa0a0d8c033002e51bcdefef2`
- Base and initial HEAD: `fe23e009fa2fcdbf8c36746cea58b9946a138858`
- Active milestone: 2 — Android native failures
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

## Pending investigations

Additional I03 lifecycle scenarios and corrected-candidate validation; I04/I05,
I06 Linux, I07, I08, I09, I10, I11; remaining provenance; proposed issue
updates; and final consolidation.

## Next concrete action

Windows Win32/I386 priority validation is complete using verified run
`45907759163`; do not repeat it while inputs remain unchanged. Linux I01-B/I02
reports and matrix are consolidated from hosted run `45949849457`. Continue
with the remaining I03 Android lifecycle diagnostics and corrected-candidate
validation on the already provisioned hardware-accelerated ARM64 AVDs, then
execute the in-scope I04/I05 scenarios. Linux evidence is at
`https://github.com/TotalCross/totalcross-performance-lab/actions/runs/45949849457`.

## Constraints and blockers

- No Windows AMD64 execution or analysis; record it PREEXISTING / OUT_OF_SCOPE.
- No local native Windows, Linux, or macOS execution. Use hosted Actions.
- Android native tests only on local hardware-accelerated ARM64 emulators.
- No production changes, benchmarks, iOS, Android Actions, release or
  publication side effects, or PR creation.
- Current root TotalCross checkout is unrelated and must remain untouched.
