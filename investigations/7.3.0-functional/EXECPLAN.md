# TotalCross 7.3.0 Functional Validation Campaign

This plan follows the campaign request and the repository ExecPlan guidance in
`TotalCross/totalcross/.agent/PLANS.md`. It is investigation-only: no production
source changes are permitted.

## Purpose / Big Picture

Produce a reviewable, reproducible account of the remaining functional defects
and corrections in TotalCross 7.3.0. Every in-scope platform/revision
combination must have evidence or an explicit reason it could not run. The
campaign closes with committed case reports, a machine-readable matrix,
provenance, proposed issue updates, and a consolidated report.

## Working Set and Resume Protocol

- Read `CHECKPOINT.md` first for the active milestone, exact next action, and
  current blockers.
- `test-matrix.json` is the authoritative status per investigation and
  platform/revision/API; do not infer completion from prose.
- `provenance.json` records source, SDK, VM, dependency, workflow, artifact,
  toolchain, and implementation-equivalence identities. `null` means unknown,
  not verified.
- `DECISIONS.md` records policy choices that affect later work.
- `evidence/` holds compact, sanitized logs, manifests, excerpts, hashes, and
  imported historical evidence. Large binaries, packages, caches, and dumps
  stay outside Git.
- `cases/` and `scripts/` hold deterministic fixtures and reproducible
  adapters. `reports/` holds self-contained investigation reports and final
  proposed issue updates.

## Progress

- [x] 2026-11-27: Read the campaign scope and Windows priority correction;
  verified the production Win32/I386 ownership run and kept AMD64 out of scope.
- [x] 2026-11-27: Created this campaign worktree from performance-lab `main`
  at `fe23e009fa2fcdbf8c36746cea58b9946a138858` after confirming the requested
  branch did not exist locally or remotely.
- [x] 2026-11-27: Imported compact historical Linux startup and PNG evidence,
  preserving source revisions, artifact digests, test-only shim conditions,
  fixture hashes, and the distinction from frozen-master validation.
- [x] 2026-11-27: Verified the official 7.2.2 SDK/Linux VM pair and the 7.3.0
  CI package by published artifact digests and extracted binary hashes;
  checked TotalCross 4.6.0 source for I04/I05 and kept both in scope.
- [x] 2026-11-27: Confirmed local ARM64 Android emulator acceleration and API
  29/30/35/36 system images; Android Actions runtime execution is excluded.
- [x] 2026-11-27: Compared the historical Linux build source with frozen
  master and confirmed the native VM tree changed; current-master evidence
  requires an exact-source rebuild.
- [x] 2026-11-27: Added deterministic PNG fixtures, Linux startup/PNG probes,
  a reusable observation harness, and a dedicated-branch Actions workflow.
  Harness/config checks and Java compilation passed; runtime results are
  pending the Actions run.
- [x] 2026-11-27: Two hosted builds exposed bootstrap issues: frozen source
  `6b915` lacks a depot-tools ref file, and an empty zlib release override
  masked the pinned `deps.yml` entry. Commits `3394d9b` and `dc76666` pin the
  dependency metadata and forward overrides only when nonempty; both attempts
  stopped before runtime validation.
- [x] 2026-11-27: Executed the official 7.3.0 customer reproducer on local
  hardware-accelerated API 29/30/35/36 ARM64 AVDs. APIs 30/35/36 each produced
  four Skia/GLES SIGSEGV tombstones across denied and grant-in-place flows;
  pregranted controls stayed alive. API 29 produced no native crash, but an
  interactive Allow left WRITE_EXTERNAL_STORAGE denied while the explicit
  pregrant passed. The harness now resets each phase by reinstalling the app
  and uses the accessibility tree for API 29's runtime permission dialog. The
  consolidated I03 report and compact evidence are recorded; root cause stays
  open.
