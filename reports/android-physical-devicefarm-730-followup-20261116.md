# TotalCross 7.3.0 physical Android storage follow-up — 16 November 2026

## Provenance and scope

- Workflow: https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43952052000
- Authorized second round: **two** billable physical sessions, Pixel 4 Android 10 / API 29 and Pixel 5 Android 12 / API 32. No automatic additional physical retries.
- Trusted branch: `test/sqlite-plaintext-7.3.0`; execution commit: `c20f97df674ea6c6d0f6e594c09d1263ddafe6f9`.
- Original, unchanged TotalCross 7.3.0 APK: `totalcross.apprvks`, SHA-256 `8c6190fc5425a8f33db48900e7c9e7f8b1a2b9ff13a3d4667fe9cfc1325e685a`.
- Source SHA: `5464c21e3107e3f1ce9c287b724829e2bb870c1d`.
- Corrected test bundle: preparation run `43944824284`, artifact `14265191482` (test ZIP SHA-256 `e3bda7f9d4477ab699cc733cb860eab7fb0a5c0fb1ecd09839a9abb1e8d3e786`).
- Follow-up test sequence: **grant first**, run internal and external File/SQLite operations; then revoke/deny and run negative control.

## Actual physical results

| Operation | Android 10 (Pixel 4) with READ + WRITE granted | Android 12 (Pixel 5) with MANAGE_EXTERNAL_STORAGE allowed |
|---|---|---|
| Memory + private on-disk SQLite | PASS | PASS |
| Create/delete `/sdcard/asd` | PASS | PASS |
| Create/reopen/update external plaintext SQLite | PASS | PASS |
| Open/update pre-existing external SQLite fixture | PASS | PASS |
| Plaintext header / SQLite integrity verification | PASS | PASS |
| Python unittest | 1 test, 0 failures (7.964 s) | 1 test, 0 failures (98.168 s, including denied-phase wait) |
| Negative phase | **INCONCLUSIVE:** prior PID's PASS events were reused; current process stopped at runtime permission dialog | External stages NOT_REACHED after access denied / runtime permissions UI |

### Android 10: what the permission controls actually showed

- Pre-grant `dumpsys package`: both `READ_EXTERNAL_STORAGE` and `WRITE_EXTERNAL_STORAGE` were `granted=true` after explicit `adb pm grant` commands (both exited 0).
- The pre-granted phase successfully completed **all** File + SQLite stages. This rules out a general failure to open plaintext SQLite on the tested Android 10/7.3.0 binary with usable file access.
- After `pm revoke` of **both** READ and WRITE (exit 0), `dumpsys package` reported both `granted=false`; `appops get` still showed `LEGACY_STORAGE: allow`. This is relevant state information but does **not** prove the application retained usable access.
- **Correction based on raw logcat:** `denied-runtime.logcat` retained PASS events from the previous grant phase (PID `28693`, 20:40:34). The new denied-phase process (PID `28804`, 20:40:37) logged startup and `external-paths`, then Android opened `GrantPermissionsActivity`; it did **not** emit new external SQLite PASS events. The harness had deduplicated events by stage/status/detail without checking process PID, so it incorrectly classified stale events as a PASS. The negative-phase result is **INCONCLUSIVE**.
- This round did **not** reproduce the customer's persistent failure with the isolated smoke app. The customer's different app behavior, exact database path, request timing, permissions state and manifest remain relevant.

### Android 12: permission behavior

- The pre-granted `MANAGE_EXTERNAL_STORAGE` phase completed all File + SQLite stages.
- When appops was set to `MANAGE_EXTERNAL_STORAGE: ignore`, private SQLite remained successful, but the external stages stopped after `external-paths`: no external result was emitted in the 90-second observation window.
- `GrantPermissionsActivity` and later `Settings$AppManageExternalStorageActivity` were observed in the negative phase. This is a permissions/UI handshake, not evidence of failure in the SQLite engine. It is not a completed negative File-operation assertion.

## Device Farm status is separate from application results

**Both AWS runs were marked `FAILED`, while both actual unittest suites ran successfully with XML reporting `tests=1, failures=0, errors=0`.** Both customer artifact bundles contain `junit-results.xml` plus `unittest.log`, and both test-spec outputs end with `OK` and clean test-script completion.

