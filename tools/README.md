# Tools

Dataset download/verification, benchmark packaging, result validation, and analysis utilities live here.

Tools should be reproducible, avoid hidden local paths, and validate inputs and outputs rather than assuming a particular workstation layout. Fetch or verify the official image corpus with `python3 tools/datasets/image_scroll.py fetch image-scroll/v1` or `python3 tools/datasets/image_scroll.py verify image-scroll/v1`. The standard-library-only tool reads the pinned hashes and expected shape from `datasets/image-scroll/v1/dataset.json`; payloads are kept under ignored `.local-data/datasets/`. A manifest or content-count mismatch is an error and stops dataset-dependent measurements.
