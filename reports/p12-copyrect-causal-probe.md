<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# P12 copyRect causal probe

The predicted transition occurred: expensive stabilization (observation one),
expensive measured sample 1 (observation two and admission), then four fast
cached-final samples. Changing only the experimental copyRect fallback route,
while retaining second-observation admission, ended the repeated smooth work.
This is strong causal evidence that generic draw-plan handling prevents final-
raster reuse in the observed current-master unprepared path. It is not a product
fix or a decision to replace admission policy.

## Experiment and provenance

The lab implementation measured was `e9cb47bbe2750ec3a19341514283b9f19002d8b4`.
Custom TotalCross source tested: `fc08c39499dead73b327ad259a992ab34ec42870`,
based on current-master reference `5a44f503bf6fa1bec350f1218f4d501a70fc4812`.
The runtime commit exists on isolated local branch `codex/p12-copyrect-causal`;
its exact source patch is committed in the lab at
[experiments/p12-copyrect-causal/runtime.patch](../experiments/p12-copyrect-causal/runtime.patch).
It is reproduced on the base with `git apply --unidiff-zero runtime.patch`.
No production runtime branch was changed or merged. The existing production
Java copyRect, ImagePipeline admission/cache methods, JPEG/encoded-image source,
preparation and typed runtime defaults are identical to the base. Only experiment
routing and enabled test accounting differ.

One runner launched **one measured TotalCross/native application process**;
runner exit **0**, explicit native child exit **0**, one complete valid run record
and final summary, no failures. Inline preflight came from that same process.
No measured replacement, warmup, preparation, scrolling, alternate profile/policy,
historical run, Windows run or P12 matrix ran. The focused native surface-routing
unit-test executable ran once before measurement; it is a separate offline test,
not a TotalCross benchmark application launch.

The package uses only default with the experiment-local `CausalDefault` entry,
which keeps the existing default UI and installs hooks. The switch stays off
through normal startup and turns on immediately before the explicit stabilization.
Normal benchmark builds exclude these hooks and still compile against official
7.2.2. The official binary cannot enforce the routing change, so SDK, tcvm and
Launcher were built from the one exact custom runtime revision, Release macOS
arm64, using existing pinned depot artifacts. No binaries from different
TotalCross revisions were mixed.

The canonical [provenance/hash index](../experiments/p12-copyrect-causal/provenance.json)
records SDK JAR, Launcher, libtcvm hashes, exact configure/build/runner commands,
package identity, process exits/counts and preserved first-process artifact paths
and hashes. Raw output and normal build artifacts remain local. Stdout's UI
resource initialization warning (`IOException`, read-only filesystem) did not
prevent preflight/result emission or successful exit; stderr was empty.

## Fixed workload and measurement

Exactly the existing 663-image `image-scroll/v1` dataset, manifest order and top
position 0 were used: application 540×960, viewport 540×910, drawable 1080×1920,
scale 2, tile width 179, six visible rows/eighteen ImageControls. Control, Image and
row references were retained throughout. Every stabilization/sample painted
exactly 6/18; default runtime configuration was verified by preflight and identical
before/after reports. No retired raw mask API was used or substituted. Preparation
requests were zero. One untimed whole-tree stabilization repaint preceded exactly
five measured `paintTreeOnly` calls.

Stabilization had no whole-tree timing sample; cumulative ImageControl instrumentation
reported 348.214998 ms. This inner accounting does not turn stabilization into a
sixth measured whole-tree sample.

## Five samples and counters

All counts below are per paint; counters reset before each event. Cached =
probe/hit/miss, copy = physical attempt/hit/fallback, resolve = resolveForDrawing
calls/cache hits inside resolve, variant = observations/admissions, native mat =
offscreen native geometry materializations. Direct generic/smooth counters track
draw-plan execution on the destination, separately from materializing a smooth
geometry variant offscreen.

| Event | paintTree ms | ImageControl total ms | Cached P/H/M | Copy A/H/F | Resolve calls/hits | Variant O/A | Native mat | Direct generic/smooth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Stabilization (untimed) | — | 348.214998 | 18/0/18 | 18/0/18 | 20/0 | 18/0 | 18 | 0/0 |
| 1 | 349.357000 | 348.897248 | 18/0/18 | 18/0/18 | 20/0 | 18/18 | 18 | 0/0 |
| 2 | 3.588625 | 3.275458 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 | 0/0 |
| 3 | 3.576917 | 3.277625 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 | 0/0 |
| 4 | 3.570500 | 3.264083 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 | 0/0 |
| 5 | 3.570541 | 3.271419 | 18/18/0 | 0/0/0 | 2/0 | 0/0 | 0 | 0/0 |

