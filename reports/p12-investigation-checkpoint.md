<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# P12 investigation checkpoint — execution paused

**Status:** benchmark execution is paused pending investigation. P12 is not
complete. This is a technical checkpoint, not a performance conclusion.

## Stop event

During interactive observation of the corrected historical-style workload,
application performance appeared substantially worse than expected across the
profiles observed so far.

This observation is only the reason for stopping the matrix. It does not
establish a TotalCross regression, a failed optimization, an invalid benchmark,
or a broken typed configuration.

The active family was scroll, profile target-color, measured round 2. The
runner was interrupted with Ctrl+C. Its Python process returned exit code 130
with KeyboardInterrupt in subprocess.communicate. The process directory
contains only tcbench-run.json; it has no completed run record, stdout, or
stderr for that round. Treat it as **interrupted/incomplete**, not as a
benchmark failure. A process scan after interruption found no image-rendering
launcher or TotalCross benchmark process still running.

Exact command active at interruption, from the benchmark-lab root:

    python3 runners/run.py image-rendering scroll --profile default,target-color,physical-variant,raster-variants,scroll-reuse,combined-standard,combined-compact --rounds 3 --warmups 1 --timeout-seconds 600 --width 540 --height 960 --runtime-source /Users/flsobral/repos/totalcross-runtime-p12 --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 --package-manifest .local-data/packages/image-rendering-macos-p12-final-18e2e93/package-manifest.json --results-dir .local-data/results/image-rendering-p12-final-18e2e93/scroll

The run directory was created at 2026-10-02 22:18:31 UTC. The incomplete
target-color round 2 process configuration was created at 22:46:57 UTC, at
least 28m26s after matrix start. The exact Ctrl+C timestamp was not persisted.
Completed, corrected P12 measured records sum to about 26m33s of child
wall-time; this excludes preflight, warmups, runner gaps, and the interrupted
round.

## Source state and environment

Benchmark-lab source state at measurement time:

- Branch: perf/image-rendering-benchmarks
- HEAD: 18e2e93a83e1d02163d01b8ec19b97a758695fa1
- Working tree: clean
- Working-tree diff: empty
- Results recorded benchmarkWorkingTreeDirty=false

Ordered P12 implementation commits present before this checkpoint document:

1. 934d998 — define image-rendering benchmark contract
2. 57ae0b4 — validate versioned benchmark datasets
3. 50f3e5e — add image decode workload
4. f97c60a — add image scroll and preparation workloads
5. a07700e — add cross-platform benchmark runners
6. 42ff20a — validate benchmark tooling contracts
7. ed11ad1 — add frame pacing workloads
8. 69730c1 — restore historical scroll workload geometry
9. 44923e1 — collect production flick callback samples
10. 18e2e93 — pass window size to scroll launchers

TotalCross source used by the final package and run records:

- Checkout: /Users/flsobral/repos/totalcross-runtime-p12
- Source SHA: 5a44f503bf6fa1bec350f1218f4d501a70fc4812
- Git status at capture: detached HEAD, clean working tree.
- The macOS package builder required a clean checkout and matched
  runtimeArtifactSourceCommit to totalcrossSourceCommit; both are the SHA
  above. The current status snapshot is in the evidence bundle.
- A separate development checkout,
  /Users/flsobral/repos/totalcross-image-scroll-raster-fast-path, was on
  feat/frame-pacing-scheduling-diagnostics at
  1c6306b0861c589b8c6abe5f494c5c623db346f9 and was dirty. Its complete
  status and diff were captured in the bundle; none of those files were changed
  or staged for this checkpoint.

Host and corpus:

- Host Fabios-M1-Pro.local; macOS 26.5.2, build 25F84, arm64
- Java: Zulu OpenJDK 17.0.12+7
- Dataset: image-scroll/v1, 663 files (660 JPEG, 3 PNG)
- Dataset manifest SHA-256: 4dac75139e4e7095f5843a696f5fcd84055bf798e90b49614d6e4243120f5dbe
- Published archive SHA-256: a7e5545ca6565033d0c5b31bfa81cf89c972d5ba21566dc711df282de3b97b42
- The verified manifest file list is lexicographically ordered.
- Final measured scroll logical size: 540x960; drawable size: 1080x1920;
  display scale: 2.
- The measured inner scroll viewport was 540x910; the scrollbar range was
  recorded as 0 through 39091.
- Runtime renderer: RASTER; reported refresh rate and session type were null.
- Primary runs had diagnostics disabled. The recorded runtime also reported
  diagnosticsSupported=false.
- Run metadata records runtimeIdentity artifact SHA-256
  8c7383a189b742d848003b19ca641ece3c0a428d194e1a08313cf4e55d7b5254 for the
  final default profile and
  6b676abe718863d5214a0c4e34e9d9d8fe5463988c71fea5f1da8c8adcff8282 for the
  completed target-color profile. Package and per-process runtime-file hashes
  are preserved in the copied manifests and tcbench-run.json files.
- The final package manifest records libtcvm.dylib SHA-256
  913d412094cf8cc5fd7a66625b7abfa17bdb70784d868f3748322f3ecf353d97 for the
  profile packages.

The source-state snapshots, platform details, dataset identity files, package
manifests, build logs, and raw results are in the ignored local bundle
artifacts/p12-checkpoint/. Its file checksums are in
artifacts/p12-checkpoint/SHA256SUMS. The archive is
artifacts/p12-checkpoint.tar.gz; SHA-256:
2a2bde179c807175e37a94a0b229aea2513fe2ab83b17af0b050ea8d65787a2a.
The 47.5 MB source dataset, generated packages, and build outputs remain in
ignored .local-data/ paths and are not committed.

## Benchmark architecture

The suite is in benchmarks/image-rendering/ in the performance-lab
repository.

- Shared app/controller: ImageRenderingBenchmarkApp
- Workloads: ScrollWorkload, DecodeWorkload, and PacingWorkload
- Profile entry points: the ten classes under
  benchmarks/image-rendering/src/totalcross/bench/imagerendering/profiles/
- Dataset tool: tools/datasets/image_scroll.py; the descriptor is
  datasets/image-scroll/v1/dataset.json
- Runner: runners/run.py on macOS/Linux; the corresponding Windows runner is
  runners/windows/run-image-rendering-benchmark.ps1
- macOS package/deployment helper: tools/packaging/build_macos.py
- Windows package helper: tools/packaging/build_windows.py
- Package inventory: each built package's package-manifest.json

The final macOS package manifest records benchmark source
18e2e93a83e1d02163d01b8ec19b97a758695fa1, TotalCross source and runtime
artifact source 5a44f503bf6fa1bec350f1218f4d501a70fc4812, Java compile release
8, macOS arm64, and the verified dataset identity. Its native build directory
was .local-data/build/runtime-p12-macos; CMakeCache records Release, arm64,
and Ninja. build_macos.py verifies those properties and copies the native
Launcher and libtcvm.dylib into each profile package.

The builder reused the existing SDK. Its manifest has sdkBuildCommand: [];
the SDK was not rebuilt as part of the final package command. The SDK artifact
itself has no source SHA recorded by this packaging step.

For deployment, the package builder compiles the benchmark Java sources with
javac --release 8, makes one profile JAR per entry class, then invokes
tc.Deploy for macOS with /p /n <profile-prefix> /o <deployment-dir>.
The package manifest maps each profile to its entry class, executable, runtime
files, and SHA-256 values. The runner selects the executable for the chosen
profile and validates runtime/package hashes before recording a run.

The runner writes tcbench-run.json for each child process, starts preflight,
warmup, and measured children as fresh processes, checks child exit/protocol
output, and aggregates TCBENCH_JSON records into per-cell *.summary.json
files. There is no separate result-collection command. Raw stdout, stderr,
DebugConsole output, and per-process configuration records are preserved in
the evidence bundle.

## Historical workload compatibility

The corrected scroll workload keeps these historical layout semantics:

- Exactly 663 dataset images, arranged as 221 rows of 3 columns.
- Logical window size 540x960. The measured launcher uses /scr
  -2,-2,540,960.
- tileWidth = (540 - 3) / 3 = 179 square pixels.
- The outer and inner ScrollContainer hierarchy, blue container backgrounds,
  inner pane inset by 40 pixels at the top and 60 at the bottom, green row
  containers, and three ImageControls per row.
- The current official manifest is lexicographically ordered, matching the
  historical path sort for common entries.
- Three full endpoint traversals in the corrected workload: cold forward
  (top to bottom), warm reverse (bottom to top), warm forward (top to bottom).
  “Cold” describes first traversal in the process, not a guaranteed cold OS
  filesystem cache.
- Prepared profiles explicitly request visible-image preparation before a
  pass and at viewport-sized progress points while scrolling. The default and
  target-color profiles measured here do not request preparation.

Intentional or known differences from
ImageScrollRealWorkloadBenchmarkApp:

- The lab uses the versioned, verified manifest and consumes all 663 entries,
  including 3 PNG files. The historical helper filters .jpg/.jpeg paths.
  Both report 663 images, but the image population is not proven byte-for-byte
  identical.
- The lab loads from the validated dataset root via File and scales with
  getSmoothScaledInstance; the historical app constructs Image from each
  sorted pathname. Both load and scale each control during UI construction.
- The lab always runs three full scrollbar-endpoint passes. Historical source
  defaults to one pass and has a configurable 3000 ms scroll duration. The
  traversal timing/termination rule therefore differs and must be kept in
  view during the later methodology investigation.
- The lab selects production typed runtime annotations on separate entry
  classes. It does not pass historical raw optimization masks and does not
  inject test-only Image policy.
- The lab reports paint-callback interval percentiles and workload-level
  timings. The historical benchmark records a broader set of diagnostic and
  accounting fields.
- Prepared profiles are a separate explicit preparation workload in the lab.
  The historical app can request one initial prefetch before its timed passes.

## Implemented profile configuration

These mappings describe the checked-in profile classes. “Exercised” indicates
whether a completed corrected run recorded the profile; it does not imply
validation of every implementation.

| Profile | Typed production configuration | Exercised in corrected records |
|---|---|---|
| default | No runtime annotation; production defaults | Yes: decode, pacing, scroll |
| target-color | targetColorConversion=ENABLED | Yes: scroll round 1; round 2 interrupted |
| physical-variant | physicalVariantCache=ENABLED | No in corrected run |
| raster-variants | Target color and physical variant cache enabled | No in corrected run |
| compact | ImageStorageProfile.COMPACT | Yes: decode |
| scroll-reuse | scrollRasterReuse=ENABLED | No in corrected run |
| prepared-legacy | LEGACY_PER_ENTRY_THREAD; explicit preparation | No in corrected run |
| prepared-semaphore | SEMAPHORE_PROCESS_WORKER; explicit preparation | No in corrected run |
| combined-standard | Standard storage; both raster variants and scroll reuse enabled; semaphore worker | No in corrected run |
| combined-compact | Compact storage; both raster variants and scroll reuse enabled; semaphore worker | No in corrected run |

The completed target-color record contains matchedRules: image-rule-0 and
reports target-color conversion enabled, physical variant cache disabled, and
the other production defaults. The default record reports standard storage
and both raster variant features disabled. No claim is made here about the
other profiles' deployed effective configurations; their corrected scroll
cells had not yet run.

## Exact execution protocol and commands

The final dataset fetch was:

    python3 tools/datasets/image_scroll.py fetch image-scroll/v1 --cache-dir .local-data/datasets/p12-final/image-scroll/v1 --force

The runner verifies the cached descriptor, manifest, file count, sizes, and
per-file hashes before a dataset-dependent cell. An explicit verification
command for reproducing that check is:

    python3 tools/datasets/image_scroll.py verify image-scroll/v1 --cache-dir .local-data/datasets/p12-final/image-scroll/v1

Native macOS build settings preserved in CMakeCache:

    cmake -S "$TOTALCROSS_SOURCE/TotalCrossVM" -B .local-data/build/runtime-p12-macos -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 -DQRCODEGEN_RELEASE_TAG=qrcodegen-20250123-r2 -DSQLITE3_RELEASE_TAG=sqlite3-3.32.3-r2 -G Ninja
    cmake --build .local-data/build/runtime-p12-macos --target tcvm Launcher --parallel

The SDK was reused and the final package manifest confirms no SDK build was
requested by the package helper. The original SDK build shell command was not
serialized with the benchmark records; this checkpoint does not invent one.

