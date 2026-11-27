# I02 — Linux PNG decoding

## Result

**Conditional frozen-master result: FAIL, 8 of 9 expected cases.** The
unmodified frozen-master run aborted in Linux startup with exit 134 before the
PNG probe marker, so it executed no decoder cases. With the preserved
test-only `realpath` shim, the probe completed with exit 0 and wrote its
completion marker, but a valid indexed PNG was rejected during construction.
The original 136-byte RGBA PNG decoded successfully through both
`Image(File)` and `Image(byte[])` in this conditional run.

The shim changes only the test process environment; the production VM binary
is unchanged. Keep the shimmed decoder result separate from unmodified runtime
behavior. The workflow's green conclusion means it captured the findings; it
does not mean the decoder suite passed.

## Case results

| Case | Result | Observation |
| --- | --- | --- |
| RGBA PNG, `Image(File)` | PASS with shim | 36×36; all 1,296 pixels materialized |
| RGBA PNG, `Image(byte[])` | PASS with shim | 36×36; all 1,296 pixels materialized |
| TCZ PNG | PASS with shim | 2×2; first pixel `0x80ff0000` |
| Alpha PNG | PASS with shim | 2×2; alpha retained |
| Indexed PNG with palette transparency | **FAIL with shim** | Constructor rejected it with `ImageException: Invalid or unsupported encoded image`; no pixel decode occurred |
| JPEG, `Image(File)` and `Image(byte[])` | PASS with shim | Both decoded 512×512 and 262,144 pixels |
| Invalid file and byte-array input | PASS with shim | Both rejected as expected |

The 136-byte RGBA fixture SHA-256 is
`958903b3f880fbf626fa8fbba8f69856a989f5930531984be9585aac08a5aba6`.
The indexed 2×2 fixture SHA-256 is
`0823539a40acde890b3a769c7c48490e5bf083da51c78898fdbea67c8119c10e`. The
fixtures and all nine captured output lines are retained in the test case and
[the shared Linux Actions evidence record](../evidence/linux-actions-45949849457.json).

## Indexed-PNG rejection boundary

The runtime reports the exception from the constructor path before pixel
materialization. At frozen source
`6b915883dd202f6db891990f6c3af26fb645ecc7`,
[`image_Image.c`](https://github.com/TotalCross/totalcross/blob/6b915883dd202f6db891990f6c3af26fb645ecc7/TotalCrossVM/src/nm/ui/image_Image.c#L71-L86)
throws this message when `imageEncodedBagInspect()` returns false.
[`ImageEncodedBag.c`](https://github.com/TotalCross/totalcross/blob/6b915883dd202f6db891990f6c3af26fb645ecc7/TotalCrossVM/src/nm/ui/image/ImageEncodedBag.c#L91-L163)
contains the PNG structural inspector and explicitly accepts indexed color
type 3 at bit depths 1, 2, 4, and 8, subject to palette and transparency
bounds.

The retained fixture is 2×2, 8-bit indexed color type 3 with three palette
entries and three transparency values. All IHDR, PLTE, tRNS, IDAT, and IEND
chunk CRCs validate, and the 14-byte IDAT inflates to the expected six scanline
bytes. This creates an unresolved source/runtime discrepancy: the captured VM
rejects this structurally valid fixture even though the inspected source's
format checks appear to accept its structure. The precise rejecting condition
has not been identified. The captured run does not show that the indexed case
reached libpng or zlib.

## Runtime bindings and prior report

`LD_DEBUG=bindings` records `/lib/x86_64-linux-gnu/libpng16.so.16` loaded in the
conditional process. Its zlib symbol requests, including `inflate`,
`inflateReset2`, `crc32`, `adler32`, `deflate`, and related reset/init/end
symbols, resolve to `./libtcvm.so`. This is an observed binding relationship,
not proof that symbol interposition caused the indexed constructor rejection;
the indexed case is rejected before decode/materialization.

Existing issue [#564](https://github.com/TotalCross/totalcross/issues/564)
records an earlier master-only ADLER32 failure for the same 136-byte RGBA
fixture at source `61034a7562e7fa43df076dcc38bcd48128605395`. In this frozen
master conditional-shim run, both RGBA constructors decode successfully. The
unmodified attempt still cannot reach PNG decoding because of I01-B startup.
The results therefore separate the earlier materialization failure from the
current indexed-format rejection and do not establish an ABI cause for either.

## Build and scope

This run used the exact frozen-master source and SDK/VM pair recorded in the
shared evidence JSON, built with the pinned Linux container and native
dependencies. The native runtime binary hashes and build bundle digest were
verified. Other platforms remain `NOT_RUN`; indexed PNG was exercised through
`Image(File)` only, while the RGBA PNG covered both file and byte-array paths.
No production source was changed. A proposed update to issue #564 is retained
without editing the remote issue.
