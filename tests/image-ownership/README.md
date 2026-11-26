# Persistent image ownership target smoke

This small TotalCross application exercises the ownership lifecycle in the
native Windows, Linux, and Android runtimes. It reconstructs 64 screens without
forcing GC, checks that shared `ImageControl` owners are released immediately,
verifies the materialized raster is reused while an owner remains and evicted
after the last owner detaches, and checks a red pixel after drawing.

The app is deliberately in `totalcross.ui.image`, matching the benchmark-only
access pattern used by `ImageDrawPathProbeAccess`. It reads package-private
ownership counters already present in the tested SDK. It does not add SDK
instrumentation or alter the public bridge surface.

`tools/image_ownership_smoke.py` compiles and deploys the app against the SDK
artifact and platform runtime artifacts from one GitHub Actions run. It rejects
artifacts whose source commit or tree differs from the workflow checkout and
writes a machine-readable provenance record beside the deployment. Native run
results use the `TC_IMAGE_OWNERSHIP_JSON ` line and are archived with full logs.

The target app and its small generated PNG fixture contain no external dataset.
It complements the focused JUnit regressions in TotalCrossSDK; it does not
replace those tests or the SDK registration operation-count checks.
