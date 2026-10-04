<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# P12 historical writePixels warm-path probe — 2026-10-03

Restoring the historical opaque physical-1:1 writePixels attempt on the current
reconstructed cached-final path recovered **94.708283%** of the residual historical
warm gap in this workload. All 18 visible controls hit that native path during
stabilization and every measured sample. The warm paintTree median fell from
3.650708 ms to **1.156250 ms**, approaching the historical 1.016875 ms reference.
Native hits and unchanged cache/materialization counters establish the mechanism;
this result does not declare the historical production architecture restored.

## Exact sources, artifacts and process boundary

Benchmark implementation: `1f326e833882e9a9299ad74c57b2486f27bc5c5a`.
Isolated TotalCross source: `18baece1f199ab5d2e7cad6d864c40c188bd1bab`.
Historical reference implementation: `f5dad132cafea5c9086f6f946a6f44ca5bcb5f76`.
Parent runtime: `f95c280db3d6856d17582ea31d47aaded6a0e492` (physical-only routing
plus immediate admission); original current base: `5a44f503`.
The delta from the parent contains only skia_image_backing.cpp, focused
skia_surface_test.cpp tests, and a test metric header. SDK routing, admission,
lookup, generation/scale/backing validity, final-raster representation, native
geometry/materialization, decode and renderer settings are unchanged.

[source comparison](../experiments/p12-writepixels-warm/source-comparison.md)
documents exact Graphics.copyRect/drawSurface/helper/opacity predicates and source
blob identities. The historical RGBA planner was verified byte-for-byte after
accounting adaptation. A private test metric switch enables the equivalent of
historical bit2 only after startup. It defaults off; no actual optimization mask
or production API is changed. Opacity proofs are kept outside backing storage,
keyed by handle/generation, because current backing lacks historical opacity state.
Other historical compact-format conversion branches remain conservatively excluded
from this default-RGBA experiment; native capture confirms all measured sources
are format 0 RGBA8888. No eligibility was broadened or geometry forced to match.

Exactly **one runner** and **one measured native application** ran, both exiting
**0**. One complete valid result and one inline preflight were emitted; no separate
preflight/warmup, replacement, historical run, Windows, alternate mask/profile,
matrix or other causal experiment. The offline native assertion executable is a
focused unit test, not another measured application. Stdout contains the earlier
UI resource read-only-filesystem IOException warning; it did not prevent the
valid record or successful exit. Stderr is empty. No recovery was needed.

The retained 663-image manifest ordering, top position 0, six rows/18 ImageControls
and row/control/Image instances are unchanged. Logical540×960, viewport 540×910,
drawable 1080×1920, scale 2 and tile 179×179 match all preceding focused probes.
Exactly one untimed stabilization and five timed whole-tree samples ran. There
was no scroll movement or prepareForDisplay. Runtime defaults before/after match.

Exact commands, build/SDK/package hashes, source patches, original first-process
paths/hashes and six aggregate snapshots are indexed once in
[provenance.json](../experiments/p12-writepixels-warm/provenance.json).
Full per-draw native records remain in the indexed runs.jsonl/stdout evidence.

## Five timings and full event accounting

ImageControl totals sum the 18 onPaint calls. Every event has 6 row paints and
18 ImageControl paints. Stabilization has no whole-tree timed sample. Times in
this table are milliseconds.

| Event | paintTree | ImageControl total | Row total | Cached probes/hits/misses | Physical attempts/hits/fallbacks | Resolve calls/cache hits | Observations/admissions | Offscreen materializations |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: |
| Stabilization | untimed | 335.948796 | 0.253624 | 18/0/18 | 18/0/18 | 20/0 | 18/18 | 18 |
| Sample 1 | 1.310291 | 0.950206 | 0.216249 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |
| Sample 2 | 1.153792 | 0.841623 | 0.214125 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |
| Sample 3 | 1.156541 | 0.845332 | 0.212373 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |
| Sample 4 | 1.156250 | 0.840083 | 0.221332 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |
| Sample 5 | 1.150959 | 0.837458 | 0.219292 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |

Stabilization copyRectPlan attempts/handled/fallbacks = 18/0/18, last status
20490 (`0x500a`); identity attempts/hits/fallbacks = 18/0/18. Every timed sample
has zero copyRectPlan/identity attempts, hits, handled or fallbacks and status 0.
DirectDrawPlanExecutions, genericGeometryDraws, smoothResampleDraws, targetColor
hits/fallbacks/materializations and physicalVariant hits/fallbacks/materializations
are zero for all six events. Both earlier experimental switches remain enabled.
The two residual resolve calls are outside the 18 cached-final control lookups;
they do not observe, admit or materialize deferred variants. Their prior presence
is unchanged. Native capture additionally identifies two non-control backing
draws below; no exact UI call site was instrumented.

Offscreen smooth geometry materialization occurs only during stabilization (18),
creating the reusable final rasters. It remains distinct from direct generic/
smooth destination rendering, which is zero throughout. All five samples start
warm with 18 cached-final hits and zero new materialization/observation/admission.