- [x] 2026-11-27: The third hosted Linux build passed CMake configuration and
  began native compilation, then failed because the Docker bind mount could
  not read Actions' external Git metadata and no `build-provenance.json` was
  present. The workflow now writes provenance from the exact frozen commit and
  tree before invoking the canonical container; the identity script accepted
  this manifest in a no-Git fixture. Hosted run `45949849457` subsequently
  completed build and runtime jobs. The verified Linux result and build-bundle
  artifacts are consolidated in the I01-B/I02 reports, matrix, and provenance;
  the conditional PNG run passed eight of nine cases and the exact fortified
  `realpath` check remains unresolved.
- [x] 2026-11-27: Reused and reverified the Windows Win32/I386 priority run
  `45907759163`; its same-runtime startup and ownership checks passed. No
  AMD64 test or analysis was performed.
- [x] Milestone 0: provenance, legacy-port review, historical evidence import,
  harness/workflow contract, and CI/emulator capability checks are complete.
- [x] Milestone 1: Linux realpath startup (I01-B) and PNG decode (I02) runtime
  findings are consolidated; the original failure and conditional shim result
  remain separately reported.
- [x] I03: official 7.3.0 customer scenarios ran on API 29/30/35/36; API 30
  follow-ups recorded the Settings-rotation crash, a passing pregranted
  lifecycle control, and a diagnostic foreground surface crash. Repeated
  requests remain NOT_RUN because the first denied transition crashes and no
  corrected candidate is available.
- [x] I04: API 30 normal, invalid-mode, permission, and barrier write/close
  probes completed. No `fwrite` abort in completed cases; denied return and
  exact native overlap remain inconclusive.
- [ ] I05: shutdown probes ran; findings and report remain to be committed.
- [ ] Milestone 2: I05 shutdown findings remain to be checkpointed.
- [ ] Milestone 3: run Linux ownership validation (I06) and remaining
  `Image(String)` checks (I07), importing equivalent historical evidence.
- [ ] Milestone 4: validate Android filesystem and SQLite permission recovery
  (I08/I09), then SQLite compatibility (I10).
- [ ] Milestone 5: restricted release workflow validation (I11), final matrix,
  issue proposals, and consolidated report.

## Current Architecture and Scope

