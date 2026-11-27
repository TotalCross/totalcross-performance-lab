# I04/I05 — TotalCross 4.x legacy-port check

The highest available 4.x SDK tag in the product checkout is `v4.6.0`, tag
commit `a535fd8eec26f21385a2bff309ac6df91cb1490e` (2022-02-18). The findings
below use that exact release snapshot and the frozen 7.x source snapshot.

## I04 — `File.writeBytes`

Commit `e2c9f0795f213d780efe0ea78e958d7f55c13721` (2017-08-04), included in
4.6.0, introduced `File.CLOSED`, transitioned successfully closed objects to
that state, and added `INVALID || CLOSED` guards to Java and native file
operations including `writeBytes`. The same mode guards are present in frozen
7.x. The POSIX `fileWriteBytes` helper in 4.6.0 calls `fwrite(...,
fref.handle)` without independently validating the `FILE*`; the frozen 7.x
helper has the same boundary. The legacy guard therefore covers use after
close and invalid open state, but does not cover a live-mode object whose
underlying native handle is null or stale. No exact 4.x correction for that
reported failure shape was found. **I04 remains in scope** and should focus on
establishing whether the failing object state is invalid/closed or live with a
bad native handle.

## I05 — shutdown mutex lifetime

In 4.6.0, Android `Loader.quitVM()` calls `Launcher4A.stopVM()`, waits in a
sleep loop while `canQuit` is false, then closes TCZ resources and kills the
process. `stopVM()` reads `eventThread.running` and posts shutdown work. This
release has no idempotent shutdown guard, bounded acknowledgment, or explicit
ownership protocol that would establish the destroyed-mutex fix described by
I05. A later 2026 change, `d2d63370e21d5b23f0d4490806c0f66b0a454f1e`, adds
bounded asynchronous shutdown acknowledgment and idempotence, but it is not a
4.x release and its stated purpose is nonblocking shutdown; it does not by
itself prove the reported native mutex lifetime is fixed. **I05 remains in
scope.**

## Scope decision

Neither investigation is excluded by a verified 4.x-to-7.x port. I04's
closed/invalid state guard is already present in 7.x but is narrower than the
reported underlying-handle failure. I05 lacks a matching 4.6.0 correction.
Both remain `NOT_RUN` pending the authorized local ARM64 emulator campaign.
