# PNG decoding case

Fixtures are copied from the historical master-only Linux run and verified by
SHA-256. Test `Image(File)` and `Image(byte[])`, TCZ loading, alpha and indexed
PNG fixtures, a positive JPEG control, and invalid input. Force pixel
materialization and assert dimensions, pixel count, alpha/transparency
properties, selected pixel relationships, and exception type. Record
constructor success separately from decode success and log the first pixel for
comparison.

The imported result only covers the RGBA PNG and JPEG fixtures through file and
byte-array constructors. Its startup used a test-only realpath interposer, so
it does not demonstrate unmodified VM startup. See `../../reports/I02-linux-png.md`.

| Fixture | Format | Dimensions | SHA-256 |
| --- | --- | ---: | --- |
| `fixtures/comparison-png.png` | RGBA PNG, 8-bit | 36x36 | `958903b3f880fbf626fa8fbba8f69856a989f5930531984be9585aac08a5aba6` |
| `fixtures/comparison-control.jpg` | JPEG, 8-bit, 3 components | 512x512 | `df0035534c5c12d024763dce5f515023ad7e16139f4278b360291b2f0261fb51` |
| `fixtures/alpha.png` | RGBA PNG, 8-bit alpha | 2x2 | `79938a708543f85c5c04bd15747a1c0314c7cbfca0ae0be09f69b4e4f5b6df3e` |
| `fixtures/indexed.png` | Indexed PNG with palette transparency | 2x2 | `0823539a40acde890b3a769c7c48490e5bf083da51c78898fdbea67c8119c10e` |
| `fixtures/tcz-png.png` | RGBA PNG resource used only through TCZ | 2x2 | `79938a708543f85c5c04bd15747a1c0314c7cbfca0ae0be09f69b4e4f5b6df3e` |
| `fixtures/invalid.bin` | Invalid image input | n/a | `71933a2f8897a278956c0cae49de3f2a1d9a2e7ea5b6f7daabc2f7e83a4e3131` |

Recreate the generated fixtures with
`python3 scripts/generate-functional-png-fixtures.py`. The PNG probe logs
construction, decode/materialization, dimensions, pixel count, first pixel,
and exception separately. Invalid input is a negative case and passes only
when image construction or materialization rejects it.
