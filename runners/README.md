# Runners

Cross-platform benchmark orchestration lives here.

Runners should favor fresh-process execution, explicit timeouts, deterministic matrix order, validated machine-readable output, and recorded environment/runtime provenance. Platform-specific wrappers are acceptable when required, but parsing and result contracts should remain shared where practical.

## Image-rendering suite

The standard-library Python runner supports macOS and Linux. Point it at a clean
TotalCross source checkout and a locally verified corpus:

```sh
export TOTALCROSS_SOURCE=/path/to/totalcross
python3 runners/run.py dataset fetch image-scroll/v1
python3 runners/run.py image-rendering scroll --profile default --rounds 3 \
  --runtime-file /path/to/launcher
```

Decode uses the full filesystem/TCZ × full/half scale × sequential/seeded-random
matrix by default. `--sources`, `--scales`, and `--orders` narrow that matrix;
`--profile` selects named production configurations. Scroll and preparation
accept multiple comma-separated profiles. Every cell has a preflight process,
optional warmups, and fresh measured processes. The runner stores logs and
results beneath `results/image-rendering/`.

The PowerShell 5.1 runner has its own dataset fetch and verify paths and does not
require Python:

```powershell
$env:TOTALCROSS_SOURCE = 'C:\src\totalcross'
.\runners\windows\run-image-rendering-benchmark.ps1 -FetchDataset
.\runners\windows\run-image-rendering-benchmark.ps1 -VerifyDataset
.\runners\windows\run-image-rendering-benchmark.ps1 -Family scroll `
  -Profile default -Rounds 3 -PackageManifest C:\bench\package-manifest.json
```

Build a Windows package from a clean benchmark checkout and clean TotalCross
source checkout. The runtime home must contain the tested Windows launcher and
VM artifacts at `etc/launchers/win32/Launcher.exe` and
`dist/vm/win32/tcvm.dll`; pass the source SHA used for those artifacts. Verify
the dataset cache first; the builder embeds its resources for TCZ decode runs.
The SDK build is opt-in so an already tested SDK can be reused:

```sh
python3 tools/packaging/build_windows.py \
  --runtime-source /path/to/totalcross \
  --runtime-home /path/to/tested/windows/runtime \
  --runtime-artifact-commit <40-character-totalcross-sha> \
  --build-sdk \
  --output .local-data/packages/image-rendering-windows
```

The package contains a launcher and runtime files for each named profile plus a
validated `package-manifest.json`. Generated packages and benchmark results
are local artifacts and stay out of Git. The PowerShell runner requires the
package and source revisions to match the current checkouts.

On macOS, build the native runtime and all profile launchers from the same
TotalCross SHA. For the currently pinned depot-tools release, pass its QRCodeGen
and SQLite tags explicitly so CMake does not use the stale defaults in its
autofetch helpers:

```sh
cmake -S "$TOTALCROSS_SOURCE/TotalCrossVM" -B .local-data/build/runtime-p12-macos \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DQRCODEGEN_RELEASE_TAG=qrcodegen-20250123-r2 \
  -DSQLITE3_RELEASE_TAG=sqlite3-3.32.3-r2 -G Ninja
cmake --build .local-data/build/runtime-p12-macos --target tcvm Launcher --parallel
python3 tools/packaging/build_macos.py \
  --runtime-source "$TOTALCROSS_SOURCE" \
  --native-build-dir .local-data/build/runtime-p12-macos \
  --runtime-artifact-commit <40-character-totalcross-sha> \
  --output .local-data/packages/image-rendering-macos
```

The helper checks that the native artifacts came from this source checkout,
are Release arm64 binaries, and match the runtime SHA. It embeds the verified
corpus for TCZ decode runs. Then run a focused pacing cell or the full pacing
family through the package manifest:

```sh
python3 runners/run.py image-rendering pacing --workload flick-60 --rounds 3 \
  --package-manifest .local-data/packages/image-rendering-macos/package-manifest.json
```