The final package was built from the pinned runtime checkout and the verified
dataset, equivalent to:

    python3 tools/packaging/build_macos.py --runtime-source /Users/flsobral/repos/totalcross-runtime-p12 --native-build-dir .local-data/build/runtime-p12-macos --runtime-artifact-commit 5a44f503bf6fa1bec350f1218f4d501a70fc4812 --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 --output .local-data/packages/image-rendering-macos-p12-final-18e2e93

The builder's full log and resulting manifest are in the evidence bundle. The
builder itself runs the Java compile and tc.Deploy steps described above.

The full final decode matrix command was:

    python3 runners/run.py image-rendering decode --profile default,compact --rounds 3 --warmups 1 --timeout-seconds 300 --runtime-source /Users/flsobral/repos/totalcross-runtime-p12 --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 --package-manifest .local-data/packages/image-rendering-macos-p12-final-44923e1/package-manifest.json --results-dir .local-data/results/image-rendering-p12-final/decode

A single profile is selected with --profile <name>; for example, the
corrected scroll smoke used the default profile, while the stopped matrix
command above selected seven profiles. Scroll/preparation package launchers
receive the requested window through /scr -2,-2,<width>,<height>. The runner
default and measured primary runs did not pass --diagnostics. There were no
additional environment overrides required by the matrix; runtime, dataset,
package, dimensions, timeout, rounds, warmups, and results location were
command-line arguments.

The matrix is the result collection operation: it stores one summary per
completed cell plus process JSON, stdout, stderr, and DebugConsole files under
--results-dir. To locate them, inspect the directory named by that option;
no post-processing or separate report command ran before interruption.

## Timing methodology

For each scroll/preparation cell, the runner launches a preflight process, one
fresh process per warmup, and one fresh process per measured round. The
interrupted scroll matrix requested one warmup and three measured rounds for
each profile. The completed default profile therefore has one warmup and three
measured children; target-color has one warmup, one completed measured child,
and one interrupted measured child.

ScrollWorkload creates the containers, reads all dataset entries, constructs
663 images, calls getSmoothScaledInstance(179,179), creates the ImageControls,
resizes the scroll containers, and sets the initial scrollbar position before
the timed pass begins. It waits for an initial 50 ms timer before beginning
traversal. Image loading, scaling, and UI construction are outside scroll
wallTime.

The driver requests a 120 px vertical scrollContent step per timer callback
and schedules the next callback for 16 ms later. It continues to the scrollbar
endpoint; this is a requested timer cadence, not a guarantee that callbacks or
paints occur every 16 ms. Each pass starts its timer at passStartedNs and
stops at the endpoint. Reported wallTime is the sum of the three pass wall
times; the 1 ms inter-pass timer gap, initial stabilization, process launch,
and UI construction are outside it.

For scroll, the app's profile onPaint calls super.onPaint and then the shared
collector. While a pass is active, the collector samples System.nanoTime()
and appends the interval since the previous main-window paint callback.
Percentiles sort the samples and linearly interpolate at (n-1)*fraction; max
is the largest observed interval. These are paint callback intervals, not a
hardware-vsync trace. No sample is printed as it is collected. The app emits
its run and summary JSON records at the end of a successful child.

For prepared profiles, initial visible preparation is awaited before that
pass's timer starts. During the timed traversal, additional visible preparation
requests are made after viewport-sized scroll progress. The time waiting for
those requests is included in pass wall time and is also reported separately.
The completed default and target-color scroll records have preparation false
and preparationWaitTimeNs=0.

Diagnostics were disabled for primary timing. The recorded native runtime
reported diagnostics unsupported, so public runtime diagnostic counters were
not enabled. JSON/stdout emission is at child completion rather than per
frame. The frame callback still performs a clock read and sample append on
each collected paint; its overhead remains an investigation candidate.

## Completed and interrupted execution records

All times below are from saved run records. Decode cells do not define paint
percentiles. Wall is the per-child wallTime; an em dash means the workload did
not record that statistic. Diagnostics were disabled for these corrected
primary records. Unless noted, runtime SHA is
5a44f503bf6fa1bec350f1218f4d501a70fc4812.

### Corrected final decode matrix

The 16 cells below completed all three measured rounds with zero reported
failures: 48 measured child processes. Full per-process JSON and logs are
preserved in results/final-decode-44923/.

| Profile | Source | Scale | Order | Round 1/2/3 wall (ms) | Result |
|---|---|---|---|---:|---|
| compact | filesystem | full | seeded-random | 3064.9, 3045.1, 3072.7 | complete, 0 failures |
| compact | filesystem | full | sequential | 3052.4, 3109.1, 3047.7 | complete, 0 failures |
| compact | filesystem | half | seeded-random | 4346.3, 4260.4, 4343.8 | complete, 0 failures |
| compact | filesystem | half | sequential | 4338.7, 4383.2, 4378.5 | complete, 0 failures |
| compact | TCZ | full | seeded-random | 3069.3, 3073.1, 3044.0 | complete, 0 failures |
| compact | TCZ | full | sequential | 3082.9, 3063.4, 3038.5 | complete, 0 failures |
| compact | TCZ | half | seeded-random | 4264.0, 4342.3, 4227.6 | complete, 0 failures |
| compact | TCZ | half | sequential | 4237.0, 4344.0, 4246.0 | complete, 0 failures |
| default | filesystem | full | seeded-random | 1808.0, 1826.5, 1791.0 | complete, 0 failures |
| default | filesystem | full | sequential | 1800.4, 1830.9, 1844.6 | complete, 0 failures |
| default | filesystem | half | seeded-random | 6289.2, 6282.7, 6315.8 | complete, 0 failures |
| default | filesystem | half | sequential | 6321.7, 6361.3, 6318.6 | complete, 0 failures |
| default | TCZ | full | seeded-random | 1803.0, 1822.7, 1800.1 | complete, 0 failures |
| default | TCZ | full | sequential | 1822.3, 1806.9, 1813.1 | complete, 0 failures |
| default | TCZ | half | seeded-random | 6276.1, 6331.5, 6344.8 | complete, 0 failures |
| default | TCZ | half | sequential | 6292.5, 6287.2, 6257.1 | complete, 0 failures |

### Corrected smoke cells before the stopped matrix

| Family/profile/workload | Round | Status | Wall | p50 / p95 / p99 / max | Cold/warm | Diagnostics | Runtime SHA | Benchmark SHA |
|---|---:|---|---:|---|---|---|---|---|
| pacing / default / flick-40 | 1 | complete | 2123.7 ms | 25.211 / 26.110 / 27.657 / 29.664 ms; 71 samples | not applicable | disabled | 5a44f503 | 44923e1a |
| scroll / default / scroll | 1 | complete | 280.127 s | 285.605 / 293.764 / 297.474 / 442.337 ms; 972 samples | cold-forward, warm-reverse, warm-forward | disabled | 5a44f503 | 44923e1a; runner had the uncommitted window-size fix later committed as 18e2e93a |

### Corrected scroll matrix at interruption

| Profile | Round | Status | Wall | p50 / p95 / p99 / max | Traversal | Diagnostics | Benchmark SHA |
|---|---:|---|---:|---|---|---|---|
| default | 1 | complete | 280.375 s | 285.865 / 294.629 / 300.045 / 368.658 ms; 972 samples | cold-forward, warm-reverse, warm-forward | disabled | 18e2e93a |
| default | 2 | complete | 280.271 s | 285.693 / 293.997 / 298.394 / 370.778 ms; 972 samples | cold-forward, warm-reverse, warm-forward | disabled | 18e2e93a |
| default | 3 | complete | 281.382 s | 288.496 / 297.024 / 301.268 / 358.693 ms; 972 samples | cold-forward, warm-reverse, warm-forward | disabled | 18e2e93a |
| target-color | 1 | complete | 282.496 s | 288.741 / 298.455 / 304.684 / 381.408 ms; 972 samples | cold-forward, warm-reverse, warm-forward | disabled | 18e2e93a |
| target-color | 2 | **interrupted** | unavailable | unavailable | incomplete; no completed pass record | disabled in launch config | 18e2e93a |

The two preflight children and two warmups (default and target-color) completed;
warmup timings are not represented as measured cells. No corrected measured
scroll rounds started for physical-variant, raster-variants, scroll-reuse,
combined-standard, or combined-compact. prepared-legacy and prepared-semaphore
were not requested by this scroll matrix.

The final corrected chain therefore has 54 completed measured child processes:
48 decode, one flick smoke, one scroll smoke, and four scroll-matrix rounds.
The active matrix itself had four completed measured children and one
interrupted child. Before the correction chain, 53 preliminary measured
processes and 40 divergent pre-correction measured records are retained
separately. The 40 pre-correction records remain quarantined and are not
baseline evidence; their summaries, logs, and crash reports are inside
results/quarantined-pre-correction-20261002T215714Z/. An earlier decode
matrix and initial smoke outputs are also preserved as preliminary records.
Across all locally preserved P12 result summaries plus the completed
target-color round-1 raw record, 147 measured process records exist; this
includes superseded and quarantined records and is not a count of accepted
final measurements.

## Investigation candidates

These are observations from source and saved metadata for later investigation;
they are not diagnoses and no code was changed for them:

| Candidate | Current checkpoint evidence |
|---|---|
| Intended TotalCross runtime build | Final run records identify source SHA 5a44f503…; package manifest records the same source and runtime-artifact SHA. Native CMake settings are Release arm64. |
| Typed annotations in deployed metadata | Completed target-color output has matchedRules: image-rule-0 and target-color conversion enabled. Other profile cells did not run in the corrected scroll matrix. |
| Effective profile configuration | Default output reports production defaults; target-color output reports target conversion enabled with physical-variant cache disabled. Other named profiles remain unverified at runtime in the corrected matrix. |
| Diagnostics/instrumentation | diagnosticsEnabled=false; runtime says diagnostics unsupported. Paint-interval collection is active for scroll and has a per-paint clock read plus append. |
| Image load/scale on every frame | Source constructs and scales images in ScrollWorkload construction before passStartedNs; no such work is in the paint collector. |
| Repeated prepareForDisplay | Not used in completed default/target-color scroll runs. Prepared profiles explicitly request it before each pass and during traversal, but those corrected profiles have not run. |
| Historical scroll driver semantics | Both use ScrollContainer, 120 px programmatic scroll steps, and top/bottom traversal concepts. The current runner advances to full endpoints with a nominal 16 ms timer; historical source defaults to a 3000 ms duration and one pass. |
| Repaint volume | The corrected tree has 663 ImageControls and 221 rows as expected. Current run records do not count per-child paints, so repaint volume relative to the historical fixture is unverified. |
| Logical/drawable scaling | Requested logical 540x960, observed drawable 1080x1920, display scale 2. |
| Renderer/backend | Run metadata says RASTER, matching the expected selected backend. |
| Frame timing overhead | Intervals are timestamps after super.onPaint; samples are accumulated in memory and JSON is emitted only at child completion. Sampling overhead has not been isolated. |
| Native build mode | Package builder and CMakeCache record Release arm64, not a debug native build. |
| SDK/native/package provenance | Native runtime and package source SHA agree. The SDK was reused (sdkBuildCommand=[]), and this build record does not attest the SDK artifact's source SHA. |
| Display/session detail | displayRefreshHz and sessionType were null in the records, so the display cadence and host session mode are not established here. |
| Corpus equivalence | Current verified manifest is sorted, but contains 660 JPEG and 3 PNG files; historical source filters JPEG extensions. Exact historical corpus equivalence is not established. |

The main numerical observation motivating this stop is the saved corrected
scroll data: default pass wall times are about 280–281 seconds per full
three-direction cell, with paint-callback p50 near 286–288 ms. This is recorded
only as a reproduction target for the next investigation.

## Validation and deferred work

Checkpoint validation was limited to:

- python3 -m unittest discover -s tests — passed, 34 tests in 1.135 seconds.
- git diff --check — passed.

The corrected source-contract and runner-contract tests were also run on the
implementation commits. Windows packaging/execution was not done: the used
Mac checkout lacks etc/launchers/win32/Launcher.exe and
dist/vm/win32/tcvm.dll, and PowerShell was unavailable on this host.

The full scroll/preparation/pacing profile matrices, Windows package, and
final P12 analysis are deferred until the performance/runtime questions above
are investigated. Do not mark P12 complete or resume benchmarks without
explicit user instruction.

## Additional stop before official-package run (2026-10-02)

The later instruction to stop arrived while preparing a provenance-controlled
run against the official TotalCross package. A fresh process scan found no
image-rendering runner, TotalCross launcher, or benchmark child active. No
process was terminated for this stop, no command was running, and no additional
benchmark cell or process was started. The earlier `scroll / target-color /
round 2` interruption above remains the last interrupted benchmark cell.
Accepted completed measurement counts and times are unchanged: 54 completed
children in the corrected chain, about 26m33s measured wall time; the separate
interrupted child is not counted as a completed measurement.

