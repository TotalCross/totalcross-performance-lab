# SQLite plaintext regression probe — TotalCross 7.3.0

This test uses **the exact upstream build**, not a Maven SDK or independently compiled TCVM:

- package workflow: [40878222908](https://github.com/TotalCross/totalcross/actions/runs/40878222908)
- later release workflow: [40879229660](https://github.com/TotalCross/totalcross/actions/runs/40879229660)
- source revision: `5464c21e3107e3f1ce9c287b724829e2bb870c1d`
- upstream GitHub artifact ID: `12899147776`, name `TotalCross-7.3.0`

The GitHub Actions workflow `.github/workflows/sqlite-plaintext-7.3.0.yml` builds and deploys with the extracted **official SDK/TCVM** for Windows, macOS, Linux x64, Linux ARM32, Linux ARM64, Android and iOS. Only the three desktops are executed in CI; mobile packages are retained for device tests. Linux ARM32 and ARM64 are deployed but not executed.

## Tests

`SQLitePlaintextProbe` emits `TC_SQLITE_JSON` records and exits with status 0 on success, nonzero on failure. It uses no encryption option, key, codec, or SEE API.

1. `:memory:`: open, query `sqlite_version()`, create, insert, select.
2. New on-disk SQLite database: create, insert, read.
3. Close and reopen: read, update, `PRAGMA integrity_check`.
4. Verify first 16 bytes of generated database are `SQLite format 3\\0`, proving on-disk content is standard plaintext SQLite.

The app logs the resolved `Settings.appPath`, platform, SQLite version, database path, stages, and exception stack on error. The runner records file hashes, source SHA, machine details, deployment logs, runtime stdout/stderr, structured events, and execution summary. The workflow uploads these even on failure.

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

Available deployment targets: `windows`, `macos`, `linux-x64`, `android`, `ios`. For binaries, database fixtures, and diagnostic output see the GitHub Actions artifacts, not tracked Git files.

## Linux x64 native startup issue observed (2026-10-31)

On the exact 7.3.0 Linux runtime, the desktop test currently cannot reach its SQLite stages: the unmodified TCVM crashes on start with glibc `*** buffer overflow detected ***` and signal `SIGABRT`. The captured gdb stack is:

```
__realpath_chk
startVM() from ./libtcvm.so
executeProgram() from ./libtcvm.so
main()
```

Upstream `TotalCrossVM/src/init/posix/startup_c.h` uses `char resolved[MAX_PATHNAME]` then `realpath(path, resolved)`; `MAX_PATHNAME` is 1024 in `TotalCrossVM/src/util/xtypes.h` on Linux. Modern glibc fortify expects a buffer at least `PATH_MAX` (commonly 4096) for the non-allocating `realpath` call and aborts in `__realpath_chk`. **This is a separate native startup failure, not a SQLite result.** The lab intentionally does not patch the official runtime; CI archives the native backtrace. Repair belongs upstream, preferably by using `realpath(path, NULL)` and freeing the allocation, then rebuilding and retesting.
