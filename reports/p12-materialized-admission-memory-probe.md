<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# P12 single-slot final-raster admission: memory and duplicate work

Recommend **IMMEDIATE admission for the final materialized raster of ordinary
persistent visible image controls**, retaining exactly one slot and the existing
exact scale/generation/invalidation contracts. In the repeated-scroll workload,
both policies admitted all 663 images and retained exactly the same bytes.
Immediate admission avoided 663 expensive materializations and reduced workload
time by 11.365 s. Second-observation provides a real retention benefit for the
controlled one-shot shape: 272,220,336 fewer cache-owned bytes, but only for 531
images that were never used again. This experiment recommends architecture; it
does not implement a production fix or change native speculative admission.

## Identity, execution and recovery

Benchmark implementation: `b82701c43a783e30f8cd920347db31eb1e71e99e`.
Isolated TotalCross revision: `1944f203c4bf2130ab8fda1497d0922bacacfaf0`, based on
`18baece1f199ab5d2e7cad6d864c40c188bd1bab`. One consistent Release macOS ARM64
SDL/Skia runtime, SDK and default-only package served all four applications.
The [provenance index](../experiments/p12-admission-memory/provenance.json)
contains exact build commands, SDK/Launcher/libtcvm hashes, full and parent
patches, unchanged native speculative function hashes and all process evidence
hashes. The [analysis/evidence record](evidence/p12-materialized-admission-memory-probe.json)
preserves per-image accounting, frame positions/times, complete aggregates,
calculations and original evidence paths/hashes.

Exactly **four measured native application processes**, in this order:

| Case | Workload | Policy | Native exit | Runner exit | Complete valid records |
| --- | --- | --- | --- | --- | --- |
| 1 | one-shot | SECOND_OBSERVATION | 0 | 1 | 1, recovered offline |
| 2 | one-shot | IMMEDIATE | 0 | 0 | 1 |
| 3 | repeated-scroll | SECOND_OBSERVATION | 0 | 0 | 1 |
| 4 | repeated-scroll | IMMEDIATE | 0 | 0 | 1 |

There were no warmup, separate preflight, historical, Windows, replacement or
other measured applications. Each inline default preflight ran in its measured
application. Before measurements, clean exact sources, all ten packaged file
hashes, three build artifact hashes, full/parent patches and the complete
`image-scroll/v1` dataset passed verification. Dataset manifest SHA-256:
`4dac75139e4e7095f5843a696f5fcd84055bf798e90b49614d6e4243120f5dbe`.

Two tooling failures are preserved, without replacing a native measurement.
An initial CLI invocation used unsupported `--profiles` instead of `--profile`;
it exited 2 before creating any native process directory. After correction,
case 1 emitted its complete run/summary and exited 0. Its runner then exited 1
because an overly broad schema text edit had changed tileWidth's const from 179
to 169 while changing nominal cadence from 17 to 16. The original record actually
has the correct 179 tile width and passed every other contract after offline
schema correction. Cases 2–4 used an analysis-only schema correction wrapper;
the deployed Java package, SDK, runtime and configuration remained identical.
No application was rerun. The durable schema now requires 179 and a regression
test fixes both tile and cadence constants. Original logs/configs/exits and the
correction wrapper/launch commands are hashed in the evidence index. UI startup's
read-only-filesystem resource warning did not prevent any complete record.

## Controlled policies, routes and accounting

The [exact protocol](../experiments/p12-admission-memory/protocol.md) defines all
boundaries. Both policies use the same one-slot ImagePipeline and exact key;
only the guarded Java final-raster admission selector differs. Physical-only
copyRect fallback and historical safe opaque device-1:1 writePixels eligibility
are identical. Decode, JPEG denominator selection, STANDARD storage, RASTER
renderer, ownership, generations, invalidation and prefetch behavior are unchanged.
Native TARGET_COLOR/PHYSICAL observation/store bodies are byte-identical to the
parent and pass explicit miss/materialize/hit tests. Their measured variant
counters are zero under default configuration; this experiment does not evaluate
changing those policies. Explicit async preparation/prefetch is not exercised.

