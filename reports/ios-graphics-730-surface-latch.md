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
