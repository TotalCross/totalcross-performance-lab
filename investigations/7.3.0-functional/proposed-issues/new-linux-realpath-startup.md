# Proposed TotalCross issue: Linux startup abort in `realpath`

## Suggested title

Linux 7.3.0 aborts in `__realpath_chk` before application startup

## Report text

On Ubuntu 24.04 with glibc 2.39, the official TotalCross 7.3.0 Linux x86_64
package and a Release build from frozen master commit
`6b915883dd202f6db891990f6c3af26fb645ecc7` abort before the application's
first startup marker. Normal, short, and symlink install paths all terminate
with exit 134 and `*** buffer overflow detected ***`; GDB captures
`__realpath_chk → startVM → executeProgram → main`. The long-path cases also
terminate before startup, with a separate launcher `__stpcpy_chk` stack and a
512-byte destination. None of these cases timed out.

Short paths fail too, so path length alone does not explain the 7.3.0/frozen
master failure. Source inspection finds a 1,024-byte `resolved` buffer passed
to `realpath`, but GDB optimized out `resolvedlen`, and the artifact did not
record `_FORTIFY_SOURCE` or complete compiler flags. The exact fortified bounds
check and root cause remain unconfirmed.

The official 7.2.2 package is not a usable realpath control in this setup: its
normal, short, and symlink cases stop in dynamic loading on undefined symbol
`glCompressedTexSubImage2D`; its long path separately fails in launcher code.

Reproduction matrix, exact artifact hashes, source references, logs, and
limitations are recorded in:

- `investigations/7.3.0-functional/reports/I01-B-linux-realpath.md`
- `investigations/7.3.0-functional/evidence/linux-actions-45949849457.json`

Recommended diagnostic: preserve the effective compiler flags and inspect the
fortified `realpath` call arguments and destination-size computation in a
debuggable build. Validate any correction with the same short, normal, long,
and symlink cases before startup.

This is a proposal only; no remote issue was created or edited.
