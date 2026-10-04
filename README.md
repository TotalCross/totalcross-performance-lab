# TotalCross Performance Lab

Benchmarking, profiling, performance experiments, datasets, runners, and analysis tooling for TotalCross across platforms.

This repository is the home for repeatable TotalCross performance workloads and the tooling used to run, package, validate, and analyze them. Product code and correctness regressions remain in the main [TotalCross repository](https://github.com/TotalCross/totalcross).

## Scope

The lab may contain:

- benchmark applications and workload fixtures;
- dataset descriptors and manifests;
- cross-platform runners and packaging tools;
- result schemas and parsers;
- profiling and diagnostics helpers;
- durable performance-analysis documentation.

Generated benchmark results, logs, binaries, deployed packages, and temporary evidence should normally stay outside Git unless a specific artifact is intentionally maintained as a fixture.

## Repository layout

- `benchmarks/` — benchmark workloads and applications.
- `datasets/` — versioned dataset descriptors and usage contracts.
- `runners/` — cross-platform benchmark orchestration.
- `schemas/` — machine-readable result and dataset contracts.
- `tools/` — packaging, validation, download, and analysis utilities.

## Datasets

Datasets are versioned independently from benchmark code. Large payloads may be hosted outside Git while this repository keeps their descriptors, integrity metadata, and usage contract.

The first registered dataset is `image-scroll/v1`, used by the TotalCross image-rendering scroll/decode workloads.

See [DATASETS.md](DATASETS.md) and [datasets/image-scroll/v1/README.md](datasets/image-scroll/v1/README.md).

## Image-rendering suite status

The first image-rendering investigation (P12) is complete. The lab captured the
causal path from the recurring raster regression through the production-candidate
validation that supported TotalCross PR #488.

The final production candidate was TotalCross
`bdd27273ead29bab320cba43b9ebad27be9b87ad`, measured with lab source
`264b9fba8581f08f3c0e4f31529831b7270d2c95`. Its static warm run recorded
18/18 cached-final hits, zero generic/smooth destination draws, and a 5.509 ms
paint tree. The repeated-scroll run recorded no interval above 100 ms across
9,720 measured frame intervals.

See [reports/p12-production-candidate-final.md](reports/p12-production-candidate-final.md)
for the concise closure and the individual P12 reports for causal evidence.
Generated packages and raw run outputs remain intentionally outside Git under
ignored local-data paths.

## Licensing

Source code in this repository is licensed under the MIT License unless a file says otherwise.

Datasets are **not automatically covered by the MIT License**. Their provenance, access, and redistribution terms are documented separately in [DATASETS.md](DATASETS.md).