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


## Result — physical Device Farm run 43317087120 (2026-11-12)

- **SDK:** 7.3.0 native diagnostic source `d1fa0fa4b9186cce4bc1d1f4bdf91872713a3954`, original baseline `5464c21e`.
- **Workflow:** https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43317087120
- **Evidence:** https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43317087120/artifacts/13990155992
- **Device:** iPhone 17 (A3258), iOS 26.3.1, screenshot 1206×2622; GL safe-area drawable 1206×2334 (402×778 points, scale 3).
- **Appium:** FAIL; initial `darkFraction=0.9976`, zero RGBY hits, `initialVisualPass=false`; button and updated-visual checks also fail.
- **Native file collection:** PASS, `tc-ios-native-graphics.log` has **40 lines**; stages also listed in `ios-native-graphics-summary.json`.
- **GL initialization:** `create-context selected=1`; `drawable storage=1 renderbuffer=1206x2334 fbStatus=0x8cd5` (complete), `surfaceReady=1`.
- **Screen updates:** **No `graphics-update` or `present` stage** in the entire trace, so `graphicsUpdateScreenIOS` and `presentRenderbuffer:` were never reached by the existing instrumentation.
- **Touch delivery:** all 8 UIKit touch events (4 taps × down/up) were enqueued as mouse events and drained by the VM. No Java `button-pressed` stage was observed. This could involve targeting/coordinate conversion; native delivery itself is operational.

### Leading cause hypothesis — persistent surface-change guard

The initial `viewDidLayoutSubviews` sets `surfaceWillChange=true` and queues a `screenChange` event. Before that event is processed, `setScreenValues` writes the **same** dimensions into `screen` and marks `surfaceReady=true`. When `screenChange` runs, `screenApplyConfiguration` can return `SCREEN_CHANGE_NONE`, and `screenChangeCommitted` exits immediately. The branch `graphicsScreenChange` which clears `surfaceWillChange` is therefore skipped. `graphicsUpdateScreen` then returns without `flushSkia` or `graphicsUpdateScreenIOS` whenever `surfaceWillChange` remains true.

Evidence: `TotalCrossVM/src/nm/ui/darwin/mainview.m`,
`TotalCrossVM/src/nm/ui/darwin/childview.m`,
`TotalCrossVM/src/event/darwin/event.m`,
`TotalCrossVM/src/nm/ui/GraphicsPrimitives_c.h`,
`TotalCrossVM/src/nm/ui/backend/graphics/gles/gfx_Graphics_c.h`.

**Confidence:** high but not yet proven at runtime, because `graphicsUpdateScreen` itself was not instrumented to print the guard. Recommended next experiment: add a sampled log at the `graphicsUpdateScreen` early-return branch and/or test a minimal iOS-only release of the initial `surfaceWillChange` guard after the drawable is ready. Keep this separate from PR #540 (the unsuccessful view-hierarchy rollback). Do not start another billable Device Farm run without explicit opt-in.

