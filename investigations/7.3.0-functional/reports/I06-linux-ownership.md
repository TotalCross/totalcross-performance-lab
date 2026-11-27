# I06 — Linux ownership comparison

## Result

**Conditional PASS for the ownership assertions.** The baseline and corrected
SDK probes completed all seven stages on Ubuntu 22.04 with the same frozen
Linux VM. The baseline recorded 6,046 ownership mismatches; corrected SDK
`94af2b8b653cad509994b5ccf3dbb60ac28ef920` recorded zero and passed each
ownership assertion.

The Linux VM aborts before normal application startup with
`*** buffer overflow detected ***` and exit 134. The ownership executions
therefore used the existing test-only `__realpath_chk` shim. This validates the
ownership behavior under that startup workaround; it does not validate normal
Linux startup. Both probes also reached the original 2x2 PNG draw fixture and
failed in the native decoder, so the Linux ownership comparison used the
bundled 8x8 red JPEG control. The independent PNG behavior remains tracked in
I02.

## Run and identities

- Actions run: [45989644203](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/45989644203)
- Job artifact: `15193167516`, SHA-256
  `d13ecea7447310f6f8af596e93d963940a4482dc57757213d7447290d4ffb849`
- Corrected source: `94af2b8b653cad509994b5ccf3dbb60ac28ef920`, tree
  `539f5b424b6f4593c7d96074d69ff077a38ed361`
- Baseline runtime source: `6b915883dd202f6db891990f6c3af26fb645ecc7`, tree
  `44047160610b7efcb3d49768736af95bde19f85f`
- Linux VM SHA-256:
  `99cd2a97e86c553460ddf982ece3951bb6e62056ac2b31494f6f6c82250453e4`
- Linux launcher SHA-256:
  `8819cd991679f12998d22e6e17cd898afd3f75d79e7085b89ca8c7d2d9894166`
- JPEG fixture SHA-256:
  `2f3259c72424d54b5ad1914b51e6671aae694e6c2bdb09e2c48de2214ae39ff6`

Both modes used two screens of 1,510 controls, verified detach/reattach,
reparenting, shared ownership, replacement, raster cache reuse/eviction, and
native rendering. The corrected render was `0xFE0000`; its image pixel was
red-dominant as expected for the JPEG control.

Machine-readable assertions and retained stage markers are in
[the Linux evidence record](../evidence/I06/linux-x86_64-45989644203.json) and
[marker log](../evidence/I06/linux-x86_64-45989644203-markers.log). The earlier
unmodified startup failure remains in
[the original Linux record](../evidence/I06/linux-x86_64-45978158503.json).
