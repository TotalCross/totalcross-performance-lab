# I02 — Linux PNG decoding

## Historical finding

A master-only Linux x86_64 run at source
`61034a7562e7fa43df076dcc38bcd48128605395` loaded a 136-byte RGBA PNG and a
512x512 JPEG. The test-only realpath interposer was enabled because the
unmodified startup path could abort; the production VM was unchanged. The PNG
constructors succeeded, but forcing pixel materialization failed for both
`Image(File)` and `Image(byte[])`. libpng reported an IDAT ADLER32 checksum
mismatch; the VM raised
`IllegalStateException: Could_not_materialize_encoded_image`. Both JPEG paths
decoded all 262144 pixels. The harness exited 0 to preserve its findings, but
its verdict is `overallPass=false`.

Run `45740940460`, job `139645497342`, result artifact `15080812232`, SHA-256
`7318fb350214299b1d503825d1554825c9718b06b086982a9ba88b195967d6c3`. The
artifact expires 2026-12-06. The exact fixture files and hashes are recorded in
`../cases/png-decoding/README.md`; the copied shim is under
`../cases/linux-startup/`.

The historical runtime used `libtcvm.so` SHA-256
`29af2de6c0cb8394259ff481f7aab271bb618436278b7475defd580018a77a2b` and
launcher SHA-256
`657093694da2a5ad9845dd91865639f2be39e6c7411946294e3c0f37aa194912`.

This is historical evidence from commit `61034...`, not frozen master
`6b915...`. The two source revisions differ in native VM code, including
file, SQLite, and image implementation files; the old VM binary cannot stand
in for a current-master build. It covers only the RGBA PNG, JPEG control, file and byte-array
constructors, and forced materialization. It does not cover TCZ PNG, alpha or
indexed variants, invalid input, exact decoder symbol bindings, or the current
master. Do not infer a zlib/libpng ABI cause from the checksum message alone.

## Required next run

Rebuild and execute the exact fixture against frozen master on hosted Linux
x86_64 first without an interposer. If startup prevents decoding, preserve that
as a separate I01-B result, then use the recorded shim only for a conditional
decoder investigation. Test file, byte-array, TCZ, alpha, indexed, JPEG, and
invalid inputs; force pixel access and compare dimensions and selected pixel
values. Inspect actual runtime decoder bindings only if the failure reproduces.

## Status

Historical source result: **FAIL (PNG materialization)** under conditional
startup shim. Frozen-master campaign and other required platforms: **NOT RUN**.
No production source was changed.
