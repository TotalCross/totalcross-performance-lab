# Physical Android File + SQLite storage regression — 16 November 2026

## Objective and exact immutable APK

Compare TotalCross 7.3.0 on physical Android 8.1, Android 10, Android 12 and Android 15.
Use the unchanged original plaintext SQLite / File probe to determine whether
the customer's Android 10 denial vs Android 12 success relates to Android
storage/runtime permissions.

- GitHub Actions: [run 43942659901](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43942659901).
- Official test APK: `totalcross.apprvks` / `sqlite-plaintext-smoke.apk`.
- APK SHA-256: `8c6190fc5425a8f33db48900e7c9e7f8b1a2b9ff13a3d4667fe9cfc1325e685a`.
- TotalCross 7.3.0 source SHA: `5464c21e3107e3f1ce9c287b724829e2bb870c1d`.
- Original GitHub artifact: `14007058527` from `43359416885`.
- All four tests used individually pinned physical Pixel device ARNs;
  AWS `deviceSelectionConfiguration.maxDevices=1` and recorded
  `matchedDevicesCount=1` for each.
- The first attempt [43942334109](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43942334109)
  failed at AWS OIDC trust verification because its GitHub branch was not
  trusted. **It scheduled no paid device sessions**. The jobs were then
  moved onto already-trusted `test/sqlite-plaintext-7.3.0`.

## Measured results

| Device | Actual API | Internal SQLite | No-grant /sdcard | Explicit storage grant | Post-grant /sdcard | Outcome |
|---|---:|---|---|---|---|---|
| Google Pixel 2 XL / Android 8.1.0 | **27** | PASS in initial phase | Blocks at Android runtime permission dialog | `pm grant WRITE_EXTERNAL_STORAGE`: exit 0; `granted=true` in `dumpsys package` | **INCONCLUSIVE**: app never emitted second-phase Java stages; permission controller remained foreground | Inconclusive |
| Google Pixel 4 (Unlocked) / Android 10 | **29** | PASS in initial phase | Blocks at Android runtime permission dialog | `pm grant WRITE_EXTERNAL_STORAGE`: exit 0 | **INCONCLUSIVE**: no second-phase Java stages; permission controller remained foreground | Inconclusive, relevant repro path reached |
| Google Pixel 5 (Unlocked) / Android 12 | **32**, not 31 | Not attempted | Not attempted | Not attempted | Not attempted | **Harness precondition failure**: expected API 31; actual API 32 |
| Google Pixel 8 / Android 15 | **35** | PASS in both phases | External directory `EACCES`, all external SQLite cases failed | `appops MANAGE_EXTERNAL_STORAGE allow` | **PASS:** create/delete `/sdcard/asd`, SQLite create/reopen, existing fixture read/update, plaintext header | Full application-level PASS |

Every phone installed/loaded the ARM64 TotalCross VM. All four physical
AWS jobs completed, but their *overall* Device Farm result was `FAILED`
for different reasons. The Android 15 `unittest` reported **1 passed /
0 failed** with all expected SQLite/File assertions, yet AWS classified
its job as failed because the custom test package omitted JUnit XML.
AWS reported: `No JUnit XML test results file was found in the output
artifacts. Run pytest with --junit-xml and write the report under
$DEVICEFARM_LOG_DIR.` Do not equate the AWS run badge with the
application's File/SQLite result.

### Per-device AWS evidence

| Device | Physical run ID | GitHub evidence artifact ID | Recorded device minutes (total / metered) |
|---|---|---:|---|
| Pixel 2 XL / Android 8.1 | `2e49c72e-65ba-42dd-bb77-1ffc30333523` | [14263826408](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43942659901/artifacts/14263826408) | 3.87 / 3.46 |
| Pixel 4 / Android 10 | `bc03a7ae-9bd7-4575-92a8-7fb81d37fa06` | [14264426183](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43942659901/artifacts/14264426183) | 3.65 / 3.27 |
| Pixel 5 / Android 12 | `158e23ba-4b7c-4214-9302-04d16774630c` | [14263506091](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43942659901/artifacts/14263506091) | 0.58 / 0.21 |
| Pixel 8 / Android 15 | `8064ace3-2aa1-4456-b994-f7aab7c53aa6` | [14264615770](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43942659901/artifacts/14264615770) | 0.90 / 0.51 |

AWS usage minutes were obtained from `GetRun.deviceMinutes`; they are not
an estimate in dollars. No additional paid sessions have been booked.

## Important Android 8.1 and 10 observation

