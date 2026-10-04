<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# P12 read-only physical mapping capture — 2026-10-03

Exactly one native application process ran from benchmark commit
`564ce7c1bbda2b4995108683696d954631be04ca`, using the default-only official
TotalCross 7.2.2 package, runtime source `5a44f503bf6fa1bec350f1218f4d501a70fc4812`.
The native child exited **0** (the runner rejects any nonzero child return code);
the runner exited **0**, with one complete schema-valid measured record and no
failures. One inline preflight record was emitted by that same process; no
separate preflight/warmup/replacement process ran. There were zero preparation
requests and zero timed paint samples. One untimed stabilization repaint
preceded eighteen read-only metadata captures.

The complete validated record, provenance, process count/exit status and original
artifact paths/hashes are preserved in
[evidence JSON](evidence/p12-physical-mapping-probe-2026-10-03.json).
The original logs are under
`.local-data/results/image-rendering-physical-mapping-readonly-probe/run-20261003T054657Z-90240/processes/0001-default-measured-1/`.
Stdout includes an initialization `IOException: Error Code: 30 - Read-only file
system` warning from UI resource setup; it did not prevent the inline preflight,
complete result or successful exit. Stderr is empty. No recovery or second launch
was needed. TotalCross runtime/SDK source and cache-admission policy are unchanged.

## Actual axes and common per-control metadata

Logical application dimensions are **540×960**, the logical viewport is **540×910**,
and drawable dimensions are **1080×1920**. Display scale and every captured
Graphics content scale are **2**. Public Graphics translation and clip vary as
listed below. The source-derived native canvas scale is `(2,2)`, because
`skia_setSurfaceScale` resets the matrix and applies that captured Graphics scale.
This canvas reconstruction and the gate/rectangle calculations are offline
source-derived evaluations of runtime metadata, not newly instrumented native
matrix/gate measurements.

All eighteen controls share these captured fields (the JSON lists every field):

- Operation count `1`, operations `[1]` (`SMOOTH_SCALE`), parameters
  `[179,179,0,0]`, draw-plan dimensions `[179,179]`.
- Output `179×179`; root content scale `0.5`; root hardware scales `(1,1)`;
  presentation hardware scales `(1,1)`; destination/output content scales `2`.
- Native backing type `totalcross.ui.image.NativeImageBacking`, valid and stable;
  backing mutation generation **1**; opacity state `1`.
- Raw Image generation `null`, availability `false`. No value is inferred from
  the backing generation. `inspectionObservableStateUnchanged=true` observes
  only backing reference identity and its pure generation getter.
- Alpha, materialize alpha and output alpha masks `255`; root frame count `1`,
  current frame `-1`, root width of all frames `0`.
- Draw origin `(0,0)`; clip origin `(0,0)` and clip width `179`.
- Compiled `b=c=tx=ty=0`, output transform width/height `179`, smooth `true`,
  fill `false`. Compiled `a=d` varies as shown below.

## Per-control dimensions, transform and prior cost

Dimensions are width×height. Physical root equals backing for each control;
logical root equals intrinsic dimensions. Prior cost is ImageControl.onPaint from
the already completed draw-path probe, not a new timing measurement. Ratios are
mapped physical source pixels per device pixel in X and Y; equal X/Y ratios also
hold for the clipped bottom row.

| Index | Dataset path | Intrinsic / root logical | Root physical / backing | Output | a = d | Source/device ratio X = Y | Prior ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | `-1009782731.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 19.064541 |
| 1 | `-1012043485.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 18.837666 |
| 2 | `-1013143947.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 19.397667 |
| 3 | `-1015024107.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 19.502584 |
| 4 | `-1026010547.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 19.523792 |
| 5 | `-1028874041.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 18.890167 |
| 6 | `-1038926037.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 18.781209 |
| 7 | `-104018500.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 18.937167 |
| 8 | `-1040544427.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 18.593458 |
| 9 | `-1042033183.jpg` | 1024×1024 | 512×512 | 179×179 | 2.8603351955307263 | 1.4301675977653632 | 18.601375 |
| 10 | `-1042180667.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 18.546708 |
| 11 | `-1043960095.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 18.679500 |
| 12 | `-1056468936.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 18.593916 |
| 13 | `-1059601584.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 19.303000 |
| 14 | `-108958495.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 19.365750 |
| 15 | `-1096038007.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 0.453125 |
| 16 | `-111131558.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 0.397250 |
| 17 | `-1111384947.jpg` | 1000×1000 | 500×500 | 179×179 | 2.793296089385475 | 1.3966480446927374 | 0.389292 |