## Native writePixels counters and timing

| Event | Attempts/hits/fallbacks | Copied bytes | Planner-clipped hits | Opacity scans/pixels | Attempt ms | writePixels ms | Canvas fallback ms |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| Stabilization | 20/18/2 | 7715616 | 0 | 18/2306952 | 2.250957 | 1.105085 | 0.039584 |
| Sample 1 | 20/18/2 | 7715616 | 0 | 0/0 | 0.532000 | 0.525003 | 0.037709 |
| Sample 2 | 20/18/2 | 7715616 | 0 | 0/0 | 0.450456 | 0.446918 | 0.028417 |
| Sample 3 | 20/18/2 | 7715616 | 0 | 0/0 | 0.455165 | 0.451960 | 0.029208 |
| Sample 4 | 20/18/2 | 7715616 | 0 | 0/0 | 0.453749 | 0.450958 | 0.028125 |
| Sample 5 | 20/18/2 | 7715616 | 0 | 0/0 | 0.454542 | 0.451626 | 0.027958 |

Every event has **20 attempts, 18 hits, 2 fallbacks/normal canvas draws**. The
only rejection reason is sizeMismatch=2 per event; invalidTargetOrSource,
alphaMask, sourceRect, matrix, fractionalDestination, destinationBounds, opacity,
unsupportedFormat, sourcePixels and writeFailure are all zero. Attempt timing
includes eligibility/proof/subset/write work; write timing is nested within it,
so these totals must not be added. Timers and record insertion add small overhead
inside measured painting; capture/JSON reads occur after the paintTree timer.

The 18 viewport sources are 358×358 RGBA8888 (native format 0), physical final
rasters with canvas scale/translation `[2,2,0,0]`. Their opacity before/after is
unknown 0→provenOpaque 1 during stabilization, then 1→1 for every sample. Exactly
18 full-raster alpha scans (2,306,952 pixels) occur during stabilization; none
occur in samples. The same native handles and all geometry/reasons remain stable
across the six events. No opacity value is inferred for rejected sources.

## Captured physical geometry for each visible control

Rectangles are `[left,top,right,bottom]`, right/bottom exclusive. All 18 records
have hit=true, rejection=none, source format 0, size358×358 and proven opacity1.
The source column is both input physical source and clipped physical subset;
the device column is both mapped and clipped device destination. Logical
destinations are exactly half the device coordinates. Matrix `[2,2,0,0]` applies
to every attempt. Each full hit copies 512,656 bytes; each partial bottom hit 8592.

| Index | Dataset path | Native handle | Source physical | Device destination | Bytes |
| --- | --- | ---: | --- | --- | ---: |
| 0 | `-1009782731.jpg` | 188 | [0, 0, 358, 358] | [2, 84, 360, 442] | 512656 |
| 1 | `-1012043485.jpg` | 189 | [0, 0, 358, 358] | [362, 84, 720, 442] | 512656 |
| 2 | `-1013143947.jpg` | 190 | [0, 0, 358, 358] | [722, 84, 1080, 442] | 512656 |
| 3 | `-1015024107.jpg` | 191 | [0, 0, 358, 358] | [2, 446, 360, 804] | 512656 |
| 4 | `-1026010547.jpg` | 192 | [0, 0, 358, 358] | [362, 446, 720, 804] | 512656 |
| 5 | `-1028874041.jpg` | 193 | [0, 0, 358, 358] | [722, 446, 1080, 804] | 512656 |
| 6 | `-1038926037.jpg` | 194 | [0, 0, 358, 358] | [2, 808, 360, 1166] | 512656 |
| 7 | `-104018500.jpg` | 195 | [0, 0, 358, 358] | [362, 808, 720, 1166] | 512656 |
| 8 | `-1040544427.jpg` | 196 | [0, 0, 358, 358] | [722, 808, 1080, 1166] | 512656 |
| 9 | `-1042033183.jpg` | 197 | [0, 0, 358, 358] | [2, 1170, 360, 1528] | 512656 |
| 10 | `-1042180667.jpg` | 198 | [0, 0, 358, 358] | [362, 1170, 720, 1528] | 512656 |
| 11 | `-1043960095.jpg` | 199 | [0, 0, 358, 358] | [722, 1170, 1080, 1528] | 512656 |
| 12 | `-1056468936.jpg` | 200 | [0, 0, 358, 358] | [2, 1532, 360, 1890] | 512656 |
| 13 | `-1059601584.jpg` | 201 | [0, 0, 358, 358] | [362, 1532, 720, 1890] | 512656 |
| 14 | `-108958495.jpg` | 202 | [0, 0, 358, 358] | [722, 1532, 1080, 1890] | 512656 |
| 15 | `-1096038007.jpg` | 203 | [0, 0, 358, 6] | [2, 1894, 360, 1900] | 8592 |
| 16 | `-111131558.jpg` | 204 | [0, 0, 358, 6] | [362, 1894, 720, 1900] | 8592 |
| 17 | `-1111384947.jpg` | 205 | [0, 0, 358, 6] | [722, 1894, 1080, 1900] | 8592 |

