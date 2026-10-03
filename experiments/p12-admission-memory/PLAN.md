<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# Measure one-slot final-raster admission memory and duplicate work

This ExecPlan follows unchanged runtime AGENTS.md/.agent/PLANS.md, read in full
for the preceding experiment; their Git diff from that read is empty.

## Purpose / Big Picture
Compare second observation and immediate admission in exactly four processes,
one-shot and repeated list scrolling. Recommend final-materialized admission only;
no production fix or native speculative admission change.

## Working Set and Resume Protocol
Read this plan first. .local-data/runtime-admission-memory derives from18baece1.
Image/ImagePipeline accounting and experiment-only class capture ownership/key
lifecycle without changing release semantics. Native image backing accounting tags
source/derived records without retaining Java/backing references or changing
storage/generations. Native writePixels uses the exact preceding predicates;
summary mode avoids accumulating per-draw geometry/timers over long routes.
This directory's runtime.patch/full delta and memory.patch/parent delta reproduce
source. provenance.json indexes source/build/tests/package/four first processes.
protocol.md defines fixed route/cadence/extra-paint handling; report interprets
cache-owned, all live derived and source storage independently.

## Progress
- [x] Ownership inspected: one slot; clear/replacement drops Java reference and
  releaseTextureOnly does not free software backing. GC lifetime is separate.
- [x] Implement isolated policy/ownership/source-derived accounting and focused tests.
  SDK 63 focused tests pass; native category/release and original writePixels/physical
  assertions pass. Java compilation passes for normal official SDK and isolated SDK.
  Lab 115 tests pass. No measured application has launched.
  Texture release retains the slot; only actual clear/replacement is a detach.
- [ ] Deterministic routes, parser/schema/runner/package/tests and committed artifacts.
- [ ] Four processes in ordered cases, offline analysis and architectural recommendation.
- [ ] Reports/index/checkpoint, cheap validation, commit/push and completion audit.

## Current Architecture and Scope
One cachedVariant Image and pending exact key per ImagePipeline. Generation/key
mismatch does not eagerly destroy a still-retained other slot; do not change it.
NativeImageBacking.finalize releases storage after Java references become
unreachable. Cache-owned retained bytes therefore differ from all derived native
backings (including unadmitted temporaries awaiting GC). Measure both, never
claim a slot detach immediately frees native memory. Tags/counts do not retain
objects. Fixed dataset controls remain alive throughout both workloads.

## Plan of Work
Add disabled accounting for installation/detach/replacement/invalidation and
per-index materialization/admission/hits/exact keys. Actual Native bytes/format/
physical dimensions define retained footprint. Census source references separately
from tagged live decoded and derived native records. Test both policies/capacity/
keys/generation/release, derived accounting and unchanged native variant code.
Use the same physical-only fallback and historical RGBA writes for both policies.
Async normal damage paints: initial position0; one-shot pages by viewport910;
repeated uses existing step120 down to endpoint then reverse to0. Nominal cadence16ms,
no skipped route positions; cold stalls are measured, not compensated by fake paints.
No prepare/prefetch/resolve calls. Actual paint sequence is retained and audited.
No forced GC during traversal. After natural ending snapshot, diagnostic GC may
show collection-lag separately with retained UI; never substitute it for natural
peak/end. All four processes use one exact package/source and flags only admission.

## Decision Log
Separate slot-owned bytes from native derived allocations/liveness and decoded
storage, because second observation could reduce retention but increase uncollected
temporary rasters. Keep original detach/finalizer behavior untouched. Index per-image
primitive counters only; no strong tracking registry or ownership transfer.
Native per-draw clocks/records disabled in summary mode; explicit experiment
materialization and frame diagnostics identical for both policies.

## Validation and Acceptance
SDK first/second observation, single slot/key/generation/release/memory accounting
and disabled guards; existing SDK admission/backing/decode suites; native category
liveness/release and prior eligibility/parity/variant admission tests; all lab tests;
headers/official/custom Java compile; exact Release arm64 package/source/dataset hashes.
Commit implementation before any measured application. Four cases only, preserve
surprising/partially valid records and never silently rerun. No broad matrix,
Windows/historical runtime or production changes. Source/native speculative
variant code must compare unchanged to parent except independent accounting tags.

## Risks and Open Questions
One-shot page boundaries inherently repaint straddling controls; report actual
once/multiple counts, never artificially reobserve solely for admission. Repeated
normal paints may admit nearly all under both policies. Extra asynchronous paints
must be captured, not hidden. GC lag can inflate all-derived backing memory;
cache-owned counters and optional post-run GC resolve that distinction. No byte
budget/global cache proposal unless measured architecture proves insufficient.

## Idempotence and Recovery
Four exclusive ordered launch markers; one runner per case. No warmup/preflight
application. Preserve all failed/partial first evidence; tooling-only pre-result
failure must be corrected offline before any explicit replacement decision.
Never reexecute due to surprising results. Previous packages/evidence unchanged.

## Outcomes & Retrospective
Pending. Production final admission and native TARGET_COLOR/PHYSICAL second-use
policies unchanged. Final report must document d273518 P3 one-slot/second-use
bounded-state rationale and missing representative workload tradeoff evidence.