## Per-control translation, clipping and rectangles

Rectangles use `[left,top,right,bottom]` (right/bottom exclusive). Graphics clip
is relative `[x,y,width,height]`; translation is `[x,y]`. Source and destination
are the clipped normal copyRect logical rectangles. Mapped source is in physical
backing coordinates; device destination uses native float conversion and the
captured scale. Smooth and strict evaluations produce the same rectangles.

| Index | Graphics translation | Clip | Visible source | Logical destination | Mapped physical source | Device destination |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | [1, 42] | [0, 0, 179, 179] | [0, 0, 179, 179] | [1, 42, 180, 221] | [0.0, 0.0, 500.0, 500.0] | [2.0, 84.0, 360.0, 442.0] |
| 1 | [181, 42] | [0, 0, 179, 179] | [0, 0, 179, 179] | [181, 42, 360, 221] | [0.0, 0.0, 500.0, 500.0] | [362.0, 84.0, 720.0, 442.0] |
| 2 | [361, 42] | [0, 0, 179, 179] | [0, 0, 179, 179] | [361, 42, 540, 221] | [0.0, 0.0, 500.0, 500.0] | [722.0, 84.0, 1080.0, 442.0] |
| 3 | [1, 223] | [0, 0, 179, 179] | [0, 0, 179, 179] | [1, 223, 180, 402] | [0.0, 0.0, 500.0, 500.0] | [2.0, 446.0, 360.0, 804.0] |
| 4 | [181, 223] | [0, 0, 179, 179] | [0, 0, 179, 179] | [181, 223, 360, 402] | [0.0, 0.0, 500.0, 500.0] | [362.0, 446.0, 720.0, 804.0] |
| 5 | [361, 223] | [0, 0, 179, 179] | [0, 0, 179, 179] | [361, 223, 540, 402] | [0.0, 0.0, 500.0, 500.0] | [722.0, 446.0, 1080.0, 804.0] |
| 6 | [1, 404] | [0, 0, 179, 179] | [0, 0, 179, 179] | [1, 404, 180, 583] | [0.0, 0.0, 500.0, 500.0] | [2.0, 808.0, 360.0, 1166.0] |
| 7 | [181, 404] | [0, 0, 179, 179] | [0, 0, 179, 179] | [181, 404, 360, 583] | [0.0, 0.0, 500.0, 500.0] | [362.0, 808.0, 720.0, 1166.0] |
| 8 | [361, 404] | [0, 0, 179, 179] | [0, 0, 179, 179] | [361, 404, 540, 583] | [0.0, 0.0, 500.0, 500.0] | [722.0, 808.0, 1080.0, 1166.0] |
| 9 | [1, 585] | [0, 0, 179, 179] | [0, 0, 179, 179] | [1, 585, 180, 764] | [0.0, 0.0, 512.0, 512.0] | [2.0, 1170.0, 360.0, 1528.0] |
| 10 | [181, 585] | [0, 0, 179, 179] | [0, 0, 179, 179] | [181, 585, 360, 764] | [0.0, 0.0, 500.0, 500.0] | [362.0, 1170.0, 720.0, 1528.0] |
| 11 | [361, 585] | [0, 0, 179, 179] | [0, 0, 179, 179] | [361, 585, 540, 764] | [0.0, 0.0, 500.0, 500.0] | [722.0, 1170.0, 1080.0, 1528.0] |
| 12 | [1, 766] | [0, 0, 179, 179] | [0, 0, 179, 179] | [1, 766, 180, 945] | [0.0, 0.0, 500.0, 500.0] | [2.0, 1532.0, 360.0, 1890.0] |
| 13 | [181, 766] | [0, 0, 179, 179] | [0, 0, 179, 179] | [181, 766, 360, 945] | [0.0, 0.0, 500.0, 500.0] | [362.0, 1532.0, 720.0, 1890.0] |
| 14 | [361, 766] | [0, 0, 179, 179] | [0, 0, 179, 179] | [361, 766, 540, 945] | [0.0, 0.0, 500.0, 500.0] | [722.0, 1532.0, 1080.0, 1890.0] |
| 15 | [1, 947] | [0, 0, 179, 3] | [0, 0, 179, 3] | [1, 947, 180, 950] | [0.0, 0.0, 500.0, 8.379888268156424] | [2.0, 1894.0, 360.0, 1900.0] |
| 16 | [181, 947] | [0, 0, 179, 3] | [0, 0, 179, 3] | [181, 947, 360, 950] | [0.0, 0.0, 500.0, 8.379888268156424] | [362.0, 1894.0, 720.0, 1900.0] |
| 17 | [361, 947] | [0, 0, 179, 3] | [0, 0, 179, 3] | [361, 947, 540, 950] | [0.0, 0.0, 500.0, 8.379888268156424] | [722.0, 1894.0, 1080.0, 1900.0] |

