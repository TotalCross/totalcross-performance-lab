# iOS 7.3.0 native graphics diagnostics

## Objective

Find why a physical iPhone displays a black viewport with TotalCross 7.3.0
even though the Java graphics smoke logs `canvas-painted-initial=PASS`.

The working 7.2.2 control (August 24, 2026) rendered all four colored panels
and processed a button tap. The earlier 7.3.0 experiment that removed the
safe-area `root_view` failed with a 99.87% dark screenshot; see
[PR 540](https://github.com/TotalCross/totalcross/pull/540). This experiment
uses **the original 7.3.0 root-view hierarchy** and adds only logging.

## Version and provenance

- Original 7.3.0 baseline: `5464c21e3107e3f1ce9c287b724829e2bb870c1d`
- Instrumented native source: `d1fa0fa4b9186cce4bc1d1f4bdf91872713a3954`
- Native SDK package CI: [run 43306936627](https://github.com/TotalCross/totalcross/actions/runs/43306936627)
- Java test: `tests/ios-graphics/src/totalcross/lab/graphics/GraphicsSmokeProbe.java` (unchanged)
- Appium color / touch assertions: unchanged; optional native trace collection added
- Build workflow: `.github/workflows/ios-graphics-730-native-diag.yml`
- IPA builder: `tools/ios_graphics_730_native_diag_build.py`

The package is accepted only if CI reports success, the source SHA matches,
there is exactly one non-expired `TotalCross-7.3.0` artifact, the GitHub
artifact metadata references the expected run and SHA, and its SHA-256 digest
matches the downloaded ZIP.

## Native trace

The temporary Objective-C probe writes a structured, append-only trace to:

`Documents/tc-ios-native-graphics.log`

This is also printed to stderr. The Appium test attempts to download this file
in its `finally` block, even if a visual assertion fails. If unavailable, an
`ios-native-graphics-pull-error.txt` file explains the error. When available,
`ios-native-graphics-summary.json` provides per-stage counts, while
`ios-graphics-appium-summary.json` references it.

Expected `TC_IOS_GFX` stages:

| Stage | Diagnostic purpose |
| --- | --- |
| `init-gles-enter`, `load-view`, `init-gles-layout`, `init-gles-exit` | Initial view/window sizes and native surface readiness |
| `child-init`, `set-screen`, `layout`, `layout-resized`, `safe-area` | Layer bounds, content scale, layout changes |
| `create-context`, `create-attachments`, `drawable-skip`, `drawable` | EAGL selection, drawable storage result, native renderbuffer dimensions, framebuffer status |
| `graphics-setup`, `graphics-update`, `present` | OpenGL context selection, update count, first two suppressed frames, actual `presentRenderbuffer:` results |
| `touch`, `touch-count`, `event-enqueue`, `event-drain` | UIKit touch delivery, scaled coordinates, VM event queue |

The OpenGL framebuffer-complete constant is `GL_FRAMEBUFFER_COMPLETE = 0x8CD5`.
A `presented=1` flag means `presentRenderbuffer:` returned success; it is
**not proof** that screenshot pixels were displayed correctly.

The `present` trace is sampled for the first 64 calls and each 100th
subsequent call (also early failed presentations). The diagnostics intentionally
avoid any GL reinitialization, framebuffer replacement, artificial extra
draw, force-redraw, or modification of the two-frame suppression.

## Execution safety

A branch push runs only the **free build/packaging** job, with no AWS credentials.
A physical Device Farm session requires explicit `workflow_dispatch` and
`execute=true`; `execute=false` builds only. Previously scheduled AWS runs
can be recovered using `collect_run_arn` without booking new devices.

The same Appium assertions still require visible initial colors, a successful
button event and the updated colors. Review screenshots, device model, iOS
version and structured native trace together; do not interpret AWS `PASSED`
or Java `onPaint` on their own as proof of visible rendering.

**Do not ship this instrumentation**: it creates a diagnostic file and emits
native GL lifecycle/touch metadata. Remove after diagnosing the regression.
