# I03 — Android Skia/EGL lifecycle crash

## Result

**FAIL on API 30, 35, and 36; NOT_REPRODUCED on API 29.** The official
TotalCross 7.3.0 Android ARM64 runtime produced four SIGSEGV tombstones on
each of API 30, 35, and 36 across denied and grant-in-place permission flows.
The exact customer APK and a diagnostic build showed the same native failure.
Pregranted controls stayed alive on all four APIs.

API 29 did not produce a native crash in the tested denied, grant-in-place, or
pregranted flows. However, its interactive Allow action left
`WRITE_EXTERNAL_STORAGE` denied and the customer directory operation failed
with Error Code 13; only the explicitly pregranted control created and deleted
`/sdcard/asd`. This is a filesystem permission recovery failure for I08, not
evidence that the API 29 EGL flow passed.

The crash is localized to the Skia/GLES surface-change path, but the root cause
is **open**. The current source destroys an EGL context before reinitializing
Skia, whose initialization resets its previous surface. This ordering is a
testable hypothesis. The run did not record EGL context identifiers, current
context state, or Skia resource ownership at destruction, so it does not prove
that ordering caused the crash.

## Historical context and scope

Issue [#563](https://github.com/TotalCross/totalcross/issues/563) reports a
customer crash around Android storage permission recovery. The original
reproducer in performance-lab PR #7 sets `Settings.dataPath = "/sdcard/"`,
then calls `File.createDir()` and `File.delete()`. It does not use SQLite.
This campaign ran the official 7.3.0 package only; the corrected candidate and
physical devices were not tested.

The I03 workload remains distinct from SQLite permission recovery (I09). The
API 29 permission behavior is cross-referenced in the I08 investigation because
that API uses the legacy storage permission instead of the all-files app-op.

## Tested source and artifact

- Repository: `TotalCross/totalcross`
- Source revision: `5464c21e3107e3f1ce9c287b724829e2bb870c1d`
- Official Actions run: [40878222908](https://github.com/TotalCross/totalcross/actions/runs/40878222908)
- Artifact ID: `12899147776`, name `TotalCross-7.3.0`
- Artifact SHA-256: `a966f79d9193c7ee5757cfd66d17d73fbd73a478f7debe9394d898c413f044d5`
- Nested package SHA-256: `c9552cb95e1a09798637ad74266f91b62c6ea0ddc3d8dafa8402ac987f70288e`
- SDK jar SHA-256: `23a0e5f16146414419c43f418d554f494d6acad362aa0e03ca11e11bfd430475`
- Embedded Android `libtcvm.so` SHA-256:
  `bf630c7bf8a7a33323631c3b59699157d621a4f4587aac77779931a2de2544ad`
- Native Build ID: `961a27eeb19136ff86d2db5cb08bae194e967b9a`
- Package target SDK: 36.
- Exact and trace APKs were rebuilt from the pinned official SDK and customer
  Java source. The trace variant adds four `Vm.debug` markers around the
  existing create/delete operation; it does not change the file operations.
- Rebuilt APK hashes are in each API's JSON evidence. API 36's imported
  campaign run used a prior package build; its APK hashes differ, while its
  embedded native library hash and Build ID match.

The artifact ZIP hash was verified after download. API 29, 30, and 35 reused
the same rebuilt APK pair and native library. Each permission phase started
from a fresh install to reset app data and Android's user-set permission state.

## Environment and cases

All tests ran locally on ARM64 Android emulator images accelerated through the
Apple M1 Pro GPU renderer. No Android runtime test ran in GitHub Actions.

| API | Android | AVD fingerprint | Denied | Grant in flow | Pregranted |
| --- | --- | --- | --- | --- | --- |
| 29 | 10 | `google/sdk_gphone64_arm64/emulator64_arm64:10/QSR1.211112.011/13135432:userdebug/dev-keys` | No native crash; trace logged permission error | No native crash; Allow left WRITE denied and operation failed | Created/deleted; process stayed alive |
| 30 | 11 | `google/sdk_gphone_arm64/emulator_arm64:11/RSR1.240422.006/12134477:userdebug/dev-keys` | SIGSEGV | Trace created/deleted, then SIGSEGV | Created/deleted; process stayed alive |
| 35 | 15 | `google/sdk_gphone64_arm64/emu64a:15/AE3A.240806.043/12960925:userdebug/dev-keys` | SIGSEGV | Trace created/deleted, then SIGSEGV | Created/deleted; process stayed alive |
| 36 | 16 | `google/sdk_gphone64_arm64/emu64a:16/BE2A.250530.026.F3/13894323:userdebug/dev-keys` | SIGSEGV | Trace created/deleted, then SIGSEGV | Created/deleted; process stayed alive |

API 30, 35, and 36 each produced four native crashes: exact and trace variants
in denied and grant-in-place phases. API 29 produced none. The trace denied
operation logged Error Code 1 on API 30 and Error Code 13 on APIs 29, 35, and
36. Grant-in-place trace phases on APIs 30, 35, and 36 logged both file markers
before the native crash.

For API 29 the accessibility hierarchy exposed Android's runtime Allow/Deny
dialog, and the harness tapped the selected button. The dialog requested
`READ_EXTERNAL_STORAGE`; after Allow, `WRITE_EXTERNAL_STORAGE` remained
`granted=false`, and `File.createDir()` returned Error Code 13. A separate
pregranted WRITE control succeeded. This package targets SDK 36 on Android 10;
the interaction therefore does not establish that the campaign's legacy
permission recovery correction works on API 29.

On API 30, `WRITE_EXTERNAL_STORAGE` was explicitly pregranted as a neutral
baseline and the `MANAGE_EXTERNAL_STORAGE` app-op was varied per phase. On API
35 and 36, the `MANAGE_EXTERNAL_STORAGE` app-op was varied. Android 30+
permission transitions opened All files access Settings.
On these emulator images, `monkey` exits with status 251 despite launching the
app, so the harness uses the manifest's launch activity through
`am start -W`. This launch fallback is recorded and is not treated as an
application failure.

## Native evidence

The API 30, 35, and 36 crashes were SIGSEGV / SEGV_MAPERR on the TotalCross
Event Thread. Denied flows faulted at `0x30`; grant-in-place flows faulted at
null. The common symbolized frames include:

```text
GL2Encoder::s_glDrawRangeElements
(anonymous namespace)::FillRectOp::onExecute
GrDirectContext::~GrDirectContext
SkGpuDevice::~SkGpuDevice
initSkia
initGLES
Java_totalcross_Launcher4A_nativeSurfaceChanged
```

Every crash reported the same `libtcvm.so` Build ID. API 29's app process
remained alive in all three phases and the tombstone directory was empty after
the run. The API 30/35 native stack excerpts and per-phase event logs are
preserved under `../evidence/I03/`; API 36 excerpts and the initial emulator
System UI ANR evidence are preserved there as well. The four full tombstones
per crashing API were inspected and are not committed.

The first API 36 attempt showed a System UI ANR over the permission screen.
That attempt is classified inconclusive. Selecting Wait cleared the overlay;
the subsequent retry produced the four recorded TotalCross tombstones.

## Source inspection

The inspected source is the official tested revision
`5464c21e3107e3f1ce9c287b724829e2bb870c1d`:

- `TotalCrossVM/src/nm/ui/backend/graphics/gles/gfx_Graphics_c.h:74`:
  `androidDestroyEGL()` unbinds the current EGL context, destroys the context
  and surface, and terminates the display.
- `gfx_Graphics_c.h:104-171`: when the Java surface changes and graphics were
  initialized, `androidApplySurfaceChange()` destroys the old EGL state,
  releases the old native window, applies the new screen configuration, and
  calls `initGLES()`.
- `gfx_Graphics_c.h:246-355`: `initGLES()` creates and makes the replacement
  EGL context current, then calls `initSkia()`.
- `TotalCrossVM/src/nm/ui/skia/skia.cpp:124-127`:
  `initSkia()` begins by calling `destroySkiaScreen()`.
- `skia.cpp:180-187`: `destroySkiaScreen()` clears the canvas, resets the
  bitmap, and resets the Skia surface; it does not explicitly record or check
  the EGL context associated with those resources.

This source order is consistent with the Skia/GLES stack, but static source
inspection plus a crash stack is insufficient to establish a lifecycle
contract violation. Do not treat the existing hypothesis as the root cause.

## Reproduction

1. Download artifact `12899147776` from Actions run `40878222908` and verify
   its SHA-256 against the provenance above.
2. Use `tools/android_client_main_build.py` to compile the source-identical
   exact APK and marker-only trace APK with the pinned 7.3.0 SDK.
3. Boot one of the listed ARM64 AVDs with GPU host acceleration.
4. Run `tools/android_client_main_test.py --out <results> --timeout 45`.
   The harness installs the APK afresh for each denied, grant-in-place, and
   pregranted phase, captures logcat and screenshots, and records PIDs,
   permission state, markers, and exit conditions.
5. On API 30, grant WRITE as the neutral baseline and vary the
   MANAGE_EXTERNAL_STORAGE app-op. On API 35/36, vary the all-files app-op. On
   API 29, vary WRITE_EXTERNAL_STORAGE and use the runtime permission dialog.

When each API uses a separate results directory, place the exact and trace
APKs at `<results>/exact/deployed/install/android/` and
`<results>/trace/deployed/install/android/` respectively. The API 29, 30, and
35 evidence runs used the same rebuilt APK pair; only the emulator and test
output directory changed.

The campaign command outputs are preserved as compact JSON and sanitized log
excerpts in `../evidence/I03/`. Rebuilding the probe is not required to inspect
the committed crash evidence.

## Findings and unresolved work

**Established**

- The official 7.3.0 Android ARM64 native runtime crashes in denied and
  grant-in-place surface transitions on API 30, 35, and 36.
- Pregranted controls complete the customer create/delete operation and remain
  alive on all four tested APIs.
- API 29's interactive Allow choice did not grant the legacy write access
  required by this customer path; an explicit pregrant did.
- The same native Build ID appears in all API 30/35/36 crashes.
- The current source destroys EGL before its Skia surface reset occurs during
  replacement initialization.

**Not established**

- That EGL destruction ordering causes the crash.
- The exact Activity, surface callback ordering, EGL context handle/current
  state, or Skia resource owner at each crash.
- Behavior of the corrected candidate.
- Behavior on physical Android devices.

Settings return without changing authorization, repeated requests,
background/foreground, and rotation were not separately exercised. The
primary denied, in-flow, and pregranted controls already reproduce the crash
on three priority APIs; those additional scenarios would not distinguish its
current platform classification. APIs 24 and 31 were not provisioned. Record
these combinations as untested rather than inferring results.

## Recommended diagnostic sequence

1. Add temporary native tracing for EGL display/surface/context handles,
   `eglGetCurrentContext()`, `eglGetCurrentSurface()`, surface generations,
   and Skia surface/context creation and destruction. Keep the original
   customer behavior and build the exact same 7.3.0 source.
2. Reproduce one denied and one grant-in-place case on API 30 or 35, then
   compare the trace with a pregranted control.
3. Test whether releasing old Skia GPU resources while the old EGL context is
   current changes the result. Treat this as a diagnostic experiment; do not
   ship a production lifecycle change without evidence.
4. Separately investigate why API 29's interactive grant leaves
   `WRITE_EXTERNAL_STORAGE` denied under target SDK 36.

Acceptance requires the original customer operation to survive denied,
grant-in-place, and pregranted permission transitions without native crashes;
successful authorization recovery must create and delete the directory in the
same process, and denied access must report the expected error. Repeat the
functional matrix on the corrected candidate before declaring the correction
validated.

## Evidence index

- `../evidence/I03/android-api29-run.json`
- `../evidence/I03/android-api29-log-excerpt.log`
- `../evidence/I03/android-api29-permission-prompt.png`
- `../evidence/I03/android-api30-run.json`
- `../evidence/I03/android-api30-log-excerpt.log`
- `../evidence/I03/android-api30-native-stack-excerpts.log`
- `../evidence/I03/android-api30-permission-prompt.png`
- `../evidence/I03/android-api35-run.json`
- `../evidence/I03/android-api35-log-excerpt.log`
- `../evidence/I03/android-api35-native-stack-excerpts.log`
- `../evidence/I03/android-api35-permission-prompt.png`
- `../evidence/I03/android-api36-run.json`
- `../evidence/I03/native-crash-excerpts.log`
- `../evidence/I03/first-attempt-systemui-anr.png`
