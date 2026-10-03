<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# Admission memory comparison protocol

Exactly four processes, in order: one-shot SECOND_OBSERVATION; one-shot IMMEDIATE;
repeated-scroll SECOND_OBSERVATION; repeated-scroll IMMEDIATE. One exact isolated
SDK/native revision and default-only package serves every case. No warmup, separate
preflight, preparation or prefetch. Initial ordinary startup painting uses the
unchanged generic route; after 50 ms the experiment resets accounting once,
requires no existing final slots, enables physical-only fallback and safe
historical writePixels, and requests one normal damage paint at position 0.

Both policies retain exactly one final raster per pipeline. IMMEDIATE sets only
the existing guarded immediate-final-admission diagnostic field; SECOND_OBSERVATION
leaves it zero. Both use identical accounting and routing settings. Native
TARGET_COLOR/PHYSICAL variants retain second-observation semantics.

## Routes and timing

The list retains all 663 controls and Images in manifest order. Logical window
540×960, viewport 540×910, three columns of 179×179 tiles and 221 rows. Dataset
image-scroll/v1, 660 JPEG and 3 PNG. Runtime defaults, STANDARD storage and RASTER
renderer remain unchanged.

One-shot uses positions 0, 910, 1820, ... then the exact scrollbar endpoint.
There is no backward step. Page-boundary straddling and the shortened final step
can repaint controls; per-image paint/materialization/admission counts identify
these naturally repeated images. No paint is added to trigger second observation.

Repeated-scroll reuses the existing fixed-step distance 120 and timer cadence
16 ms: 0, 120, ... exact endpoint, then endpoint−120, endpoint−240, ... 0. The
endpoint is included once. Every position must paint before the next move. The
same nominal schedule and exact positions/order apply to both policies; actual
cold paint time and scheduler delays are measured outcomes. Positions are never
skipped to compensate for stalls. A 1 ms timer polls completion only when the
ordinary damage paint has not yet happened; it does not request another paint.

Scrolling calls normal scrollContent and painting occurs through the ordinary
window damage loop. Every observed full scroll paint is logged, including extra
paints at the same position. The validator rejects skipped/out-of-route positions
and requires all 663 controls encountered. Extra paints are never discarded or
silently normalized; any between-policy difference is an analysis limitation.

## Accounting and measurement boundaries

Explicit experiment diagnostics enable one timer around each successful final
resolve and one around the scroll paint tree. The resolve timer includes decode,
geometry and presentation synchronization; it is not a smooth-only CPU timer.
Existing row/Image clocks run identically in both policies. JSON/frame capture
occurs after paint timing and contributes to workload wall time. A compact memory
progress record at the first and every fiftieth paint preserves partial evidence
if the process fails before the final record. Native
writePixels clocks and per-draw record vectors are disabled in summary mode;
eligibility, opacity proof, clipping and copy behavior are unchanged.

Primitive Java ledgers track actual slot bytes/count, installation, replacement,
detach, invalidation, exact scale/generation keys, pending candidates and per-image
paints/materializations/admissions/hits. Native storage uses physical dimensions,
format and rowBytes/backingBytes. Texture release alone retains the cached Image
and software backing; it is not reported as a slot detach or native free.

Native diagnostic tags hold raw addresses without ownership. Decoded root
backings are tagged when independently available; geometry-derived records are
tagged at native registration within the tracked resolve context, including any
temporaries awaiting GC. This workload has one smooth node, so those outputs are
final-raster representations. All native backing totals remain separately visible.
Other native storage is total minus tagged derived minus tagged decoded at the
same snapshot; peak totals must not be subtracted to fabricate a category peak.
Root-referenced decoded bytes are censused separately at the end.

No forced GC occurs during traversal. Natural ending memory is recorded first.
Two diagnostic Vm.gc calls then produce a separately labeled collection-lag
snapshot with the retained UI unchanged; this is never substituted for natural
peak/end memory. Native released counts report real backing release events, while
slot detaches report reference removal. Diagnostic maps/Java ledgers and other
non-backing heap allocation are outside native backing byte totals.

## Failure and interpretation

Each case receives an exclusive launch marker and fresh results directory.
Preserve every first exit, stdout/stderr/config/preflight and partial result. No
surprising valid/partial result is replaced. No fifth process is authorized by
this protocol. Offline recovery is preferred for parser/schema failures.

Report per-case lifecycle, natural cache-owned and all-native-derived peak/end,
source/decoded and other native storage, post-GC diagnostics, work/paint/wall/stalls,
and per-workload A/B deltas. Admission rate uses unique admitted exact keys over
unique materialized exact keys. Reuse counts must name their denominator (hits per
admitted key and fraction of admitted controls with later hits). The theoretical
663×358×358×4=339,890,928 byte bound is an estimate, not measured retention.
Recommend final-raster admission only. Do not change production behavior or native
speculative admission, propose a global cache without evidence, or merge PR #1.
