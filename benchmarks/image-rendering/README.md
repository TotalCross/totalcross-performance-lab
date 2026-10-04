# Image rendering benchmark contract

This suite measures the reconstructed TotalCross image and scroll behavior
without changing runtime code. It uses the immutable `image-scroll/v1` corpus
and selects behavior through the production typed runtime annotations on its
entry classes. The corpus stays outside Git.

## Workload families

- **decode** — filesystem or generated TCZ input, full or half scale, and
  sequential or seeded-random order. Seeded order uses Fisher-Yates with
  xorshift32 and seed `12012026`. Each measured cell starts a fresh process.
- **scroll** — the pinned corpus is displayed as 663 square `ImageControl`s in
  221 green rows of three inside the blue two-container scroll hierarchy.
  Directional results are kept separate for `cold-forward`, `warm-reverse`, and
  `warm-forward` passes.
- **preparation** — default/no-preparation reference and explicit
  `ScrollContainer.prepareForDisplay(...)` using either production worker.
- **pacing** — current production flick timer and synthetic work cadences. The
  update-listener/flick selector is package-private in the pinned runtime, so
  the suite does not depend on it. No runtime scheduling switches are exposed.

The default logical window size is 540x960, with 179px square tiles and a
vertical scroll pane inset into the window. The host drawable size and display
scale are recorded separately. A fresh process is not described as a cold
filesystem cache; `cold-forward` names the first traversal workload phase.

## Named image profiles

| Profile | Typed production configuration |
| --- | --- |
| `default` | No runtime annotation; production defaults. |
| `target-color` | Target color conversion enabled. |
| `physical-variant` | Physical variant cache enabled. |
| `raster-variants` | Target color conversion and physical variant cache enabled. |
| `compact` | Compact image storage. |
| `scroll-reuse` | Scroll raster reuse enabled. |
| `prepared-legacy` | Legacy per-entry worker and explicit preparation. |
| `prepared-semaphore` | Semaphore process worker and explicit preparation. |
| `combined-standard` | Standard storage, both raster variants, scroll reuse, semaphore worker. |
| `combined-compact` | Same as combined-standard with compact storage. |

Every non-default entry uses `@RuntimeConfiguration` and
`@ImageRuntimeRule`. The workload code is shared; profiles are separate entry
classes. The selected class name is the machine-readable profile identity.
`RuntimeConfigurationReport.describe()` is captured verbatim for human
provenance and is never parsed.

## Results and diagnostics

Applications emit `TCBENCH_JSON ` followed by one JSON object per line. Run
records use `schemas/benchmark-run-v1.schema.json`; the shared runner validates
them before writing a summary using
`schemas/benchmark-summary-v1.schema.json`. Environment fields follow
`schemas/environment-v1.schema.json`. Durations are integer nanoseconds in
records; rendered reports convert them to milliseconds.

The primary timing matrix runs with diagnostics disabled. Separate diagnostic
runs enable only the public IMAGE/PREFETCH/SCHEDULING domains needed by that
workload, then record before/after `RuntimeDiagnosticSnapshot` values and
`deltaSince`. Aggregate domain/kind values are never labeled as private
per-feature counters.

Frame summaries include p50, p95, p99, maximum interval, and the shares at or
under 22.222 ms and 16.667 ms. Mean FPS alone is not used to claim a frame
budget was met.

## Preconditions and commands

Use the runner README for build and platform setup. Dataset-dependent runs
require a successfully verified dataset before preflight. Each measured cell
uses a fresh process, a finite timeout, and strict child exit/output checks.
The runner records the exact TotalCross source revision and runtime/package
hashes. Raw records and logs stay in ignored `.local-data/` or `results/`
directories.

TCZ decode resources are generated from the verified dataset and embedded in
each profile package. Filesystem decode and scroll workloads read the verified
cache through TotalCross file streams.

RDP or hosted-CI timings are not treated as stable performance baselines.
Comparisons are made only within the same host, dataset identity, runtime
revision, build mode, dimensions, renderer/session, and measurement protocol.
The report presents per-run tail statistics and failure counts; it does not
produce a synthetic performance score or recommend the combined profiles for
production.


## Static native draw-path probe

`draw-path-probe` is a focused default-only scroll mode at 540x960, with inline
RASTER/STANDARD preflight and diagnostics disabled. It performs one ordinary
untimed stabilization repaint at position 0, resets existing SDK test accounting,
and measures one direct paint-tree call. It then resets accounting and paints
each of the same eighteen visible ImageControls exactly once in manifest order,
without preparation, scrolling, another stabilization paint or Image replacement.

