# Datasets

Benchmark datasets are versioned independently from the source code in this repository.

The MIT License in `LICENSE` applies to source code and documentation unless a file says otherwise. Dataset payloads do not automatically inherit that license. Each dataset entry must document its source, provenance, redistribution status, storage location, integrity contract, and versioning policy.

## Registered datasets

### image-scroll/v1

Primary image workload for TotalCross image scrolling, decode, preparation, and rendering benchmarks.

- Dataset ID: `image-scroll`
- Version: `v1`
- Expected files: 663
- Historical payload mix: 660 JPEG and 3 PNG
- Storage: public Amazon S3 objects in `us-west-2`
- Repository payload policy: dataset binaries are not stored in Git
- Version policy: `v1` is immutable; content changes require a new dataset version

Artifacts:

- `https://totalcross-benchmark-data.s3.us-west-2.amazonaws.com/image-scroll/v1/totalcross-image-scroll-v1.zip`
- `https://totalcross-benchmark-data.s3.us-west-2.amazonaws.com/image-scroll/v1/manifest.json`
- `https://totalcross-benchmark-data.s3.us-west-2.amazonaws.com/image-scroll/v1/SHA256SUMS`

See [datasets/image-scroll/v1/README.md](datasets/image-scroll/v1/README.md) for the benchmark contract.

## Provenance and redistribution

The `image-scroll/v1` payload is hosted separately from this source repository. Its source/provenance and redistribution status must be treated independently from the MIT-licensed code here.

Do not infer dataset licensing from the repository license. If a future dataset is known to be redistributable under a specific license, record that explicitly in its own descriptor.
