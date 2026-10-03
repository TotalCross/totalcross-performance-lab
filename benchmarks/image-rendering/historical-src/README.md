<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# Historical static preparation probe

This isolated source set supports only TotalCross
`f5dad132cafea5c9086f6f946a6f44ca5bcb5f76`, natural defaults, and the static
`paint-preparation-probe`. The normal package builders and P12 configuration
checks continue to use the normal controller and production runtime APIs.

The historical builder compiles the existing `ScrollWorkload`, `BenchSupport`,
`ScrollTiming`, and `profiles/Default` with this controller. In a generated
staging copy of `ScrollWorkload`, it changes only the two diagnostics imports
to benchmark-namespace adapters and inserts an identity snapshot helper outside
timed regions. Every existing workload and measurement method stays unchanged.
The adapters report unsupported; their other methods throw if unexpectedly
called. They do not introduce APIs into the historical SDK or its namespaces.

Both `ImageOptimizationSettings.getMask()` and `getEffectiveMask()` must be
32799 before UI construction and after measurement. The controller never sets
a mask. The same manifest loader supplies all 663 images in manifest order,
including three PNGs, and the same nested hierarchy and scaling calls are used.
Identity snapshots retain and compare row, control and Image references; the
result includes the paths/formats and manifest indices of the 18 visible controls.

From the benchmark repository root, after building the historical SDK and a
fresh native ARM64 Release directory containing `tcvm` and `Launcher`:

```sh
python3 tools/packaging/historical_paint_probe.py build \
  --runtime-source /path/to/clean-historical-checkout \
  --native-build /path/to/fresh-historical-native-build \
  --dataset-cache .local-data/datasets/p12-final/image-scroll/v1 \
  --output .local-data/historical-static-probe
```

Commit tooling before measurement, then launch exactly one process:

```sh
python3 tools/packaging/historical_paint_probe.py run \
  --package .local-data/historical-static-probe
```

The native cache must select the software surface, Skia and SDL, match the
historical source checkout and depot-tools pin, and use Release/arm64. Deployment
must preserve the freshly built Launcher/library hashes. The manifest records
SDK/native hashes, source fingerprints, compile/deploy/launch commands and the
dataset identity. An exclusive `launch-attempt.json` prevents another launch
against the same package, including after a timeout or failure. It must be
preserved. The run uses inline preflight only, no warmup process and no scrolling.

Five samples before and five after the single preparation callback are checked
with the existing preparation-result validator plus stricter historical
configuration, instance identity and six-row/eighteen-control checks. Raw logs,
results, packages, build directories and datasets remain outside Git.