**Planner-clipped hits = 0 does not mean the bottom row was fully painted.**
Graphics.drawSurface already clipped the last three controls to logical height 3
before this helper: input source height 6 and destination device height 6. The
helper therefore made no further clip adjustment (`clipped=false`). Fifteen
358×358 copies plus three 358×6 copies total **7,715,616 bytes per event**. Native
tests separately prove additional device clipping matches historical behavior.

The two additional native sources also have format 0 but retain opacity 0
(unknown/unproven), because size mismatch rejects before the opacity scan:

| Native handle | Backing size | Input source physical | Logical destination | Mapped device destination | Result |
| --- | --- | --- | --- | --- | --- |
| 174 | 540×7 | [0, 0, 540, 7] | [0, 943, 540, 950] | [0, 1886, 1080, 1900] | sizeMismatch → normal canvas fallback |
| 181 | 7×30 | [0, 0, 7, 30] | [533, 40, 540, 70] | [1066, 80, 1080, 140] | sizeMismatch → normal canvas fallback |

Both are scaled2× into device pixels, so source/device extents fail equality.
Their clipped plan rectangles are unavailable/null because the planner returns
before clip planning; zero copied bytes/write time is preserved. Neither is one
of the eighteen retained ImageControls. All captured metadata is constant across
the six events except native timings and viewport opacity proof availability.

## Interpretation: Case A, with a remaining gap

| Reference | paintTree ms | Scope |
| --- | ---: | --- |
| Current recurring unprepared | 278.192000 | Prior generic smooth HANDLED path |
| Physical-only/second-observation warm median | 3.573729 | Prior samples2–5 |
| Immediate-admission warm median | 3.650708 | Prior samples1–5 |
| Current prepared reference | 3.532000 | Prior reference |
| Restored writePixels warm median | **1.156250** | New samples1–5, 18 native hits each |
| Historical stabilized reference | 1.016875 | Prior historical reference |

The original residual gap is 3.650708−1.016875=**2.633833 ms**. Restoring the
historical RGBA path recovers 3.650708−1.156250=**2.494458 ms**, or
**94.708283% of that gap**. Warm cost drops **68.328%** versus immediate admission.
The remaining gap is **0.139375 ms** (13.706% above historical ; 1.137× historical).
This is Case A: native counters prove all 18 cached-final viewport draws hit,
and timing approaches historical. High confidence that removal of this path
explains a substantial part of the residual regression for this workload.

Median native write time is0.451626 ms; median ImageControl total is 0.841623 ms.
The median tree cost still includes cache lookups, native call/clip/control/row
work, two scaled canvas fallback draws and instrumentation. Captured canvas
fallback time is about 0.028 ms per warm paint. These counters do not isolate the
remaining historical difference or prove those extra draws account for it.
A single five-sample process and separately measured fixed references cannot
establish exact performance equivalence; no repeat/alternate run was authorized.

No historical process ran and no historical native-hit counters were collected,
so this result does **not** prove that every historical control hit writePixels.
It does prove restored historical eligibility can handle the reconstructed final
rasters and recover nearly all measured residual cost. Prior conclusions about
generic HANDLED preventing reuse and second-observation delaying admission remain
supported and uncontradicted. The experiment is not a production optimization
design or a declaration that the historical architecture is fully restored.
Production cache-admission policy remains explicitly unresolved and unchanged.

## Validation and limitations

Before measurement: all 105 lab Python tests; 58 focused SDK tests (admission,
scale, backing, decode requirement/policy); 16 new native eligibility/default-off/
clipping/parity cases with proof reuse/generation invalidation plus existing
physical identity/surface assertions; 3 runtime headers; official 8/custom 11 Java
sources compiled; consistent ARM64 Release SDK/tcvm/Launcher build; default-only
SDK deployment; exact clean committed identities; full/parent patch hashes;
historical source blobs and exact planner comparison; package schema, all package
and build artifact hashes; complete dataset verification; offline valid protocol
accepted, missing/duplicate summary rejected; fresh exclusive launch marker.

The initial native test build failed because directly including SkCanvas required
a newer C++ standard than the existing test target. The final test uses the
existing skew test bridge. A disabled-case fixture initially saw preceding
clipped-case counters; clearing event evidence before disabling corrected it.
No eligibility changes followed that fixture failure. Original validation logs
are indexed. No measured application was launched by those failed validations.

After measurement: one runner/native exit 0 and one complete result/preflight,
all six event snapshots/geometry/byte/rejection totals, preserved hashes and
unchanged original runtime/policy section verified offline; all 105 Python tests
and git diff --check passed. No further native application or experiment ran.
Broad platform/sanitizer/matrix validation is skipped as outside this isolated
experiment. Compact-format fast paths are explicitly excluded and unmeasured.
Production branches/APIs/admission and unrelated runtime behavior are unchanged;
the checkpoint open policy section is preserved verbatim. PR #1 is unmerged.
