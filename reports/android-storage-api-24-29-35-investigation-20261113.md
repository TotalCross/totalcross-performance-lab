# Android storage and SQLite — APIs 24, 29 and 35 (2026-11-13)

## Purpose

Reproduce the customer report: TotalCross 7.3.0 cannot create/delete
`/sdcard/asd` or access a plaintext SQLite database under `/sdcard`
on **Android 10 (API 29)**, but succeeds on Android 12. Compare API 24,
29 and 35 without changing the application, native VM or Android manifest.

## Pinned input

- Source: TotalCross 7.3.0 at `5464c21e3107e3f1ce9c287b724829e2bb870c1d`
- Official SDK package: run `40878222908`, artifact `12899147776`
- APK: `sqlite-plaintext-smoke.apk` from performance-lab Android 15
  successful job in [run 43359416885](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43359416885),
  [artifact 14007058527](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43359416885/artifacts/14007058527)
- Identical APK SHA-256 in all attempted jobs:
  `8c6190fc5425a8f33db48900e7c9e7f8b1a2b9ff13a3d4667fe9cfc1325e685a`
- `minSdk=24`, `targetSdk=36`, manifest includes `WRITE_EXTERNAL_STORAGE`
  and `MANAGE_EXTERNAL_STORAGE`, but **not** `READ_EXTERNAL_STORAGE`.
- The native runtime `libtcvm.so` is packaged **only** under
  `lib/arm64-v8a/`. Some other libraries exist in x86/x86_64 folders
  but do not implement TCVM. The automated probe checks the native
  `libtcvm.so` ABI specifically.

## Execution attempts and concrete outcome

| Run | Platform | API 24 | API 29 | API 35 |
| --- | --- | --- | --- | --- |
| [43469201808](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43469201808) | Linux, x86_64 Android Emulator + KVM | APK installed; `libtcvm.so` missing for x86_64, Java application never ran | Same | Same, because the first script selected x86_64 instead of the available ARM64 translation |
| [43470568980](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43470568980) | macOS Apple Silicon hosted runners, ARM64 Emulator | `HVF error: HV_UNSUPPORTED`, guest never booted | Same | Same |
| [43359416885](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43359416885) (existing proven baseline) | Linux Android 15 x86_64 Google APIs image **with ARM64 translation**, app installed explicitly `--abi arm64-v8a` | Not exercised | Not exercised | **PASS:** `/sdcard` denied before granting `MANAGE_EXTERNAL_STORAGE`; internal SQLite passed; after special access granted, external directory and external SQLite passed |

**The newly requested API 24/29 runtime tests remain *INCOMPLETE*, not
FAIL for file/SQLite behavior.** The app never executed on those two guest
OS versions. Do not interpret their GitHub Actions red status as proof
of the customer's Android 10 issue.

### Why the hosted environments cannot complete the whole matrix

- The pinned native VM build explicitly uses
  `nativeAndroidAbis = ['arm64-v8a']` in
  `TotalCrossVM/android/tcvm/build.gradle`. The related dependency
  `sljit/fetch.sh` only recognizes `android/arm64-v8a`, not Android x86.
- Linux/KVM Android 7 and Android 10 x86_64 Google APIs images advertised
  `ro.product.cpu.abilist=x86_64,x86`, with **no ARM64 translation**.
  The Android 15 x86_64 image advertised `x86_64,arm64-v8a`.
- The hosted macOS Apple Silicon CI image permits downloading/creating
  ARM64 AVDs for 24/29/35 but the QEMU/HVF backend exits immediately:
  `HVF error: HV_UNSUPPORTED` and `failed to initialize HVF: Invalid argument`.
  It cannot provide hardware virtualization from within this hosted VM.

## Additional matrix-harness control: Android 15 PASS

[Run 43474107912](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43474107912)
completed **SUCCESS** using the same 7.3.0 APK and the new
`android_storage_api_matrix.py` on a Linux/KVM Android 15 (API35)
x86_64 Google APIs emulator with ARM64 translation.

[Evidence artifact 14062755329](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43474107912/artifacts/14062755329):

- `status=COMPLETE`, original APK SHA-256
  `8c6190fc5425a8f33db48900e7c9e7f8b1a2b9ff13a3d4667fe9cfc1325e685a`
- VM ABI `arm64-v8a`; emulator ABIs `x86_64,arm64-v8a`;
  installed explicitly for `arm64-v8a`.
- Internal SQLite memory/create/reopen/plaintext-header: **PASS both phases**.
- `MANAGE_EXTERNAL_STORAGE: ignore`: `/sdcard/asd` **EACCES 13**,
  external SQLite create/reopen and existing fixture **FAIL**.
- `MANAGE_EXTERNAL_STORAGE: allow`: directory create/delete,
  external SQLite create/reopen/header and pre-existing SQLite fixture
  **PASS** without permission UI.
- This independently validates the new collector, not API24/29 or
  the original customer's failure.

## Existing source-level hypothesis (not yet reproduced on API 29)

`AndroidPermissionManager.mediaPermissionCandidates()` uses
`READ_EXTERNAL_STORAGE` below API33 only if the APK declares it, and
adds `WRITE_EXTERNAL_STORAGE` only for API < 29. Since the APK does
not declare READ and API29 excludes WRITE, its file-access permission
plan has **no runtime storage permissions** on Android 10. Special
`MANAGE_EXTERNAL_STORAGE` stages only exist on API >= 30. On API24,
WRITE can still be requested. This is a concrete logic gap independent
of whether Android's scoped storage rules would actually allow `/sdcard`
writes with targetSdk 36.

The native `NativeDB.c` uses `sqlite3_open_v2` directly, unlike
`File_c.h` which uses `FILE_RETRY_ACCESS` after EACCES/EPERM. SQLite
might fail without triggering the permission flow even if that flow
could resolve an underlying authorization issue.

## Reproduction on a physical Apple Silicon Mac

The branch includes
[`tools/run_android_storage_api_matrix_local.sh`](../tools/run_android_storage_api_matrix_local.sh)
and [`tools/android_storage_api_matrix.py`](../tools/android_storage_api_matrix.py).
On a **physical Apple Silicon Mac** with Android Studio's SDK Command-line
Tools, Java/JDK, Python 3 and GitHub CLI authenticated (`gh auth login`):

```bash
git clone https://github.com/TotalCross/totalcross-performance-lab.git
cd totalcross-performance-lab
git switch test/android-storage-api-24-29-35
bash tools/run_android_storage_api_matrix_local.sh
```

The script verifies the SHA-256 of the original artifact, installs
Google APIs ARM64 Android 7.0, 10 and 15 emulator images if missing,
runs each AVD on its own port, applies runtime permissions appropriate
to its API, and archives the results under
`android-api-results/api-{24,29,35}/`. It does not schedule paid
AWS Device Farm devices or alter TotalCross production code.

For each API it records installed ABI and package manifest, app grants
and appops before/after, the exact `/sdcard/asd` create+delete stages,
`jdbc:sqlite` creation/reopen, existing plaintext SQLite fixture,
internal `Settings.appPath` control and logcat. Physical execution
of this local script **has not yet been performed**.

## Next decision

Run APIs 24/29 on physical Mac (or another physical ARM64 host with
working KVM/HVF) and examine their JSON per-stage evidence. Only then
consider changing `AndroidPermissionManager` and/or APK manifest or
the native SQLite permission recovery. A separate CI-only Android15
ARM64-translation control is provided to validate the matrix harness
on the existing Linux/KVM runners.
