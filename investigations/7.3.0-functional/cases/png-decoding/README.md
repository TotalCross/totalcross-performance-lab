# PNG decoding case

Fixtures are copied from the historical master-only Linux run and verified by
SHA-256. Test `Image(File)` and `Image(byte[])`, TCZ loading, alpha and indexed
PNG fixtures, a positive JPEG control, and invalid input. Force pixel
materialization and assert dimensions, pixel count, selected pixel values,
and exception type. Record constructor success separately from decode success.

The imported result only covers the RGBA PNG and JPEG fixtures through file and
byte-array constructors. Its startup used a test-only realpath interposer, so
it does not demonstrate unmodified VM startup. See `../../reports/I02-linux-png.md`.

| Fixture | Format | Dimensions | SHA-256 |
| --- | --- | ---: | --- |
| `fixtures/comparison-png.png` | RGBA PNG, 8-bit | 36x36 | `958903b3f880fbf626fa8fbba8f69856a989f5930531984be9585aac08a5aba6` |
| `fixtures/comparison-control.jpg` | JPEG, 8-bit, 3 components | 512x512 | `df0035534c5c12d024763dce5f515023ad7e16139f4278b360291b2f0261fb51` |