## Eighteen-control gate table

`T` = true, `F` = false, `?` = unknown. Columns follow native gate order.
G5 gives `smooth/strict` results; every other gate has the same pass value for
both modes. G1 stability; G2 generation equality; G3 geometry compilation;
G4 no fill; G5 smooth eligibility; G6 positive axis transform; G7 integer
translation; G8 positive axis canvas; G9 a=canvas X; G10 d=canvas Y; G11 source
bounds; G12 source integrality; G13 device destination integrality;
G14/G15 width/height extent equality.

| Index | G1 | G2 | G3 | G4 | G5 smooth/strict | G6 | G7 | G8 | G9 | G10 | G11 | G12 | G13 | G14 | G15 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 1 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 2 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 3 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 4 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 5 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 6 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 7 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 8 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 9 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 10 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 11 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 12 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 13 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 14 | T | ? | T | T | T/F | T | T | T | F | F | T | T | T | F | F |
| 15 | T | ? | T | T | T/F | T | T | T | F | F | T | F | T | F | F |
| 16 | T | ? | T | T | T/F | T | T | T | F | F | T | F | T | F | F |
| 17 | T | ? | T | T | T/F | T | T | T | F | F | T | F | T | F | F |

The actual ordered reach state is preserved separately from counterfactual pass
values. For every smooth evaluation, G1/G2 `reached=true`, G3–G9
`reached=null`, and G10–G15 `reached=false`. For every strict evaluation,
G1/G2 `reached=true`, G3–G5 `reached=null`, G6–G15 `reached=false`.
For **every** control in both modes: `firstFailingGate=null`,
`firstFailingGateName=null`, `unresolvedEarlierGates=[2]`, `allGatesPass=false`.
The earliest known failing gate is G9 `aEqualsCanvasScaleX` for smooth and
G5 `smoothEligible` for strict. No definitive first native failure is claimed
across unresolved generation equality.

## Gate distributions

Counts are true / false / unknown over eighteen controls. Later predicates are
computed independently where their inputs are available.

| Gate | Smooth T/F/? | Strict T/F/? |
| --- | --- | --- |
| 1. sourceBackingStable | 18/0/0 | 18/0/0 |
| 2. mutationGenerationsEqual | 0/0/18 | 0/0/18 |
| 3. compileGeometry | 18/0/0 | 18/0/0 |
| 4. noFill | 18/0/0 | 18/0/0 |
| 5. smoothEligible | 18/0/0 | 0/18/0 |
| 6. positiveAxisTransform | 18/0/0 | 18/0/0 |
| 7. integerTranslation | 18/0/0 | 18/0/0 |
| 8. positiveAxisCanvas | 18/0/0 | 18/0/0 |
| 9. aEqualsCanvasScaleX | 0/18/0 | 0/18/0 |
| 10. dEqualsCanvasScaleY | 0/18/0 | 0/18/0 |
| 11. sourceBoundsValid | 18/0/0 | 18/0/0 |
| 12. integerSourceCoordinates | 15/3/0 | 15/3/0 |
| 13. integerDeviceDestination | 18/0/0 | 18/0/0 |
| 14. equalDeviceSourceWidth | 0/18/0 | 0/18/0 |
| 15. equalDeviceSourceHeight | 0/18/0 | 0/18/0 |

