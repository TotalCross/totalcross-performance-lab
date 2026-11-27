# Proposed update for TotalCross issue #564

## Suggested update text

A fresh frozen-master Linux x86_64 run on Ubuntu 24.04/glibc 2.39 was blocked
by the same startup abort before the PNG probe: exit 134 in
`__realpath_chk → startVM → executeProgram → main`. With a test-only startup
shim (the VM binaries were unchanged), the PNG probe completed and decoded
the 136-byte RGBA fixture through both `Image(File)` and `Image(byte[])`;
TCZ/alpha PNG, JPEG file/bytes, and invalid-input controls also passed.

A valid 2×2, 8-bit indexed PNG with PLTE and tRNS was rejected by the image
constructor before pixel materialization. Its chunk CRCs validate and IDAT
inflates to the expected scanlines. The inspected frozen source parser appears
to accept indexed color type 3 with this palette/transparency structure, so
the exact rejection condition is still unknown. The run does not show that this
case reached libpng or zlib. Although `LD_DEBUG=bindings` records zlib symbols
from `libpng16.so.16` binding to `libtcvm.so`, this observation does not
establish that interposition caused the constructor rejection.

This separates the earlier RGBA ADLER32 failure from the current indexed-PNG
constructor rejection. The frozen-master result is conditional on the test-only
startup shim; the unmodified runtime still cannot reach image decoding.

Details, fixture hashes, exact binaries, and the complete case matrix are in:

- `investigations/7.3.0-functional/reports/I02-linux-png.md`
- `investigations/7.3.0-functional/evidence/linux-actions-45949849457.json`

This is a proposed update only; issue #564 was not edited.
