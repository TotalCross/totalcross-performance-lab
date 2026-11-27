<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# TotalCross 7.3.0 Functional Validation — Final Report

## Campaign result

The functional validation campaign is complete within its authorized scope.
No production source was changed. Tests ran only on Windows Win32/I386,
Linux x86_64, macOS ARM64, and local hardware-accelerated Android ARM64
emulators. Windows AMD64 was not tested or analyzed further.

**The persistent image ownership correction is functionally validated on the
production Windows Win32/I386 target.** Corrected source
`94af2b8b653cad509994b5ccf3dbb60ac28ef920` passed the minimal native startup
gate and the existing ownership smoke against the same I386 runtime in hosted
run [45907759163](https://github.com/TotalCross/totalcross/actions/runs/45907759163).
The smoke completed two screens of 1,510 controls, released all owners after
ancestor detach, passed reattachment, reparenting, sharing, replacement, raster
cache, and native pixel checks, and exited with code 0. All tested TotalCross
PE files were I386 (`0x014c`). The AMD64 crash remains a separate preexisting,
out-of-scope issue.

## Investigation outcomes

| Investigation | Outcome | Main limitation |
| --- | --- | --- |
| I01-B Linux startup | INCOMPLETE | 7.3.0 and frozen master abort before application startup; 7.2.2 is an inconclusive control. |
| I02 Linux PNG | INCOMPLETE | 8/9 shimmed cases passed; indexed PNG rejected during construction. |
| I03 Android lifecycle | FAIL / NOT_REPRODUCED | Native crashes on APIs 30/35/36; API 29 Allow left write permission denied; no corrected candidate run. |
| I04 Android file write | INCONCLUSIVE | Denied Settings return and overlap inside native `fwrite` not established. |
| I05 Android shutdown | FAIL | One destroyed-mutex abort in ten file-I/O exits; owner and native stack unknown. |
| I06 persistent ownership | PASS | Windows Win32/I386 PASS; Linux assertions pass only with test-only startup shim and JPEG control. |
| I07 image fallback | PASS | All 16 cases passed per platform; Linux/macOS retained the documented device-path skips. |
| I08 Android storage | PASS | APIs 29/30/35/36 passed tested private, app-specific external, and app-created shared cases. |
| I09 Android SQLite permissions | PASS | API matrix passed; public wrapper limits primary/extended SQLite result codes. |
| I10 SQLite compatibility | INCOMPLETE | No customer database; 7.2.2 Linux/macOS unavailable for SQLite execution. |
| I11 release workflow | PARTIAL | Static review and package evidence passed; release workflow dry-run and Win32/I386-specific release packaging were not verified. |

The machine-readable statuses and per-platform results are in
[`test-matrix.json`](../test-matrix.json). Reports retain exact case details,
fixtures, limitations, and evidence references.

## Release and external actions

I11 verified version consistency, versioned notes, package inventory, Linux and
macOS packaged-ZIP checks, publication guards, and point-in-time public
availability. PR #538 and #539 remain draft; #539 is conflicting. The release
workflow itself was not dispatched. This campaign created no tag, GitHub
Release, Maven publication, Artifactory upload, or S3 upload. The report
[`I11-release-workflow.md`](I11-release-workflow.md) records the dry-run
limitations and exact evidence.

No GitHub issue or product PR was created or edited. Proposed issue updates are
drafts under `proposed-issues/`. The campaign branch contains only the
functional fixtures, diagnostics, reports, and evidence authorized for this
work.

## Remaining product limitations

- Linux x86_64 ownership results require the test-only `realpath` shim; normal
  Linux startup remains blocked before application code.
- Linux PNG behavior has an unresolved indexed-PNG rejection.
- Android I03 repeated permission requests and corrected-candidate validation
  were not run because the initial denied transition already reproduces the
  crash and no corrected candidate was available.
- I04's denied-return behavior and native write overlap remain inconclusive.
- I05's intermittent destroyed-mutex abort lacks a native stack.
- I10 uses synthetic SQLite data. The customer database was not supplied.
- I11 did not run a release-workflow dry-run or establish Win32/I386 packaging
  specifically for the release PR.
- PR #567's JavaSE, macOS ARM64, and Android ARM64 historical smoke claims lack
  recoverable linked run/artifact IDs; those claims are not treated as
  independently verified historical evidence.

These are recorded limitations, not untracked work. Windows AMD64 remains
outside the campaign and is not a gate for the production Win32/I386 ownership
result.
