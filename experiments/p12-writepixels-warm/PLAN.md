<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# Isolate historical opaque writePixels on current cached-final draws

This ExecPlan follows the runtime AGENTS.md and .agent/PLANS.md, read in full.

## Purpose / Big Picture
Measure whether historical opaque device-1:1 writePixels explains the remaining
warm gap. Preserve physical-only routing and immediate admission; restore only
the native backing draw attempt, with normal canvas fallback. One runner/process,
one stabilization, five tree samples, no production policy or other experiments.

## Working Set and Resume Protocol
Read this plan first. .local-data/runtime-writepixels-warm derives from f95c280db.
Native skia_image_backing.cpp owns the restored helper/accounting; its test header
and skia_surface_test.cpp expose only test metrics and parity cases. This directory's
source-comparison.md documents exact historical/current sources and adaptations.
runtime.patch is the complete delta from 5a44f503; writepixels.patch is only the
delta from f95c280db. provenance.json indexes source/build/package/test/process
hashes and commands. Dedicated report reports measured evidence and limits.
Normal benchmark sources exclude this directory's hooks/entry. Shared protocol
and existing draw/admission counters are unchanged.

## Progress
- [x] Starting lab clean at published 49fb0c5; historical/current call paths inspected.
- [x] Restored narrow historical RGBA helper/switch and passed native eligibility/parity tests.
- [ ] Exact runtime committed/built, 105 lab/58 SDK tests pass; commit tooling then package/hash audit.
- [ ] One process, offline analysis, report/checkpoint, final validation and push.

## Current Architecture and Scope
Historical f5dad132 passed bit-2 optimizationMask to NativeImageBacking drawing.
Current function calls drawOnCanvas directly. Cached final physical RGBA pixels
are 358x358 with content scale 2: canvas scale2 maps logical179 destinations to
physical358, so device1:1 can be eligible despite nonidentity logical canvas scale.
Historical buildWritePixelsDeviceCopyPlan maps the positive axis canvas matrix,
requires integer/bounded source and integer equal-size device destination, and
intersects device clip/target bounds. Opacity proof precedes pixel writes.
Keep these predicates exactly. Current backing lacks historical opacity metadata:
use experiment-local handle/generation proof caching, never change backing storage
or generation. Other historical compact formats are not enabled for this default
RGBA-only probe; reject them conservatively and retain normal canvas fallback.

## Plan of Work
Use existing private NativeImageBacking test metric bridge for switch/accounting,
without SDK/API or production setting changes. Switch defaults off and enables
only after startup via isolated hooks composed over prior immediate hooks. Record
all native attempts, reasons, format/opacity, input/mapped/clipped rectangles,
bytes and operation timings. Reset event counters via existing reset hook while
retaining valid opacity proofs. Add native enabled/disabled/invalid/clip/parity
cases. Extend pinned package/parser/schema tests without outcome acceptance gates.
Build Release arm64 SDK/tcvm/Launcher at one committed source then package clean
committed lab. Verify dataset/hashes and exclusive fresh launch marker, run once.

## Decision Log
Restore historical RGBA helper in the same native file; no generalized production
fast-path architecture or public feature flag. Do not introduce metadata fields
or alter final-raster representation; generation-keyed proof cache is isolated
accounting/adaptation to missing historical opacity state. Retain fallback code
and no mask configuration changes; private experiment switch represents bit2.

## Validation and Acceptance
Focused native positive/negative/parity tests, prior SDK admission/scale/backing/
decode suites, all lab tests, headers, official/custom Java compile, exact native
build/package hashes, parser/schema/one-process audit. Counters must establish
actual hits or reasons; no required timing threshold or forced hit. Expensive
platform/sanitizer/matrix validation deferred outside isolated experiment scope.

## Risks and Open Questions
May reject geometry/opacity or remain slow with actual hits. Do not change
eligibility to force hits. Pixel scanning/native timestamps impose overhead;
report first-proofs versus reused proofs and time the write itself separately.
No evidence yet that all historical controls actually hit historical writePixels.

## Idempotence and Recovery
Exclusive launch-authorized.json before sole runner. Preserve all first-process
output. No replacement after valid samples; setup failure needs offline correction
and explicit decision, never silent retry. Keep old worktrees/artifacts intact.

## Outcomes & Retrospective
Pending. Production admission and unrelated behavior stay unchanged. Preserve
checkpoint open policy section verbatim; record all causal cases honestly.
