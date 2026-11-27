# I01-B — Linux realpath startup abort

## Historical finding

The Linux x86_64 job in performance-lab PR #4's 7.3.0-package run failed
before its SQLite probe. The process log records `*** buffer overflow
detected ***`, `Aborted`, and exit 134. The GDB stack reaches glibc
`__realpath_chk` from `startVM()` in `libtcvm.so`. The host was an Azure Linux
runner with glibc 2.39. See the sanitized excerpts in `../evidence/I01-B/`.

The tested package artifact came from TotalCross source
`5464c21e3107e3f1ce9c287b724829e2bb870c1d`; it is not a GitHub 7.3.0 release
and is not frozen master. Run `41888918200`, job `126780740748`, artifact
`13353195526` (`sqlite-plaintext-7.3.0-linux-x64`), artifact SHA-256
`92c614f33549cf740a80b4c3d2ba94a57774ca3a1de7e80bb2ea2418f1843d3f`.
The artifact is retained through 2026-12-04.

The upstream package artifact for that source revision is run `40878222908`,
artifact `12899147776`, wrapper SHA-256
`a966f79d9193c7ee5757cfd66d17d73fbd73a478f7debe9394d898c413f044d5`.
Its nested TotalCross ZIP SHA-256 is
`c9552cb95e1a09798637ad74266f91b62c6ea0ddc3d8dafa8402ac987f70288e`.
The packaged SDK jar SHA-256 is
`23a0e5f16146414419c43f418d554f494d6acad362aa0e03ca11e11bfd430475`; the
Linux `libtcvm.so` SHA-256 is
`94e823963427a67decdb2aaeb99722e297e375a7d772b438ef85cae1449160fb`.
This matches the VM hash recorded in the failing deployment artifact.

This confirms the historical startup failure for that package/runtime pair;
it does not establish the exact path-length trigger or current-master behavior.
The code path uses `realpath(path, resolved)` from `startup_c.h`; Linux's
`MAX_PATHNAME` is 1024. A test-only `__realpath_chk` shim was used in a
separate PNG run and must remain classified as conditional evidence.

## Required next run

Run official 7.2.2, the archived 7.3.0 package, and frozen master
`6b915883dd202f6db891990f6c3af26fb645ecc7` on hosted Linux x86_64. Exercise
normal, short, long, and symlink paths without a shim first. Preserve shell,
startup, and application markers separately and report the process exit code,
not only a wrapper or GDB status. Capture runner image, glibc, compiler flags,
and `_FORTIFY_SOURCE` configuration. Only then run the conditional shim case.

## Status

Historical package result: **FAIL (startup)**. Frozen-master and release-pair
campaign cases: **NOT RUN**. No production source was changed.
