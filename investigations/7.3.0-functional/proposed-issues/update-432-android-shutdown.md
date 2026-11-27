# Proposed update to TotalCross issue #432

## Android API 30: destroyed-mutex abort during VM exit with file I/O active

A focused probe built from the official TotalCross 7.3.0 SDK reproduced
`FORTIFY: pthread_mutex_lock called on a destroyed mutex`, followed by SIGABRT
on an Android 11 / API 30 ARM64 emulator. The probe starts an app-private file
writer on a Java worker thread, requests `MainWindow.exit()` after a readiness
barrier, and performs writes, flush, and close without worker-side debug calls
after the exit request. One of ten clean cycles aborted; eight subsequent
cycles did not reproduce.

Normal exit, ten SQLite shutdown attempts, and a foreground worker-only exit
completed without the same FORTIFY signature. The first file-I/O probe build
logged from the worker after shutdown and is excluded as instrumentation
confounded. The clean crash had no retained native backtrace, so the mutex
owner, failing function, and whether the worker was inside `fwrite`, `flush`,
`close`, or another VM operation are unknown. This is evidence of a
shutdown/thread-lifetime failure mode, not proof of a specific mutex owner.

### Reproduction and evidence

The exact test source and runner are in the TotalCross performance-lab
investigation branch:

- `investigations/7.3.0-functional/cases/android-shutdown/Main.java`
- `investigations/7.3.0-functional/tools/android_file_write_shutdown_build.py`
- `investigations/7.3.0-functional/evidence/I05/android-api30-shutdown-results.json`
- `investigations/7.3.0-functional/evidence/I05/android-api30-shutdown-events.log`

Runtime identity: official 7.3.0 artifact from Actions run `40878222908`,
SDK jar SHA-256 `23a0e5f16146414419c43f418d554f494d6acad362aa0e03ca11e11bfd430475`,
Android `libtcvm.so` SHA-256
`bf630c7bf8a7a33323631c3b59699157d621a4f4587aac77779931a2de2544ad`.

### Suggested investigation and acceptance

Capture the native stack and identify the mutex owner and teardown sequence.
Ensure shutdown coordinates with outstanding worker calls before destroying
VM-owned resources, or safely rejects calls after teardown begins. Add a
bounded regression test that covers active file I/O, SQLite work, active Java
workers, permission return, and repeated VM initialization/termination. The
same destroyed-mutex FORTIFY abort must not occur in ten bounded runs, and no
worker may access a native resource after its lifetime ends.

This proposed update is linked to the existing issue rather than opening a
duplicate. It is a review draft only; no remote issue was changed.
