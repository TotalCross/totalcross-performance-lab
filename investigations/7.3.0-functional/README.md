# TotalCross 7.3.0 Functional Validation

This workspace records the functional investigation campaign for TotalCross
7.3.0. It preserves reproducible tests and evidence for existing defects and
corrections. It does not modify production code in `TotalCross/totalcross`.

## Scope

The active backlog is I01-B through I11 in `EXECPLAN.md`. Windows AMD64 startup
is recorded as a preexisting, out-of-scope defect. Windows native validation
uses Win32/I386 on GitHub Actions only. Linux x86_64 and macOS ARM64 native
tests also use GitHub Actions; Android ARM64 runtime tests use a local
hardware-accelerated emulator only. JavaSE is used only for SDK-level controls.
No performance benchmarks, iOS tests, releases, publications, or production
changes are part of this campaign.

## Resume

Read `CHECKPOINT.md` first. The authoritative per-test statuses are in
`test-matrix.json`; frozen and still-missing source/artifact identities are in
`provenance.json`. Investigation reports live under `reports/`, reproducible
fixtures and commands under `cases/` and `scripts/`, and compact retained
evidence under `evidence/`.

## Result semantics

The matrix uses `PASS`, `FAIL`, `REGRESSION`, `PREEXISTING`, `BLOCKED`,
`NOT_REPRODUCED`, `INCONCLUSIVE`, `OUT_OF_SCOPE`, and `NOT_RUN`. Test outcome,
scope, evidence origin, startup, execution, assertions, exit code, and
limitations are separate fields. Historical validation is never represented as
a test run from this campaign.

## Repository and branch

The campaign branch is `investigation/totalcross-7.3.0-functional-validation`
in `TotalCross/totalcross-performance-lab`, based on the fetched `main` commit
`fe23e009fa2fcdbf8c36746cea58b9946a138858`. The branch is kept separate from
the benchmark worktree and from all production branches.
