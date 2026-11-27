# Campaign preflight capabilities

Captured 2026-11-27. No TotalCross runtime was executed locally.

## Linux Actions path

The product repository's canonical reusable workflow is
`TotalCross/totalcross/.github/workflows/build.yml`. Its default build matrix
includes multiple platforms; its `selective` input does not select only
Linux x86_64. The Linux job uses the versioned
`totalcross/linux-amd64:v1.0.7` Docker image, CMake Release, and Ninja. It
downloads the prepared native dependency artifact produced by
`scripts/prepare-native-dependencies.sh`.

The campaign workflow must therefore be a focused, branch-only Linux workflow
that reuses this Docker image, pinned dependency bootstrap, and CMake/Ninja
commands. It must not run the product-wide platform matrix. Remove or upstream
the focused path when the canonical workflow gains case-scoped platform
selection.

The historical Linux VM artifact at source `61034a7562e7fa43df076dcc38bcd48128605395`
cannot stand in for frozen master `6b915883dd202f6db891990f6c3af26fb645ecc7`:
the native source diff includes file, SQLite, image, and Android permission
code. The campaign runner must build the exact frozen master source.

The performance-lab already has a Linux SQLite workflow that fetches the
cross-repository 7.3.0 Actions artifact using
`PERFORMANCE_LAB_GH_TOKEN || github.token`. The unauthenticated artifact API
returned HTTP 401, so the campaign workflow must retain that established
token fallback. The new workflow must trigger on push to the dedicated
investigation branch; its first-run configuration cannot depend on
`workflow_dispatch` while the workflow exists only on that branch.

## Local Android emulator

- Host architecture: Apple Silicon ARM64.
- Emulator acceleration: Hypervisor.Framework OS X Version 27.2, available.
- AVDs: `Codex_ImageOwnership_API36_ARM64`,
  `Pixel_3a_API_34_extension_level_7_arm64-v8a`.
- Installed ARM64 Google API / Play Store images: API 34, API 36, API 37.
- API 29, 30, and 35 images are not installed at capture time.
- No ADB device was running during the check.
- SDK manager:
  `/opt/homebrew/share/android-commandlinetools/cmdline-tools/latest/bin/sdkmanager`.

All Android runtime cases remain local ARM64 emulator work. GitHub Actions
Android runtime execution is out of scope.
