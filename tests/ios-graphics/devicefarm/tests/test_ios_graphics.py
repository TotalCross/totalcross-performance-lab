"""Physical-iPhone visual smoke for TotalCross 7.3.0 Skia and basic UI.

The native app writes paint/callback checkpoints into Documents. Appium pulls
those checkpoints and captures PNG screenshots. PNG pixels are decoded with
Python's standard library so a totally black screen CANNOT be mistaken for
success just because the native onPaint call returned without an exception.

Expected: 4 large initial RGBY panels, then CYAN/MAGENTA/ORANGE/PURPLE after
a real coordinate tap on the TotalCross Button. Label and Edit update as well.
"""
import base64
import json
import os
from pathlib import Path
import re
import struct
import time
import unittest
import zlib

from appium import webdriver
from appium.options.ios import XCUITestOptions

OUT = Path(os.environ.get("DEVICEFARM_LOG_DIR", "/tmp"))
OUT.mkdir(parents=True, exist_ok=True)
TRACE_NAME = "tc-ios-graphics-report.log"
PALETTE = {
    "initial": {"red": (255, 0, 0), "green": (0, 255, 0),
                "blue": (0, 0, 255), "yellow": (255, 255, 0)},
    "updated": {"cyan": (0, 255, 255), "magenta": (255, 0, 255),
                "orange": (255, 200, 0), "purple": (132, 60, 220)},
}


def save(name, value):
    (OUT / name).write_text(value, encoding="utf-8", errors="replace")