The official GitHub package was downloaded and its outer artifact digest
matched the GitHub artifact metadata. Workflow `37076804175` (Packages
`totalcross`), source SHA
`5a44f503bf6fa1bec350f1218f4d501a70fc4812`, published artifact
`11256633898` (`TotalCross-7.2.2`) with digest
`sha256:4eed292bc20af56ef55cbb7397ffc090c3690b1b1d8f41d75cfbb70ebe6cec41`.
The contained package ZIP SHA-256 is
`dddbc50ffae0ce3a1b6f3b315d99cf971190238524c960cd06035066cab337dd`. The
official SDK JAR, macOS Launcher, and macOS `libtcvm.dylib` hashes are
`389204c26d4377a5964d529ed6aaac0b751dd39c5546c6310918d085bb9baf49`,
`3439082ff2b6e7bab37d7049b5860b6d4743297536bb7c9ba6806a2b45445884`, and
`421f957d551a75022a92db21638620732614e6d033a6f417ada09c6867cb8f24`.
These files remain in ignored `.local-data/official-totalcross-7.2.2/`.
The package was not used to build, deploy, or launch a benchmark application;
there is no new official-package run or result record.

At this stop, the performance-lab branch was
`perf/image-rendering-benchmarks` at
`139e05649e28f9fdd551bb3bc53ada4854e04650`, matching its remote tracking
branch before this addendum. The local uncommitted paths were
`schemas/benchmark-package-v1.schema.json`,
`schemas/benchmark-run-v1.schema.json`,
`schemas/environment-v1.schema.json`,
`schemas/official-runtime-provenance-v1.schema.json`, and
`tools/packaging/build_macos.py`. These edits were an unfinished optional
official-package provenance mode for the now-paused run; the CLI/profile
selection path was not complete. They were not committed as completed P12
implementation. Their exact tracked diff, new schema, status, and related
artifact metadata are preserved in
`artifacts/p12-checkpoint/current-stop-20261002T234841Z/`.

The benchmark source checkout used by earlier completed runs remains
`/Users/flsobral/repos/totalcross-runtime-p12` at
`5a44f503bf6fa1bec350f1218f4d501a70fc4812`, clean. The separate development
checkout `/Users/flsobral/repos/totalcross-image-scroll-raster-fast-path`
was at `1c6306b0861c589b8c6abe5f494c5c623db346f9` on
`feat/frame-pacing-scheduling-diagnostics` and dirty; its status and tracked
diff were captured in the current-stop evidence snapshot.

After capturing the state, the lightweight checks were run: `git diff
--check`, `python3 -m py_compile tools/packaging/build_macos.py runners/run.py`,
and `python3 -m unittest discover -s tests` (34 tests passed in 1.151 seconds).
No performance workload, app build/deploy, or benchmark-launch command was
run after the stop. The official-package implementation remains incomplete;
these checks do not validate its end-to-end behavior.

The updated ignored evidence archive is
`artifacts/p12-checkpoint.tar.gz`, SHA-256
`2a2bde179c807175e37a94a0b229aea2513fe2ab83b17af0b050ea8d65787a2a`. The
earlier archive with SHA-256
`e28a85e15f32d66d5b2f08765c4da5e4bd11de0809e6bd4b84cc9de404b0bc6a` is
preserved as `artifacts/p12-checkpoint-before-latest-stop.tar.gz`. Both are
ignored by Git. No diagnosis or performance conclusion has been added.

## Latest pause during official runtime provenance work (2026-10-03)

On the latest explicit pause request, a fresh process scan found no benchmark
runner, launcher, or TotalCross child active. No child was terminated, no
benchmark command was running at this latest stop, and no additional P12 cell,
preflight, package build, or benchmark process was started. The prior
`scroll / target-color / round 2` interruption above is still the only
interrupted measured cell. The corrected P12 count remains 54 completed
measured children, totaling approximately 26m33s of measured child wall-time;
preflight, warmups, runner gaps, and the interrupted child are excluded.

The exact command from the earlier interruption is recorded under “Stop
event”. No new command replaced it at this pause. It was the seven-profile
scroll matrix with one warmup and three requested measured rounds per profile.

This continuation started from performance-lab HEAD
`3ae6ec23ac298a397cabcc5d5c087da3c46f5bc2` on
`perf/image-rendering-benchmarks`, matching `origin/perf/image-rendering-benchmarks`
at that point. The TotalCross source checkout used by earlier measured runs is
still clean at `5a44f503bf6fa1bec350f1218f4d501a70fc4812`. The separate
TotalCross development checkout remains at
`1c6306b0861c589b8c6abe5f494c5c623db346f9` with its unrelated local changes;
no files there were changed by this continuation. The current host remains
macOS 26.5.2 arm64 with Zulu Java 17.0.12+7. Dataset identity remains
`image-scroll/v1`, manifest SHA-256
`4dac75139e4e7095f5843a696f5fcd84055bf798e90b49614d6e4243120f5dbe`, archive
SHA-256 `a7e5545ca6565033d0c5b31bfa81cf89c972d5ba21566dc711df282de3b97b42`.

During the resumed work, the optional official GitHub package provenance path
was extended across `tools/packaging/build_macos.py`,
`tools/packaging/official_runtime.py`, `runners/run.py`, the benchmark
preflight record, schemas, and focused unit tests. It pins the previously
recorded official workflow/artifact/package identity, checks copied and
extracted package files and deployed Launcher, TCZ, and native-library hashes,
and lets the runner consume a source-less package manifest. A guarded default
scroll preflight can report and verify renderer, diagnostics, runtime policy,
dataset, and historical geometry before a measured child. These changes were
not used to build or launch an application after the pause. The official
artifact, SDK, Launcher, and `libtcvm.dylib` hashes remain those listed in the
previous stop section and in the ignored evidence bundle.

The latest source diff and the untracked provenance schema/helper are captured
under `artifacts/p12-checkpoint/current-stop-latest/`. This snapshot includes
the pre-commit status, diff stat, binary patch, runtime checkout status, process
scan, and the three new source files. `python3 -m unittest discover -s tests`
passed (38 tests, 1.146 seconds). Python byte-compilation of
`tools/packaging/official_runtime.py`, `tools/packaging/build_macos.py`, and
`runners/run.py` passed, and `git diff --check` passed. An initial byte-compile
command mistakenly included a Java source file and failed with Python's
`SyntaxError`; the corrected Python-only command passed. No Java/SDK/native
build, package deployment, package preflight, or benchmark validation was run
for this provenance path. Its package-level integration remains unverified.

The source edits were committed as
`472dd24773077530752d6743477ec61ec94713ac` (`feat(bench): attest official
runtime package inputs`). This feature commit follows the two pause/checkpoint
commits `139e056` and `3ae6ec2`. The final checkpoint document is committed
separately. They provide provenance and preflight controls only; no performance
problem was diagnosed or fixed. Existing timing data and the investigation
candidates above are unchanged. P12 remains paused and incomplete.

The ordered branch commits after `main` are listed in the final response and
preserved in `artifacts/p12-checkpoint/current-stop-latest/commits-before-implementation-commit.txt`;
the latest snapshot also records the feature commit and post-commit repository
state.

Latest ignored evidence bundle: `artifacts/p12-checkpoint.tar.gz`, SHA-256
`1a17f6c1d0aae2b52ba3eff2fcb4b367465d518769554d58741486395c63bff0`.
`artifacts/p12-checkpoint/SHA256SUMS` covers the preserved bundle contents.

## Official-package default scroll comparison (2026-10-02, America/Sao_Paulo)

The user-authorized single `scroll/default` experiment used only GitHub Actions
workflow run `37076804175`, artifact `11256633898` (`TotalCross-7.2.2`), source
SHA `5a44f503bf6fa1bec350f1218f4d501a70fc4812`. Before build, the outer
artifact SHA-256 matched the GitHub digest
`4eed292bc20af56ef55cbb7397ffc090c3690b1b1d8f41d75cfbb70ebe6cec41`; the
contained package ZIP was
`dddbc50ffae0ce3a1b6f3b315d99cf971190238524c960cd06035066cab337dd`. The
SDK JAR, macOS Launcher, and `libtcvm.dylib` matched the pinned hashes
`389204c26d4377a5964d529ed6aaac0b751dd39c5546c6310918d085bb9baf49`,
`3439082ff2b6e7bab37d7049b5860b6d4743297536bb7c9ba6806a2b45445884`, and
`421f957d551a75022a92db21638620732614e6d033a6f417ada09c6867cb8f24`.
Dataset verification passed for 663 files and manifest SHA-256
`4dac75139e4e7095f5843a696f5fcd84055bf798e90b49614d6e4243120f5dbe`.

The official package builder compiled against that package's
`dist/totalcross-sdk-7.2.2.jar` and `dist/libs/*`, then called `tc.Deploy` for
`Default.jar` only. The generated package inventory contains only `default`;
no SDK or native runtime build was run. The exact javac and `tc.Deploy`
invocations and full output are preserved in
`.local-data/packages/image-rendering-macos-official-p12-default-9731f6c.build.log`.
The package manifest is
`.local-data/packages/image-rendering-macos-official-p12-default-9731f6c/package-manifest.json`.

One required runner preflight passed before timing: renderer RASTER; STANDARD
storage; target-color conversion, physical-variant cache, scroll reuse,
automatic preparation, explicit preparation, and diagnostics disabled; worker
LEGACY_PER_ENTRY_THREAD; 663 controls, 221 rows by 3 columns, logical 540x960,
tile width 179, dataset `image-scroll/v1`. The runner then launched exactly
one fresh measured child, round 1, with zero warmups. It completed with zero
failures and 972 paint samples. No other profile or round was run.

| Metric | Official package, one measured round | Previous corrected local default |
|---|---:|---:|
| Scroll wall time | 278.893 s | about 280–281 s |
| Paint p50 | 284.406 ms | about 286–288 ms |
| Paint p95 | 292.748 ms | about 294–297 ms |
| Paint p99 | 298.137 ms | about 298–301 ms |
| Paint max | 371.784 ms | about 359–371 ms |
| Samples | 972 | 972 |

The very slow scroll behavior reproduced with the official SDK, deployer,
Launcher, and native library: the one official-package result was about 279 s,
close to the earlier 280–281 s local-build results. This single comparison does
not identify a cause or measure feature effectiveness. The measured stdout
also contains a `Read-only file system` warning from
`Resources.uiStyleChanged`; the child still completed successfully. No
investigation or fix was performed.

The deployed profile provenance is recorded in the package manifest: input
JAR SHA-256 `c4c350fc4407bfad7e6fb677f246ec8d2593427ca58b5466033798d0adbe07f5`,
executable SHA-256 `3439082ff2b6e7bab37d7049b5860b6d4743297536bb7c9ba6806a2b45445884`,
application TCZ SHA-256 `c1f45b6b08ae3b1135ca922004f5de3de672610ddf7802ededaed10581637095`,
and deployed `libtcvm.dylib` SHA-256
`421f957d551a75022a92db21638620732614e6d033a6f417ada09c6867cb8f24`.
The benchmark source commit was `9731f6c3b5f16683deae8dc257f1bc6e5a8b64ff`;
the runtime source identity was `5a44f503bf6fa1bec350f1218f4d501a70fc4812`.

The exact runner invocation was:

    python3 runners/run.py image-rendering scroll --profile default --rounds 1 --warmups 0 --timeout-seconds 600 --width 540 --height 960 --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 --package-manifest .local-data/packages/image-rendering-macos-official-p12-default-9731f6c/package-manifest.json --results-dir .local-data/results/image-rendering-p12-official-default --require-default-scroll-preflight

Raw preflight, measured JSON, stdout, DebugConsole, and summary remain outside
Git under
`.local-data/results/image-rendering-p12-official-default/run-20261003T002224Z-44831/`.
No P12 matrix, preparation, SIGBUS, Windows, or additional benchmark work was
resumed. P12 remains incomplete and paused pending further explicit direction.

## Historical-driver explicit repaint probe (2026-10-02, America/Sao_Paulo)

This separate investigation kept the corrected 663-control, 221-row by 3-column
`image-scroll/v1` layout at 540x960 with 179-pixel tiles and production default
runtime policy. It executed one top-to-bottom pass using the historical
time-based target, 3000 ms duration, 16 ms cadence, bounded sleeps of at most
4 ms, separate `scrollContent()` and explicit `repaintNow()` timers, and
per-frame records. The pass reached the valid scrollbar endpoint 39091.

