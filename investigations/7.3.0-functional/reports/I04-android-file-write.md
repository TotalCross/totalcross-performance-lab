# I04 — Android `File.writeBytes` SIGABRT

## Result

**INCONCLUSIVE on Android API 30 ARM64.** Completed normal, recovered-permission,
invalid-mode, failed-open, and ten barrier-released write/close cases did not
produce the reported `fwrite`/invalid-`FILE*` abort. The denied all-files access
return did not complete the file operation, so that scenario remains
inconclusive. No live-mode `File` with a null or stale native handle was
constructed through the public API. The historical 4.x correction review does
not exclude I04; this is not a confirmed fix validation.

## Scope and historical context

I04 concerns an Android `File.writeBytes()` native abort reportedly involving
`fwrite()` and a null or invalid `FILE*`. The 4.6.0 source check is recorded in
[the legacy-port report](legacy-port-check.md). Commit
`e2c9f0795f213d780efe0ea78e958d7f55c13721` added guards for `INVALID` and
`CLOSED` modes, and those guards are present in 7.x. The POSIX write helper in
4.6.0 and frozen 7.x still passes the stored handle directly to `fwrite()`;
no exact correction for a live-mode object with a null or stale handle was
found. I04 remains in scope.

## Tested artifact and environment

- Product source revision represented by the official package:
  `5464c21e3107e3f1ce9c287b724829e2bb870c1d`.
