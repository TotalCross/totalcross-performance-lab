# I05 — Android native shutdown SIGABRT

## Result

**FAIL under one controlled API 30 ARM64 file-I/O shutdown run; root cause
open.** With a probe that makes no native debug call after requesting VM exit,
one of ten file-I/O shutdown cycles emitted `FORTIFY: pthread_mutex_lock called
on a destroyed mutex`, followed by SIGABRT on `Thread-2`. The next eight
cycles did not reproduce it. The first harness version logged from the worker
after the exit request and is excluded as instrumentation-confounded. The
clean reproduction still has no native backtrace, so the mutex owner and the
worker's exact instruction at failure are unknown.

Normal `MainWindow.exit()` and repeated initialization/termination passed ten
runs. Ten SQLite shutdown attempts emitted no FORTIFY abort. A separate active
Java worker exited cleanly when the user pressed the foreground button. Exit
after an external-storage permission request and successful grant also
completed. The background/foreground worker case did not reach its shutdown
button: it crashed first in the independent EGL surface-change path documented
under I03.

## Scope and related issue

The 4.6.0 port check is in [the legacy-port report](legacy-port-check.md).
It found no applicable shutdown-mutex correction, so I05 remains in scope.
Open TotalCross issue [#432](https://github.com/TotalCross/totalcross/issues/432)
tracks unsafe thread lifecycle and explicitly calls for cooperative Android
shutdown/join. Its scope is related but it does not record this reproduced
API 30 FORTIFY signature. A proposed self-contained issue update is in
`../proposed-issues/update-432-android-shutdown.md`; no remote issue was edited.

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
- Probe source and build identity are preserved in
  `cases/android-shutdown/Main.java`,
  `tools/android_file_write_shutdown_build.py`, and the evidence JSON.

## Test cases

| Case | Result | Evidence |
| --- | --- | --- |
| Normal `MainWindow.exit()` and repeated app initialization/termination | PASS, 10/10 | Each process logged startup and exit request; no fatal marker. |
| Exit during controlled file I/O | FAIL, 1/10 | FORTIFY destroyed-mutex abort occurred once in the clean probe; 8 subsequent runs did not reproduce. |
| Exit during SQLite query | PASS, 10/10 | Query-start marker preceded exit request in all runs; no fatal marker. The probe cannot prove the query remained inside SQLite at the exact exit instant. |
| Exit with active Java worker thread in foreground | PASS, 1/1 | Worker READY marker preceded the button-triggered `MainWindow.exit()`; process exited without FORTIFY. |
| Exit after external permission request | PASS, 1/1 | `MANAGE_EXTERNAL_STORAGE` started as ignored; Settings All files access was granted; write completed, then exit completed. |
| Exit after background/foreground | BLOCKED by I03 | The worker-screen diagnostic SIGSEGV occurred during foreground surface reinitialization before the I05 exit control could be invoked. |

The clean file-I/O probe creates an app-private file, starts a worker, then
performs repeated 1 MiB writes, flush, and close while the UI thread requests
exit after the readiness barrier. In the captured fatal cycle, `WRITE_BEGIN`
precedes `EXIT_REQUEST`; FORTIFY follows the exit request before any write-
complete marker. The worker has no post-operation debug call. This event order
rules out the earlier post-exit debug marker as the only trigger, but it does
not identify which native operation was active at the failing instruction.
The observed failure sequence was:

```text
TC_I05 case=file-io state=WRITE_BEGIN bytes=1048576
TC_I05 case=file-io state=EXIT_REQUEST after=worker-ready
FORTIFY: pthread_mutex_lock called on a destroyed mutex (address varies)
Fatal signal 6 (SIGABRT) ... in tid ... (Thread-2)
```

One clean cycle reproduced this signature; the remaining eight cycles in the
bounded follow-up did not. `ApplicationExitInfo` did not provide a crash trace,
and no new tombstone was available when checked. An earlier APK contained a
post-exit `WRITE_COMPLETE` debug call and aborted after that marker. That result
is retained as preliminary but excluded as confirmation because the debug call
could itself touch the destroyed mutex.

## Findings and unresolved cause

**Established:** a clean probe that has no worker-side debug logging after the
exit request can still produce a destroyed-mutex FORTIFY abort during the
file-I/O shutdown scenario. Normal exit, worker-only exit, SQLite shutdown,
and permission-grant-then-exit controls completed without this abort under the
tested conditions. The file-I/O event ordering is barrier-controlled at worker
readiness, but the harness cannot show whether the worker was inside `fwrite`,
`flush`, `close`, or another VM operation at the exact failing instruction.

**Not established:** which native mutex was destroyed; whether it belongs to
TotalCross, bionic stdio, or another runtime component; the exact call stack and
resource owner; whether shutdown should join this class of worker by contract;
or whether a worker continued after a VM-owned resource was released. Do not
attribute the failure to `File.writeBytes`, SQLite, EGL, or one specific global
mutex without a retained native backtrace.

## Reproduction

Build the isolated modes against the pinned official SDK:

```sh
python3 tools/android_file_write_shutdown_build.py \
  --sdk-home /path/to/extracted/official-7.3.0/TotalCross \
  --android-sdk /path/to/android-sdk \
  --groups I05 --out /tmp/tc730-i05-build
```

Run each mode in a fresh application process on the API 30 ARM64 AVD. The
file-I/O case was limited to ten total cycles for that APK and scenario.
The probe source, APK hashes, per-cycle markers, and compact result counts are
preserved in `../evidence/I05/android-api30-shutdown-results.json` and
`android-api30-shutdown-events.log`. Repeating identical file-I/O runs is not
recommended without first improving native crash capture.

## Recommended follow-up and acceptance

Instrument Android VM shutdown to record the owner and lifetime of each native
mutex, outstanding Java/native worker calls, and the exact thread stack at
teardown. Validate that shutdown either waits for active operations or safely
rejects work after teardown begins. Use a deterministic native barrier around
the implicated operation once its owner is known. Cover file I/O, SQLite,
permission return, active workers, and repeated initialization/termination.

The proposed update to issue #432 asks to track this API 30 FORTIFY signature
alongside its broader Android thread-shutdown work. Acceptance should include a
reproducer and ten clean bounded runs with no destroyed-mutex abort, plus
proof that no worker calls into native code after its required VM resources are
destroyed.

## Evidence index

- `../evidence/I05/android-api30-shutdown-results.json`
- `../evidence/I05/android-api30-shutdown-events.log`
- `../evidence/I03/android-api30-background-foreground-diagnostic.json`
- `legacy-port-check.md`
