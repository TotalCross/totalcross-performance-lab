# Tools

Dataset download/verification, benchmark packaging, result validation, and analysis utilities live here.

Tools should be reproducible, avoid hidden local paths, and validate inputs and outputs rather than assuming a particular workstation layout. Fetch or verify the official image corpus with `python3 tools/datasets/image_scroll.py fetch image-scroll/v1` or `python3 tools/datasets/image_scroll.py verify image-scroll/v1`. The standard-library-only tool reads the pinned hashes and expected shape from `datasets/image-scroll/v1/dataset.json`; payloads are kept under ignored `.local-data/datasets/`. A manifest or content-count mismatch is an error and stops dataset-dependent measurements.

Generate platform packages with `tools/packaging/build_windows.py` or `tools/packaging/build_macos.py`. Both helpers require a clean TotalCross checkout, a runtime artifact SHA matching that checkout, and a verified local corpus cache. They build all ten typed-annotation profile launchers, embed the corpus for TCZ decode, and write `package-manifest.json` with source identities, dataset identity, configuration, and artifact hashes. The Windows helper consumes a tested Windows runtime home; the macOS helper validates a Release arm64 CMake build. The matching PowerShell runner and corpus fetch/verification commands are in `runners/windows/`.
