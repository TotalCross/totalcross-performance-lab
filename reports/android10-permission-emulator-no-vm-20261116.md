# TotalCross 7.3.0 — Android 10 permission coordinator, VM-free emulator regression
Date: 2026-11-16

## Goal and provenance

Reproduce the Android 10 filesystem authorization problem **without changing or building the TotalCross VM**. The standalone APK compiles the complete original `AndroidPermissionManager.java` pinned to TotalCross source SHA `5464c21e3107e3f1ce9c287b724829e2bb870c1d`, together with a small non-TotalCross Java Activity and Android framework SQLite. The fixture declares `WRITE_EXTERNAL_STORAGE` explicitly, requests legacy external storage, and observes any READ permission implied by Android.

Two identical Android 10 (API 29) emulator setups were exercised with application `targetSdk=29` and `targetSdk=36`.

- Original coordinator + independent APK, correct permission button automation:
  https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43964893012
  - targetSdk 29 artifact: https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43964893012/artifacts/14274889781
  - targetSdk 36 artifact: https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43964893012/artifacts/14275901877
- Original coordinator with **both full host-side scenarios completing** on targetSdk 36 (interactive grant test in that earlier run was inconclusive due clicking the prompt rather than the button): https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43964029362
- Isolated **candidate-only** coordinator using the single textual replacement `SDK_INT < Build.VERSION_CODES.Q` to `SDK_INT <= Build.VERSION_CODES.Q`, applied in the workflow to a copied Java source file, with no changes to SDK/VM:
  https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43965795327
  - targetSdk 29 artifact: https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43965795327/artifacts/14277295761
  - targetSdk 36 artifact: https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43965795327/artifacts/14276161089

Both candidate jobs completed successfully. The second baseline run's targetSdk 36 job had a transient *inconclusive* start/no-log event in the READ-only scenario; its other stages, including the fully automated runtime permission grant, completed and are inspectable. That inconclusive phase must not be counted as a TotalCross failure. The baseline targetSdk 36 READ-only scenario did complete in the earlier run.

## Actual Android 10 observations

| Permission state and operation | Unchanged 7.3.0 manager | <=Q candidate manager |
| --- | --- | --- |
| Initial READ=false, WRITE=false, framework SQLite in application-private files directory | PASS | PASS |
| Initial READ=false, WRITE=false, create /sdcard file | FAIL: EACCES | FAIL before authorization: EACCES |
| Initial READ=false, WRITE=false, open external framework SQLite | FAIL: SQLITE_CANTOPEN | FAIL before authorization: SQLITE_CANTOPEN |
| READ=true, WRITE=false, requestFileAccessBlocking() | Returns DENIED (-1) immediately without requesting WRITE | Presents WRITE permission, callback WRITE=0, returns GRANTED (1) |
| READ=true, WRITE=false, File and SQLite after permission-flow attempt | FAIL EACCES / SQLITE_CANTOPEN | PASS / PASS |
| READ=false, WRITE=false, user presses Allow on runtime permission dialog | Requests READ only, callback READ=0, WRITE remains false | Requests READ+WRITE, callback READ=0 and WRITE=0 |
| File and SQLite after pressing Allow | FAIL EACCES / SQLITE_CANTOPEN | PASS / PASS |
| READ=true, WRITE=true, direct File + SQLite | PASS / PASS | PASS / PASS |

All fully completed core observations above were reproduced at both `targetSdk=29` and `targetSdk=36`. No native TotalCross code or native SQLite library was compiled in either workflow.

The particularly strong regression reproduction is **a successful-looking permission request that does not grant enough access for the blocked operation**:

1. Baseline: with both permissions absent, Android 10 displays a runtime dialog for **READ only**; the user approves it.
2. `AndroidPermissionManager.requestFileAccessBlocking()` returns `GRANTED (1)` because its `authorizationChanged` flag became true.
3. Actual state is READ=true, WRITE=false, so `/sdcard` file creation fails with `EACCES` and Android's SQLite open fails with `SQLITE_CANTOPEN`.
4. Single-condition candidate: requests both READ and WRITE, user approves, both become true, and the two operations then pass.

The experiment also demonstrates that **granting READ alone cannot satisfy all legacy filesystem writes** even with `Environment.isExternalStorageLegacy()==true`.

## What is and is not proven

**Proven:** API29/Q is excluded from WRITE permission candidates in 7.3.0. The precise single-line selection change fixes the Android 10 permission recovery regression in an independent APK using the exact Java coordinator logic and Android permission UI. This is a behavioral test, not only a source contract test.

**Not proven:** that the customer's `Main.zip`, arbitrary existing SQLite database, or Android 10 physical device will work after shipping a modified TotalCross release. This experiment uses framework SQLite, not the VM's JNI SQLite integration. The customer's manifest, exact path and call order have not been examined in this experiment.

**Separate unaddressed path:** `TotalCrossVM/src/nm/db/NativeDB.c` directly calls `sqlite3_open_v2()`, without the `FILE_RETRY_ACCESS` wrapper used in `TotalCrossVM/src/nm/io/posix/File_c.h`. When external SQLite is the *first* operation, there may be no preceding File permission recovery, and changing `mediaPermissionCandidates()` alone will not introduce one. This requires a carefully designed, distinct fix and test (including SQLite error handling and lock/thread constraints). Internal SQLite should remain unaffected by external permission dialogs.

**Outside scope:** Android 11+ scoped storage and optional all-files access, Android 13+ media permissions, iOS `appPath` errors, and permission state after application updates. The single API29 condition cannot fix all such cases.

## Recommended production follow-up (not implemented here)

1. Restore the Android 10 candidate selection of a *declared* `WRITE_EXTERNAL_STORAGE` permission by changing the API comparison from `< Q` to `<= Q` in `AndroidPermissionManager.mediaPermissionCandidates()`. Add API27/29/30 source regression coverage and test requesting and denying WRITE; don't broaden defaults on Android 11+.
2. Keep permission-result semantics separate from the success of the retried File/SQLite operation. The granted callback is a *change in permission state*, not a guarantee that arbitrary paths have become accessible.
3. Diagnose the **direct native SQLite first-open** path separately. Preserve lock ordering and avoid invoking a modal Android permission request under a native SQLite mutex; a permission recovery should precede, or safely wrap and retry, a failed open exactly once when it is truly an access-denied filesystem error.
4. Verify the customer's effective AndroidManifest permissions and the exact path and opening sequence of the database using the supplied application; distinguish private `Settings.appPath` from public `/sdcard`.
5. Only after source checks consider another physical-device test. No billable Device Farm sessions were started for this experiment.

## Files

- Original experiment: `test/android10-storage-permission-emulator`
- Candidate experiment: `test/android10-storage-permission-emulator-patched`
- Independent Android app: `experiments/android-permission-emulator/app/src/main/java/totalcross/android/ProbeActivity.java`
- ADB emulator test runner: `experiments/android-permission-emulator/run_emulator.py`
- Candidate CI: `.github/workflows/android-permission-candidate-no-vm.yml`
- Production TotalCross 7.3.0 source was not modified.
