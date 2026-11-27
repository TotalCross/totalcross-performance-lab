# I07 — `Image(String)` filesystem fallback

## Result

**PASS on the four required platforms, with explicit conditional Linux
coverage.** The exact corrected SDK candidate passed the full 16-case probe on
Windows Win32/I386, Linux x86_64, macOS ARM64, and a hardware-accelerated
Android API 36 ARM64 emulator. Every run had zero failed cases and a successful
completion marker. Linux used the test-only realpath shim because its unmodified
runtime aborts before application startup. The Linux and macOS device-path
cases were skipped because those desktop filesystems denied or do not support
the device path; Android and Windows exercised the path where available.

## Windows Win32/I386

Run [45989644203](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/45989644203)
reused the verified corrected SDK and production Win32/Release Skia/SDL
runtime. All 16 cases passed; process exit was 0. PE machine `0x014C` was
verified for the source launcher, VM, deployed executable, and deployed VM.
The deployed `tcvm.dll` hash matches the exact Win32 runtime.

## Linux x86_64

The unmodified frozen runtime exited 134 before the probe with
`*** buffer overflow detected ***`. Under the test-only startup shim, all 16
reported cases completed with zero failures and exit 0; one unsupported device
path case was skipped. This result is conditional on the shim and does not
establish normal Linux startup.

## macOS ARM64

The canonical CMake/Ninja build completed on an ARM64 hosted runner. All 16
reported cases completed with zero failures and exit 0; the device-path case
was skipped because the desktop filesystem is read-only for that path.

## Android ARM64

The local hardware-accelerated API 36 emulator completed all 16 cases with
zero failures, skips, or native crashes. The VM reported the Apple M1 Pro host
GPU. Android process exit is not exposed by the local runner; the complete PASS
marker and no-crash state were recorded.

## Evidence

The hosted run produced artifacts for Windows I386, Linux x86_64, and macOS
ARM64. Their digests, runtime/SDK hashes, PE architecture, complete case
results, and compact runtime markers are retained under `../evidence/I07/`.
The local Android artifact and markers are retained in
[the API 36 evidence record](../evidence/I07/android-api36-arm64.json).