## Scale-equality hypothesis and comparison with previous draw-path evidence

Both `aEqualsCanvasScaleX` and `dEqualsCanvasScaleY` are false for all eighteen
controls: seventeen have `a=d=500/179=2.793296089385475`, and index 9 has
`a=d=512/179=2.8603351955307263`, versus canvas scale 2.
**Scale equality is a demonstrated sufficient rejection condition for each
control (indices 0–17)** under the source-derived native predicate evaluation.
No control refutes the scale-equality hypothesis. This establishes a sufficient
later rejection, not the earliest native rejection: the raw Image generation
remains unavailable and G2 unresolved. Strict identity also independently rejects
smooth operations at G5. Width and height extent equality fail for all eighteen.
The three clipped controls additionally have noninteger mapped source bottoms
(`8.379888268156424`), so their source-integrality predicate is false.

The prior draw-path probe reported status `217099` / `0x3500b` for every control:
identity attempted/fallback, no physical-copy hit, generic geometry and smooth
resampling. The new metadata is consistent with that common fallback path.
It does not measure new timing/counters or resolve the raw generation predicate.

## Three fast controls versus fifteen slower controls

The fast paths are indices 15–17: `-1096038007.jpg`, `-111131558.jpg`,
`-1111384947.jpg`. Their prior ImageControl costs were
0.453125, 0.397250, 0.389292 ms; the other fifteen ranged
18.546708–19.523792 ms (median 18.890167 ms).

Root/backing dimensions and transform/resampling ratios do **not** separate the
groups: the fast controls have intrinsic/logical roots 1000×1000 and physical
roots/backings 500×500, exactly like fourteen slower controls. All share root
content scale 0.5, hardware scales 1, output 179×179 and canvas scale 2; index 9
alone is 1024×1024 / 512×512. For the shared 500-root case,
source/device ratios are 1.3966480446927374 in both axes (device/source 0.716), including
the clipped controls. All eighteen follow the same smooth-scale operation.

**Clipping and visible area cleanly separate these observed groups.** The slow
controls translate to Y=42,223,404,585,766 with clip/source height 179; the fast
controls translate to Y=947 with clip/source height 3. The viewport ends at
Y=950. Their logical visible areas are 179×179=32,041 versus 179×3=537,
and their device areas are 358×358=128,164 versus 358×6=2,148: a
59.666666666666664× reduction in each area. For the shared 500-root geometry, the mapped
source rectangles are `[0,0,500,500]` versus `[0,0,500,8.379888268156424]`,
physical source areas 250,000 versus 4189.944134078212.
The slow 512-root outlier has mapped area 262,144 but the same full device area.
All X translations occur in both groups, so horizontal placement does not separate
them. The destination Y/bottom clipping and source height/area do.

The prior median timing ratio is 47.552340×,
compared with the 59.666667× visible-area ratio. This is a strong geometric
correlation consistent with reduced visible smooth-resampling work. Because the
measurements come from separate focused probes and no controlled timing experiment
was authorized, it does not prove causal attribution or exact area-proportional
cost. No generation value, production fix or cache-admission decision follows
from this result. No additional process, P12 matrix, cache experiment or platform
validation was run.

## Subsequent authorization audit

A later request named the same package-manifest and results-directory paths. The
matching run was already present, with one accepted native child, one complete
schema-valid result and no failures. Its package manifest SHA-256 is
`30389cd399119d9e6c2dc321663a887f506b95ea3c2fe2538b6d15146aee3d9c`; its saved
run-record SHA-256 is
`e0914e2d6fae01bf2d2abe0e5bae0ba018c3ab195b9c1ef61a48d0147177d570`. Because
the request also required no earlier attempt for that package/result pair and
prohibited a second process, no additional application process was launched.
The existing record was revalidated offline against package provenance, dataset
identity, schemas, inline preflight and all eighteen physical-mapping
evaluations. This audit adds no runtime measurement.
