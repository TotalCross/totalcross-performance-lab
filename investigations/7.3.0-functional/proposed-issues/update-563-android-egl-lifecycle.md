# Proposed update for TotalCross issue #563

## Suggested title

Add Android 11, 15, and 16 reproductions of the Skia/EGL lifecycle crash

## Update text

The campaign reproduced the native crash in the official TotalCross 7.3.0
Android ARM64 package on hardware-accelerated API 30, 35, and 36 emulators.
Each API produced four SIGSEGV tombstones: exact and diagnostic customer
builds during denied and grant-in-place storage permission flows. All crashed
threads were the TotalCross Event Thread. Denied phases faulted at `0x30`;
grant-in-place phases faulted at null. The shared stack includes
`FillRectOp::onExecute`, `GrDirectContext::~GrDirectContext`,
`SkGpuDevice::~SkGpuDevice`, `initSkia`, `initGLES`, and
`Java_totalcross_Launcher4A_nativeSurfaceChanged`. The embedded native library
was identical across these runs (SHA-256
`bf630c7bf8a7a33323631c3b59699157d621a4f4587aac77779931a2de2544ad`, Build ID
`961a27eeb19136ff86d2db5cb08bae194e967b9a`).

The pregranted controls stayed alive on all tested APIs. On API 30, 35, and 36,
the trace grant-in-place control created and deleted `/sdcard/asd` before
crashing. The denied trace logged the expected permission error before the
native crash. API 29 did not reproduce the native crash; its runtime permission
dialog requested `READ_EXTERNAL_STORAGE`, and the directory operation still
failed after Allow because `WRITE_EXTERNAL_STORAGE` remained denied. A
pregranted WRITE control succeeded. That API 29 permission result is tracked
separately from this EGL issue.

The current tested source destroys and terminates the previous EGL context
before creating the replacement context. `initSkia()` then resets the previous
Skia surface during initialization of the replacement context. This order is
consistent with the observed stack, but the campaign did not record context
handles/current-context state or Skia resource ownership. The root cause is
therefore **not established**.

The exact source, artifact hashes, API fingerprints, phase results, native
stacks, limitations, and reproduction commands are in:

- `investigations/7.3.0-functional/reports/I03-android-egl-lifecycle.md`
- `investigations/7.3.0-functional/evidence/I03/android-api29-run.json`
- `investigations/7.3.0-functional/evidence/I03/android-api30-run.json`
- `investigations/7.3.0-functional/evidence/I03/android-api30-native-stack-excerpts.log`
- `investigations/7.3.0-functional/evidence/I03/android-api35-run.json`
- `investigations/7.3.0-functional/evidence/I03/android-api35-native-stack-excerpts.log`
- `investigations/7.3.0-functional/evidence/I03/android-api36-run.json`

Recommended next diagnostic: instrument EGL context and surface handles,
`eglGetCurrentContext()`, surface generation, and Skia surface/context release;
then compare denied, grant-in-place, and pregranted runs on API 30 or 35. Do not
infer the fix from the current ordering alone. Validate a future correction
against the same customer operation on the priority Android APIs.

## Acceptance criteria

- The original customer create/delete operation survives denied and
  grant-in-place permission transitions without a native crash.
- A successful in-flow grant performs the operation in the same process.
- Denied access returns the expected permission error.
- Pregranted access remains functional.
- The functional matrix passes on the corrected candidate for the supported
  ARM64 Android API range; physical-device coverage is reported separately.

This is a proposed update only. No remote issue was changed.
