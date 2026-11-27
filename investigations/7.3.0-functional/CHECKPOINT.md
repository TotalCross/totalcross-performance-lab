# Campaign Checkpoint

## Current state

- Branch: `investigation/totalcross-7.3.0-functional-validation`
- Base and initial HEAD: `fe23e009fa2fcdbf8c36746cea58b9946a138858`
- Active milestone: 1 — Linux startup and PNG blockers
- Last completed campaign commit: `0294d6f` (runner and harness)
- Previous evidence checkpoint: `42008b9`
- Production source edits: none

## Frozen references

- TotalCross master at campaign snapshot: `6b915883dd202f6db891990f6c3af26fb645ecc7`
- Ownership implementation: `94af2b8b653cad509994b5ccf3dbb60ac28ef920`
- Ownership PR head: `926e964841ac64dca172a648bce1ffcc6d60d153` (open)
- Windows I386 historical validation: Actions run `45907759163` (PASS)
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
- Confirmed the accepted Win32/I386 run completed successfully and checked its
  job and artifact metadata.
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
- Confirmed local ARM64 AVD acceleration and API 34/36/37 images; API 29/30/35
  images are not currently installed.
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

## Pending investigations

I01-B, I02, I03, I04/I05, I06 Linux, I07, I08, I09, I10, I11, remaining
provenance, case reports, proposed issue updates, and final consolidation.

## Next concrete action

Push the dedicated branch to trigger
`.github/workflows/functional-validation-730.yml`. Review its compact result
artifact, record the exact run and binary identities,
then update I01-B/I02 reports and the matrix. The archived 7.3.0 artifact is
verified and unexpired as of 2026-11-27; current campaign runtime cases have not
run yet.

## Constraints and blockers

- No Windows AMD64 execution or analysis; record it PREEXISTING / OUT_OF_SCOPE.
- No local native Windows, Linux, or macOS execution. Use hosted Actions.
- Android native tests only on local hardware-accelerated ARM64 emulators.
- No production changes, benchmarks, iOS, Android Actions, release or
  publication side effects, or PR creation.
- Current root TotalCross checkout is unrelated and must remain untouched.