The SDK, deployer, Launcher, and `libtcvm.dylib` came only from workflow run
`37076804175`, artifact `11256633898` (`TotalCross-7.2.2`), source SHA
`5a44f503bf6fa1bec350f1218f4d501a70fc4812`, with the previously recorded
official artifact and runtime hashes. The default-only package was built from
benchmark source commit `b3b6b6501fa89cf86d4a796721643bc9de447c17`; the compiler
used the official `dist/totalcross-sdk-7.2.2.jar` and `dist/libs/*`, and only
`Default.java` was compiled from the profile directory. No SDK or runtime build
was run. The profile input JAR SHA-256 is
`4e9b920f9af162e1741b199c9b29a59b45c2f949bf404bf3b780fe3db7d27b53`, deployed
executable SHA-256 is
`3439082ff2b6e7bab37d7049b5860b6d4743297536bb7c9ba6806a2b45445884`, deployed
TCZ SHA-256 is
`9611414b090b7d016cb6652f956c768b346855bc5bc95f5c403596fdb5a33d88`, and
deployed `libtcvm.dylib` SHA-256 is
`421f957d551a75022a92db21638620732614e6d033a6f417ada09c6867cb8f24`. The
package manifest SHA-256 is
`0ea341937e2710f441f06ce56720e3f360c22e5e21b223567b5cd7152dbec201`.

The default preflight passed before measurement: RASTER renderer, STANDARD
storage, target-color conversion, physical-variant cache, scroll raster reuse,
automatic and explicit preparation, and diagnostics disabled; legacy
per-entry-thread worker; 663 controls, 221 rows by 3 columns, logical 540x960,
179-pixel tiles, and the verified 663-file `image-scroll/v1` dataset. There
were zero warmups and one measured child.

| Measurement | Result | Samples |
|---|---:|---:|
| Total pass wall time | 3.542595 s | 1 pass |
| Frame count | 11 | 11 frames |
| Frame-start interval p50 / p95 / p99 / max | 324.827 / 333.519 / 333.752 / 333.811 ms | 10 intervals |
| `scrollContent()` p50 / p95 / p99 / max | 0.016 / 0.083 / 0.122 / 0.132 ms | 11 frames |
| Explicit `repaintNow()` p50 / p95 / p99 / max | 322.644 / 333.346 / 333.681 / 333.764 ms | 11 frames |
| Total active work p50 / p95 / p99 / max | 322.659 / 333.421 / 333.709 / 333.781 ms | 11 frames |
| Final position / endpoint | 39091 / 39091 | reached |

The time-based trajectory reached its final target at elapsed 3.222 s; total
pass wall time was 3.543 s including the final repaint. This is near the
intended 3-second trajectory, with about 0.543 s of additional wall time. The
explicit repaint itself is very slow in this workload: its p50 was 322.644 ms,
while `scrollContent()` p50 was 0.016 ms. The 324.827 ms median frame-start
interval closely tracks the explicit repaint time, so this result points
primarily to synchronous rendering/repaint cost rather than fixed-step driver
overshoot. This is not a regression comparison: the prior default result's
284.4 ms p50 is a paint-callback interval, not an explicit repaint timer, and
no older runtime build was measured here.

For context, the current fixed-step P12 default cell took about 278.9 s for
three directions and recorded 972 paint-callback intervals (p50 284.406 ms).
This historical probe took 3.543 s for one top-to-bottom pass and recorded 11
explicit repaint durations (p50 322.644 ms). The pass counts and p50
definitions differ, so these wall times and p50 values are not like-for-like.

The measured child exited successfully and emitted one run record and one
summary. The runner command returned status 1 after its post-run default gate
tried to read generic viewport fields that this dedicated result shape does
not emit; the official preflight had already verified those dimensions before
timing. The saved preflight and child records passed offline protocol and
historical-result validation after runner fix commit `13cfd0d`. No second
measured child was launched. A nonfatal read-only filesystem warning from
`Resources.uiStyleChanged` appeared during startup.

The exact invocation was:

    python3 runners/run.py image-rendering scroll --profile default --scroll-driver historical-driver --rounds 1 --warmups 0 --timeout-seconds 600 --width 540 --height 960 --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 --package-manifest .local-data/packages/image-rendering-macos-official-historical-driver-b3b6b65/package-manifest.json --results-dir .local-data/results/image-rendering-historical-driver-official --require-default-scroll-preflight

The raw result, preflight, and logs remain ignored under
`.local-data/results/image-rendering-historical-driver-official/run-20261003T005925Z-76353/`.
The probe and runner fixes are commits `b3b6b6501fa89cf86d4a796721643bc9de447c17`
and `13cfd0d`; no other P12 workload was resumed.

## Official-package paint-tree split probe (2026-10-02, America/Sao_Paulo)

This focused probe separates the benchmark scroll's Java paint tree from the
additional work performed by `repaintNow()`. It uses benchmark-only subclasses
to time visible row and `ImageControl.onPaint()` calls. At each fixed scrollbar
position it performs one untimed stabilization repaint, then takes five direct
`scroll.onPaint(getGraphics()); scroll.paintChildren();` samples and five
`scroll.repaintNow()` samples. The probe does not alter the production runtime
or the normal scroll drivers.

The app emitted its default-policy preflight inline before the samples. The
single fresh process confirmed RASTER, STANDARD storage, target-color
conversion/physical-variant cache/scroll raster reuse/automatic preparation
disabled, `LEGACY_PER_ENTRY_THREAD`, diagnostics disabled, no explicit
preparation, and `image-scroll/v1` with 663 images, 221 rows, 3 columns,
540x960 logical size, and 179-pixel tiles. The verified dataset manifest SHA-256
is `4dac75139e4e7095f5843a696f5fcd84055bf798e90b49614d6e4243120f5dbe`.

The package contains only the `default` profile and was built at benchmark
source commit `c5d01d8ff1421b55a2be7d36dd135deae8d28a99` with the official SDK,
deployer, Launcher, and `libtcvm.dylib` from workflow run `37076804175`, artifact
`11256633898` (`TotalCross-7.2.2`), source SHA
`5a44f503bf6fa1bec350f1218f4d501a70fc4812`. The outer artifact digest is
`4eed292bc20af56ef55cbb7397ffc090c3690b1b1d8f41d75cfbb70ebe6cec41`; the
contained package ZIP SHA-256 is
`dddbc50ffae0ce3a1b6f3b315d99cf971190238524c960cd06035066cab337dd`, official
SDK JAR SHA-256 is
`389204c26d4377a5964d529ed6aaac0b751dd39c5546c6310918d085bb9baf49`, Launcher
SHA-256 is `3439082ff2b6e7bab37d7049b5860b6d4743297536bb7c9ba6806a2b45445884`,
and official `libtcvm.dylib` SHA-256 is
`421f957d551a75022a92db21638620732614e6d033a6f417ada09c6867cb8f24`.

The built default profile input JAR SHA-256 is
`2a1cfdac72df419d06dba242e868f7681ee82d0d65b3d482e20a5647df77a521`, deployed
executable SHA-256 is
`3439082ff2b6e7bab37d7049b5860b6d4743297536bb7c9ba6806a2b45445884`,
application TCZ SHA-256 is
`339fb1db93443a090de1416e757cc58b0c05a56c167aa4e105e750feaf57edc3`, and
deployed `libtcvm.dylib` SHA-256 is
`421f957d551a75022a92db21638620732614e6d033a6f417ada09c6867cb8f24`. The
package manifest SHA-256 is
`5b8842168d6558585ab730efaeb610f90e83e3bfa86a16115e172df8bf5abd9f`.

| Position | Phase | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | Rows / images per sample | Cumulative ImageControl paint (5 samples) |
|---|---|---:|---:|---:|---:|---:|---:|
| Top (0) | paint tree | 277.857 | 279.393 | 279.581 | 279.628 | 6 / 18 | 1388.710 ms |
| Top (0) | `repaintNow()` | 281.387 | 282.385 | 282.498 | 282.526 | 6 / 18 | 1388.268 ms |
| Middle (19545) | paint tree | 278.599 | 278.737 | 278.746 | 278.748 | 6 / 18 | 1389.005 ms |
| Middle (19545) | `repaintNow()` | 281.431 | 281.538 | 281.544 | 281.546 | 6 / 18 | 1389.126 ms |
| Bottom (39091) | paint tree | 278.873 | 279.340 | 279.424 | 279.444 | 6 / 18 | 1392.213 ms |
| Bottom (39091) | `repaintNow()` | 281.003 | 283.256 | 283.305 | 283.317 | 6 / 18 | 1389.679 ms |

Visible row/image counts matched between phases at every sample and all three
positions. The estimated median residual (`repaintNow()` p50 minus paint-tree
p50) was 3.530 ms at top, 2.833 ms in the middle, and 2.130 ms at bottom. No
sample painted the full corpus. Six rows and 18 images out of 221 rows and 663
images indicate that clipping/culling is working at all three positions.
Across each five-sample phase, cumulative `ImageControl.onPaint()` time was
about 1.389 seconds, or roughly 278 ms per sample. That nearly equals the
paint-tree median, so image-control painting accounts for nearly all measured
tree time. The additional repaint/update/present portion in this static probe
is small compared with the tree itself.

This supports the Java/UI paint tree as the main contributor to the earlier
roughly 323 ms scroll repaint observation. The fixed positions and stabilization
repaints make this probe different from continuously scrolling; its
`repaintNow()` p50 values were about 281 ms, so it does not explain the full
difference from the earlier 322.644 ms historical-driver median. Each phase has
only five samples, so the p95/p99 values and residual estimates are directional,
not stable tail estimates. No feature effectiveness or performance regression
claim is made.

The exact single-process runner command was:

    python3 runners/run.py image-rendering scroll --profile default --scroll-driver paint-split-probe --rounds 1 --warmups 0 --timeout-seconds 180 --width 540 --height 960 --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 --package-manifest .local-data/packages/image-rendering-macos-official-paint-split-c5d01d8/package-manifest.json --results-dir .local-data/results/image-rendering-paint-split-official --require-default-scroll-preflight --fail-fast

One measured app process ran, with one inline preflight record and no separate
preflight process. Raw output remains outside Git at
`.local-data/results/image-rendering-paint-split-official/run-20261003T012408Z-12993/`;
the default-only package and build log remain under
`.local-data/packages/image-rendering-macos-official-paint-split-c5d01d8/`.
No P12 matrix, preparation, SIGBUS, Windows, or additional benchmark work was
resumed.

## Official-package explicit preparation paint comparison (2026-10-02,
America/Sao_Paulo)

This one-process probe compares repeated paint-tree work at the top of the
default scroll viewport before and after one explicit
`scroll.prepareForDisplay(callback)`. It uses the official TotalCross package
from workflow run `37076804175`, artifact `11256633898` (`TotalCross-7.2.2`),
runtime source SHA `5a44f503bf6fa1bec350f1218f4d501a70fc4812`. The benchmark
package inventory contains only `default`; its manifest SHA-256 is
`e65b33ebd8a58b1cc1f90b75311e0dcac9be7136e8f8e656a68e18d1704a8351`. The
official SDK JAR, Launcher, and `libtcvm.dylib` hashes match the pinned values
recorded above. The deployed input JAR SHA-256 is
`935158309b87fe0a7a2b8b485de2d72780fbf71b0da91f77ea2c7312ec5ea606`, the
application TCZ is
`fa562554d98361a4c056fc4e54f972e320406fa46768ff4b10c86e0ce4dd93d8`, the
executable is
`3439082ff2b6e7bab37d7049b5860b6d4743297536bb7c9ba6806a2b45445884`, and the
deployed native library is
`421f957d551a75022a92db21638620732614e6d033a6f417ada09c6867cb8f24`.

The inline preflight confirmed RASTER, STANDARD storage, target-color
conversion/physical-variant cache/scroll raster reuse/automatic preparation
disabled, `LEGACY_PER_ENTRY_THREAD`, diagnostics disabled, and
`image-scroll/v1` with 663 controls, 221 rows, 3 columns, logical size 540x960,
and 179-pixel tiles. Phase A performed one untimed stabilization repaint and
five paint-tree samples at scroll position 0. The process then invoked
`prepareForDisplay` once and waited for its single callback before taking five
Phase C paint-tree samples. It reused the same UI instances throughout; the
scroll position and visible row/image counts matched across both phases.

