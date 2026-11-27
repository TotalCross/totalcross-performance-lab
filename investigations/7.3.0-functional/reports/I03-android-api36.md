# I03 — Android Skia/EGL lifecycle crash

## Result

**FAIL — reproduced on the official 7.3.0 package, Android API 36, ARM64 AVD.**
The exact customer APK and a diagnostic build each crashed during denied and
grant-in-place permission flows. The pregranted trace control created and
deleted `/sdcard/asd` without crashing. Four SIGSEGV tombstones were collected
across the two permission flows.

This is a reproduction of the reported native failure, not a validated root
cause or correction. All four stacks enter `libtcvm.so` through
`nativeSurfaceChanged` → `initGLES` → `initSkia`; they include Skia GPU drawing
and `GrDirectContext` teardown frames. The evidence localizes the crash to the
Skia/GLES surface-change path. It does not yet isolate which lifecycle event or
resource state triggers it.

## Tested package and device

- Source commit: `5464c21e3107e3f1ce9c287b724829e2bb870c1d`
- Official 7.3.0 Actions run `40878222908`, artifact `12899147776`
- Artifact SHA-256: `a966f79d9193c7ee5757cfd66d17d73fbd73a478f7debe9394d898c413f044d5`
- Nested package SHA-256: `c9552cb95e1a09798637ad74266f91b62c6ea0ddc3d8dafa8402ac987f70288e`
- SDK jar SHA-256: `23a0e5f16146414419c43f418d554f494d6acad362aa0e03ca11e11bfd430475`
- Device: `Codex_ImageOwnership_API36_ARM64`, Android 16 / API 36,
  `arm64-v8a`, `sdk_gphone64_arm64`
- Fingerprint: `google/sdk_gphone64_arm64/emu64a:16/BE2A.250530.026.F3/13894323:userdebug/dev-keys`
- Acceleration: Hypervisor.Framework; emulator GPU mode `host`; renderer Apple
  M1 Pro
- Exact APK SHA-256:
  `44d425592047c867156c803750a1101f5010434711ed2ad0ef7cad14decbfe23`
- Trace APK SHA-256:
  `f8440c08f7a325161aaa0b1ad7f7bd377baf990f4202dbf4a492c9000553aec8`
- Embedded `lib/arm64-v8a/libtcvm.so` SHA-256:
  `bf630c7bf8a7a33323631c3b59699157d621a4f4587aac77779931a2de2544ad`
- Native Build ID: `961a27eeb19136ff86d2db5cb08bae194e967b9a`

The two APK variants use the same native library. The trace variant adds four
`Vm.debug` messages around the customer's `File.createDir()` and `delete()`;
the exact APK preserves the Java input unmodified. Source and package hashes,
phase results, tombstone hashes, and runtime identity are in
`../evidence/I03/android-api36-run.json`.

## Observations

The first attempt was inconclusive because Android displayed a System UI
“Application Not Responding” dialog over the All files access screen. The
emulator's **Wait** action cleared that dialog. Its screenshot is preserved as
`../evidence/I03/first-attempt-systemui-anr.png`; it is not counted as a
TotalCross crash.

After clearing the overlay, the same API 36 AVD produced these results:

| Variant and phase | Result |
| --- | --- |
| Exact, denied | Process received SIGSEGV; app disappeared after the permission transition. |
| Exact, grant in place | Process received SIGSEGV after Settings granted access. |
| Exact, pregranted | Process remained alive. |
| Trace, denied | Logged `totalcross.io.IOException: Error Code: 13 - Permission denied`, then received SIGSEGV. |
| Trace, grant in place | Created and deleted `/sdcard/asd`, then received SIGSEGV about 76 ms after the delete marker. |
| Trace, pregranted | Created and deleted `/sdcard/asd`; process remained alive. |

The four signals were `SIGSEGV` / `SEGV_MAPERR`, in the TotalCross event
thread. Fault addresses were `0x30` for denied phases and null for
grant-in-place phases. The common native stack contains
`FillRectOp::onExecute`, `GrDirectContext::~GrDirectContext`,
`SkGpuDevice::~SkGpuDevice`, `initSkia`, `initGLES`, and
`Java_totalcross_Launcher4A_nativeSurfaceChanged`. The grant-in-place stacks
also include the emulator's `GL2Encoder::s_glDrawRangeElements` frame. Compact
per-crash stack excerpts are in `../evidence/I03/native-crash-excerpts.log`;
the four full tombstones remain outside Git under `/tmp/tc730-android/build-retry/`.

The runner exited 1 because `inPlaceRemainsSameProcess` was false. This matches
the captured SIGSEGV; the other trace controls passed. The run is a confirmed
failure of the official 7.3.0 package on this API 36 emulator.

## Scope and next work

Only API 36 was exercised. API 29, 30, and 35, the corrected candidate, repeated
requests, unchanged Settings return, background/foreground transitions, and
rotation remain untested. Do not generalize this result to other Android APIs
or physical devices. Next, compare the exact and trace reproducers on the
available priority API images, preserving each tombstone and the same native
library identity where applicable.
