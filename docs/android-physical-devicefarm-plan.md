# Physical Android 8 / 10 / 12 / 15 Device Farm regression matrix

## Motivation

Customer's TotalCross 7.3.0 File and plaintext SQLite regression persists on
Android 10 and does not occur on Android 12. The original APK
(`sqlite-plaintext-smoke.apk`, source SHA
`5464c21e3107e3f1ce9c287b724829e2bb870c1d`, SDK package run
`40878222908`) contains only ARM64 `libtcvm.so`. GitHub's older
Android x86 emulators cannot load it, and GitHub-hosted macOS/Linux ARM64
lack nested hardware virtualization. Physical Android devices avoid both
issues.

Android 8 (API 26) is a reasonable pre-scoped-storage control for Android 7
(API 24) with regard to external-storage permissions. It does *not* replace
Android 7 for full compatibility and is not identical in every permission
detail.

## Desired physical test cases

Run exactly the same APK, once on each available device/OS:

- Android **8.x** (API 26–27): legacy runtime storage permissions;
- Android **10.x** (API 29): reproduce customer failure;
- Android **12.x** (API 31–32): compare against customer passing device;
- Android **15.x** (API 35): modern regression control, already verified
  with the current emulator.

Record device model, actual OS version/API, installed ABI, APK SHA-256,
manifest and `dumpsys package` permissions, appops, logcat, and each
`TC_SQLITE_JSON` stage independently. Specifically:

1. In-app private `Settings.appPath`: memory/in-app SQLite creation,
   reopen, plaintext header and integrity.
2. Client's `Settings.dataPath="/sdcard/"`:
   create/delete `/sdcard/asd`, create/read/reopen an external SQLite
   database, and access a *preexisting* plaintext SQLite fixture placed by
   the test harness (not by TotalCross).
3. First launch without storage permission; capture whether the runtime
   permission dialog/Settings is shown, whether operations fail or block,
   whether the app resumes after returning.
4. Grant the applicable permission through the physical test's test host:
   legacy `WRITE_EXTERNAL_STORAGE` (API 26/29) where supported, or
   `MANAGE_EXTERNAL_STORAGE` via the corresponding AppOps setting
   (API 31/35, if declared). Never claim that granting legacy WRITE on
   targetSdk 36 guarantees unrestricted `/sdcard` access.
5. Relaunch and repeat every case; preserve both the negative and positive
   traces. Do not automatically label a positive grant phase PASS when the
   native DB did not actually reopen.

## IAM read-only inventory (executed without booking)

- First [workflow 43483384859](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43483384859):
  OIDC authentication succeeded but `devicefarm:ListDevices` returned
  `AccessDeniedException` for
  `GitHubActions-TotalCross-DeviceFarm`.
- Second [workflow 43483575844](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43483575844):
  OIDC succeeded; `GetProject` and `ListDevicePools` succeeded. Existing
  pools are named `Top Devices` (ten static device ARNs, OS versions not
  included in pool rules) and `iphone` (iOS phone, OS >25).
  `ListDevices` remains denied; this means **catalog availability is
  unknown**, not that Android 8/10/12 devices are absent.
- The minimum read permission for catalog discovery is
  `devicefarm:ListDevices`, typically with resource `*`, attached to
  the trusted OIDC role's identity policy. This does not grant permission
  to create pools or schedule device runs.

## Scheduling design (no billable execution initiated)

The AWS `ScheduleRun` API supports
`deviceSelectionConfiguration` as an alternative to a named device pool.
Each manual run can filter:

```python
deviceSelectionConfiguration={
    "maxDevices": 1,
    "filters": [
        {"attribute": "PLATFORM", "operator": "EQUALS",
         "values": ["ANDROID"]},
        {"attribute": "OS_VERSION", "operator": "GREATER_THAN_OR_EQUALS",
         "values": ["10.0"]},
        {"attribute": "OS_VERSION", "operator": "LESS_THAN",
         "values": ["11.0"]},
    ],
}
```

This is only a request-structure example, **not** an actual scheduled run.
Before booking, require a free per-version `ListDevices` validation
(or a verified explicit device ARN from the user's Device Farm console),
a one-device maximum, valid project-specific IAM permission, and an
explicit `execute=true` user-approved billable step.

The app should run under an automated test host that can call ADB and
collect logcat; an Appium test should trigger startup and capture
`TC_SQLITE_JSON`. Without a structured result, Device Farm's generic
installer success or random fuzz does not validate File/SQLite behavior.

No paid AWS device run has been scheduled by this investigation.
