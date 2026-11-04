# SQLite plaintext regression probe — TotalCross 7.3.0

This test uses **the exact upstream build**, not a Maven SDK or independently compiled TCVM:

- package workflow: [40878222908](https://github.com/TotalCross/totalcross/actions/runs/40878222908)
- later release workflow: [40879229660](https://github.com/TotalCross/totalcross/actions/runs/40879229660)
- source revision: `5464c21e3107e3f1ce9c287b724829e2bb870c1d`
- upstream GitHub artifact ID: `12899147776`, name `TotalCross-7.3.0`

The GitHub Actions workflow `.github/workflows/sqlite-plaintext-7.3.0.yml` builds and deploys with the extracted **official SDK/TCVM** for Windows, macOS, Linux x64, Linux ARM32, Linux ARM64, Android and iOS. Windows and macOS run SQLite natively in CI; Linux x64 is attempted and reports a distinct pre-SQLite native startup error. The Android APK is also installed and run on an API 35 Google APIs x86_64 emulator with ARM64 native bridge. iOS packages remain for later device tests. Linux ARM32 and ARM64 are deployed but not executed.

## Tests

`SQLitePlaintextProbe` emits `TC_SQLITE_JSON` records and exits with status 0 on success, nonzero on failure. It uses no encryption option, key, codec, or SEE API.

1. `:memory:`: open, query `sqlite_version()`, create, insert, select.
2. New on-disk SQLite database: create, insert, read.
3. Close and reopen: read, update, `PRAGMA integrity_check`.
4. Verify first 16 bytes of generated database are `SQLite format 3\\0`, proving on-disk content is standard plaintext SQLite.

On Android the test mirrors its structured events into the TotalCross native debug channel so `adb logcat` can capture them (normal stdout alone is insufficient). A separate Python executor checks APK ABIs and emulator ABI support, installs and launches the APK, monitors logcat, and requires all five stage PASS records; it records installation, launch, ABI metadata, failures, screenshot and crash logcat.\n\nThe app logs the resolved `Settings.appPath`, platform, SQLite version, database path, stages, and exception stack on error. The runner records file hashes, source SHA, machine details, deployment logs, runtime stdout/stderr, structured events, and execution summary. The workflow uploads these even on failure.

## CI prerequisites

Cross-repository GitHub Actions artifact access may require an Actions-read token. If the default job token is denied access to `TotalCross/totalcross`, configure `PERFORMANCE_LAB_GH_TOKEN` in this repository with **read-only Actions access** to the upstream repository. The build uses `github.token` as fallback.

Native GUI execution on GitHub-hosted macOS requires a graphical session; Linux uses `xvfb-run`. A timeout or window-system error is distinct from a SQLite failure and will appear in `runtime.log`.

iOS deployment may require configured Apple signing materials in the 7.3.0 SDK package; an unsuccessful iOS deploy must not be interpreted as SQLite regression. Android deployment may require Android build tools. Per-platform CI failures remain independent and archive logs.

## Local reproduction

Use Java 17, Python 3.11 and a downloaded copy of the original artifact ZIP:

```bash
python tools/sqlite_smoke.py build --target linux-x64 \
  --package /path/to/upstream-artifact.zip --out sqlite-smoke-results
python tools/sqlite_smoke.py execute --target linux-x64 --out sqlite-smoke-results
```

Available deployment targets: `windows`, `macos`, `linux-x64`, `linux-arm`, `android`, `ios`. For binaries, database fixtures, and diagnostic output see the GitHub Actions artifacts, not tracked Git files.

## Client external storage reproducer (2026-11-04)

The client-provided `Main.zip` contains `Main.java`, `TestPermission.java`, and an APK. **The Java sample does not use SQLite:** `TestPermission.initUI()` sets `Settings.dataPath = "/sdcard/"`, then `checkFolderPermission()` does `new File(Convert.appendPath(Settings.dataPath, "asd")).createDir(); ... delete();`. That operation exercises access to the root of shared storage, outside the application's sandbox.

The Android smoke probe executes this exact `/sdcard/asd` create/delete sequence, followed by **unencrypted** SQLite database create/insert/select, reopen/update/`integrity_check`, and SQLite header verification at `/sdcard/tc-sqlite-7_3_0-external-probe.db`. In addition, the runner uses host Python SQLite to create a **pre-existing** database at `/sdcard/tc-sqlite-7_3_0-existing-probe.db` before the test runs. The TotalCross app must read and update its original row; the runner then pulls it back and verifies content and integrity with Python SQLite. The existing in-app and in-memory tests remain as controls. No customer APK or customer data is committed into this repository.

The APK is deployed with the TotalCross 7.3.0 `/android_manage_external_storage` flag, declaring `android.permission.MANAGE_EXTERNAL_STORAGE` in the manifest. The emulator then runs the *identical APK twice*, without changing TCVM binaries:

1. **Permission denied:** `adb shell appops set PACKAGE MANAGE_EXTERNAL_STORAGE ignore`. TCVM's native `File.c` retries an `EACCES` error by launching the Android Settings all-files-access permission screen and blocking for a response. The runner detects that screen and issues Android BACK to deny/dismiss it, recording the permission UI and native failure. A captured prompt is reported distinctly if the native call remains blocked.
2. **Permission granted:** `adb shell appops set PACKAGE MANAGE_EXTERNAL_STORAGE allow`; require `external-dir`, `external-sqlite-create`, `external-sqlite-reopen`, `external-sqlite-header`, `external-existing-db`, and `external-result` all PASS, along with in-app tests. The pulled SQLite file must contain the value written by TotalCross and pass a host-side integrity check.

It captures `apk-permissions.txt`, `appops-ignore.txt`, `appops-allow.txt`, separate `events-denied.json`/`events-granted.json`, `runtime-android-denied.logcat`/`runtime-android-granted.logcat`, screenshots, and summary files even if a phase fails. The `adb appops` toggle validates permission-dependent behavior; the test **observes** and dismisses the real special-permission Settings screen in the denied phase but does **not** automate a human's consent/grant through that screen. Android's special all-files access is not granted merely by adding the manifest permission.

## Android emulator coverage\n\nCI uses `reactivecircus/android-emulator-runner@v2`, an API 35 `google_apis` `x86_64` image and KVM on Ubuntu 24.04. The official TotalCross APK contains an ARM64 native library, so the runner checks the image's `ro.product.cpu.abilist` for `arm64-v8a` before installation. Incompatible ABIs or native-bridge failures are reported separately from SQL errors, and **a successful emulator run is not a substitute for testing an ARM64 phone**. The Android action stores separate denied/granted logcat and JSON events, both SQLite fixture files, permission screen screenshot/observations, `android-execution-summary.json`, APK and device diagnostics.\n\nRun from an already-booted emulator after a successful deploy:\n\n```bash\npython3 tools/android_sqlite_smoke.py --out sqlite-smoke-results --timeout 90\n```\n\n## Linux x64 native startup issue observed (2026-10-31)

On the exact 7.3.0 Linux runtime, the desktop test currently cannot reach its SQLite stages: the unmodified TCVM crashes on start with glibc `*** buffer overflow detected ***` and signal `SIGABRT`. The captured gdb stack is:

```
__realpath_chk
startVM() from ./libtcvm.so
executeProgram() from ./libtcvm.so
main()
```

Upstream `TotalCrossVM/src/init/posix/startup_c.h` uses `char resolved[MAX_PATHNAME]` then `realpath(path, resolved)`; `MAX_PATHNAME` is 1024 in `TotalCrossVM/src/util/xtypes.h` on Linux. Modern glibc fortify expects a buffer at least `PATH_MAX` (commonly 4096) for the non-allocating `realpath` call and aborts in `__realpath_chk`. **This is a separate native startup failure, not a SQLite result.** The lab intentionally does not patch the official runtime; CI archives the native backtrace. Repair belongs upstream, preferably by using `realpath(path, NULL)` and freeing the allocation, then rebuilding and retesting.