def iter_png_sampled_rgb(data):
    """Decode PNG RGB/RGBA 8-bit noninterlaced pixel samples (no dependencies).

    Decode all rows to handle PNG's differential filtering; sample about a
    90x90 grid to avoid keeping a second full-size pixel buffer in memory.
    """
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Appium screenshot is not PNG")
    pos = 8
    compressed = []
    width = height = channels = None
    while pos + 12 <= len(data):
        length = struct.unpack_from(">I", data, pos)[0]
        name = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if name == b"IHDR":
            width, height, depth, kind, cm, fm, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or kind not in (2, 6) or interlace != 0:
                raise ValueError("Unsupported PNG encoding: bit=%s color=%s interlace=%s"
                                 % (depth, kind, interlace))
            channels = 4 if kind == 6 else 3
        elif name == b"IDAT":
            compressed.append(body)
        elif name == b"IEND":
            break
    if not width or not height or not compressed:
        raise ValueError("PNG missing dimensions or pixel data")
    decoded = zlib.decompress(b"".join(compressed))
    stride = width * channels
    if len(decoded) != (stride + 1) * height:
        raise ValueError("Unexpected PNG decompressed size")
    previous = bytearray(stride)
    xstep = max(1, width // 90)
    ystep = max(1, height // 90)
    offset = 0
    for y in range(height):
        kind = decoded[offset]
        current = bytearray(decoded[offset + 1:offset + 1 + stride])
        offset += stride + 1
        if kind == 1:
            for i in range(channels, stride):
                current[i] = (current[i] + current[i - channels]) & 255
        elif kind == 2:
            for i in range(stride):
                current[i] = (current[i] + previous[i]) & 255
        elif kind == 3:
            for i in range(stride):
                current[i] = (current[i] + ((current[i - channels] if i >= channels else 0)
                                             + previous[i]) // 2) & 255
        elif kind == 4:
            for i in range(stride):
                a = current[i - channels] if i >= channels else 0
                b = previous[i]
                c = previous[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
                current[i] = (current[i] + pred) & 255
        elif kind != 0:
            raise ValueError("Unsupported PNG scanline filter: " + str(kind))
        if y % ystep == 0:
            for x in range(0, width, xstep):
                i = x * channels
                yield width, height, (current[i], current[i + 1], current[i + 2])
        previous = current


def png_metrics(data, stage):
    colors = PALETTE[stage]
    hits = {name: 0 for name in colors}
    samples = colored = bright = dark = 0
    width = height = 0
    for width, height, (r, g, b) in iter_png_sampled_rgb(data):
        samples += 1
        if max(r, g, b) - min(r, g, b) > 85:
            colored += 1
        if max(r, g, b) >= 110:
            bright += 1
        if max(r, g, b) < 30:
            dark += 1
        for name, expected in colors.items():
            if max(abs(r - expected[0]), abs(g - expected[1]), abs(b - expected[2])) <= 45:
                hits[name] += 1
    # Distinct palette colors in multiple independent sample points are much
    # stronger evidence than "onPaint returned" or the Device Farm PASS flag.
    has_all_colors = min(hits.values()) >= max(10, int(samples * 0.004))
    visible = bright >= samples * 0.18 and colored >= samples * 0.03
    return {
        "stage": stage, "width": width, "height": height,
        "sampledPixels": samples, "brightFraction": round(bright / samples, 4),
        "colorfulFraction": round(colored / samples, 4),
        "darkFraction": round(dark / samples, 4),
        "expectedColorHits": hits,
        "allExpectedColorsVisible": has_all_colors,
        "significantVisibleContent": visible,
        "pass": has_all_colors and visible,
    }


def installed_bundle(driver):
    apps = driver.execute_script("mobile: listApps", {
        "applicationType": "User",
        "returnAttributes": ["CFBundleIdentifier", "CFBundleName",
                             "CFBundleDisplayName", "UIFileSharingEnabled"],
    })
    save("ios-installed-apps.json", json.dumps(apps, indent=2))
    if not isinstance(apps, dict):
        raise RuntimeError("Unexpected installed-app listing")
    candidates = [(bundle, meta) for bundle, meta in apps.items()
                  if isinstance(meta, dict) and meta.get("UIFileSharingEnabled") is True]
    match = [(bundle, meta) for bundle, meta in candidates
             if bundle == "com.application.name" or
             "graphics" in (bundle + " " + str(meta.get("CFBundleName") or "")).lower()]
    if len(match) == 1:
        return match[0][0]
    if not match and len(candidates) == 1:
        return candidates[0][0]
    raise RuntimeError("Ambiguous file-sharing application: " + repr(candidates))


def pull_trace(driver, bundle):
    b64 = driver.execute_script("mobile: pullFile", {
        "remotePath": "@%s:documents/%s" % (bundle, TRACE_NAME),
    })
    if not isinstance(b64, str):
        raise ValueError("pullFile returned non-base64 payload")
    contents = base64.b64decode(b64, validate=True).decode("utf-8", errors="replace")
    save(TRACE_NAME, contents)
    events = []
    for line in contents.splitlines():
        if line.startswith("TC_GRAPHICS_JSON "):
            events.append(json.loads(line[len("TC_GRAPHICS_JSON "):]))
    save("ios-graphics-events.json", json.dumps(events, indent=2))
    return events


def has_pass(events, name):
    return any(e.get("stage") == name and e.get("status") == "PASS"
               for e in events)


def no_failures(events):
    return not [e for e in events if e.get("status") == "FAIL"]


def wait_for_events(driver, bundle, names, seconds=60):
    deadline = time.monotonic() + seconds
    events = []
    while time.monotonic() < deadline:
        try:
            events = pull_trace(driver, bundle)
            if not no_failures(events):
                return events
            if all(has_pass(events, name) for name in names):
                return events
        except Exception as exc:
            save("ios-last-pull-error.txt", repr(exc))
        time.sleep(2)
    return events


def layout_ratio(events, name):
    for item in reversed(events):
        if item.get("stage") != "layout":
            continue
        match = re.search(r"(?:^|;)%s=([0-9.]+)" % re.escape(name),
                          item.get("detail", ""))
        if match:
            return float(match.group(1))
    raise RuntimeError("Missing layout ratio " + name)


class IOSGraphicsTest(unittest.TestCase):
    def test_native_graphics_visible_and_interactive(self):
        report = {"result": "INCONCLUSIVE", "source": "TotalCross 7.3.0 iOS graphics",
                  "tests": ["4 colored shapes, Label, Edit, Button, button repaint"]}
        driver = None
        try:
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.automation_name = "XCUITest"
            options.set_capability("appium:autoLaunch", True)
            options.set_capability("appium:newCommandTimeout", 180)
            driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
            report["sessionCreated"] = True
            bundle = installed_bundle(driver)
            report["bundleId"] = bundle
            report["windowSize"] = driver.get_window_size()

            initial = wait_for_events(driver, bundle,
                                      {"startup", "controls-created",
                                       "canvas-painted-initial"}, seconds=60)
            report["initialStages"] = sorted(set(e.get("stage") for e in initial
                                                   if e.get("status") == "PASS"))
            initial_png = driver.get_screenshot_as_png()
            (OUT / "ios-graphics-initial.png").write_bytes(initial_png)
            try:
                save("ios-page-source-initial.xml", driver.page_source)
            except Exception as exc:
                report["initialSourceError"] = repr(exc)
            if not no_failures(initial) or not all(
                    has_pass(initial, key) for key in
                    ("startup", "controls-created", "canvas-painted-initial")):
                report["result"] = "FAIL"
                self.fail("Native app did not initialize and paint all controls; inspect report")
            report["initialScreenshot"] = png_metrics(initial_png, "initial")
            if not report["initialScreenshot"]["pass"]:
                report["result"] = "FAIL"
                self.fail("Graphics are not visibly rendered: initial PNG missing color panels "
                          "(black screen or incorrect raster). See screenshot and JSON.")

            ratio_x = layout_ratio(initial, "buttonCenterRelX")
            ratio_y = layout_ratio(initial, "buttonCenterRelY")
            dimensions = driver.get_window_size()
            report["buttonCenterRatio"] = [ratio_x, ratio_y]
            report["buttonTapAttempts"] = []
            changed = []
            # On some iOS versions the status-bar/safe-area inset shifts the
            # canvas origin relative to Appium's full-screen coordinates.
            for delta_y in (0.0, 0.035, -0.035, 0.07):
                x = int(dimensions["width"] * ratio_x)
                y = int(dimensions["height"] * (ratio_y + delta_y))
                try:
                    driver.execute_script("mobile: tap", {"x": x, "y": y})
                    report["buttonTapAttempts"].append({"x": x, "y": y})
                except Exception as exc:
                    report["buttonTapAttempts"].append({"x": x, "y": y,
                                                         "error": str(exc)})
                changed = wait_for_events(driver, bundle,
                                          {"button-pressed", "canvas-painted-updated"},
                                          seconds=10)
                if (has_pass(changed, "button-pressed")
                        and has_pass(changed, "canvas-painted-updated")):
                    break
            updated_png = driver.get_screenshot_as_png()
            (OUT / "ios-graphics-after-button.png").write_bytes(updated_png)
            try:
                save("ios-page-source-after-button.xml", driver.page_source)
            except Exception as exc:
                report["updatedSourceError"] = repr(exc)
            report["finalStages"] = sorted(set(e.get("stage") for e in changed
                                                 if e.get("status") == "PASS"))
            if not no_failures(changed) or not (
                    has_pass(changed, "button-pressed")
                    and has_pass(changed, "canvas-painted-updated")):
                report["result"] = "FAIL"
                self.fail("Button press / repaint not observed; see screenshot and trace")
            report["updatedScreenshot"] = png_metrics(updated_png, "updated")
            if not report["updatedScreenshot"]["pass"]:
                report["result"] = "FAIL"
                self.fail("Native event ran but updated palette is not visible in screenshot")
            report["result"] = "PASS"
        except BaseException as error:
            report["error"] = repr(error)
            raise
        finally:
            save("ios-graphics-appium-summary.json", json.dumps(report, indent=2))
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