Both cases retain the existing list, all 663 ImageControls/Images in manifest
order, 221 rows and three columns. Logical window 540×960, drawable 1080×1920,
viewport 540×910, 179×179 tiles, display scale 2. Every final raster is actual
358×358 RGBA8888 (format 0), rowBytes 1,432, backingBytes **512,656**.

One-shot: 0, 910, 1820, ... 38220, exact endpoint **39091**: **44** normal damage
paints. It never scrolls backward. **531 images painted once and 132 twice**
because of unavoidable boundary overlap; 795 ImageControl paints total. There
are no synthetic resolves or extra paints to trigger admission.

Repeated: existing fixed step **120**, 0 to exact endpoint 39091, then −120 steps
back to 0, endpoint painted once. The existing **16 ms nominal timer cadence**
is reused, with no skipped positions and each position painted before the next
move. There are **653** normal damage paints and **11,778** ImageControl paints.
Every image painted at least three times; most painted 18 or 19 times. The
complete per-image paint histogram is in the evidence JSON. Both policies have
identical ordered positions, per-image paint counts and paint sequences. All
four cases have **zero extra paints**. Actual elapsed intervals differ with cold
paint cost and scheduler delay; these are measured outcomes, not identical wall
clock schedules. No broad matrix was introduced.

Explicit experimental diagnostics time each successful final resolve and scroll
paint tree. Resolve timing includes decode, geometry and synchronization; it is
not a smooth-only CPU timer. Frame/JSON accounting happens after paint timing
and contributes to workload wall time. Native writePixels event clocks and
per-draw record retention are disabled; their time counters remain zero. The
first/every-fiftieth progress record preserves partial evidence if needed.

Cache ownership and native allocation lifetime are separate. Clearing/replacing
a slot removes its reference; releaseTextureOnly alone retains the Image and
software backing. No forced GC occurs during traversal. Natural ending memory
is captured first, then two diagnostic GC calls observe collection lag with the
UI still retained. These post-GC results never replace measured natural peaks.
Primitive ledgers/raw-address tags do not own Images or backings. Their own heap
memory, encoded files and other Java/C++ allocations are outside native backing
byte totals.

## Lifecycle and admission

All four cases encounter **663 unique images**, see **663 unique exact keys**,
and have zero slot replacements, detaches/evictions and invalidations. No pending
key is overwritten (`discardedPending=0`). Native offscreen geometry counts and
Java observations equal the registered materialization counts below.

| Case | Materializations / observations | Admissions / unique admitted keys | Cached-final probes | Hits | Misses | Pending keys never admitted |
| --- | --- | --- | --- | --- | --- | --- |
| 1 one-shot second | 795 | 132 | 795 | 0 | 795 | 531 |
| 2 one-shot immediate | 663 | 663 | 795 | 132 | 663 | 0 |
| 3 repeated second | 1,326 | 663 | 11,778 | 10,452 | 1,326 | 0 |
| 4 repeated immediate | 663 | 663 | 11,778 | 11,115 | 663 | 0 |

Admission rate (unique admitted keys / unique materialized keys): **19.9095%,
100%, 100%, 100%**, respectively. Reuse after admission, measured as fraction of
admitted images with later hits: **0%, 19.9095%, 100%, 100%**. Hits per admitted
key: **0, 0.199095, 15.764706, 16.764706**. The 132 one-shot second-use admissions
occur on each image's last paint and have no subsequent hit. Its 531 pending
candidates remain unadmitted when the traversal ends; they are route-irrelevant
but their Image objects remain alive, preserving normal list lifetime.

## Measured memory and allocation lifetime

Every listed natural peak equals natural end in these runs; no tagged derived
or decoded backing was released during traversal. Counts/bytes come from actual
native backing storage, not logical dimensions or an allocation estimate.

