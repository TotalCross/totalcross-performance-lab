# P12 production-candidate closure

## Status

P12 is complete. The image-rendering benchmark suite, dataset contracts,
cross-platform runners, package provenance checks, causal probes and durable
reports are ready to merge as reusable performance-lab infrastructure.

The production correction was merged through
[TotalCross PR #488](https://github.com/TotalCross/totalcross/pull/488).

## Provenance

- TotalCross production candidate:
  `bdd27273ead29bab320cba43b9ebad27be9b87ad`
- Performance-lab source used for the final candidate runs:
  `264b9fba8581f08f3c0e4f31529831b7270d2c95`
- Dataset: `image-scroll/v1`
- Dataset manifest SHA-256:
  `4dac75139e4e7095f5843a696f5fcd84055bf798e90b49614d6e4243120f5dbe`
- Logical display: 540x960
- Drawable: 1080x1920
- Viewport: 540x910
- Display/content scale: 2

Raw packages, logs and run outputs remain outside Git by design. Exact package
hashes, commands and local result paths are recorded in the TotalCross final
reconstruction evidence and in the P12 investigation records.

## Final production-candidate results

Static warm draw-path probe:

- `paintTree`: 5.509 ms
- cumulative ImageControl paint: 4.984 ms
- cached-final: 18 probes / 18 hits / 0 misses
- generic-geometry draws: 0
- smooth-resample draws: 0

Repeated scroll used 3 warmups plus 10 measured runs:

| Route | p50 | p95 | max | >100 ms |
| --- | ---: | ---: | ---: | ---: |
| cold forward | 70.456 ms | 73.900 ms | 98.178 ms | 0 |
| warm reverse | 16.348 ms | 16.743 ms | 30.483 ms | 0 |
| warm forward | 16.313 ms | 16.627 ms | 47.995 ms | 0 |

Across all 9,720 measured route frame intervals, none exceeded 100 ms.

The generic admission regression also confirms that first generic use leaves the
final-raster slot empty and second observation admits the single final-raster
entry.

## Causal conclusions

The investigation closed three production questions.

First, the recurring raster regression came from copyRect routing: after a
physical-copy miss, generic/smooth native drawing could consume the request and
prevent Java from materializing a reusable final raster. The production fix
restores physical-only probing followed by Java final-raster fallback.

Second, the one-slot cache and its admission rule are separate concerns. The
controlled memory experiment showed that second-observation saves retention for
true one-shot consumers, while repeated persistent scrolling gains no retained
memory benefit and pays a duplicate materialization. Production therefore keeps
second-observation for generic/transient resolution and allows immediate
admission only for deterministic persistent UI ownership.

Third, the isolated historical opaque device-1:1 write path reduced the warm
median from about 3.651 ms to about 1.156 ms, recovering about 94.7% of the
remaining historical gap. Production reconnects that behavior through the typed
`opaqueWritePixels` policy with conservative eligibility and fallback.

The detailed evidence remains in:

- `reports/p12-copyrect-causal-probe.md`
- `reports/p12-immediate-admission-probe.md`
- `reports/p12-writepixels-warm-path-probe.md`
- `reports/p12-materialized-admission-memory-probe.md`
- `reports/p12-physical-mapping-probe-2026-10-03.md`
- `reports/p12-investigation-checkpoint.md`

## Limits

The final production package had runtime diagnostics disabled/unsupported for
the required counters. The final repeated-scroll run therefore does not claim
materialization/admission totals, writePixels hit counts, materialization time,
or live/peak derived-raster memory.

The dedicated Windows performance benchmark was not run. TotalCross PR #488 did
pass Windows and `windows-native-legacy` build validation, so this is a
performance-evidence gap rather than an unresolved implementation or build
blocker.

## Next use of the lab

Do not reopen P12 merely to reproduce the completed causal probes. New work
should extend the reusable lab toward bounded diagnostic packages for macOS and
Windows, using exact runtime provenance and a small hypothesis-driven
configuration matrix rather than exhaustive combinations.