The benchmark-only `totalcross.ui.image.ImageDrawPathProbeAccess` source accesses
package-private accounting already present in the SDK. It is included in the
application JAR/TCZ and does not modify or replace SDK classes. Result counters,
raw status integer/hex, decoded status flags, classifications and per-control
timings are checked with `schemas/image-draw-path-probe-v1.schema.json` and the
runner's consistency checks. A status describes the last plan attempt; controls
with multiple attempts are explicitly marked. Physical-copy accounting exposes
hits only; physical-copy attempt/fallback counters are unavailable.
Native identity status flags also participate in classification: the Image
identity hit/fallback getters stay zero on the copyRect native entry point.
The raw getters remain separate counters and are never replaced with inferred
counts. Hex formatting preserves the full status instead of using native
`Integer4D.toHexString`, which emits only four uppercase digits.

Use a package built from committed benchmark tooling and the validated official
runtime, then launch one measured process with no warmups:

```sh
python3 runners/run.py image-rendering scroll --profile default \
  --scroll-driver draw-path-probe --rounds 1 --warmups 0 \
  --timeout-seconds 180 --width 540 --height 960 \
  --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 \
  --package-manifest /path/to/package-manifest.json \
  --results-dir .local-data/results/image-rendering-draw-path-probe \
  --require-default-scroll-preflight --fail-fast
```

This mode does not run the scrolling workload or call `prepareForDisplay`.
Target-color/physical-variant activity under the default policy is recorded as
unexpected rather than hidden or forced to zero. The materialized cache-admission
policy remains a separate unresolved question; this probe changes no policy.

For the original probe at benchmark commit `b9506e8`, saved stdout contains a
complete measurement but its hex string is truncated and its classification
omits native identity fallback when the Image getter is zero. Recover only those
two presentation fields offline; preserve the emitted fields, counters and
timings, and do not launch another process:

```sh
python3 tools/analyze_draw_path_probe.py --stdout /path/to/stdout.log \
  --package-manifest /path/to/package-manifest.json \
  --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 \
  --output /path/to/analysis.json --recover-legacy-status
```

Recovery requires that exact benchmark commit and the known original encoding
and classification. The analyzer checks package hashes, preflight, the protocol,
manifest order and the same result contract as the runner. Ordinary runner
validation remains strict.

## Physical mapping metadata probe

`physical-mapping-probe` uses the same default-only inline preflight and top
viewport. One stabilization repaint creates normal draw plans; the helper then
reads the eighteen retained Images at each control's actual Graphics scale. It
records immutable plan fields, backing metadata, public Graphics translation
and clip, and drawable dimensions. It performs no timed paint or preparation.

The native source resets the canvas matrix and applies Graphics contentScale
before each draw, so the host evaluator derives that matrix from captured runtime
values. `tools/physical_mapping.py` reproduces the actual scale/smooth-scale
chain's double composition, float rectangles, normal copyRect clipping and the
fifteen ordered predicates. Unknown chains require exact additional semantics
and are rejected rather than approximated. Gate `pass` and `reached` use true,
false and null (unknown). Later predicates are computed independently even when
an earlier gate is unknown or false. `firstFailingGate` is definitive only when
all preceding gates are known true; `earliestKnownFailingGate` and
`unresolvedEarlierGates` distinguish a known rejection from unresolved earlier
predicates. `allGatesPass` is false for any known rejection, null when unknown
predicates remain without a known rejection, and true only when all gates pass.
Both allowSmooth=true (physical copy) and false (physical identity draw) are
reported. Raw metadata stays separate from these source-derived evaluations.

Backing mutation generation is captured even when nonzero. The raw Image-side
generation is unavailable through read-only APIs: `sourceMutationGeneration`
is null and `sourceMutationGenerationAvailable` is false. The helper never calls
the synchronizing Image generation getter. `mutationGenerationsEqual` is therefore
unknown, while scale equality, source bounds/integrality, device integrality and
extent equality still receive independently computed results.
`inspectionObservableStateUnchanged` checks only backing reference identity and
its read-only generation; it cannot prove an unobserved private Image field.
No pixels, mutable storage, setters or private reflection bypass are used.
The result contract is `schemas/physical-mapping-probe-v1.schema.json`. Use the
same sole-process command as draw-path-probe with
`--scroll-driver physical-mapping-probe`; reuse previous paint timings for cost
correlation instead of measuring performance again.