| Case | Cache-owned peak/end count | Cache-owned peak/end bytes | All native derived peak/end count | All native derived peak/end bytes | Allocated final bytes |
| --- | --- | --- | --- | --- | --- |
| 1 | 132 | 67,670,592 | 795 | 407,561,520 | 407,561,520 |
| 2 | 663 | 339,890,928 | 663 | 339,890,928 | 339,890,928 |
| 3 | 663 | 339,890,928 | 1,326 | 679,781,856 | 679,781,856 |
| 4 | 663 | 339,890,928 | 663 | 339,890,928 | 339,890,928 |

Cache-owned bytes are about **64.536 MiB** for case 1 and **324.145 MiB** for the
other cases. All native derived storage includes unadmitted/duplicate rasters
awaiting GC, so second-use's cache retention benefit must not be confused with a
lower natural allocation peak: it allocated more derived bytes in both workloads.

Decoded/source native storage is identical in every case: **663 records,
679,314,768 bytes live/peak**, matching the ending root-referenced decoded census.
Other native backing storage is **143 records / 408,256 bytes** at natural end,
computed by subtracting source and derived categories at the same snapshot.
No category peak is fabricated by subtracting unrelated peak values.

| Case | All native peak/end count | All native peak/end bytes | Post-GC derived live count/bytes | Derived native releases during diagnostic GC |
| --- | --- | --- | --- | --- |
| 1 | 1,601 | 1,087,284,544 | 132 / 67,670,592 | 663 |
| 2 | 1,469 | 1,019,613,952 | 663 / 339,890,928 | 0 |
| 3 | 2,132 | 1,359,504,880 | 663 / 339,890,928 | 663 |
| 4 | 1,469 | 1,019,613,952 | 663 / 339,890,928 | 0 |

After diagnostic GC, derived live bytes exactly match slot-owned bytes in every
case. The source/decoded category remains retained. These native release counts
are real backing frees, distinct from the zero slot detaches/replacements.

The dimension-multiplication theoretical upper bound for one final slot across
663 pipelines is **663×358×358×4 = 339,890,928 bytes**. This is an estimate derived
from uniform raster geometry. It happens to equal the measured fully admitted
footprint, but it does not include source storage, native temporaries or other
heap/storage and is not used as a substitute for measured memory.

## Work, time and stalls

Seconds below exclude the post-run GC from workload/paint/materialization times.
Application wall includes startup, inline preflight, reporting and diagnostic GC.

| Case | Workload s | Total paint s | Final-resolve materialization s | Application wall s |
| --- | --- | --- | --- | --- |
| 1 | 17.052685 | 16.782956 | 15.077021 | 19.866258 |
| 2 | 14.694163 | 14.392488 | 12.707480 | 16.234106 |
| 3 | 33.765818 | 27.707400 | 25.099017 | 35.567524 |
| 4 | 22.401074 | 15.110912 | 12.556925 | 24.094973 |

| Case | Paint p50 ms | p95 ms | p99 ms | max ms | Paints >16.667 ms | >22.222 ms | >100 ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 380.786 | 391.857 | 419.111 | 439.145 | 44 | 44 | 44 |
| 2 | 326.581 | 333.048 | 371.979 | 387.119 | 44 | 44 | 44 |
| 3 | 57.790 | 123.052 | 126.292 | 344.587 | 327 | 327 | 107 |
| 4 | 1.365 | 67.299 | 69.487 | 346.318 | 216 | 216 | 1 |

These cold-inclusive route statistics are not static warm-paint benchmarks.
Immediate still pays the first materialization for each new image. In repeated
scrolling it removes the second expensive materialization, shifting most frames
to ordinary cache reuse; no explicit preparation is involved.

## Paired deltas and architectural interpretation

Memory deltas are IMMEDIATE minus SECOND_OBSERVATION. Saved time/work is SECOND
minus IMMEDIATE; positive values mean immediate avoided work.

