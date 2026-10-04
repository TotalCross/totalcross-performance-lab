<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# Exact historical/current native backing draw comparison

Historical reference: `f5dad132cafea5c9086f6f946a6f44ca5bcb5f76`.
Current reference: `5a44f503bf6fa1bec350f1218f4d501a70fc4812`.
The blob IDs for all three inspected paths are in source-reference-blobs.json.
Inspect these versions with `git show <revision>:<path>` in the runtime repository.

Graphics.java copyRect (historical lines 1565 onward, current lines 1517 onward)
first looks up a cached final raster, then uses copyRectNative on the resolved
Image. The current generic smooth HANDLED branch interfered with reuse; the
previous causal runtime corrects that branch only under its isolated hook. That
routing and all current Graphics.java code are unchanged in this experiment.

GraphicsPrimitivesSkia_c.h drawSurface applies content/hardware scale, translation
and logical source/destination clipping. For NativeImageBacking it divides source
logical coordinates by scaleW/H, so the final physical358 raster is addressed in
physical units while destination179 coordinates are mapped by canvas scale2.
Historical lines 490–500 read optimizationMask and pass it as the final argument.
Current lines 496–505 pass only alphaMask. This experiment leaves call-site ABI
and geometry unchanged and supplies bit-2-equivalent enablement inside the callee
through the existing private native test metric bridge.

Historical skia_image_backing_draw_to_surface (lines 2094–2111) attempts
skia_image_backing_try_write_pixels before drawOnCanvas. tryWritePixels (828–943)
requires bit2 and calls buildWritePixelsDeviceCopyPlan (658–754). The planner's
predicates and arithmetic are restored verbatim, with only counter adaptation:
valid target/source; alpha255; bounded positive integer source; positive finite
axis canvas matrix with no skew/perspective; integer device destination; exact
source/device extent equality; intersect canvas device clip and actual target
pixel bounds; offset source by the same clipping amount. No identity-matrix or
full-source requirement is added. A scale2 logical draw is allowed only when its
device extent exactly matches the physical source.

Historical RGBA proveOpaqueForWritePixels (545–577) uses known opacity or scans
all source alpha bytes via snapshot/peekPixels, recording opaque/translucent.
The current NativeImageBackingRecord has no opacity field. For this experiment,
proofs are cached outside the record, keyed by handle and existing mutation
generation, and cleared at enablement. Event accounting reset retains valid
proofs. This changes neither backing representation/pixels nor cache validity.
Unknown RGBA opacity performs the same alpha-byte scan; a failed proof falls back.
The subset is obtained from snapshot/peekPixels/extractSubset and written at the
clipped integer device destination. Actual canvas.writePixels failure returns to
the unchanged drawOnCanvas implementation. Hits retain historical target alias
mutation notification. The screen has no backing alias; no final source mutation
is introduced. The normal switch-off path retains the existing drawOnCanvas behavior.

Only historical **RGBA** handling is enabled. The historical compact-format row
conversion branches are outside this default-only final-RGBA experiment; other
formats conservatively reject with unsupportedFormat and draw normally. No
representation conversion or expanded eligibility forces a hit. This limitation
is explicit and native-tested; capture verifies the actual measured source format.
No claim is made that all historical controls actually hit the original path.

Native accounting retains every attempted draw's source handle/format/dimensions,
opacity before/after proof, input physical source and logical destination, mapped
device destination, clipped source/device rectangle, matrix, rejection, hit,
bytes/clipping and attempt/write/fallback timings. The private switch defaults to
zero; isolated entry enables it only after startup, alongside the unchanged routing
and admission hooks. The actual runtime optimization mask/defaults never change.