| Top position (0) | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | ImageControl.onPaint p50 / sample | Cumulative ImageControl.onPaint (5 samples) | Rows / images per sample |
|---|---:|---:|---:|---:|---:|---:|---:|
| Before preparation | 278.192 | 280.546 | 280.845 | 280.920 | 277.762 ms | 1391.137 ms | 6 / 18 |
| After preparation | 3.532 | 3.760 | 3.799 | 3.808 | 3.255 ms | 16.516 ms | 6 / 18 |

`prepareForDisplay` was invoked at monotonic timestamp
`1200276079390000 ns`; its callback completed at
`1200276785966041 ns`. The measured wait was `706.576 ms`, with one request,
one callback, and status `callback-completed`. At request time, 18 visible
ImageControls were counted. The first prepared sample was 3.808 ms and all five
prepared samples remained below 3.81 ms. Before and after positions were both
0; every sample painted six rows and 18 ImageControls, so the timing comparison
is valid.

The absolute paint-tree p50 improvement was `274.660 ms`, a `98.73%`
reduction. In this controlled comparison, explicit preparation/materialization
state accounts for the dominant repeated `ImageControl.onPaint` cost. This
result does not identify a deeper native cause. RuntimeDiagnostics reported
unsupported in the official runtime, so internal ready/adopted/failure counts
were unavailable; only the visible request count and callback result were
recorded.

The exact one-process invocation was:

    python3 runners/run.py image-rendering scroll --profile default --scroll-driver paint-preparation-probe --rounds 1 --warmups 0 --timeout-seconds 180 --width 540 --height 960 --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 --package-manifest .local-data/packages/image-rendering-macos-official-paint-preparation-d466536/package-manifest.json --results-dir .local-data/results/image-rendering-paint-preparation-official --require-default-scroll-preflight --fail-fast

The runner summary records one successful measured child, zero failures, and
one inline preflight; it started no separate preflight process. The run source
commit was `d466536b3f4d3c0cf2b70eb1cd9e7caf0bfa711a`. Raw output remains
outside Git at
`.local-data/results/image-rendering-paint-preparation-official/run-20261003T015757Z-45068/`.
No second probe, fixed-step benchmark, historical driver, profile variant,
matrix, SIGBUS, or Windows run was started.


## Open follow-up: materialized cache admission policy

The historical `f5dad132cafea5c9086f6f946a6f44ca5bcb5f76`
implementation in `Image.resolveForDrawing` cached the resolved representation
immediately (presentation-state synchronization omitted here):

```java
Image resolved = resolvePipeline(...);
deferred.cacheMaterializedVariant(...);
return resolved;
```

Current master `5a44f503bf6fa1bec350f1218f4d501a70fc4812` uses
second-observation admission (presentation-state synchronization and generation
refresh omitted here):

```java
Image resolved = resolvePipeline(...);

boolean admitted =
    deferred.observeMaterializedVariant(
        scaleBits,
        sourceDecodeGeneration);

if (admitted) {
    deferred.cacheMaterializedVariant(
        scaleBits,
        resolved,
        sourceDecodeGeneration);
}
```

**This change is NOT considered an accepted final design decision.**

The user recalls that this tradeoff was explicitly discussed during the
original optimization work and that the conclusion favored immediate
admission.

After the historical performance comparison is complete, revisit the original
rationale, measurements, memory behavior and cache policy before proceeding
with a production fix.

This task does not change cache admission behavior or any TotalCross source.
The source difference is an unresolved follow-up, not proof of the cause of
any observed timing difference.


## Historical static probe: pre-measurement setup failure (2026-10-03)

The benchmark branch and remote both started at
`5a081100c6b1fb51e4ff382cfd164f9b85e5a6cc`. The existing separate historical
checkout `/Users/flsobral/repos/totalcross-history-f5dad132` was verified clean
at `f5dad132cafea5c9086f6f946a6f44ca5bcb5f76`, the requested historical
`codex/scroll-raster-reuse-windows-package` revision. No TotalCross source was
changed or committed; it remained clean after builds and the launch.

The historical SDK was rebuilt with `--rerun-tasks`, and `tcvm` and `Launcher`
were compiled in a fresh ARM64 Release native directory. The initial dependency
fetch hit a QR-code asset HTTP 404. The successful configure used an existing
prebuilt dependency cache at the exact historical depot-tools pin
`0ebff1d7202fab6e61758344219f60fa757fe6ce`, with the QR-code and SQLite release
tags used by the current comparison build. This reuses dependency prebuilts,
not current-master runtime binaries or SDK outputs. The CMake configuration
selected the software surface, Skia and SDL.

The isolated historical package compiled and deployed using the historical
SDK and the freshly built Launcher/library. Package validation checked that
both deployed native hashes matched their build outputs. The original shared
ScrollWorkload and manifest loader supplied the UI and measurement methods;
only diagnostic imports in staging and an untimed instance-identity helper
were added. Normal P12 runtime validation was not changed.

One application process was launched from tooling commit
`66c3e47b26dc11e8fb8d67769295c8859f0e1330`. Its inline preflight reported and
accepted configured/effective masks `32799/32799`. It then exited with code 1
while logging dataset identity at the end of UI construction:

```text
totalcross.json.JSONException: JSONObject["id"] not found.
totalcross.bench.imagerendering.ScrollWorkload.<C> 227
```

This was a benchmark tooling error: the generated config passed dataset
verification fields but omitted `id` and `version`. **No Phase A sample or
Phase B preparation request ran. There are no historical timing results from
this attempt and no performance conclusion can be drawn from it.** The process
also logged a resource-cache write warning (`Error Code: 30 - Read-only file
system`); execution continued past that warning to the configuration error.

Tooling commit `219c33e` fixes dataset metadata and adds a regression test. It
also handles native builds that echo the same protocol records to stdout and
DebugConsole, without counting duplicates as additional measured runs. The
launch-attempt guard and all first-attempt evidence are retained. The user
subsequently authorized exactly one replacement application process;
its completed measured run is documented below. The first failed process does
not count as the measured historical probe because it produced no samples or
preparation request.

Historical artifact SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| SDK JAR | `44d20645746cad03fdac67e757e6b088eb4a3082a2ecd9abea0c8d6e20451ef8` |
| Launcher | `a417b281f35ca00701977a60b420c3d50a5ef90f1176a52bcb3c4962756c8133` |
| libtcvm.dylib | `efd6b0e86146a32e9b3376b312728f1b0eea198d7b47f67b2616d99a2dae74ae` |

Exact successful build/deploy and first-attempt launch commands follow.
Benchmark commands use `/Users/flsobral/repos/totalcross-performance-lab` as
their working directory; deployment uses the staged historical runtime home.

```sh
cd /Users/flsobral/repos/totalcross-history-f5dad132/TotalCrossSDK && ./gradlew-agent dist -x test --rerun-tasks
cmake -S /Users/flsobral/repos/totalcross-history-f5dad132/TotalCrossVM -B /Users/flsobral/repos/totalcross-performance-lab/.local-data/historical-static-f5dad132/native-pinned -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 -DTCVM_DEPOT_TOOLS_DIR=/Users/flsobral/repos/totalcross-runtime-p12/TotalCrossVM/deps/totalcross-depot-tools -DSQLITE3_RELEASE_TAG=sqlite3-3.32.3-r2 -DQRCODEGEN_RELEASE_TAG=qrcodegen-20250123-r2
cmake --build /Users/flsobral/repos/totalcross-performance-lab/.local-data/historical-static-f5dad132/native-pinned --target tcvm Launcher -j 8
python3 tools/packaging/historical_paint_probe.py build --runtime-source /Users/flsobral/repos/totalcross-history-f5dad132 --native-build .local-data/historical-static-f5dad132/native-pinned --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 --output .local-data/historical-static-f5dad132/probe-final
python3 tools/packaging/historical_paint_probe.py run --package .local-data/historical-static-f5dad132/probe-final
/usr/bin/java -cp '/Users/flsobral/repos/totalcross-performance-lab/.local-data/historical-static-f5dad132/probe-final/classes:/Users/flsobral/repos/totalcross-history-f5dad132/TotalCrossSDK/dist/totalcross-sdk.jar:/Users/flsobral/repos/totalcross-history-f5dad132/TotalCrossSDK/dist/libs/*' tc.Deploy /Users/flsobral/repos/totalcross-performance-lab/.local-data/historical-static-f5dad132/probe-final/Default.jar -macos /p /n historical-static-paint /o /Users/flsobral/repos/totalcross-performance-lab/.local-data/historical-static-f5dad132/probe-final/deploy/
/Users/flsobral/repos/totalcross-performance-lab/.local-data/historical-static-f5dad132/probe-final/deploy/install/macos/historical-static-paint /scr -2,-2,540,960
```

Full expanded javac/deploy commands, source fingerprints, dataset identity,
CMake configuration and deployed hashes are in the ignored
`.local-data/historical-static-f5dad132/probe-final/package.json`. The local
`.local-data/historical-static-f5dad132/evidence.json` indexes commands, failure
state and artifact hashes. Logs remain in its `logs/` directory and the
`probe-final/` package. SDK full/agent logs remain in the historical checkout's
ignored `TotalCrossSDK/agent-logs/` directory.

`python3 -m unittest discover -s tests` passed all 59 tests after the fix;
`git diff --check` passed. The initial SDK build and forced SDK rebuild passed;
ARM64 Release configure/native build and final benchmark compile/deploy passed;
the application setup attempt failed as described above. No current-master
measurement was rerun. No scrolling driver, profile matrix, Windows build,
sanitizer matrix or full scrolling benchmark was executed: those are outside
this static-probe task.


## Historical static preparation paint comparison (2026-10-03)

The user authorized exactly one replacement application process after the
pre-measurement setup failure. That replacement **completed successfully**, exit
code 0, using the already corrected and verified package. No SDK/native rebuild
or tooling modification preceded this replacement launch, and no third process
was launched. Benchmark HEAD at measurement was
`9582e247a153cd6afb5827f361eae6dfe1d38dd5`; the branch and remote matched that
SHA before measurement. Historical TotalCross HEAD remained clean and unchanged
at `f5dad132cafea5c9086f6f946a6f44ca5bcb5f76`.

The inline preflight emitted and accepted both
`ImageOptimizationSettings.getMask() == 32799` and
`ImageOptimizationSettings.getEffectiveMask() == 32799` before measurement.
Both remained 32799 after measurement. No mask was set, no alternate profile or
prefetch mode was selected, and public runtime diagnostics were unavailable.
The native build provenance is the fresh ARM64 Release historical build and
artifact hashes recorded in the preceding section, not an official-package
runtime or current-master binary. Renderer metadata comes from the verified
native build configuration (software surface, Skia, SDL).

The shared manifest loader used image-scroll/v1 in its current manifest order:
663 images, 660 JPEG and 3 PNG, 221 rows, 3 columns, 179x179 tiles, and logical
resolution 540x960. The nested ScrollContainers, `new Image(File)` loading and
`getSmoothScaledInstance(179,179)` calls are the same shared workload code.
The measured inner viewport was 540x910, display scale 2, at position 0.
After one untimed stabilization repaint, Phase A collected exactly five
paint-tree samples. Phase B issued exactly one
`scroll.prepareForDisplay(callback)` and waited for one callback. Phase C
collected exactly five samples with no UI rebuild, Image replacement or scroll
movement. Every sample painted six rows and eighteen ImageControls; scrollbar
and content positions were 0 throughout. Reference snapshots checked the same
row, control and Image instances, and the result validator confirmed the same
18 visible manifest entries.

All five individual samples are below. Timings are in milliseconds; the raw
nanosecond values remain in the indexed result. Each row has counts 6/18 and
position 0 for both phases. Row time and ImageControl time are separately timed
callbacks, not disjoint components to add to the enclosing paint-tree time.

| Sample | Before paintTree | Before rowPaint | Before ImageControl | After paintTree | After rowPaint | After ImageControl |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 1.296500 | 0.234583 | 0.914624 | 7.722042 | 3.544958 | 3.902876 |
| 2 | 1.022375 | 0.211000 | 0.714042 | 0.924708 | 0.207583 | 0.652624 |
| 3 | 1.016875 | 0.207876 | 0.712380 | 0.913375 | 0.206084 | 0.643878 |
| 4 | 1.011292 | 0.207959 | 0.707416 | 0.943750 | 0.205875 | 0.668794 |
| 5 | 1.001375 | 0.208167 | 0.699208 | 0.983208 | 0.206709 | 0.708627 |

| Historical phase | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | ImageControl.onPaint p50/sample (ms) | Rows/images per sample |
|---|---:|---:|---:|---:|---:|---:|
| Unprepared | 1.016875 | 1.241675 | 1.285535 | 1.296500 | 0.712380 | 6 / 18 |
| Prepared | 0.943750 | 6.374275 | 7.452489 | 7.722042 | 0.668794 | 6 / 18 |