- Official package: Actions run [40878222908](https://github.com/TotalCross/totalcross/actions/runs/40878222908), artifact `12899147776`.
- Artifact SHA-256:
  `a966f79d9193c7ee5757cfd66d17d73fbd73a478f7debe9394d898c413f044d5`.
- Nested SDK package SHA-256:
  `c9552cb95e1a09798637ad74266f91b62c6ea0ddc3d8dafa8402ac987f70288e`.
- SDK jar SHA-256:
  `23a0e5f16146414419c43f418d554f494d6acad362aa0e03ca11e11bfd430475`.
- Embedded Android `libtcvm.so` SHA-256:
  `bf630c7bf8a7a33323631c3b59699157d621a4f4587aac77779931a2de2544ad`.
- Environment: API 30 / Android 11, ARM64 AVD, fingerprint
  `google/sdk_gphone_arm64/emulator_arm64:11/RSR1.240422.006/12134477:userdebug/dev-keys`;
  Android Emulator 36.3.10 with GPU rendering on Apple M1 Pro.
- Probe APKs were deployed from the exact official 7.3.0 SDK. APK hashes and
  case results are in `../evidence/I04/android-api30-file-write-results.json`.

## Cases and results

| Case | Result | Observation |
| --- | --- | --- |
| App-private create/write/flush/readback/close | PASS | Readback matched all 16 bytes. |
| Write after close | PASS | Java `IOException: Invalid file object.`; process completed. |
| Write in `DONT_OPEN` mode | PASS | Java `IOException` reports the unsupported mode. |
| Unavailable `/proc` path | PASS | Constructor threw `ENOENT` before a `File` handle existed. |
| External write, pregranted | PASS | Wrote and flushed 22 bytes. |
| External write after Settings grant | PASS | After granting All files access, wrote and flushed 22 bytes. |
| External write after unchanged/denied Settings return | INCONCLUSIVE | App-op remained `ignore`; process stayed alive without a completion marker. No abort was observed. |
| Barrier-released concurrent write/close | PASS, limited | Ten 8 MiB write/close pairs returned; no abort. The probe does not establish simultaneous execution inside native `fwrite`. |
| File write during VM shutdown | INCONCLUSIVE | I05's separate file-I/O shutdown probe produced one destroyed-mutex abort, but its missing native stack does not establish `File.writeBytes`/`fwrite` as the call site. See the [I05 report](I05-android-shutdown.md). |

For the denied case, `WRITE_EXTERNAL_STORAGE` was pregranted as a neutral
baseline and `MANAGE_EXTERNAL_STORAGE` was set to `ignore`. The VM opened All
files access Settings. Returning without changing the app-op left the process
alive at the operation with no completion marker. A separate recovery run set
the app-op to `allow` while Settings was open; the write completed and the app
exited normally.

The write/close race releases both worker threads from a shared start barrier
and uses an 8 MiB payload to widen the native-write window. All ten writes
reported the full byte count and all closes returned. The harness records the
call boundary but does not instrument inside `fwrite`; therefore it does not
prove overlap at the C library call. The earlier 64 KiB version also completed
without abort but consistently let the write finish before close; it is
superseded by the larger-payload run.

## Source inspection

At the tested 7.3.0 revision:

- `TotalCrossSDK/src/main/java/totalcross/io/File.java:791` declares the
  deploy-time `File.writeBytes` implementation through `File4D`.
- `TotalCrossVM/src/nm/io/File.c:576` implements the native bridge. It rejects
  `INVALID`, `CLOSED`, `DONT_OPEN`, and `READ_ONLY` modes before dispatching.
- `File.c` stores the native `NATIVE_FILE` record in the `File_fileRef` byte
  array created during open. The successful close path calls `fileClose()` and
  then `mark_closed()`, which clears the reference and changes the mode.
- `TotalCrossVM/src/nm/io/posix/File_c.h:186` flushes and closes the stored
  `FILE*`; `:630` calls `fwrite(bytes + offset, 1, length, fref.handle)`.
  `tiF_writeBytes_Bii` and `tiF_close` do not share a per-file lock in this
  path. The concurrent probe did not reproduce an invalid-handle failure, so
  this observation is not proof that the race is responsible for the report.
- The helper checks the cast `fwrite()` result for `< 0`; the run did not force
  a short write or a libc error, so return-value behavior under those
  conditions remains unverified.

The failed-open public API path throws from the constructor and invalidates the
object; it does not yield a usable `File` on which a later write can be called.
The tested post-close and `DONT_OPEN` cases are intentional contract violations
and returned Java exceptions rather than aborting the process.

## Findings and uncertainty

**Established:** the tested 7.3.0 runtime guards closed/invalid modes; ordinary
writes and a granted external-storage write succeed; the tested misuse cases
throw Java exceptions; ten barrier-released write/close attempts did not abort.

**Not established:** whether the historical failure used a closed/invalid
object or a live object with a stale/null native handle; whether a partial
`fwrite()` can occur; whether `close()` and `writeBytes()` can overlap inside
the native helper; or whether the denied permission path eventually returns an
exception. No FORTIFY diagnostic or native stack was captured for I04.

No matching existing `File.writeBytes`/`fwrite` issue was found in the checked
issue search. Because the reported failure was not reproduced, this campaign
does not propose a new issue yet.

## Reproduction

Build the probes from the official SDK and local Android SDK:

```sh
python3 tools/android_file_write_shutdown_build.py \
  --sdk-home /path/to/extracted/official-7.3.0/TotalCross \
  --android-sdk /path/to/android-sdk \
  --groups I04 --out /tmp/tc730-i04-final-build
```

Run the standard and external probes on the hardware-accelerated API 30 ARM64
AVD. For the concurrent case, install
`i04race/deployed/install/android/i04race.apk` and launch
`totalcross.appzmtw/.Loader`. The exact package and native hashes, markers,
app-op states, and assertions are recorded in
`../evidence/I04/android-api30-file-write-results.json` and
`android-api30-file-write-events.log`.

## Recommended follow-up and acceptance

If the original customer reproducer or a valid live-mode stale-handle
reproducer becomes available, instrument handle creation, close, mode changes,
permission recovery, and the call into `fwrite()`. A future correction should
return a documented Java I/O error for invalid native state, avoid use-after-
close across threads, and preserve the complete write result. Validate normal,
failed-open, closed, denied, recovered, and synchronized concurrent cases
without native aborts before considering I04 resolved.

## Evidence index

- `../evidence/I04/android-api30-file-write-results.json`
- `../evidence/I04/android-api30-file-write-events.log`
- `legacy-port-check.md`