The product source is `TotalCross/totalcross`; this campaign's central
workspace is `TotalCross/totalcross-performance-lab`. Existing issue and PR
reproducers are in the performance-lab `main` history, including the Android
EGL reproducer (#7) and earlier SQLite/Linux diagnostics (#4). Do not create a
parallel benchmark suite or repeat the performance investigation.

The corrected ownership implementation is TotalCross commit
`94af2b8b653cad509994b5ccf3dbb60ac28ef920`; its open PR is #567 at
`926e964841ac64dca172a648bce1ffcc6d60d153`. Windows I386 startup and ownership
validation passed in Actions run `45907759163`. The run has been reverified
against the priority correction: it builds this exact source with the
production Win32/Release rendering configuration, executes the minimal startup
probe and then the existing ownership smoke against the same I386 runtime, and
compares both historical I386 artifacts on the same runner. Retain it as
verified historical evidence; do not repeat the run while its inputs remain
unchanged. The Windows I386 correction is functionally validated; Linux
x86_64 remains the required I06 execution. No Windows AMD64 runtime test,
revision bisect, or new crash dump is allowed.

## Plan of Work

### Milestone 0 — Preparation

1. Freeze official 7.2.2, official 7.3.0, current TotalCross master, PR #545,
   PR #565, PR #567, historical Linux PNG run, and release PR #538/#539
   provenance. Verify which PR commits are on `master` versus stacked feature
   branches; never call a PR merged into an intermediate branch a master fix.
2. Verify available/expired artifacts and exact SDK/VM pairings. Verify the
   implementation-equivalence claim for PR #567 and import its JavaSE,
   Windows I386, macOS ARM64, and Android ARM64 evidence where recoverable.
3. Check legacy TotalCross 4.x for applicable Android `File.writeBytes` and
   shutdown fixes. Exclude I04/I05 only with source-commit evidence.
4. Reuse the existing case fixtures, define a single branch-triggered workflow
   and adapters, and verify the runner/emulator capabilities. A workflow newly
   added only on this branch must not depend on `workflow_dispatch`; use a
   dedicated-branch push trigger when an Actions run is required.
5. Commit the completed provenance inventory and explicit initial matrix before
   starting the full case campaign. A focused branch-only Linux workflow is
   justified because the canonical reusable workflow cannot select Linux
   alone; reuse its runner image, pinned dependency bootstrap, and CMake/Ninja
   build path, then remove or upstream the focused path when the canonical
   workflow supports case-scoped platform selection.

### Milestone 1 — Linux startup and PNG blockers

**I01-B:** inspect the actual startup source and reproduce against official
7.2.2, official 7.3.0, and frozen master. Exercise normal, short, long, and
symlink paths; record the unmodified failure before using the preserved shim.
Collect exact call, buffer capacity, native stack, glibc/FORTIFY/build flags,
markers, and exit code. Shim results remain conditional. Prepare an issue or
issue update if unresolved.

**I02:** verify the exact 136-byte PNG and hash; test `Image(File)`,
`Image(byte[])`, TCZ PNG, alpha, indexed PNG, JPEG, and invalid input. Force
pixel materialization and assert dimensions/pixels/exceptions. On Linux, first
reproduce with original loading semantics; then inspect `LD_DEBUG` bindings,
decode using the VM's exact static headers/libraries, compare VM-integrated
behavior, and pursue allocator/ABI/cleanup hypotheses only if evidence points
there. Keep proven, disproven, and open hypotheses separate.

### Milestone 2 — Android native failures

**I03:** run the customer reproducer and diagnostic variants on available ARM64
emulator APIs, prioritizing 29, 30, 35, and 36; use 24/31 only when available
and discriminating. Cover pregranted, in-flow grant/denial, unchanged Settings
return, repeated requests, background/foreground, and rotation where
applicable. Preserve logcat, tombstone, lifecycle, surface, EGL, Skia, and file
operation evidence. Do not promote the EGL hypothesis to a root cause without
direct evidence; no physical-device claim. The official package fails denied
and grant-in-place flows on API 30/35/36; API 29 did not crash but Allow left
WRITE denied. API 30 rotation within Settings reproduces the crash; a separate
pregranted customer lifecycle control passed once, while a diagnostic worker
screen failed on foreground surface recreation. Repeated requests are recorded
NOT_RUN because the first denied transition already crashes and no candidate is
available.

**I04:** the 4.6.0 review found no exact correction for a live-mode object with
a null/stale native handle. API 30 normal, invalid-mode, permission, and
barrier write/close cases are recorded; denied return and in-native overlap
remain inconclusive. Do not claim the `fwrite` abort is fixed.

**I05:** the 4.6.0 review found no applicable shutdown fix. API 30 probes cover
normal exit, file I/O, SQLite, active workers, permission return, and repeated
termination; the one file-I/O destroyed-mutex abort is documented with its
missing native stack. Intermittent repeats are capped at ten. Do not change
product code.

### Milestone 3 — Image behavior

**I06:** import verifiable historical JavaSE/Windows/macOS/Android ownership
results, verify PR #567 source equivalence, and execute only remaining Linux
x86_64 baseline/candidate ownership scenarios. If startup or PNG blocks a
case, classify it under I01-B or I02 and preserve the reason. Include tree
detach/reattach, reparent, sharing, mutation/replacement, GC/lifecycle,
rendering/pixels, and shutdown assertions; no timing or memory-consumption
claims.

**I07:** test TCZ-first `Image(String)` fallback on Windows I386, Linux x86_64,
macOS ARM64, and Android ARM64 using the exact corrected SDK/VM provenance.
Cover filesystem-only, TCZ-only, both, malformed/empty TCZ entries, missing or
invalid filesystem files, path forms/boundaries, `Image(File)` parity,
snapshot semantics, and native ownership. Use JPEG controls on Linux when PNG
is blocked. Record startup and decoder blockers separately.

### Milestone 4 — Filesystem and SQLite

**I08:** compare official 7.3.0 and corrected candidate on available Android
APIs. Matrix private, app-specific external, and shared storage against actual
API/targetSdk/manifest rules and granted/denied/recovered states. Exercise
create, read, write, list, metadata, rename, delete, and directory operations;
verify API 29 legacy recovery and no API 30+ legacy request loop.

**I09:** separately validate direct native SQLite permission recovery for
private and authorized shared storage, denied/granted/denied recovery,
read-only/invalid/corrupt DB, close/reopen, and restart persistence. Record
SQLite result and extended codes; run `integrity_check`. Do not confuse this
with format compatibility.

**I10:** use plaintext databases from external SQLite, 7.2.2, and 7.3.0; test
cross-platform transfer, app update persistence, WAL snapshots, and an invalid
negative control. Compare 7.2.2, 7.3.0, and corrected candidate on permitted
platforms. Record headers, hashes, logical content, SQLite version/options,
errors, queries, and integrity results. Use synthetic data if the customer DB
is unavailable; do not claim the exact customer file was validated.

### Milestone 5 — Release workflow and closure

**I11:** inspect #538/#539 and canonical release workflows. Validate SDK,
Win32/I386, Linux, macOS ARM64, packaging/inventory, version consistency,
release notes, dry-run, and absence of tags/releases/publication. Exclude
Android runtime, AMD64, iOS, and any unguarded publication path. Classify as
partial when the safe exclusions prevent a full dry-run.

At each completed or blocked investigation, update and commit its report,
matrix, evidence, and checkpoint before moving on. Finalize
`reports/FINAL-REPORT.md` and `RESULTS.md`; ensure no result depends only on
chat, local transient logs, or expiring artifacts.

## Validation and Acceptance

- Use only Windows Win32/I386, Linux x86_64, macOS ARM64 hosted Actions, and a
  local hardware-accelerated Android ARM64 emulator for native runtime work.
- No Windows AMD64 runtime tests, iOS builds, physical devices, Device Farm,
  Android Actions, performance/load/throughput/FPS/frame-pacing/memory
  benchmarks, releases, tags, publications, or PR creation.
- A runtime PASS requires startup and completion markers, expected assertions,
  bounded timeout, process exit status, and compatible verified SDK/VM
  provenance. Build/package/install alone is not runtime validation.
- Keep failures and independent cases isolated. A baseline failure does not
  prove a later candidate failure is unrelated; compare signatures and stages.
- Record every unexecuted combination with `NOT_RUN` or a supported blocker.
  Mark shimmed results conditional.
- Run focused harness contract checks before expensive platform work. Commit
  each logical slice and preserve compact evidence; never commit binaries,
  dependency caches, full SDK/APK payloads, or raw dumps.

## Risks and Open Questions

- The corrected PRs are stacked and may not be present in official 7.3.0 or
  master; exact compatible SDK/VM combinations must be reconstructed.
- Historical Actions artifacts may expire. Preserve text evidence and hashes;
  rebuild only exact source when an artifact is unavailable and necessary.
- Linux startup and PNG defects may block multiple cases independently.
- Android emulator API images and hardware acceleration may be unavailable;
  record missing configurations rather than substituting CI/device testing.
- The original customer SQLite database may be unavailable.
- A new workflow can run on a branch push, but manual dispatch availability
  must not be assumed for branch-only workflow files.

## Idempotence and Recovery

Use the dedicated branch and worktree only. Before each change, inspect scoped
status/diff and preserve any unrelated work. Reuse existing PR #4/#7 fixtures
and artifacts. Never delete caches or replace source files. A rerun must use
the same pinned SDK/VM and fixture and must create a new evidence record rather
than overwrite prior failures. Push only this campaign branch, only when
needed to run Actions or preserve the committed result; never force-push or
create a PR.

## Outcomes & Retrospective

Pending. Update only at milestone completion or when evidence materially
changes the interpretation.

## Revision Note

2026-11-27: Initial campaign plan. Windows I386 ownership validation is an
imported pass; Linux ownership is the remaining I06 runtime requirement.
2026-11-27: Reverified the existing Windows Actions artifact against the
priority architecture correction. Corrected Win32 startup and ownership both
pass; the campaign continues with Linux I01-B/I02 result consolidation.
