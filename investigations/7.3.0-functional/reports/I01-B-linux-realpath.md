# I01-B — Linux `realpath` startup abort

## Result

**FAIL on the official 7.3.0 package and frozen master; root cause remains
open.** All four path forms aborted before the application startup marker on
both revisions, including 60- and 68-byte short paths. Resolved path length
alone does not explain the failure. The official 7.2.2 package could not serve
as a valid control for three path forms because its `libtcvm.so` failed dynamic
symbol loading; its separate 1,260-byte path run hit a launcher copy bound.

The hosted workflow and artifact capture succeeded. These are functional test
failures, not a green runtime result. All captured cases were bounded and none
timed out.

## Path matrix

| Revision | Normal | Short | Long | Symlink |
| --- | --- | --- | --- | --- |
| Official 7.2.2 | 85 bytes: blocked, exit 16 (`glCompressedTexSubImage2D` undefined) | 60 bytes: same loader failure, exit 16 | 1,260 bytes: exit 134 in `__stpcpy_chk`, destination capacity 512 | 91 bytes: same loader failure, exit 16 |
| Official 7.3.0 | 85 bytes: `__realpath_chk`, exit 134 | 60 bytes: same stack, exit 134 | 1,260 bytes: same stack, exit 134 | 91 bytes: same stack, exit 134 |
| Frozen master | 93 bytes: `__realpath_chk`, exit 134 | 68 bytes: same stack, exit 134 | 1,268 bytes: same stack, exit 134 | 99 bytes: same stack, exit 134 |

Every 7.3.0 and frozen-master case recorded `*** buffer overflow detected
***`, `Aborted`, no application marker, and a GDB stack
`__realpath_chk → startVM → executeProgram → main`. These findings match the
previous report that the 7.3.0 package aborts before its SQLite probe, while
now also demonstrating the same startup failure in frozen master.

## Source and failure boundary

At frozen master commit
`6b915883dd202f6db891990f6c3af26fb645ecc7`,
[`startup_c.h`](https://github.com/TotalCross/totalcross/blob/6b915883dd202f6db891990f6c3af26fb645ecc7/TotalCrossVM/src/init/posix/startup_c.h#L36-L50)
defines `copyResolvedPath()`, allocates `char resolved[MAX_PATHNAME]`, then
calls `realpath(path, resolved)`. [`xtypes.h`](https://github.com/TotalCross/totalcross/blob/6b915883dd202f6db891990f6c3af26fb645ecc7/TotalCrossVM/src/util/xtypes.h#L318-L325)
sets Linux `MAX_PATHNAME` to 1,024 bytes. The observed glibc entry point is
`__realpath_chk`, but GDB optimized its `resolvedlen` argument out. The
result artifact does not preserve the compiled `_FORTIFY_SOURCE` value or
complete compiler flags, so the exact fortified size check has not been
confirmed as the root cause.

The 7.2.2 long-path failure is separate: GDB shows
`__stpcpy_chk(destlen=512) → main` for the 1,260-byte path, before a `startVM`
frame. The other 7.2.2 cases never reached TotalCross startup because the host
loader reported `./libtcvm.so: undefined symbol: glCompressedTexSubImage2D`.
Neither result should be conflated with the 7.3.0/frozen-master `realpath`
stack.

## Build and artifact provenance

The comparison ran in hosted Actions run
[45949849457](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/45949849457),
on Ubuntu 24.04 with glibc 2.39. Frozen master was built from the exact commit
above in `totalcross/linux-amd64:v1.0.7`, Release, with depot-tools pinned to
`0fd3c98727c87a441bc9c8d2c8dd2b731ef0861a`. The uploaded build bundle was
downloaded before expiry; its ZIP digest and the `Launcher`/`libtcvm.so`
hashes match the recorded build identity. The runtime is ELF64 x86-64.

The archived 7.3.0 package is from source
`5464c21e3107e3f1ce9c287b724829e2bb870c1d`; official 7.2.2 and 7.3.0 package,
SDK, launcher, and VM identities are indexed with the path observations in
[the Linux Actions evidence record](../evidence/linux-actions-45949849457.json).
The same record contains the host, toolchain, dependency release tags, exact
result-artifact digest, and compact stack excerpts. The pinned native build used
libpng `1.6.48-r3` and zlib-ng `2.1.6-r3`.

## Status and next diagnostic

The startup abort is present in both the tested 7.3.0 package and frozen master;
this run does not establish a new regression or prove a root cause. Next work
should preserve the exact frozen source and runner configuration and capture
the fortified call's resolved-buffer size and effective compile flags. No
production source was changed. The Windows I386 correction remains a separate
PASS; no AMD64 runtime test or analysis is part of this investigation.
