# Campaign Decisions

## D1 — Exclude Windows AMD64 startup

**Decision:** Record the existing AMD64 startup crash as `PREEXISTING`,
`OUT_OF_SCOPE`, historical evidence only. Do not reproduce it, bisect it, collect
dumps, or use it as a Windows acceptance gate. All Windows native validation
uses Win32/I386 on hosted Windows Actions. The completed run
`45907759163` is imported evidence, not a run executed by this campaign.

**Reason:** The historical customer artifacts and production Windows target are
32-bit; an x64 failure does not establish a production-target regression.

## D2 — No production edits

This campaign investigates existing behavior and preserves reproducers. Any
production fix is separate work. No edits to `TotalCross/totalcross` are
permitted here.

## D3 — Distinguish merge destination from master

PR merge state is insufficient to prove inclusion in `master`. Record each
source/head/base SHA and compare the commit graph to the frozen `master` SHA.
The current API snapshot shows #545 and #565 merged into stacked feature
branches, while #538/#539 remain open. GitHub comparison shows #545/#565
diverge from frozen master and that their changed-file sets include the
correction implementation files. Treat them as candidate source, not as
corrections already present in master; compare exact source content before
building any combined candidate.

## D6 — Verify PR #567 implementation equivalence

The open PR head `926e964841ac64dca172a648bce1ffcc6d60d153` has a different
commit history from validated implementation `94af2b8b653cad509994b5ccf3dbb60ac28ef920`,
but the complete `TotalCrossSDK/` trees compare byte-for-byte equal. Historical
JavaSE/Windows/macOS/Android validation can be considered only after its
assertions and artifact provenance are independently recovered.

## D4 — Platform execution boundary

Native Windows, Linux, and macOS runtime tests run only in the corresponding
GitHub-hosted Actions environment; Android runtime tests run only in a local
hardware-accelerated Android ARM64 emulator. JavaSE checks are not native
runtime evidence.

## D5 — Preserve historical Windows result

The I386 startup and ownership result in run `45907759163` is retained as
historical evidence for PR #567. Do not repeat it unless subsequent source
changes invalidate implementation equivalence.

## D7 — Accept the verified production Win32 priority run

The priority correction required corrected source
`94af2b8b653cad509994b5ccf3dbb60ac28ef920` to build with the production Win32
configuration, pass a minimal native startup probe, and then pass the existing
ownership smoke against the same runtime. Run `45907759163` already completes
that sequence on one `windows-2022` runner, compares both historical I386
artifacts in the same job, records the startup markers and process exit codes,
and verifies PE machine `0x014c` for the corrected runtime and deployed
executable. Its result artifact digest was verified and compact evidence is
committed in this campaign. Reuse the result; do not dispatch a duplicate
Windows run while the source and fixture remain unchanged.

The production Windows Win32/I386 correction is functionally validated. The
Windows-specific portion of I06 is PASS; I06 overall remains NOT_RUN until the
required Linux x86_64 execution is completed. AMD64 remains a separate
preexisting, out-of-scope startup failure.
