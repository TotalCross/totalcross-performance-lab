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

Use a package built from committed benchmark tooling and the validated official
runtime, then launch one measured process with no warmups:

```sh
python3 runners/run.py image-rendering scroll --profile default   --scroll-driver draw-path-probe --rounds 1 --warmups 0   --timeout-seconds 180 --width 540 --height 960   --dataset-cache .local-data/datasets/p12-final/image-scroll/v1   --package-manifest /path/to/package-manifest.json   --results-dir .local-data/results/image-rendering-draw-path-probe   --require-default-scroll-preflight --fail-fast
```

This mode does not run the scrolling workload or call `prepareForDisplay`.
Target-color/physical-variant activity under the default policy is recorded as
unexpected rather than hidden or forced to zero. The materialized cache-admission
policy remains a separate unresolved question; this probe changes no policy.