| Comparison | One-shot | Repeated scroll |
| --- | --- | --- |
| Peak cache-owned bytes delta | +272,220,336 | 0 |
| Ending cache-owned bytes delta | +272,220,336 | 0 |
| Peak cache-memory increase | +402.2727% | 0% |
| Avoided materializations | 132 | 663 |
| Avoided allocated final bytes | 67,670,592 | 339,890,928 |
| Materialization time saved | 2.369541 s | 12.542092 s |
| Paint time saved | 2.390468 s | 12.596488 s |
| Workload time saved | 2.358522 s | 11.364743 s |
| Natural all-native-derived peak/end delta | −67,670,592 | −339,890,928 |

Second-use has a substantial sustained **cache ownership** benefit in a genuinely
one-shot traversal, retaining 80.09% fewer final rasters. Immediate spends about
259.610 MiB extra retained final memory there to save 132 materializations and
2.359 s of workload time. Most of its 663 admitted images are never reused.
That benefit is real even though collection lag makes second-use's natural
native derived peak larger before GC.

The representative repeated route **completely defeats the intended retention
benefit**: all 663 final rasters are admitted by either policy, with identical
peak/end cache-owned memory and 100% reuse of admitted controls. Second-use
instead pays an extra materialization for every image, an extra 339,890,928
allocated final bytes, 12.542 s of resolve time and 106 additional >100 ms paint
stalls. Immediate reduces workload time by about 33.657%. It also reduces natural
native derived peak by one full duplicate set while temporaries await GC.

Therefore use immediate admission for ordinary persistent visible controls and
keep the single slot. If production needs to distinguish a declared one-shot
consumer, a deterministic rule could select SECOND_OBSERVATION for an explicitly
transient/one-shot rendering context and IMMEDIATE for persistent UI controls.
That would be an explicit context contract, not a prediction from timing, size or
observed scroll speed. No such rule is implemented or measured here; a universal
immediate policy for all one-shot consumers is not justified by these data.
There is no measured capacity failure or specified memory budget proving the
one-slot architecture insufficient, so no global cache/byte-budget redesign is
proposed. Native TARGET_COLOR/PHYSICAL second-use remains outside this decision.

## Original P3 rationale and confidence

Commit **`d27351800bd09441a76c2de91ba79c50ea34c452`**, titled
`feat(image): bound raster variant state`, replaced two-slot first-use/LRU Java
materialized caching with one cached raster plus a pending exact key and
second-observation admission. Its purpose was to bound retained derived state
and avoid retaining one-use representations. The same commit introduced bounded
native speculative variant state. Its SDK smoke/unit and native contract changes
checked behavior and state bounds; it did **not** supply a representative
663-image scrolling memory/performance comparison proving the admission tradeoff.
Capacity reduction and admission delay were separate architectural choices; this
experiment holds capacity at one and supplies the missing policy evidence.

Confidence is high for this controlled route's lifecycle/memory conclusions:
exact keys, actual storage bytes, matching per-image paints, identical package,
zero extra paints, accounting conservation and post-GC ownership agreement all
hold. Timing estimates have one process per condition, deterministic order, one
macOS ARM64 host/dataset, no replicate-based variance/CI and possible host/OS
cache/scheduler effects. The 663-control list retains all roots and pipelines;
applications that recycle/remove controls can have different lifetime behavior.
No native memory-pressure GC was forced during measurement. Absolute aggregate
memory includes the dataset's retained decoded roots and is not solely a cache
policy result. Warm writePixels differences for nonopaque PNGs remain identical
between policies. Results do not establish memory budgets for other devices,
renderer/storage profiles or native speculative variants.

Validation before measurements: **63 focused SDK tests**, native category
installation/release and unchanged speculative admission tests plus prior
writePixels/physical/surface tests, normal official SDK and isolated SDK Java
compilation, Release macOS ARM64 SDK/tcvm/Launcher build and headers. Post-run:
all four original protocol records/preflights/exits and indexed hashes validate,
paired routes/paint counts match, and cheap lab tests/diff checks pass. No
production branches were changed, no production fix was attempted, and PR #1
remains unmerged.
