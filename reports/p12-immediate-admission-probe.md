<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# P12 isolated immediate-admission probe — 2026-10-03

Immediate admission eliminated the additional expensive first measured paint for
this retained top viewport. Stabilization observed and admitted all 18 successful
materializations; each measured paint used 18 cached-final hits. This is high
confidence evidence for that narrow mechanism, not a production policy decision.

## Provenance and process boundary

Benchmark implementation: `b62be52e0c4e079938a8acb0553cbb91c25dd17a`.
Isolated TotalCross: `f95c280db3d6856d17582ea31d47aaded6a0e492`.
Derived from `fc08c39499dead73b327ad259a992ab34ec42870`, the runtime preserves
parent routing exactly. The delta changes only a package-private experiment
admission switch and focused SDK tests. The switch bypasses second observation
at the existing successful-materialization admission decision, only when
physical-only routing and accounting are also enabled. Lookup, scale/generation/
backing validity, cache key/capacity, native code, decode, preparation and defaults
are unchanged relative to the parent. Normal packages exclude admission hooks.
Production branches/APIs are unchanged; source patches are published with the lab.

Exactly **one runner** and **one measured native application** ran; both exited
**0**. One complete schema-valid record and one inline preflight came from that
process. No separate warmup/preflight, replacement, historical process, alternate
policy/profile, platform build or P12 matrix ran. The native routing assertion
executable is an offline test, separate from the measured application.

The workload retained 663 manifest-ordered images and the same row/control/Image
instances: logical 540×960, viewport 540×910, drawable 1080×1920, scale 2,
179×179 tiles, position 0, 6 visible rows/18 controls. Exactly one untimed
stabilization and five timed whole-tree samples ran; no scroll movement or
preparation requests. Runtime configuration before/after matched.

Build/runner commands, source patches, artifact hashes and original evidence paths
are indexed once in [provenance.json](../experiments/p12-immediate-admission/provenance.json).
Stdout contains a UI resource initialization read-only-filesystem IOException;
it did not block preflight, measurement or successful exit. Stderr is empty.
No recovery or second launch was needed.

## Timing and complete counter sequence

ImageControl totals sum all 18 onPaint calls. Stabilization has no whole-tree
timed sample; its accounting timer records ImageControl work. All events have
rowPaintCount=6, imagePaintCount=18, position=0 and both experiment switches true.
Times are milliseconds.

| Event | paintTree | ImageControl total | Row total | Cached probes/hits/misses | Physical attempts/hits/fallbacks | Resolve calls/cache hits | Observations/admissions | Offscreen geometry materializations |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: |
| Stabilization | untimed | 350.628374 | 0.238585 | 18/0/18 | 18/0/18 | 20/0 | 18/18 | 18 |
| Sample 1 | 3.650708 | 3.312753 | 0.218126 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |
| Sample 2 | 3.569500 | 3.266665 | 0.208042 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |
| Sample 3 | 3.750875 | 3.389623 | 0.208625 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |
| Sample 4 | 3.675917 | 3.353957 | 0.207792 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |
| Sample 5 | 3.606417 | 3.300168 | 0.208082 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 |

Remaining counters are fully accounted for:

- Stabilization: copyRectPlan attempts/handled/fallbacks = 18/0/18, last status
  20490 (`0x500a`); identity attempts/hits/fallbacks = 18/0/18.
- Each sample: copyRectPlan and identity attempts/hits/handled/fallbacks = 0;
  last status = 0. The two residual resolve calls do not materialize deferred
  images: source increments the call counter before its non-deferred return.
  They also appeared in the prior warm tree; precise UI call sites are unmeasured.
- Every event: directDrawPlanExecutions, genericGeometryDraws, smoothResampleDraws,
  physicalVariant hits/fallbacks/materializations and targetColor
  hits/fallbacks/materializations = 0.

The 18 **offscreen geometry materializations** during stabilization create smooth
final rasters for reuse. They differ from direct generic/smooth destination
rendering, whose counters remain zero. Offscreen materializations are zero for
all timed samples. The index preserves all six exact snapshots/timing integers.

## Comparison and interpretation

The five-sample paintTree median is **3.650708 ms**. Sample 1 was already
a cached-final hit for all 18 controls (3.650708 ms), versus
349.357 ms in the preceding second-observation experiment: a 345.706292 ms
reduction (98.955%). That earlier stabilization observed 18/admitted 0; expensive
sample 1 observed 18/admitted 18. Immediate admission moved those admissions
into the existing stabilization, whose ImageControl total was 350.628374 ms.
Initial materialization remains expensive.

| Reference | paintTree ms | Interpretation |
| --- | ---: | --- |
| Immediate samples 1–5 median | 3.650708 | All five samples cached-final hits |
| Prior causal warm median | 3.573729 | Samples 2–5 after second observation |
| Current prepared reference | 3.532000 | Previously measured, not rerun |
| Current recurring unprepared reference | 278.192000 | Previous generic/smooth path |
| Historical stabilized reference | 1.016875 | Previously measured, not rerun |

The median is 2.154% above prior warm cost and
3.361% above current prepared cost. Five samples from one process
do not establish steady-state equivalence or a material regression. They show
the same small-millisecond cost range after reuse. The 2.633833 ms gap
above historical (3.590×) is **separate and unexplained**.

Source isolation, first-success tests and the exact counter transition support a
high-confidence narrow causal conclusion: immediate admission removes the additional
expensive measured paint caused by second observation for this workload on the
preserved physical-only routing. It does not decide production tradeoffs for
one-shot images, cache pressure, invalidation or other workloads. Production
admission remains unresolved; this experiment does not explain the residual gap.

## Validation

Before launch: 97 lab Python tests; 58 focused SDK tests (nine admission cases,
plus destination scale, backing, decode requirement and policy); native physical
identity/surface copy assertions; focused headers; normal official Java compile
(8 sources), custom compile (10 sources); macOS ARM64 Release SDK/tcvm/Launcher
build and default-only SDK deployment; clean source/benchmark identities, exact
full/parent patches, package schema, 10 package hash entries, three build artifacts,
full dataset verification; offline parser accepted valid output and rejected
truncated/duplicate summaries. An incorrect schema filename in the offline
prelaunch check was corrected before any runner/application launch.

After launch: complete protocol/result, dataset order, axes, retained instances,
runtime defaults, counter snapshots, one-process exits and evidence hashes checked
offline; 97 Python tests and git diff --check passed. Broad platform, sanitizer and
other benchmarks are skipped as outside the isolated experiment. The open
materialized cache-admission policy section is preserved verbatim. PR #1 is unmerged.