The preparation call started at `1208026483388958 ns`; the callback
completed at `1208040867705375 ns`. Wait: **14384.316417 ms**
(14.384316 s), with one request, one callback, eighteen visible
controls at request time, and status `callback-completed`. These visible counts
are benchmark geometry/count checks, not internal ready/adopted/cache counters.
The first prepared sample was **7.722042 ms**,
slower than every unprepared sample; the remaining four prepared samples were
0.913375–0.983208 ms.

| Metric | Historical f5dad132 (ms) | Current master 5a44f503 (ms) |
|---|---:|---:|
| Unprepared paintTree p50 | 1.016875 | 278.192 |
| Prepared paintTree p50 | 0.943750 | 3.532 |
| ImageControl.onPaint before p50/sample | 0.712380 | 277.762 |
| ImageControl.onPaint after p50/sample | 0.668794 | 3.255 |
| Preparation wait | 14384.316417 | 706.576 |

The current-master column is the previously completed reference supplied by the
user, not a rerun. The measured protocol has the same workload, manifest order,
stabilization and timed calls. The historical unprepared p50 was
277.175125 ms lower, about
273.58 times faster than the current reference.

The recurring expensive ~278 ms unprepared behavior **was not reproduced** in
the historical stabilized samples: historical painting was already fast before
any explicit preparation request. This is evidence of materially different
repeated-paint behavior. It does not measure the first-ever/cold paint or the
untimed stabilization repaint, so it cannot establish whether those historical
paints were expensive. It also does not establish that the cost of executing an
identical uncached internal path increased: the historical process may already
have been using a reusable representation or native fast path. Historical
warm-cache/reuse behavior remains a necessary investigation, not a proven
cache-hit mechanism or a production regression attribution.

Preparation did **not** produce a comparable collapse in historical median
paint cost: the decrease was only 0.073125 ms
(7.19%), versus the reference's 274.660 ms (98.73%).
The historical prepared median was also lower than the current reference;
preparation itself took substantially longer. The first prepared sample and
five-sample scope should remain visible when interpreting these percentiles.
No conclusion about cache-admission causality follows from this probe.

The historical `drawableDimensions` metadata is 0x0. Source inspection explains
this getter limitation: historical `Graphics.getSurfacePixelWidth/Height`
reads simulator-only static backing dimensions for control surfaces, whereas
native `tugG_create_g` / `tugG_refresh_iiiiiif` use native screen/control fields
and `screen.contentScale`. Current getters add a native pitch/scale fallback.
Thus 0x0 is not direct evidence of a zero-size native drawable. Logical geometry,
paint counts and display scale 2 were measured, but actual native drawable
pixel dimensions were not directly captured by this historical probe. This
metadata limitation is retained rather than silently replacing it with an
inferred drawable size.

Visible paths/formats, in manifest order (all eighteen are JPEG):

| Row index | Manifest indices | Paths | Format |
|---|---|---|---|
| 0 | 0–2 | `-1009782731.jpg`, `-1012043485.jpg`, `-1013143947.jpg` | jpeg |
| 1 | 3–5 | `-1015024107.jpg`, `-1026010547.jpg`, `-1028874041.jpg` | jpeg |
| 2 | 6–8 | `-1038926037.jpg`, `-104018500.jpg`, `-1040544427.jpg` | jpeg |
| 3 | 9–11 | `-1042033183.jpg`, `-1042180667.jpg`, `-1043960095.jpg` | jpeg |
| 4 | 12–14 | `-1056468936.jpg`, `-1059601584.jpg`, `-108958495.jpg` | jpeg |
| 5 | 15–17 | `-1096038007.jpg`, `-111131558.jpg`, `-1111384947.jpg` | jpeg |

The exact replacement invocation, from the performance-lab root, was:

```sh
python3 tools/packaging/historical_paint_probe.py run --package .local-data/historical-static-f5dad132/probe-replacement
```

Its native child command was:

```sh
/Users/flsobral/repos/totalcross-performance-lab/.local-data/historical-static-f5dad132/probe-replacement/deploy/install/macos/historical-static-paint /scr -2,-2,540,960
```

Raw result, stdout/stderr, DebugConsole, launch guard, process exit record and
package provenance remain outside Git under
`.local-data/historical-static-f5dad132/probe-replacement/`. The local
`evidence.json` indexes this successful replacement and the distinct failed
setup attempt. The unresolved **Open follow-up: materialized cache admission
policy** section above is preserved verbatim. No cache-admission implementation
or other TotalCross source was changed. No current-master run, scrolling driver,
additional profile/mask, third process, extra preparation request, Windows or
P12 matrix was executed.


Post-run validation: `python3 -m unittest discover -s tests` passed all 59 tests;
`git diff --check` passed. Only this checkpoint documentation changed after the
run. No expensive platform, sanitizer or benchmark matrix was run, as the user
restricted this task to one historical static probe. No runtime/source rebuild
was needed for the replacement. PR #1 is not merged.


## Current-master native draw-path classification (2026-10-03)