Stabilization/sample 1 each had 18 copyRect draw-plan attempts, 0 handled and
18 fallbacks; 18 identity attempts, 0 hits, 18 fallbacks; last native draw status
20490 (`0x500a`: physical-copy and identity attempted/fallback, no HANDLED or
generic/smooth bits). Samples 2–5 had zero copyRect draw-plan attempts/handled/
fallback, zero physical/identity attempts/hits/fallback and reset last status 0.
Direct draw-plan execution count was zero throughout. Disabled target-color/
physical-variant hits/materializations/fallback counters stayed zero throughout.

The stabilization admitted none of its 18 observations. Sample 1 observed all
18 again and admitted all 18. Samples 2–5 recorded 18 cached-final hits each,
no misses, no new observations/admissions and no offscreen materializations.
They bypassed the draw plan and the final-raster resolve path for the visible
controls. Thus repeated direct generic smooth drawing was suppressed throughout
this experiment, and offscreen geometry/smooth materialization ceased after
admission. The counted native materializations in the first two events use the
existing smooth operation; they are not direct copyRect generic draws.

There are 20 total resolve calls in the first two events and 2 in each cached
paint. With zero hits inside resolve and 18/0 observations respectively, the
unchanged resolveForDrawing code proves that two calls per paint returned
non-deferred Images (`pipeline == null`, returns `this`). Their call-site identities
were not instrumented. They are not failed final-raster admissions or repeated
materializations. Cached-final probing precedes resolve and is counted separately,
which explains why inner-resolve cache hits stay zero while cached-final hits are
18. All counters are aggregate whole-tree scope; no new per-control timing pass
was performed.

Path classifications are: stabilization = cached-final miss → physical/identity
fallback → resolve → materialize → first observation; sample 1 = the same path →
second observation/admission; samples 2–5 = cached-final hit → ordinary raster copy.
The instrumentation includes zero-valued counters, so absence is observed rather
than omitted or inferred from timing alone.

## Comparison and causal conclusion

| Reference / phase | paintTree ms | Interpretation |
| --- | --- | --- |
| Current-master unprepared reference | 278.192 p50 | Generic smooth HANDLED on recurring uncached paints |
| Experimental measured sample 1 | 349.357000 | Materialize full variants and admit second observations |
| Experimental samples 2–5 | 3.570500–3.588625; median 3.573729 | All 18 cached-final hits, no geometry materialization |
| Current-master prepared reference | 3.532 p50 | Previously materialized/reused final rasters |
| Historical f5dad132 unprepared reference | 1.016875 p50 | Historical stabilized path with immediate admission |

Warm experimental median is 77.843619× faster (98.715373% lower)
than the recurring current-master reference, 1.181455% above
current prepared cost and 3.514423× historical stabilized cost.
The five measured values contain one expensive admission paint and four cached
paints; they should not be presented as a five-sample steady-state distribution.
The separate stabilization plus those five samples yielded the expected two
expensive events followed by four fast events.

**Confidence is high for this workload/configuration and routing mechanism.**
The narrowly enabled routing change allowed the otherwise-blocked resolve path;
unchanged second-observation admission then produced actual cached-final hits
and removed recurring materialization/resampling. Together with the prior
18-control generic/smooth HANDLED evidence, the counters support the proposed
cause of recurring unprepared paint cost. They do not merely show a timing drop.

Remaining uncertainty: this is one successful process and uses a custom Release
runtime with test accounting, compared with earlier reference processes. It
establishes the routing mechanism, not a precise population performance estimate,
a final production architecture or complete explanation of the residual difference
from historical ~1 ms. The larger first-paint cost may reflect full-variant
materialization rather than clipped direct drawing (the bottom row previously
had only three visible pixels); that attribution was not separately tested.
No unavailable raw Image mutation generation is inferred. Immediate-versus-second-
observation admission remains a separate unresolved decision.

## Validation and scope

Passed before launch: eight focused causal contracts and all 90 Python tests;
focused native surface routing assertions covering physical hits, rejected
physical-only routing and normal fallback; SDK `gradlew-agent dist -x test`;
macOS arm64 Release tcvm/Launcher/test build; current-year header validation
for six runtime files; benchmark `javac --release 8` against both official SDK
(normal package) and custom SDK (causal package); custom deployment and complete
package/runtime/dataset hash checks; valid and truncated/duplicate protocol
fixtures. Clean source/tooling implementation was committed before measurement.

Post-run offline validation rechecks record/sample order, all six 6/18 paint
counts, preserved references, runtime defaults, five timings/counters, original
artifact hashes and explicit single-process exits. `python3 -m unittest discover
-s tests` and `git diff --check` passed after the report update. No broader platform,
sanitizer or benchmark validation was run: this is a bounded causal experiment,
not authorization for a production fix or release gate. Production cache
admission, eligibility, decode/preparation/default policies and unrelated behavior
remain unchanged outside the explicitly enabled isolated experimental route.
