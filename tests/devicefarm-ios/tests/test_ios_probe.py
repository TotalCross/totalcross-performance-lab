"""Verify the TotalCross 7.3.0 iOS native File and SQLite probe.

Pulls a structured result log and SQLite file from the app's Documents via
Appium XCUITest 'mobile: pullFile'. This is reliable even when TotalCross's
Skia-rendered labels do not appear in the iOS accessibility tree.
"""
import base64
import json
import os
from pathlib import Path
import sqlite3
import time
import unittest

from appium import webdriver
from appium.options.ios import XCUITestOptions


ROOT = Path(os.environ.get("DEVICEFARM_LOG_DIR", "/tmp"))
ROOT.mkdir(parents=True, exist_ok=True)
TRACE_FILE = "tc-ios-devicefarm-result.log"
DATABASE_FILE = "sqlite-plaintext-smoke.db"
REQUIRED = {
    "startup", "ios-file-open-create", "ios-file-write", "ios-file-flush",
    "ios-file-size", "ios-file-close", "ios-file-open-read", "ios-file-read",
    "ios-file-delete", "ios-directory-precheck", "ios-directory-create",
    "ios-directory-delete", "ios-files-result", "memory", "file-create",
    "file-reopen", "plaintext-header", "result",
}


def save(name, contents):
    (ROOT / name).write_text(contents, encoding="utf-8", errors="replace")


def installed_probe_bundle(driver):
    # AWS Device Farm re-signs iOS apps and may update their bundle identifier.
    # Read the actual installed application IDs instead of guessing the ID.
    apps = driver.execute_script(
        "mobile: listApps",
        {"applicationType": "User",
         "returnAttributes": ["CFBundleIdentifier", "CFBundleName",
                              "CFBundleDisplayName", "UIFileSharingEnabled"]})
    save("ios-installed-apps.json", json.dumps(apps, indent=2))
    if not isinstance(apps, dict):
        raise RuntimeError("Unexpected installed-app listing type")
    shared = [
        (bundle, metadata) for bundle, metadata in apps.items()
        if isinstance(metadata, dict) and metadata.get("UIFileSharingEnabled") is True
    ]
    preferred = [
        bundle for bundle, metadata in shared
        if bundle == "com.application.name"
        or "sqlite" in (bundle + " " + str(metadata.get("CFBundleDisplayName") or "")
                        + " " + str(metadata.get("CFBundleName") or "")).lower()
    ]
    if len(preferred) == 1:
        return preferred[0]
    if not preferred and len(shared) == 1:
        return shared[0][0]
    raise RuntimeError("Could not uniquely identify file-sharing test app: " +
                       repr(shared)[:1000])


def pull_documents_file(driver, bundle_id, filename):
    remote = "@%s:documents/%s" % (bundle_id, filename)
    payload = driver.execute_script("mobile: pullFile", {"remotePath": remote})
    if not isinstance(payload, str):
        raise RuntimeError("pullFile returned unexpected type " + str(type(payload)))
    return base64.b64decode(payload, validate=True)


def parse_events(contents):
    events = []
    for line in contents.splitlines():
        if line.startswith("TC_SQLITE_JSON "):
            events.append(json.loads(line.split("TC_SQLITE_JSON ", 1)[1]))
    return events


class TotalCrossIosProbe(unittest.TestCase):
    def test_file_and_sqlite(self):
        driver = None
        report = {"result": "INCONCLUSIVE", "requiredStages": sorted(REQUIRED)}
        try:
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.automation_name = "XCUITest"
            options.set_capability("appium:autoLaunch", True)
            options.set_capability("appium:newCommandTimeout", 180)
            # Device Farm supplies app, UDID, platformVersion and prebuilt WDA.
            driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
            report["sessionCreated"] = True
            report["capabilities"] = {
                k: v for k, v in driver.capabilities.items()
                if k in ("platformName", "appium:platformVersion", "platformVersion",
                         "appium:deviceName", "deviceName", "appium:bundleId")
            }

            bundle = installed_probe_bundle(driver)
            report["installedBundleId"] = bundle
            deadline = time.monotonic() + 120
            attempts = 0
            trace = None
            while time.monotonic() < deadline:
                attempts += 1
                try:
                    trace = pull_documents_file(driver, bundle, TRACE_FILE)
                    if trace:
                        (ROOT / TRACE_FILE).write_bytes(trace)
                        break
                except Exception as exc:
                    report["lastPullError"] = str(exc)[:1200]
                if attempts % 5 == 1:
                    try:
                        driver.save_screenshot(str(ROOT / ("ios-probe-%03d.png" % attempts)))
                    except Exception as exc:
                        report["lastScreenshotError"] = str(exc)
                time.sleep(3)

            report["pullAttempts"] = attempts
            if not trace:
                report["result"] = "FAIL"
                try:
                    save("ios-page-source-latest.xml", driver.page_source)
                    driver.save_screenshot(str(ROOT / "ios-final-failure.png"))
                except Exception as exc:
                    report["finalDiagnosticError"] = str(exc)
                self.fail("TotalCross did not write a readable result log within 120 seconds")

            events = parse_events(trace.decode("utf-8", errors="replace"))
            save("ios-structured-events.json", json.dumps(events, indent=2))
            passing = {e.get("stage") for e in events if e.get("status") == "PASS"}
            failing = [e for e in events if e.get("status") == "FAIL"]
            report["events"] = len(events)
            report["stagesPassed"] = sorted(passing)
            report["missingStages"] = sorted(REQUIRED - passing)
            report["failures"] = failing
            if REQUIRED - passing or failing:
                report["result"] = "FAIL"
                self.fail("iOS test trace includes failures or missing PASS stages; "
                          "see ios-structured-events.json")

            database = pull_documents_file(driver, bundle, DATABASE_FILE)
            output_path = ROOT / "ios-sqlite-extracted.db"
            output_path.write_bytes(database)
            if not database.startswith(b"SQLite format 3\x00"):
                # The serialized output should be ordinary unencrypted SQLite.
                report["result"] = "FAIL"
                self.fail("Downloaded iOS SQLite file does not have SQLite format header")
            conn = sqlite3.connect(str(output_path))
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                row = conn.execute("SELECT value FROM smoke WHERE id=1").fetchone()
            finally:
                conn.close()
            report["sqliteIntegrity"] = integrity
            report["sqliteRow1"] = row[0] if row else None
            if integrity != "ok" or row != ("updated-ok",):
                report["result"] = "FAIL"
                self.fail("Downloaded iOS SQLite content did not match expected values")

            try:
                save("ios-page-source-latest.xml", driver.page_source)
                driver.save_screenshot(str(ROOT / "ios-final-pass.png"))
            except Exception as exc:
                report["finalDiagnosticError"] = str(exc)
            report["result"] = "PASS"
            report["databaseBytes"] = len(database)
        except BaseException as exc:
            report["error"] = repr(exc)
            raise
        finally:
            save("ios-appium-summary.json", json.dumps(report, indent=2))
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