Exactly one application process ran from benchmark commit
`b9506e892b407813e73756c6b44dde8ffb803bc4` on `perf/image-rendering-benchmarks`.
It used the previously validated official `TotalCross-7.2.2` package,
workflow run [37076804175](https://github.com/TotalCross/totalcross/actions/runs/37076804175),
artifact `11256633898`, source SHA
`5a44f503bf6fa1bec350f1218f4d501a70fc4812`. The official SDK, Launcher and
libtcvm hashes were revalidated against the package provenance before launch
and during offline analysis. No TotalCross source or binaries were rebuilt or
modified. Package manifest and source/deployed artifact hashes are indexed once
in `.local-data/draw-path-probe/evidence.json`.

The inline preflight accepted default RASTER/STANDARD on macOS ARM64, runtime
diagnostics disabled, target-color conversion/physical-variant cache/scroll
raster reuse/automatic preparation disabled, and LEGACY_PER_ENTRY_THREAD.
The verified image-scroll/v1 manifest has 663 images (660 JPEG, 3 PNG), 221
rows and 3 columns; logical dimensions are 540x960, tiles 179x179, inner viewport
540x910, scale 2 and drawable 1080x1920. The normal nested ScrollContainers and
Image creation/scaling were unchanged. All measured calls stayed at position 0
with the same row, ImageControl and Image references.

Protocol: one ordinary untimed stabilization repaint, one whole-tree sample,
then one direct `control.onPaint(control.getGraphics())` per visible control in
manifest order, resetting existing test accounting before each sample. No
preparation request, scroll pass, additional stabilization, alternate profile,
mask, historical runtime, Windows, matrix or cache-policy experiment ran.

The exact runner command, from the performance-lab root, was:

```sh
python3 runners/run.py image-rendering scroll --profile default \
  --scroll-driver draw-path-probe --rounds 1 --warmups 0 \
  --timeout-seconds 180 --width 540 --height 960 \
  --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 \
  --package-manifest .local-data/packages/image-rendering-macos-official-draw-path-probe/package-manifest.json \
  --results-dir .local-data/results/image-rendering-draw-path-probe \
  --require-default-scroll-preflight --fail-fast
```

The sole native child command was:

```sh
/Users/flsobral/repos/totalcross-performance-lab/.local-data/packages/image-rendering-macos-official-draw-path-probe/profiles/default/image-rendering-default /scr -2,-2,540,960
```

### Complete measurement and offline recovery

The child exited successfully and emitted one run plus one final summary,
including all 19 measured calls. The runner then exited 1 on a post-process
validation error: `$.aggregate.statusHex has an invalid format`. The raw status
was 217099, but the benchmark emitted `0x500B`. The SDK's native substitute
`Integer4D.toHexString(int)` calls `Convert.unsigned2hex(i, 4)`, producing four
uppercase digits; canonical full-width hex for that integer is `0x3500b`.
This was a benchmark presentation error after measurement, not a failed paint.

The original helper also omitted the identity-fallback classification because
it used only `Image.physicalIdentityFallbackCountForTest()`, which returned 0.
The native returned status has `DRAW_IDENTITY_FALLBACK` set in every sample.
Source inspection explains the accounting distinction: `tugG_copyRectPlanNative`
records direct executions but does not increment Image's identity hit/fallback
fields, whereas `tugG_drawGeometryNative` increments those fields. The bridge
records identity attempts and generic/smooth events from the returned status.
The raw getter counters remain 0; they are not replaced with inferred counts.

Benchmark-only fixes now format all status bits and classify identity outcomes
from the status flags as well as getter counters. An offline analyzer repairs
only the two known presentation defects for the original benchmark commit,
preserving emitted strings/classifications and all timings/counters. It validates
package hashes, the original run/summary protocol, inline preflight, retained
instances, geometry, exact manifest order, status bits, counter consistency and
timing statistics. The ordinary runner remains strict. Its original failure
record and raw stdout remain intact; the offline analysis reports `validated`.
No application was launched again and no rebuilt package was used for these
measurements.

Exact offline analysis command:

```sh
python3 tools/analyze_draw_path_probe.py \
  --stdout .local-data/results/image-rendering-draw-path-probe/run-20261003T044727Z-49989/processes/0001-default-measured-1/stdout.log \
  --package-manifest .local-data/packages/image-rendering-macos-official-draw-path-probe/package-manifest.json \
  --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 \
  --output .local-data/draw-path-probe/analysis.json --recover-legacy-status
```

### Aggregate accounting

Whole-tree paint: **290.778208 ms** (`290778208 ns`),
**6 rows / 18 ImageControls**, position 0. Enclosed ImageControl paint time:
290.292039 ms; enclosed row paint time: 0.274626 ms.
These callback timings are enclosed measurements, not independent components.

| Existing counter/state | Value |
|---|---:|
| `cachedFinalRasterHits` | 0 |
| `cachedFinalRasterMisses` | 18 |
| `cachedFinalRasterProbes` | 18 |
| `copyRectPlanAttempts` | 18 |
| `copyRectPlanFallbacks` | 0 |
| `copyRectPlanHandled` | 18 |
| `copyRectPlanLastStatus` | 217099 |
| `directDrawPlanExecutions` | 18 |
| `genericGeometryDraws` | 18 |
| `identityAttempts` | 18 |
| `identityFallbacks` | 0 |
| `identityHits` | 0 |
| `physicalCopyHits` | 0 |
| `physicalVariantFallbacks` | 0 |
| `physicalVariantHits` | 0 |
| `physicalVariantMaterializations` | 0 |
| `smoothResampleDraws` | 18 |
| `targetColorFallbacks` | 0 |
| `targetColorHits` | 0 |
| `targetColorMaterializations` | 0 |

Aggregate last status: 217099 / `0x3500b`; decoded SDK flags: handled,
identity attempted, identity fallback, generic geometry and smooth resample.
Identity hit, physical-copy hit and every target-color/physical-variant flag
are false. `unexpectedDisabledPathActivity` is false; all target-color and
physical-variant hit/materialization/fallback counters are zero.
Physical-copy accounting exposes only hits; there are no attempt/fallback
counters to report. Aggregate last status describes only its last plan attempt,
so it does not provide an aggregate identity-fallback count.

### Eighteen per-control samples

Classification **F** for every row: cached-final miss; physical identity
attempted and fell back; no physical-copy hit; generic geometry; smooth resample;
draw handled. Native identity hit and all target-color/physical-variant flags
are false. All rows have one plan attempt, one handled draw, zero plan fallback,
one cached-final probe/miss, one identity attempt, one generic draw, one smooth
resample and one direct execution. Getter identity hit/fallback counters and
physical-copy/target-color/physical-variant counters are 0. Each paints one
ImageControl and no row; no control issues more than one plan attempt.
The raw status integer is unchanged; hex and F are the offline interpretation.

| Manifest index | Path | Format | Elapsed (ms) | Classification | Raw integer / canonical hex |
|---|---|---|---:|---|---|
| 0 | `-1009782731.jpg` | jpeg | 19.064541 | F | 217099 / `0x3500b` |
| 1 | `-1012043485.jpg` | jpeg | 18.837666 | F | 217099 / `0x3500b` |
| 2 | `-1013143947.jpg` | jpeg | 19.397667 | F | 217099 / `0x3500b` |
| 3 | `-1015024107.jpg` | jpeg | 19.502584 | F | 217099 / `0x3500b` |
| 4 | `-1026010547.jpg` | jpeg | 19.523792 | F | 217099 / `0x3500b` |
| 5 | `-1028874041.jpg` | jpeg | 18.890167 | F | 217099 / `0x3500b` |
| 6 | `-1038926037.jpg` | jpeg | 18.781209 | F | 217099 / `0x3500b` |
| 7 | `-104018500.jpg` | jpeg | 18.937167 | F | 217099 / `0x3500b` |
| 8 | `-1040544427.jpg` | jpeg | 18.593458 | F | 217099 / `0x3500b` |
| 9 | `-1042033183.jpg` | jpeg | 18.601375 | F | 217099 / `0x3500b` |
| 10 | `-1042180667.jpg` | jpeg | 18.546708 | F | 217099 / `0x3500b` |
| 11 | `-1043960095.jpg` | jpeg | 18.679500 | F | 217099 / `0x3500b` |
| 12 | `-1056468936.jpg` | jpeg | 18.593916 | F | 217099 / `0x3500b` |
| 13 | `-1059601584.jpg` | jpeg | 19.303000 | F | 217099 / `0x3500b` |
| 14 | `-108958495.jpg` | jpeg | 19.365750 | F | 217099 / `0x3500b` |
| 15 | `-1096038007.jpg` | jpeg | 0.453125 | F | 217099 / `0x3500b` |
| 16 | `-111131558.jpg` | jpeg | 0.397250 | F | 217099 / `0x3500b` |
| 17 | `-1111384947.jpg` | jpeg | 0.389292 | F | 217099 / `0x3500b` |

Individual timing (ms): min **0.389292**,
median **18.809438**,
max **19.523792**,
sum **285.858167**.
Indices 0–14 took 18.546708–19.523792 ms each, while indices 15–17 took
0.389292–0.453125 ms. These are single control measurements, not distributions.

The sum exceeds the earlier 277.762 ms cumulative ImageControl reference by
8.096167 ms (**2.91%**), reasonably consistent for one probe. Aggregate enclosed
ImageControl time is 290.292039 ms; whole-tree time is 290.778208 ms, compared
with the supplied earlier paint-tree p50 of 278.192 ms. The earlier reference
was not rerun.

### Interpretation and next target

The draw-path hypothesis is confirmed by the returned native status for **all
18 individual controls**: identity attempt → identity fallback → generic
geometry → smooth resample. No cached-final, identity or physical-copy hit was
observed. The aggregate has exactly 18 attempts, handled draws, cached-final
misses, identity attempts, generic draws and smooth resamples, with zero cache
hits, identity getter hits and physical-copy hits. The proposed approximate
identity-fallback counter of 18 was **not** observed: that getter returned 0,
while all 18 independently captured statuses reported fallback. This accounting
limitation is explicit, not forced to match the hypothesis.

The next investigation target is the historical
`drawPhysicalFastPath` / `buildRasterPhysicalPlan` versus current
`physicalIdentityMapping` / `physicalIdentityDraw`, particularly why the same
179x179 presentation falls back from a cheap physical draw. This task identifies
that target; it does not investigate or implement the production fix. The
**Open follow-up: materialized cache admission policy** section is preserved
verbatim and remains unresolved and out of scope.

Raw stdout/stderr, preflight, process config and original runner failure are
under `.local-data/results/image-rendering-draw-path-probe/run-20261003T044727Z-49989/`.
The launch guard, canonical analysis, build/test logs and evidence index are
under `.local-data/draw-path-probe/`; all remain outside Git.

Validation after the complete measurement and benchmark-only recovery fixes:
`python3 -m unittest discover -s tests` passed all 70 tests, including 11 focused
draw-path contracts and saved-output recovery cases; `git diff --check` passed.
The corrected benchmark sources compile against the same official SDK with
`javac --release 8`; no replacement package or application process was created.
The offline analyzer passed the complete result contract against the verified
manifest and package. The original runner validation failure remains recorded.
No platform matrix, sanitizer, scrolling benchmark or extra performance sample
was run because this task is restricted to the single static draw-path process.


## Physical mapping metadata probe: read-only capture failure (2026-10-03)

Exactly one application process was launched from benchmark commit
`3ac6d5b019a0fdc079952ce8329d5aa1b485c791` on
`perf/image-rendering-benchmarks`. The package used the previously validated
official TotalCross 7.2.2 runtime, workflow 37076804175, artifact 11256633898,
source `5a44f503bf6fa1bec350f1218f4d501a70fc4812`. Package/source/deployed hashes
and helper inclusion were verified before launch. No SDK/native runtime rebuild
or TotalCross source modification occurred.

The inline preflight emitted default RASTER/STANDARD, macOS ARM64, diagnostics
disabled, all optional image variants/scroll reuse/automatic preparation disabled,
logical 540x960, 663 images, 221 rows, 3 columns and 179-pixel tiles. The mode
uses normal uninstrumented controls, one untimed stabilization repaint at top 0,
and no timed painting, preparation or scrolling. The capture helper obtains the
normal draw plan at each control's Graphics contentScale and is designed to
record all requested plan/backing/Graphics metadata. The host evaluator covers
the exact scale/smooth-scale chain, clipping and fifteen ordered gates for both
allowSmooth=true and false. Unsupported chains are rejected, not approximated.

### Exact execution failure

The child exited 1 before the first metadata sample was emitted:

```text
java.lang.IllegalStateException:
read-only Image generation capture requires zero backing generation
ImageDrawPathProbeAccess.mappingMetadata:126
ScrollWorkload.runPhysicalMappingProbe:509
```

The helper observed a **nonzero backing mutation generation**. Its numerical
value was not emitted and must not be inferred. The raw Image generation field
is private; deployed reflection explicitly rejects private-field access. The
existing package-private `backingMutationGenerationForP2()` accessor assigns
`max(Image generation, backing generation)` to the Image field. To honor the
explicit prohibition on mutating Images during inspection, the helper requires
zero backing generation before invoking that accessor: with nonnegative Image
generation, its assignment cannot change the value. This restrictive benchmark
precondition was disproved by execution and stopped capture before the accessor.

This is **not** a measured first failing gate of native
`physicalIdentityMapping()`. No run record or final summary was emitted, and no
per-control plan metadata, derived a/d, canvas/drawable scale, ordered native gate
results or root-size correlation was obtained. The prior draw-path results
remain valid, but they do not supply this missing metadata. No 18-control mapping
table or gate distribution can honestly be reported from this process.

The earlier conclusion remains: all 18 prior draws used identity/copy fallback,
generic geometry and smooth resampling. The source predicate
`transform.a/d == canvasScaleX/Y` remains a candidate, **not a confirmed rejecting
condition**. Historical `buildRasterPhysicalPlan` constructs a general
canvas-to-root mapping, inverts it and derives root-to-device scale; the current
predicate instead requires one-to-one source/device extents. This source
difference alone does not establish this process's native rejection or support a
production fix. The previous ~19 ms versus ~0.4 ms root/resampling-ratio correlation
is likewise unresolved without the missing root/backing values and actual clip.

Exact runner command:

```sh
python3 runners/run.py image-rendering scroll --profile default \
  --scroll-driver physical-mapping-probe --rounds 1 --warmups 0 \
  --timeout-seconds 180 --width 540 --height 960 \
  --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 \
  --package-manifest .local-data/packages/image-rendering-macos-official-physical-mapping-probe/package-manifest.json \
  --results-dir .local-data/results/image-rendering-physical-mapping-probe \
  --require-default-scroll-preflight --fail-fast
```

Sole native child command:

```sh
/Users/flsobral/repos/totalcross-performance-lab/.local-data/packages/image-rendering-macos-official-physical-mapping-probe/profiles/default/image-rendering-default /scr -2,-2,540,960
```

Raw failure/preflight/stdout/stderr/config remain outside Git in
`.local-data/results/image-rendering-physical-mapping-probe/run-20261003T052210Z-73701/`.
The exclusive launch guard and evidence index remain under
`.local-data/physical-mapping-probe/`. There is exactly one process directory,
zero metadata records and zero preparation requests; no second process, historical
runtime, additional performance benchmark, alternate profile/mask, Windows, P12
matrix, cache experiment or production fix was attempted. The authorized process
allowance is consumed. Additional runtime evidence requires a separately
authorized process after resolving the read-only capture constraint, or externally
provided equivalent metadata. This task's measurement objective remains incomplete.

The **Open follow-up: materialized cache admission policy** section is unchanged
and remains explicitly unresolved and out of scope.

Post-run validation: `python3 -m unittest discover -s tests` passed all 79 tests;
`git diff --check` passed. The nine new focused contracts cover metadata, exact
composition, ordered failures, clipping, unsupported chains, default-only/no-
preparation restrictions and read-only guards. The benchmark compiled/deployed
against the official SDK without a runtime rebuild. Those green contracts do
not prove the missing native rejection measurements; the runtime capture failed.
Expensive platform, sanitizer and benchmark validation was omitted because it
is outside the authorized single metadata process.

The manifest confirms that the three previously fast files
`-1096038007.jpg`, `-111131558.jpg` and `-1111384947.jpg` are each 1000x1000,
the same intrinsic size as fourteen of the fifteen slower files;
`-1042033183.jpg` is 1024x1024. Intrinsic size therefore does not distinguish the
fast group. Root/backing sizes and actual clipping remain unmeasured here, so
this cannot determine the requested root-size or resampling-ratio correlation.


## Physical mapping probe: offline read-only capture repair (2026-10-03)

The benchmark-only helper now captures nonzero backing mutation generations and
all independently readable plan, dimensions, scales, backing and Graphics
metadata. It never calls the synchronizing Image mutation-generation accessor.
The raw Image generation is explicitly unavailable: `sourceMutationGeneration`
is null and `sourceMutationGenerationAvailable` is false. The schema also accepts
an integer with availability true for evaluator fixtures; those fixtures are not
new runtime evidence. Inconsistent availability/value pairs are rejected.

The former zero-generation precondition is removed. The final observation checks
only backing reference identity and the pure backing-generation getter, reported
as `inspectionObservableStateUnchanged`. It does not assert that the unobservable
Image generation was checked. The repeated draw-plan request is also removed.

Both smooth-eligible and strict identity evaluations preserve all fifteen ordered
predicates. `pass` and `reached` are true/false/null, with null meaning unknown.
`mutationGenerationsEqual` is unknown when the raw Image generation is unavailable.
Scale equality, source bounds/integer coordinates, device destination integers
and extent predicates remain independently evaluated. A later known failure is
reported by `earliestKnownFailingGate`; `unresolvedEarlierGates` lists unknown
predicates before it (or all unknown predicates if no failure is known).
`firstFailingGate` and its name stay null across an earlier unknown. A known
failure before any unknown remains definitive. `allGatesPass` is false for any
known failure, null if only uncertainty remains, and true only for all true gates.

Validation: `python3 -m unittest discover -s tests` passed all 82 tests and
`git diff --check` passed. Eight benchmark Java sources compiled with
`javac --release 8` against the official TotalCross 7.2.2 SDK. Full platform,
sanitizer and benchmark validations are omitted because this change is offline
benchmark tooling and no runtime process is authorized.

Offline validation covers nonzero backing metadata with unavailable Image
generation, both known true and false later scale predicates, ordered uncertainty,
clipping, transform composition, unsupported chains and the absence of the
synchronizing accessor in probe source. Official-SDK compilation/deployment
prepares a replacement package only; no generated application is executed.
No TotalCross runtime/SDK source is changed and no new runtime evidence is claimed.
The failed capture above remains the last actual measurement attempt. A future
process requires separate authorization. The materialized cache admission policy
section remains unchanged and explicitly unresolved.

Proposed future command (not executed; exactly one process after authorization):

```sh
python3 runners/run.py image-rendering scroll --profile default \
  --scroll-driver physical-mapping-probe --rounds 1 --warmups 0 \
  --timeout-seconds 180 --width 540 --height 960 \
  --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 \
  --package-manifest .local-data/packages/image-rendering-macos-official-physical-mapping-readonly-probe/package-manifest.json \
  --results-dir .local-data/results/image-rendering-physical-mapping-readonly-probe \
  --require-default-scroll-preflight --fail-fast
```


## Physical mapping probe: successful read-only capture (2026-10-03)

A new explicit authorization permitted exactly one corrected native application
process from published benchmark HEAD
`564ce7c1bbda2b4995108683696d954631be04ca`. Before launch, the benchmark
working tree was clean, the default-only official 7.2.2 package matched this
commit, package/runtime provenance and hashes passed, and the verified
`image-scroll/v1` manifest matched the package. The new result directory did not
exist; an exclusive authorization guard recorded the prelaunch checks. No other
benchmark, warmup, separate preflight, replacement, historical runtime, platform
build, cache experiment or P12 matrix ran. TotalCross source remains unchanged.

The exact requested runner command produced one native child exit **0**, runner
exit **0**, one complete valid metadata record for all eighteen controls, and
zero failures. The inline preflight was part of the same child process. There
were zero timed paint samples and zero preparation requests. Initialization
logged a read-only-filesystem UI-resource warning, but both required records
were complete and valid; no recovery/relaunch occurred.

Detailed per-control metadata, rectangles, both gate evaluations, the eighteen-
control gate table and true/false/unknown distributions are in
[p12-physical-mapping-probe-2026-10-03.md](p12-physical-mapping-probe-2026-10-03.md).
The complete validated record and evidence index (original paths and hashes,
including package and previous draw-path evidence) are durably preserved in
[evidence/p12-physical-mapping-probe-2026-10-03.json](evidence/p12-physical-mapping-probe-2026-10-03.json).
The sole process directory is
`.local-data/results/image-rendering-physical-mapping-readonly-probe/run-20261003T054657Z-90240/processes/0001-default-measured-1/`.

Actual application dimensions are 540×960, viewport 540×910, drawable 1080×1920,
and Graphics content scale 2. Every plan has a single smooth-scale operation
`[1]`, parameters `[179,179,0,0]`, dimensions/output 179×179, root content scale
0.5, and unit root/presentation hardware scales. Seventeen intrinsic/logical
roots are 1000×1000 with physical roots/backings 500×500; index 9 is 1024×1024
with 512×512 physical root/backing. All native backings are valid and stable with
mutation generation **1**; raw Image generation is unavailable (`null`,
availability false). No unavailable value was inferred or synchronized.

Both source-derived scale-equality predicates are false for **every** control:
`a=d=500/179≈2.793296089385475` for seventeen, `512/179≈2.8603351955307263`
for index 9, against canvas scales `(2,2)`. This is a **demonstrated sufficient
rejection condition for every control**, not an assertion of the earliest native
failure. No control refutes the scale-equality hypothesis. Generation equality
is unknown 18/18. In both modes `firstFailingGate=null` and
`unresolvedEarlierGates=[2]`; smooth's `earliestKnownFailingGate=9`
(`aEqualsCanvasScaleX`), strict's is 5 (`smoothEligible`). Later independent
predicates are available: bounds/device integrality pass 18/18; source
integrality passes 15 and fails 3; width/height extent equality fail 18/18.
The other stable/compile/no-fill/positive-axis/integer-translation predicates
pass 18/18; smooth eligibility passes 18/18 for allowSmooth=true and fails 18/18
for strict identity. This is consistent with the prior draw-path record that
all eighteen reached generic geometry plus smooth resampling, without new timing
or native counters.

The previously fast paths `-1096038007.jpg`, `-111131558.jpg`,
`-1111384947.jpg` occupy row 5 (indices 15–17). Root/backing size, transform scale,
operation and physical source/device resampling ratios match fourteen slower
controls, so they do not separate the groups. **Captured clipping and visible
area do separate them:** bottom-row Y=947 clips the source/destination height
to 3, versus height 179 at Y=42,223,404,585,766 for the fifteen slower controls.
Visible logical areas are 537 versus 32,041 and device areas 2,148 versus
128,164, a 59.666667× ratio. Physical mapped source height is
8.379888268156424 versus 500 for the shared 500-root geometry. The source/device
ratio remains 1.3966480446927374 in both axes, including the clipped controls.
Prior ImageControl medians are 0.397250 ms versus 18.890167 ms (47.552339×).
This correlation is consistent with reduced visible smooth-resampling work;
it does not establish causal attribution or exact proportional scaling from
separate probes. No production change or additional experiment follows here.

Cheap offline validation: `python3 -m unittest discover -s tests` passed all
82 tests; `git diff --check` passed. Revalidation of the durable record reproduced
both gate evaluations for all eighteen controls, checked exactly one process and
one successful record, and verified preserved artifact hashes. No SDK compilation,
deployment, platform build, sanitizer or further runtime validation was needed.
The **Open follow-up: materialized cache admission policy** section is preserved
verbatim and remains explicitly unresolved and out of scope.


## copyRect causal experiment: implementation checkpoint (2026-10-03)

The next authorized experiment isolates whether current copyRect draw-plan generic
smooth handling prevents the existing resolveForDrawing/materialized-raster path.
An experiment-only runtime based on `5a44f503bf6fa1bec350f1218f4d501a70fc4812`
is committed locally as `fc08c39499dead73b327ad259a992ab34ec42870`.
Its canonical reproducible patch, ExecPlan and build provenance/hash index are
under `experiments/p12-copyrect-causal/`. Apply the zero-context patch with
`git apply --unidiff-zero runtime.patch` to the exact base. No runtime changes
are proposed as production architecture or cache-admission fixes.

A test-only field remains disabled during normal startup, then enables only the
explicit stabilization and five samples. Native copyRect keeps unchanged physical
copy/identity eligibility and returns unhandled on rejection before generic or
variant drawing, allowing unchanged Java copyRect to reach resolveForDrawing.
The production second-observation implementation in ImagePipeline is byte-identical
to the base. Counters observe cached-final probes/hits/misses, copy/identity routing,
direct generic/smooth draw, resolve calls, observations/admissions and native
geometry materializations. The full stabilization accounting is captured untimed;
exactly five whole-tree paints then retain six rows/eighteen ImageControls and
same Images at position zero, without preparation or movement.

The normal benchmark still compiles against the official SDK; experimental hook
classes and entry are selected only by `--copyrect-causal-experiment`. The causal
runner accepts only the exact custom runtime SHA and matching canonical patch,
default-only experiment entry, inline preflight and verified dataset. The runtime
uses typed policy defaults, not the retired raw optimization-mask API; preflight
and equal before/after configuration reports verify unchanged defaults.

Pre-measurement checks passed: 90 Python tests (eight new causal contracts),
focused native physical-copy routing tests, current-year header validation,
Release macOS arm64 tcvm/Launcher build, custom SDK distribution and benchmark
Java compilation against both official and experimental SDKs. Configuration
initially needed the existing SQLite tag and canonical SDL dependency path;
these were resolved without source changes. All normal build artifacts and logs
remain local. No measured native application process has run at this checkpoint.
The source/tooling checkpoint is committed before packaging/sole launch. The
cache-admission follow-up section remains unchanged and explicitly unresolved.


## copyRect causal probe: final-raster reuse demonstrated (2026-10-03)

The single authorized causal process succeeded from lab implementation
`e9cb47bbe2750ec3a19341514283b9f19002d8b4` and custom TotalCross source
`fc08c39499dead73b327ad259a992ab34ec42870` (base current reference `5a44f503`).
**Runner count 1 / exit 0; measured native application count 1 / exit 0.**
One complete valid run/summary and inline preflight were emitted. No replacement,
warmup, separate preflight, preparation, movement, alternate profile/policy,
historical run, Windows run or P12 matrix ran. The single focused native unit-test
executable ran before measurement and is counted separately from application
processes. Raw runtime output and normal build artifacts remain local.

The dedicated [causal report](p12-copyrect-causal-probe.md) contains all five
timings, per-event counters/classifications, comparison, confidence and limits.
The canonical [provenance/hash index](../experiments/p12-copyrect-causal/provenance.json)
records exact SDK/Launcher/libtcvm artifacts, source/benchmark commits, build and
runner commands, exits, and hashes of the preserved sole-process evidence under
`.local-data/results/image-rendering-copyrect-causal-probe/run-20261003T062742Z-26394/`.
The initialization read-only-filesystem resource warning was nonfatal; the native
exit was explicitly captured in `exit-status.json` and stderr was empty.

Actual geometry stayed application 540×960, viewport 540×910, drawable 1080×1920,
scale 2, top 0, six rows/eighteen ImageControls out of 663 ordered dataset images.
Retained control/Image/row references and identical before/after production
configuration reports passed. The switch was off during normal startup, then
on only for the explicit stabilization and five measured paints.

| Paint event | paintTree ms | ImageControl total ms | Cached-final probes/hits/misses | Variant observations/admissions | Native geometry materializations |
| --- | --- | --- | --- | --- | --- |
| Stabilization (untimed tree) | — | 348.214998 | 18/0/18 | 18/0 | 18 |
| Sample 1 | 349.357000 | 348.897248 | 18/0/18 | 18/18 | 18 |
| Sample 2 | 3.588625 | 3.275458 | 18/18/0 | 0/0 | 0 |
| Sample 3 | 3.576917 | 3.277625 | 18/18/0 | 0/0 | 0 |
| Sample 4 | 3.570500 | 3.264083 | 18/18/0 | 0/0 | 0 |
| Sample 5 | 3.570541 | 3.271419 | 18/18/0 | 0/0 | 0 |

Stabilization and sample 1 each had 18 physical-copy attempts, zero hits,
18 fallbacks; 18 identity attempts/fallbacks; 18 copyRect draw-plan attempts,
zero handled, 18 fallbacks (last status 20490 / `0x500a`). They reached existing
resolveForDrawing and materialized all eighteen destination-scale variants.
Stabilization admitted none, and sample 1 admitted all eighteen at observation
two. Samples 2–5 each hit all eighteen cached-final rasters with zero draw-plan
attempts, physical/identity activity, variant observations/admissions or native
geometry materializations. Direct generic/smooth draw counters were zero in all
six events because the experimental route returns unhandled before those paths.
Offscreen geometry/smooth materialization occurred only during stabilization and
sample 1, then ceased after admission. Disabled variant-path counters stayed zero.

Resolve calls were 20/20/2/2/2/2 over the six events, with zero hits inside resolve.
Counter conservation plus the unchanged resolver shows two non-deferred (`pipeline
== null`) resolves per paint; their call sites were not identified. They do not
represent final-raster cache failures: cached-final probing is earlier, and the
visible controls bypassed resolve on samples 2–5. Every event still painted 6/18.

**The detailed predicted protocol occurred:** expensive stabilization/first
observation, expensive measured sample 1/second observation/admission, then fast
cached-final samples 2–5. Their median 3.573729 ms is close to current prepared
3.532 ms and far below current recurring unprepared 278.192 ms. It remains above
historical stabilized unprepared 1.016875 ms. The experiment ends the repeated
expensive path without changing current second-observation admission; it does
not restore historical absolute timing or decide immediate admission policy.

**High-confidence causal conclusion for this workload/configuration:** current
copyRect generic smooth HANDLED prevents the existing final-raster fallback from
being exercised. Letting physical rejection fall through exposes the expected
observation/admission/cache-hit sequence and eliminates recurring geometry work.
This matches the prior all-eighteen generic-geometry/smooth-resample evidence.
Absolute cross-runtime ratios remain limited by separate reference processes,
custom Release build/test accounting and one measured process. The colder
349 ms paint may include full-variant work for the heavily clipped bottom row;
that explanation was not separately tested. No further experiment or production
fix is authorized by this finding.

Validation passed: all 90 Python tests, focused native routing assertions,
header checks, SDK/native builds, normal-official and custom-causal Java compilation,
custom deployment, offline valid/truncated/duplicate parser fixtures and original
artifact/hash/one-process revalidation. `git diff --check` passed. No broad
platform/sanitizer/benchmark validation was performed. Production admission,
physical eligibility, JPEG decode, preparation, renderer/runtime defaults and
unrelated behavior remain unchanged outside the isolated enabled routing test.
The **Open follow-up: materialized cache admission policy** section is preserved
verbatim, remains unresolved and is explicitly out of scope.


## Isolated immediate-admission experiment — implementation ready

The new experiment derives from routing revision `fc08c394` and changes only
the successful exact-scale materialized-variant admission decision, guarded by
experiment-only immediate/physical-only/accounting fields. Isolated source
`f95c280db3d6856d17582ea31d47aaded6a0e492` keeps ImagePipeline, native routing/geometry, decode, cache
keys/validity, preparation and production defaults unchanged relative to that
parent. Normal packages exclude its hooks. The same causal protocol supplies
one untimed stabilization and five timed tree samples with retained UI instances.

Before measurement, 58 focused SDK tests (nine admission cases), native physical
identity/surface assertions, 97 lab Python tests, normal official/custom Java
compilation and focused header validation passed. ARM64 Release SDK, tcvm and
Launcher are built and hashed. Source patches and build evidence are indexed in
`experiments/p12-immediate-admission/provenance.json`. Packaging and the sole
measurement remain pending. This is experimental evidence gathering; production
admission policy and the historical warm-path residual remain unresolved.
