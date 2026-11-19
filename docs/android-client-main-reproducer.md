# Android: reproducing the customer's `Main.zip` on TotalCross 7.3.0

## Exact customer input

The customer-supplied `Main.zip` contains:
- `Main.java` (648 bytes): `MainWindow`, `Window.NO_BORDER`,
  `Settings.ANDROID_UI`, `WINDOWSIZE_600X800`,
  `swap(new TestPermission())`.
- `TestPermission.java` (905 bytes): a white `Container` with an `Edit`
  field; in `initUI()`, assign `Settings.dataPath = "/sdcard/"` and
  immediately call `checkFolderPermission()`.
- `Main.apk` (24,519,986 bytes): manifest package `totalcross.appzmtw`,
  `compileSdkVersion=36`, `targetSdkVersion=36`,
  `minSdkVersion=24`. The app declares `MANAGE_EXTERNAL_STORAGE`.

No SQLite calls are present in the customer sources.

The unmodified source is checked in as
[`tests/android-client-main/original/Main.java`](../tests/android-client-main/original/Main.java)
and [`TestPermission.java`](../tests/android-client-main/original/TestPermission.java).
Both are recompiled against the *pinned official TotalCross 7.3.0 SDK*.
An independent comparison showed that the ARM64 `libtcvm.so` in the
customer's original `Main.apk` and the previously built official 7.3.0
test APK are **byte-for-byte identical**:

```
SHA256 arm64-v8a/libtcvm.so
bf630c7bf8a7a33323631c3b59699157d621a4f4587aac77779931a2de2544ad
```

The standalone [Android CI workflow](../.github/workflows/android-client-main.yml)
builds **two APKs**: `exact` (the unmodified customer sources), and `trace`
(identical control flow with exactly four additional `Vm.debug` calls:
BEGIN / CREATED / DELETED / FAIL). No extra filesystem or SQLite calls
are introduced in the trace copy. The customer-provided original APK is
**not** installed by this workflow: it is a source-identical rebuild. Both
APK variants are installed sequentially using the same app package name.

## Run results (Android 15 API 35, Google APIs x86_64 with ARM64 translation)

[Workflow run 43113450337](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43113450337)
— [download original/trace APKs, screenshots, full logcat, JSON summaries](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43113450337/artifacts/13897103604).

| Build / permission phase | File result | After returning from Android Settings |
|---|---|---|
| Exact source, permission denied | Original app opened the Settings screen; its catch renders the error in `Edit` | **SIGSEGV** in TC Event Thread |
| Exact source, permission granted during Settings | No extra trace calls; directory no longer exists at end | **SIGSEGV** in TC Event Thread |
| Exact source, permission pregranted | No error in logcat; app stayed alive | No crash |
| Traced, permission denied | `TC_CLIENT_MAIN FAIL totalcross.io.IOException: Error Code: 13 - Permission denied` | **SIGSEGV** in TC Event Thread |
| Traced, permission granted during Settings | `TC_CLIENT_MAIN CREATED` then `TC_CLIENT_MAIN DELETED` | **SIGSEGV** in TC Event Thread |
| Traced, permission pregranted | `CREATED` then `DELETED` | No crash |

The workflow is marked **FAILED** intentionally: in-place grant performed the
File operations successfully, but the application then crashed. The client
sample (no SQLite) reproduces this crash as well.

Native log signature, on the **original, uninstrumented** app and traced app:

```
Surface: getSlotFromBufferLocked: unknown buffer: 0x0
TotalCross: initSkia
emuglGLESv2_enc: GL error 0x502 [bufferId==0]
emuglGLESv2_enc: GL error 0x501 [program && !shared->isShaderOrProgramObject(program)]
libc: Fatal signal 11 (SIGSEGV) ... (TC Event Thread)
```

The native tombstone in `trace-grant-in-place-logcat.txt` includes:

```
#00 /system/lib64/libGLESv2.so
#01 libtcvm.so FillRectOp::onExecute
#06 libtcvm.so GrDirectContext::~GrDirectContext
#12 libtcvm.so SkSurface_Gpu::~SkSurface_Gpu
#13 libtcvm.so initSkia+132
#14 libtcvm.so initGLES+508
#15 libtcvm.so Java_totalcross_Launcher4A_nativeSurfaceChanged+712
```

### Likely native cause to investigate

In pinned `5464c21e` (the official 7.3.0 SDK source),
`TotalCrossVM/src/nm/ui/backend/graphics/gles/gfx_Graphics_c.h`
`androidApplySurfaceChange()` destroys the old EGL context with
`androidDestroyEGL(extension)` before calling `initGLES()` for a new
window. Only inside `initGLES()` → `initSkia()` is the old Skia
`surface` released by `destroySkiaScreen()` / `surface.reset()`.
Destroying that old surface can flush GPU commands against a deleted EGL
context or one with incompatible GL resource objects. The above native
stack is consistent with that ordering defect.

A possible fix is to release/flush the old Skia GPU surface **while its
original EGL context is still current**, *before* `androidDestroyEGL()`,
then rebuild the new Skia screen after creating the new EGL context.
This requires careful handling of `canvas` pointers and other callers,
and verification on a physical ARM64 Android device before attributing
the crash conclusively to the TCVM rather than emulator GL translation.

This lifecycle/graphics crash should be investigated independently of the
missing `MANAGE_EXTERNAL_STORAGE` authorization. `File.createDir` and
`File.delete` both completed successfully after the appop grant.
iOS is out of scope for this reproducer.