The **first** app launch successfully emitted:
`startup`, `memory`, `file-create`, `file-reopen`,
`plaintext-header` and `external-paths`. Immediately after
`external-paths`, Android started its
`GrantPermissionsActivity` using
`android.content.pm.action.REQUEST_PERMISSIONS`. The expected
`external-dir` event never appeared in 90 seconds. The test harness
detected the permission dialog and issued `KEYCODE_BACK`, but
`dumpsys window` continued showing the permissions UI in the
foreground. This means the test stalled at a **permission/UI handshake**,
not a SQLite engine failure.

The harness then issued `pm grant WRITE_EXTERNAL_STORAGE` (exit 0).
The Android 8.1 `dumpsys package` explicitly confirmed
`WRITE_EXTERNAL_STORAGE: granted=true`. Nevertheless, the earlier
permissions screen remained the focused app during the second phase,
which emitted no new `TC_SQLITE_JSON` events. **Therefore we did not
measure whether the post-grant filesystem API works on either old OS.**
These failures cannot be presented as a demonstrated inability to open
the database with the permission correctly granted.

Android 10's new permission code still deserves review: the manifest,
`AndroidPermissionManager` permission selection on API29, and native
`FILE_RETRY_ACCESS` behavior differ from the modern
`MANAGE_EXTERNAL_STORAGE` branch. But the actual physical run does
not yet isolate a 7.3.0 regression versus a test-host dialog.

## Why the Android 12 test did not run

The physical Pixel 5 advertises Android 12 and reports
`ro.build.version.sdk=32`, whereas the original test package pinned
`EXPECTED_ANDROID_API=31`. The test correctly rejected this
mismatch **before starting the app operations**. The selected model and
OS major were correct; the hard-coded API level was wrong.

## Next test design (not scheduled)

To make any additional paid session informative, first change the
harness **without modifying the production APK**:

1. Accept Android 12 **API 32** for the selected Pixel 5.
2. On Android 8.1/10, run the **pre-granted** scenario first on a clean
   app state, then revoke permissions and test denial second. This
   avoids leaving `GrantPermissionsActivity` foreground when testing
   the already-authorized path.
3. For denied tests, use an explicit UIAutomator snapshot and reliably
   tap the permission **Deny** control, then confirm focus returned to
   the TotalCross application; record if the app requests again.
4. Record `READ_EXTERNAL_STORAGE` and `WRITE_EXTERNAL_STORAGE`
   declared vs actually granted (Android `dumpsys package`) before and
   after each phase, rather than inferring from AAPT output alone.
5. Generate an actual JUnit XML test report under
   `$DEVICEFARM_LOG_DIR` so AWS accurately classifies the result.
6. If the Android 10 scenario then fails while Android 12 passes,
   compare a **7.2.2** baseline *with the same Android SDK, requested
   permission configuration, test sequence and device* to attribute
   the issue to the 7.3.0 changes.

**Billing guard:** The user's authorization covered four selected
physical devices. All four have now been run once. Do not schedule
a fifth session or retries without a new explicit authorization.


## Additional per-permission evidence and prepared follow-up harness

The physical Android 10 `dumpsys package` output makes the grant distinction
explicit:

- Initial phase: `READ_EXTERNAL_STORAGE: granted=false`,
  `WRITE_EXTERNAL_STORAGE: granted=false`, with both permissions listed
  as `restricted=true`.
- After the automation's manual `pm grant WRITE_EXTERNAL_STORAGE`:
  `WRITE_EXTERNAL_STORAGE: granted=true`, but
  **`READ_EXTERNAL_STORAGE: granted=false` remained unchanged**.
- The existing `GrantPermissionsActivity` stayed in the foreground;
  no post-grant Java stage was emitted. Therefore granting *only* WRITE
  was not an adequate positive-control setup for Android 10.

The Android 8.1 control also confirmed
`WRITE_EXTERNAL_STORAGE: granted=true` after `pm grant`, but its
permissions dialog remained in front of the app.

A corrected **build-only** test harness is available on
[`test/android-devicefarm-730-physical-matrix`](https://github.com/TotalCross/totalcross-performance-lab/tree/test/android-devicefarm-730-physical-matrix).
It now:

1. Pins the Pixel 5's actual Android 12 API to **32**.
2. Tests the pre-granted case **first** on API 27/29, explicitly attempts
   both `WRITE_EXTERNAL_STORAGE` and `READ_EXTERNAL_STORAGE`, and
   records their actual grant results.
3. Runs the denial scenario second to avoid contaminating the authorized
   phase with an unresolved permission dialog.
4. Emits a real JUnit XML report for the AWS custom host.

The updated package was successfully compiled and verified in the
**non-billable** [prepare workflow 43944824284](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43944824284),
artifact `14265191482`. It has **NOT** been executed on physical devices.
Four paid runs were used for the initial investigation; an additional
physical execution requires separate authorization.
