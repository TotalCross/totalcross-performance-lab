# Persistent image ownership target smoke

This small TotalCross application exercises persistent image ownership in
native runtimes. It builds two consecutive screens with 1,510 controls and
distinct images each without forcing GC, checks nested detach and reattach,
detached mutations, active reparenting, shared raster retention, pipeline
replacement, repeated cache reuse, and a rendered red pixel saved as PNG.

The app is deliberately in `totalcross.ui.image`, matching the benchmark-only
access pattern used by `ImageDrawPathProbeAccess`. It reads package-private
ownership counters already present in the tested SDK. It does not add SDK
instrumentation or alter the public bridge surface.

`tools/image_ownership_smoke.py` compiles and deploys the app against the SDK
and platform artifacts. Its macOS native mode launches the deployed executable
directly, records separate stdout and stderr, captures `otool -L`, requires dyld
to report the deployed freshly built `libtcvm.dylib`, and hashes the deployed
Launcher, dylib, PNG, and source artifacts. It can also consume SDK and runtime
artifacts from one GitHub Actions run, rejecting artifacts whose source commit
or tree differs from the workflow checkout. Native results use the
`TC_IMAGE_OWNERSHIP_JSON ` line and are archived with full logs.
Windows runs require AMD64 PE images for the native Launcher and TCVM, then
verify the deployed `tcvm.dll` matches the same-run artifact. The app mirrors
its structured result and failure records through `Vm.debug` so the runner can
read them from `DebugConsole.txt` when the GUI launcher has no captured stdout.
Android runs
verify the APK's ARM64 `libtcvm.so` against the same-run AAB and record the
emulator API level and ABI; `run-android` can enforce both with
`--expected-api` and `--expected-abi`.

The target app and its small generated PNG fixture contain no external dataset.
It complements the focused JUnit regressions in TotalCrossSDK; it does not
replace those tests or the SDK registration operation-count checks.
