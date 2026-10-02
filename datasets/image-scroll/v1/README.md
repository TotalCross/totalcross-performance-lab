# image-scroll/v1

`image-scroll/v1` is the first official dataset registered by TotalCross Performance Lab. It is intended for image scrolling, decode, prefetch, raster, and related rendering benchmarks.

## Artifacts

Base URL:

`https://totalcross-benchmark-data.s3.us-west-2.amazonaws.com/image-scroll/v1/`

Files:

- `totalcross-image-scroll-v1.zip` — dataset payload.
- `manifest.json` — per-file metadata and SHA-256 digests.
- `SHA256SUMS` — integrity hashes for the published ZIP and manifest.

The checked-in `dataset.json` pins the published archive and manifest SHA-256
identities. The verifier checks those values before it extracts any payload.

## Expected shape

The v1 workload contains 663 files. Historical validation identified 660 JPEG payloads and 3 PNG payloads.

The benchmark must detect file formats from file content rather than relying only on filename extensions.

## Consumption contract

A runner using this dataset should:

1. obtain `SHA256SUMS`;
2. obtain the ZIP and `manifest.json`;
3. verify the published ZIP and manifest against `SHA256SUMS`;
4. extract the ZIP to an isolated dataset directory;
5. validate extracted relative paths, file count, file sizes, and SHA-256 values against `manifest.json`;
6. reject the run if validation fails;
7. record dataset ID/version and the effective manifest identity in benchmark metadata.

The dataset payload should not be silently modified, normalized, recompressed, renamed, or replaced in place.

## Versioning

`v1` is immutable. Any payload change, including a changed file, renamed path, or regenerated corpus with different bytes, requires a new version such as `v2`.

Generated benchmark outputs and derived transformed corpora are separate artifacts and must not overwrite the source dataset.

## Licensing / provenance

Dataset licensing and provenance are tracked separately from the MIT-licensed benchmark code. See the repository-level [DATASETS.md](../../../DATASETS.md).
