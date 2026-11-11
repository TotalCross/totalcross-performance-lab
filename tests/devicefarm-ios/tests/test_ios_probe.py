"""Exercise the TotalCross 7.3.0 iOS File/SQLite probe on a physical device.

The app runs the test automatically at startup and leaves a PASS/FAIL Label
on screen. We DO NOT equate a successful Appium session with SQLite success.
"""
import json
import os
from pathlib import Path
import time
import unittest

from appium import webdriver
from appium.options.ios import XCUITestOptions


ROOT = Path(os.environ.get("DEVICEFARM_LOG_DIR", "/tmp"))
ROOT.mkdir(parents=True, exist_ok=True)
EXPECTED = "PASS: iOS File + SQLite"
FAILED = "FAIL:"


def write(name, contents):
    (ROOT / name).write_text(contents, encoding="utf-8", errors="replace")


class TotalCrossIosProbe(unittest.TestCase):
    def test_file_and_sqlite(self):
        driver = None
        report = {"result": "INCONCLUSIVE", "expected": EXPECTED}
        try:
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.automation_name = "XCUITest"
            options.set_capability("appium:autoLaunch", True)
            options.set_capability("appium:newCommandTimeout", 180)
            # Device Farm Appium server supplies app, UDID, WDA paths and iOS
            # version through --default-capabilities in the custom test spec.
            driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
            report["sessionCreated"] = True
            report["capabilities"] = {
                k: v for k, v in driver.capabilities.items()
                if k in ("platformName", "appium:platformVersion", "platformVersion",
                         "appium:deviceName", "deviceName", "appium:bundleId")
            }

            deadline = time.monotonic() + 120
            last_source = ""
            attempts = 0
            while time.monotonic() < deadline:
                attempts += 1
                try:
                    last_source = driver.page_source
                    write("ios-page-source-latest.xml", last_source)
                except Exception as exc:
                    report["lastPageSourceError"] = str(exc)
                if EXPECTED in last_source:
                    report["result"] = "PASS"
                    break
                if FAILED in last_source:
                    report["result"] = "FAIL"
                    report["reason"] = "App shows a FAIL label"
                    break
                if attempts % 10 == 1:
                    try:
                        driver.save_screenshot(str(ROOT / ("ios-probe-%03d.png" % attempts)))
                    except Exception as exc:
                        report["lastScreenshotError"] = str(exc)
                time.sleep(2)
            report["pollAttempts"] = attempts
            report["lastSourceExcerpt"] = last_source[:12000]
            if report["result"] != "PASS":
                try:
                    driver.save_screenshot(str(ROOT / "ios-final-failure.png"))
                except Exception as exc:
                    report["finalScreenshotError"] = str(exc)
                self.fail("iOS File/SQLite app did not show a PASS label: "
                          + report["result"] + "; see screenshots and page source")
        except BaseException as exc:
            report["error"] = repr(exc)
            raise
        finally:
            write("ios-appium-summary.json", json.dumps(report, indent=2))
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
