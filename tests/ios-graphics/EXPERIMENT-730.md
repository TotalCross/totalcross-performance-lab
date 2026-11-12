# iOS 7.3.0 direct-ChildView / physical-device experiment

This is a **one-time, explicitly approved, potentially billable** A/B run.
Only the commit message `run(ios): approved one-time Device Farm view experiment`
allows a push to schedule Device Farm. All other pushes build the IPA and Appium
package only. Do not reuse that exact commit message.

## Native provenance

- Repository: `TotalCross/totalcross`
- Fixed source base: `5464c21e3107e3f1ce9c287b724829e2bb870c1d` (7.3.0)
- Experiment branch: `test/ios-graphics-730-revert-safearea-view`
- Native commit: `a6e03d0327250a7992202b33799983386093da1c`
- PR: https://github.com/TotalCross/totalcross/pull/540
- SDK package workflow: https://github.com/TotalCross/totalcross/actions/runs/43292158650
- Control (7.2.2 passing): https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43277540910
- Original (7.3.0 black screen): https://github.com/TotalCross/totalcross-performance-lab/actions/runs/43265325205

## Changed and unchanged

Only the root UIView/CAEAGLLayer hierarchy in native `mainview.m/.h`
is reverted to the 24-Aug layout, including `closeWebView`. All other
7.3.0 changes are retained. The Java `GraphicsSmokeProbe` and the Appium
screen-color and button event checks are **unchanged**.

The test builds a new native SDK package with the experiment commit; it never
reuses the 7.3.0 native IPA. The artifact SHA-256 and source commit are checked
before cross-packaging the application IPA.

## Evidence / interpretation

Inspect `ios-graphics-appium-summary.json`,
`ios-graphics-initial.png`, `ios-graphics-after-button.png`,
`tc-ios-graphics-report.log`, and Device Farm video and device metadata.
A successful startup/onPaint alone does not establish visible graphics.

Record the actual iPhone model and iOS version. The previous control ran on an
iPhone 14 Pro / iOS 27.0 while the original failed on a 14 Pro Max / iOS 26.5,
so device/OS differences remain a possible confounder. A PASS with the
experimental 7.3.0, especially on the original failure device, would support
the hypothesis that the safe-area view container introduced the black screen.

This PR is a diagnostic experiment, not a production fix. Even if graphics
render, permanent changes must preserve safe-area support.

Device Farm schedule: one physical device, maximum 15 minutes as configured in
`tools/devicefarm_ios.py`. A run is scheduled **only after the SDK and IPA
build succeeds**. AWS charges can apply.
