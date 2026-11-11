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

### Running the APK manually on a physical Android device

The APK does not bundle the CI's *pre-existing* SQLite fixture. For direct APK installation on a phone, the `external-existing-db` stage now produces **SKIP** (rather than FAIL) when `/sdcard/tc-sqlite-7_3_0-existing-probe.db` is missing or does not contain the expected `fixture` table. This also handles an empty SQLite file left by older versions of the probe. All other checks remain required; `external-result` and `result` report PASS if they succeed, with the optional skip explicitly mentioned.

The GitHub Actions Android runner always preloads this fixture independently of TotalCross and **still requires an actual PASS** from `external-existing-db`, plus host-side validation of its contents and integrity.

To enable the pre-existing DB test on a physical phone, create and push the fixture using the following command on a computer with Python 3 and ADB, **before launching the app**:

```bash
python3 - <<'PY'
import sqlite3
with sqlite3.connect("tc-sqlite-7_3_0-existing-probe.db") as db:
    db.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("INSERT INTO fixture (id, value) VALUES (1, 'preexisting-from-python')")
PY
adb push tc-sqlite-7_3_0-existing-probe.db /sdcard/tc-sqlite-7_3_0-existing-probe.db
```

The app modifies this *dedicated test fixture* in place, so recreate and push it before another test run if necessary. Never use a customer database for this fixture path.

### Verified emulator result (2026-11-04)

[GitHub Actions run 41888918200](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/41888918200), [Android artifact 13352942109](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/41888918200/artifacts/13352942109):

- **Declared but denied:** `MANAGE_EXTERNAL_STORAGE: ignore`; native `File.createDir()` tries to launch Android's all-files-access Settings UI. One BACK response returns control. `/sdcard/asd` fails with `Error Code: 13 - Permission denied`. SQLite `NativeDB._open` for both newly created and pre-existing `/sdcard` databases fails with `[-1] unknown error (out of memory)` (a misleading native SQLite error, not an actual memory measurement). In-app SQLite is PASS.
- **Permission granted:** `MANAGE_EXTERNAL_STORAGE: allow`; `external-dir`, `external-sqlite-create`, `external-sqlite-reopen`, `external-sqlite-header`, `external-existing-db`, and `external-result` are all **PASS**. The host runner pulled back the existing DB and verified `value='updated-by-totalcross'` and `PRAGMA integrity_check='ok'` with standard Python SQLite.
- This **reproduces the permission-dependent failure**, but it **does not reproduce** the customer's exact `file is not a database` exception. That SQL error occurred later in `NativeDB._exec` / `Stmt.executeUpdate`, while the denied case here fails during `NativeDB._open`.

The customer-provided APK targets Android API 36, has minimum API 24, and declares `MANAGE_EXTERNAL_STORAGE`. Declaring it is not proof the user has granted special access; verify the actual permission state on the affected device.

## iOS native File / SQLite device-farm probe (2026-11-11)

The iOS build uses the same **official 7.3.0 TCVM** as the Android/desktop smoke tests. It runs **File operations before any SQLite call**, inside the iOS `Settings.appPath` (app's Documents sandbox). Every operation emits a `TC_SQLITE_JSON` event to the native debug console (`Vm.debug`) with a `BEGIN` followed by `PASS`. This identifies the last attempted operation if the VM freezes without an exception.

Stages: `ios-file-open-create`, `ios-file-write`, `ios-file-flush`, `ios-file-size`, `ios-file-close`, `ios-file-open-read`, `ios-file-read`, `ios-file-delete`, `ios-directory-precheck`, `ios-directory-create`, `ios-directory-delete`, `ios-files-result`. Then the standard SQLite `:memory:`, on-disk CREATE/INSERT/SELECT, reopen/UPDATE/integrity and plaintext header checks run. All iOS files are prefixed with `tc-ios-` and contained within `Settings.appPath`; the SQLite file `sqlite-plaintext-smoke.db` is also contained in that directory. The app permits repeat runs on iOS by safely recreating its own SQLite fixture.

The GitHub workflow deploys an actual **device-target iOS IPA**, not a simulator build, and uploads two artifacts: `sqlite-plaintext-7.3.0-ios-devicefarm` (IPA, provenance/validation JSON, use instructions) and `sqlite-plaintext-7.3.0-ios` (complete CI deploy logs and generated assets).

**Signing notice:** the original SDK's iOS template has the dummy `com.application.name` bundle identifier and an expired `Dummy Provision` profile from 2015. CI validates and reports these values; it **does not claim that this IPA is directly installable**. A device farm that supports re-signing (e.g. AWS Device Farm, BrowserStack) can apply its own signing profile; otherwise re-sign with valid Apple credentials and a suitable bundle identifier before testing. Choose a **physical iOS device**, not a simulator. Capture the native device syslog/console, including all `TC_SQLITE_JSON` events.

On iOS, the app stays open when tests finish and displays a **PASS: iOS File + SQLite** or **FAIL: <stage>** label. After uploading the IPA, start the app and inspect the last `BEGIN` without a corresponding `PASS` if it hangs. If a `FAIL` appears, collect the exception and nearby system logs. No iOS execution or runtime PASS is asserted by CI; execution occurs on the selected device farm.

## Android emulator coverage\n\nCI uses `reactivecircus/android-emulator-runner@v2`, an API 35 `google_apis` `x86_64` image and KVM on Ubuntu 24.04. The official TotalCross APK contains an ARM64 native library, so the runner checks the image's `ro.product.cpu.abilist` for `arm64-v8a` before installation. Incompatible ABIs or native-bridge failures are reported separately from SQL errors, and **a successful emulator run is not a substitute for testing an ARM64 phone**. The Android action stores separate denied/granted logcat and JSON events, both SQLite fixture files, permission screen screenshot/observations, `android-execution-summary.json`, APK and device diagnostics.\n\nRun from an already-booted emulator after a successful deploy:\n\n```bash\npython3 tools/android_sqlite_smoke.py --out sqlite-smoke-results --timeout 90\n```\n\n## Linux x64 native startup issue observed (2026-10-31)

On the exact 7.3.0 Linux runtime, the desktop test currently cannot reach its SQLite stages: the unmodified TCVM crashes on start with glibc `*** buffer overflow detected ***` and signal `SIGABRT`. The captured gdb stack is:

```
__realpath_chk
startVM() from ./libtcvm.so
executeProgram() from ./libtcvm.so
main()
```

Upstream `TotalCrossVM/src/init/posix/startup_c.h` uses `char resolved[MAX_PATHNAME]` then `realpath(path, resolved)`; `MAX_PATHNAME` is 1024 in `TotalCrossVM/src/util/xtypes.h` on Linux. Modern glibc fortify expects a buffer at least `PATH_MAX` (commonly 4096) for the non-allocating `realpath` call and aborts in `__realpath_chk`. **This is a separate native startup failure, not a SQLite result.** The lab intentionally does not patch the official runtime; CI archives the native backtrace. Repair belongs upstream, preferably by using `realpath(path, NULL)` and freeing the allocation, then rebuilding and retesting.
