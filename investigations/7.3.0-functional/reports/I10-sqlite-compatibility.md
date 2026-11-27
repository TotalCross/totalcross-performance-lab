<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# I10 — SQLite compatibility

## Result

**INCOMPLETE, with no functional failures in the executed cases.** Windows
Win32/I386 passed all 24 cases. Android ARM64 API 36 passed all 21 cases.
Linux x86_64 and macOS ARM64 passed every available 7.3.0 and candidate case.
The Linux 7.2.2 runtime failed before SQLite because `libtcvm.so` could not
resolve `glCompressedTexSubImage2D`; the published 7.2.2 SDK package contains
no macOS launcher or VM. These two platform gaps prevent a complete matrix.

The exact customer database was not supplied. This investigation used
synthetic plaintext fixtures and does not establish compatibility with that
specific database or reproduce its reported error.

## Coverage

| Target | Result | Cases | Limitation |
| --- | --- | ---: | --- |
| Windows Win32/I386 | PASS | 24 passed | Input and deployed launcher/VM binaries were verified as I386. |
| Linux x86_64 | INCOMPLETE | 15 passed, 7 blocked | Every blocked case used 7.2.2 and stopped at the unresolved OpenGL symbol before SQLite. |
| macOS ARM64 | INCOMPLETE | 15 passed, 1 unavailable | Official 7.2.2 runtime files are absent from its published SDK package. |
| Android ARM64, API 36 | PASS | 21 passed | Local hardware-accelerated emulator on an Apple M1 Pro host. |

The desktop matrix ran in [Actions run 46022844152](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/46022844152).
Linux used the previously recorded test-only startup shim. Android ran locally
on `emulator-5556`, Android 16/API 36, ABI `arm64-v8a`, with the Apple M1 Pro
OpenGL ES 3.0 host renderer. No Android Actions, Windows AMD64, iOS, or
physical-device execution was used.

## Fixtures and checks

The Windows I386 job created the runtime fixtures and a host-Python SQLite
3.45.1 external fixture. Its manifest records database and WAL hashes,
logical rows, user version, and integrity results. TotalCross 7.2.2, 7.3.0,
and candidate 94af each reported SQLite 3.32.3 in the runtime markers.

Each available revision read the external SQLite database, the WAL snapshot,
and databases produced by the other available revisions. The WAL snapshot
included its uncheckpointed `wal-committed-marker`; all executed
`integrity_check` calls returned `ok`.

For update persistence, the Windows flow started with the 7.2.2 database;
Linux, macOS, and Android started with 7.3.0 because 7.2.2 could not run or
was unavailable there. The candidate and official 7.3.0 then updated the same
database in sequence. The final database retained its origin, incremented the
first record amount to 12, and recorded both upgrade revisions.

The negative control now opens a directory as the database path. Older
runtime behavior accepted arbitrary bytes as an empty database, so that input
was not a reliable malformed-file control. The directory control was rejected
on every executed revision. It verifies path/open failure; malformed regular
SQLite-file behavior remains untested.

## Evidence and provenance

The machine-readable summary, fixture manifest, per-target results, SDK hashes,
APK hashes, Actions artifact digests, and local emulator details are in
[`evidence/I10/index.json`](../evidence/I10/index.json). The complete results
are retained in the adjacent per-target JSON files. Candidate source is
`94af2b8b653cad509994b5ccf3dbb60ac28ef920`; the I10 workflow code was at
`b0a9639fefd45751cc35ec635252f48e7874d70f` for the recorded desktop run.