- Android 10: AWS Device Farm run `604cb4ec-4786-478a-a4e3-0794fd8d0179`; GitHub artifact [14269120652](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43952052000/artifacts/14269120652).
- Android 12: AWS Device Farm run `c4825e60-fb8c-4bd4-b515-20f9a2e29f7b`; GitHub artifact [14267823879](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43952052000/artifacts/14267823879).
- Both AWS run counters: total 3; passed 2; failed 1. The precise AWS suite failure behind this classification was not determined from the downloaded top-level evidence.
- The IAM role also lacks `devicefarm:ListSuites`, producing `AccessDeniedException` when the evidence collector tried to inspect suite-level details. That is a **diagnostic access limitation**, not evidence the TotalCross test failed.
- No further paid tests should be scheduled merely to fix the reporting integration; investigate AWS suite classification using already collected artifacts or grant read-only `devicefarm:ListSuites` for diagnostics.

## Interpretation and next steps

1. **No SQLite engine regression reproduced** on the physical Android 10 or Android 12 devices with access pre-granted, using the isolated official 7.3.0 smoke APK.
2. Original Android 10 stall from first round was confounded by a pending permission UI and incomplete positive-control grant: READ remained denied after the harness granted WRITE only.
3. Investigate the **customer application** with exact Main.zip and database path, matching manifest permissions, `AndroidPermissionManager` runtime permission request timing, and native `FILE_RETRY_ACCESS` behavior. Record the final path and every requested/granted permission, appops, and callback result.
4. Do not interpret the apparent Android 10 success after revocation as permission bypass: the relevant PASS entries came from an earlier process. Future assertions must filter logcat by the current application PID and independently record appops, package grants, and UI state.
5. If customer path fails in 7.3.0 but not 7.2.2, compare both builds using the same manifest, app package, path and access state before attributing a release regression.
6. Investigate the Device Farm classification separately. Read-only `devicefarm:ListSuites` would help identify the AWS-level failed test component without rerunning billed devices.

The report is based on the two completed physical runs and the collected job, test-spec, device package, JUnit, appops and per-stage evidence.
## Source-level investigation and test-harness erratum (same date)

- Exact tested runtime source: `TotalCross/totalcross@5464c21e3107e3f1ce9c287b724829e2bb870c1d`.
- `TotalCrossVM/android/app/src/main/java/totalcross/android/AndroidPermissionManager.java`, `mediaPermissionCandidates()`: API 29/Q excludes `WRITE_EXTERNAL_STORAGE` from permission recovery even if the installed manifest declares it. Earlier APIs include WRITE. The Android 11+ path uses the separate all-files access Settings flow when requested.
- `TotalCrossVM/android/app/src/main/AndroidManifest.xml` provides baseline `WRITE_EXTERNAL_STORAGE` but not baseline `READ_EXTERNAL_STORAGE`. Hence an API 29 app with unchanged baseline declarations can enter a FILE_ACCESS recovery plan with **zero** runtime permission candidates and no all-files Settings stage. This is a defensible candidate bug; impact on the client's actual APK remains unverified because the original `Main.zip` / effective package manifest was not available during this follow-up.
- The physical smoke APK **did declare READ as well as WRITE**; both were granted manually with ADB for the positive phase. This test therefore did not cover the default-manifest scenario above.
- `TotalCrossVM/src/nm/io/posix/File_c.h` routes EACCES/EPERM from TotalCross File operations through `FILE_RETRY_ACCESS` -> `Launcher4A.requestStoragePermission()` -> `AndroidPermissionManager.requestFileAccessBlocking()`. When it cannot acquire new authorization, the original error is preserved.
- `TotalCrossVM/src/nm/db/NativeDB.c` calls `sqlite3_open_v2` without this File recovery wrapper. An external SQLite open performed before permission resolution may therefore fail directly, while a preceding TotalCross File call can initiate permission recovery.
- An isolated test harness fix was committed to the **non-billable** `test/android-devicefarm-730-physical-matrix` branch: event parsing now uses the launched app PID instead of accepting all old `logcat` records, and local tests cover old-PID false positives. No production APK, TotalCross VM or manifest was modified. No paid Device Farm run was scheduled.

The proposed production change to investigate is to include declared `WRITE_EXTERNAL_STORAGE` among Android 10/API 29 file-access recovery candidates (not merely Android 9 and below) while preserving the per-permission declaration checks and verifying actual grants. This requires controlled validation and cannot be treated as a confirmed customer fix on the evidence currently available.
