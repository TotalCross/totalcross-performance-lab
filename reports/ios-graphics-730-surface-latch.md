# iOS 7.3.0 surface-change latch experiment

## Goal

Test the hypothesis that an initial no-op `screenChange` leaves the
iOS GLES `surfaceWillChange` flag permanently set, preventing any Skia
flush or `presentRenderbuffer:` call.

This follows the **failed** native-diagnostics Device Farm run
[43317087120](https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43317087120),
where the EAGL drawable was complete (`0x8CD5`) but the trace did not
contain any `graphics-update` or `present` entries.

## Exact source

- Working control: 7.2.2 (2026-08-24) — Device Farm **PASS**.
- Failed 7.3.0 baseline: `5464c21e3107e3f1ce9c287b724829e2bb870c1d`.
- Instrumented 7.3.0 baseline: `d1fa0fa4b9186cce4bc1d1f4bdf91872713a3954`.
- Fix + additional trace: `791e8c465ccfb8c9e0d34588a5467ea9d033c762`.
- Native experiment: https://github.com/TotalCross/totalcross/pull/542
- SDK package: https://github.com/TotalCross/totalcross/actions/runs/43326093367
- Graphic IPA workflow: `.github/workflows/ios-graphics-730-surface-latch.yml`
- IPA builder: `tools/ios_graphics_730_surface_latch_build.py`.

This workflow checks that the pinned SDK run has completed both the iOS and
`Package TotalCross` jobs successfully and verifies the single
`TotalCross-7.3.0` artifact's provenance and SHA-256.

The test application `GraphicsSmokeProbe.java` and the Appium visual and
button assertions have **not** changed.

## Minimal experimental change

The only behavior change is conditional on iOS:

If `screenChangeCommitted` receives `SCREEN_CHANGE_NONE` for a ready
surface **and** `surfaceWillChange` is still set, the experiment treats
the event as `SCREEN_CHANGE_INITIAL` and uses the normal commit path.
This updates tcSettings, GL projection, dirty flags, `SK_SCREEN_CHANGE`
and the window repaint together. `SCREEN_CHANGE_INITIAL` alone does not
recreate the native surface. Normal non-empty screen changes are unchanged.

Sampling logs `screen-change-event`, `screen-change-apply`,
`screen-change-noop-release`, `screen-change-committed`,
`screen-update-guard`, `vm-screen-update`, and the previously existing
`graphics-update` / `present` stages. All traces are appended to
`Documents/tc-ios-native-graphics.log` and collected by Appium even if
the screen is black.

## Acceptance criteria

1. A no-op initial screen event is visible with `latch=1`.
2. A single `screen-change-noop-release` follows, then
   `screen-update-guard` reports `surfaceWillChange=0`.
3. The renderer reaches `graphics-update` and `present`; the latter's
   `presented=1` only means the API succeeded, not that the UI is visible.
4. Appium confirms `initialVisualPass=true`, `buttonEventPass=true`,
   and `updatedVisualPass=true`.
5. The device model and iOS version are documented for comparison.

If the condition is not reached, the trace distinguishes a missing event,
a different change flag, a dirty/enableUpdateScreen issue or a presentation
failure. Do not claim the root cause is confirmed until runtime data verifies
the path.

## AWS safeguards

A push to the `test/sqlite-plaintext-7.3.0` branch triggers a **free
Linux IPA packaging** job only. It never schedules an AWS device.

To run the **billable** test, register the workflow on the default branch
via [performance-lab PR #10](https://github.com/TotalCross/totalcross-performance-lab/pull/10),
then manually select `test/sqlite-plaintext-7.3.0` and `execute=true`.

This is a diagnostic test, **not a production fix**. Keep the native PR
in draft and do not merge until the platform lifecycle, rendering and
interaction behavior have been verified.


## Physical outcome — 2026-11-13, run 43359967677

**Status: initial graphics PASS, button interaction FAIL.** The experiment
restores the initial visible iOS 7.3.0 graphics frame; the full test does
not pass because the native pen coordinates are not converted to Java
logical coordinates.

- Run: https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43359967677
- Physical evidence ZIP: https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43359967677/artifacts/14008865868
- SDK: source `791e8c465ccfb8c9e0d34588a5467ea9d033c762`, upstream run `43326093367`, artifact `13993740050`.
- Test source: rebased performance-lab commit `6dfc139c18b1b2ca42e30a9f74ae47cd7f991b65`.
- Device: iPhone, iOS 26.3, window 402×874 points, ChildView 402×778
  points, renderbuffer 1206×2334 pixels.
- `ios-graphics-appium-summary.json`: `initialVisualPass=true`,
  `darkFraction=0.1253`, expected red/green/blue/yellow sampled hits
  538/467/474/546.
- `tc-ios-native-graphics.log`: 117 lines, `screen-change-event
  changes=0x0 latch=1`, `screen-change-noop-release forcingInitial=1`,
  `screen-change-committed latchBefore=1`, then
  `screen-update-guard surfaceWillChange=0 ready=1`.
- 5 graphics update and present records: first two `suppressed=1`
  intentionally, three later `presented=1` with `fbStatus=0x8cd5`.
- UIKit delivers 4 taps × down/up to the native VM queue; all eight
  events are drained, but the Java `button-pressed` stage never runs and
  `updatedVisualPass=false`.

### Separate pen coordinate mismatch

The first tap is child-local (201,559) **points** but is forwarded to the
VM as (603,1677) **physical pixels**. Java's `Settings.screenWidth` is
402 logical points, and `Window._postEvent` consumes the pen coordinates
without another scale transform. The native iOS `event.m` passes these
pixel coordinates directly to `postEvent`, so the Java button cannot
be hit-tested. This is unlike Android's `androidPhysicalToLogical`
conversion. Recommended next experiment: in iOS `event.m`, convert
down/up/drag coordinates by `screen.contentScale` before `postEvent`,
instrument the conversion, and verify press/repaint. Do not change Appium
assertions to mask the bug.

The existing surface-latch PR #542 remains a **draft diagnostic**, not a
verified final release fix. No new paid device run has been initiated.
