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
