# iOS 7.3.0 — basic Skia and UI visibility probe

This is a **standalone, graphical smoke test** for the pinned official
TotalCross 7.3.0 SDK (`5464c21e3107e3f1ce9c287b724829e2bb870c1d`).
It does **not** depend on SQLite or the Android storage-permission sample.

Motivation: the previous iOS File/SQLite probe completed successfully on an
iPhone 17, yet its Appium screenshot was entirely black. A native `onPaint`
callback or a Device Farm `PASSED` status is **not** proof of visible output.

## On-screen content

`GraphicsSmokeProbe.java` extends `MainWindow` and draws a simple static UI:

- **Label:** a visible test title and a status label.
- **Edit:** starts with the literal text `EDIT READY`.
- **Button:** starts with `CHANGE COLORS`.
- **PrimitivePanel (Control.onPaint(Graphics)):** four broad saturated
  rectangles (red, green, blue, yellow), black rectangle outline, crossed
  diagonal lines, white filled circle with black outline, and painted text.

Tapping the Button updates the Label and Edit, changes the button caption to
`RESET COLORS`, and redraws the four rectangles in cyan, magenta, orange,
and purple. The button callback emits a separate diagnostic checkpoint.

No animation, networking, SQLite or external permission request is involved.
The test intentionally uses only the common `MainWindow`, `Label`, `Edit`,
`Button`, `Control` and `Graphics` APIs.

## Two independent layers of verification

**1. TotalCross event log.** The app emits `TC_GRAPHICS_JSON` checkpoints to
`Vm.debug` **and** to
`Settings.appPath/tc-ios-graphics-report.log`. The latter is deliberately
created in the app-private Documents directory and downloaded through
Appium `mobile: pullFile`, because `NSLog` text can be redacted as
`<private>` in iOS unified logging. Expected PASS stages:

- `startup`
- `controls-created`
- `canvas-painted-initial`
- `button-pressed`
- `canvas-painted-updated`

A painted-stage PASS means the TotalCross callback ran, **not** that the
screen was actually presented.

**2. Screenshot pixels.** On the physical iPhone, Appium captures
`ios-graphics-initial.png` and `ios-graphics-after-button.png`. A
pure-Python PNG analyzer samples the pixels without relying on the
accessibility tree (which does not expose custom Skia drawing). It fails if
the screen is still black/near-monochrome, if any of the four expected colors
is missing in the initial frame, or if the second screenshot lacks the new
palette. Thus a successful native callback alone can **never** make this test
pass while the display stays black.

The Appium test clicks the **actual button** at the approximate normalized
coordinates logged by the app and confirms the button callback plus updated
render event before accepting the second screenshot.

The test is deliberately **conservative**. A nonstandard screenshot format,
unexpected safe-area coordinate mapping, iOS keyboard overlay, or an Appium
issue can result in FAIL/INCONCLUSIVE, and the captured images/logs should
then be reviewed manually. This is a gross smoke test, not a complete UI
rendering conformance suite.

## GitHub Actions — no automatic AWS charges

Full implementation:
[`.github/workflows/ios-graphics-devicefarm.yml`](../../.github/workflows/ios-graphics-devicefarm.yml).

The entrypoint is also present on `main`, where it **never contacts AWS**.
Because the IAM trust policy currently authorizes the branch
`test/sqlite-plaintext-7.3.0`, select that branch in the GitHub Actions
Run workflow menu. The actual graphics test is independent even though its
hosting branch also contains the earlier SQLite experiments.

1. **Free build only:** push test changes or start `Run workflow` with
   `execute=false` and `collect_run_arn` empty. The macOS runner verifies
   Java compilation, creates the iOS IPA, checks that the TCZ has the
   `ATTR_HAS_MAINWINDOW` flag, enables iOS Documents sharing in
   `Info.plist`, and packages Appium Python tests. The native TotalCross
   binary is not modified. Artifact: `ios-graphics-7.3.0-build`.
2. **Physical-device run (billable):** start
   [iOS graphics / AWS Device Farm](https://github.com/TotalCross/totalcross-performance-lab/actions/workflows/ios-graphics-devicefarm.yml),
   select branch `test/sqlite-plaintext-7.3.0`, set `execute=true` and
   leave `collect_run_arn` empty. The workflow reuses existing GitHub OIDC
   AWS variables, checks project/pool and historical-run permissions before
   scheduling, accepts **only a one-device pool**, caps a device job at
   **15 minutes**, uses Appium XCUITest and provider IPA re-signing. Then it
   waits for Device Farm and copies available run/job/suite/test artifacts.
   Artifact: `ios-graphics-7.3.0-physical-device`.
3. **Recover without another booking:** use `execute=false` and provide a
   previously scheduled AWS run ARN in `collect_run_arn`. This does not call
   `CreateUpload` or `ScheduleRun`.

### Evidence to inspect

The GitHub artifact typically contains nested Device Farm
`Customer_Artifacts.zip` with:

- `ios-graphics-initial.png` — should show original four panels and UI;
- `ios-graphics-after-button.png` — updated panels/UI;
- `ios-graphics-appium-summary.json` — actual Appium pass/fail, palette
  pixel counts and screenshot color/brightness ratios;
- `ios-graphics-events.json`, `tc-ios-graphics-report.log` — native stages;
- `ios-page-source-*.xml`, `ios-installed-apps.json` — diagnostics;
- `appium.log`, `unittest.log`, Android-independent iOS syslog, Device
  Farm video, and other available run-level artifacts.

**Never infer a graphics PASS solely from AWS's overall `PASSED` state.**
Check the Appium summary and the actual screenshots. The previous
File/SQLite black-screen symptom is exactly what this test aims to detect.

The prior 7.3.0 iOS IPA template uses a dummy provisioning profile; Device
Farm's automatic re-signing must remain enabled. The IPA from the free build
is not automatically installable on an ordinary iPhone without signing.
