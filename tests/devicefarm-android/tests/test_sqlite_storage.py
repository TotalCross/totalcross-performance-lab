"""Physical Android 8/10/12/15 regression probe for TotalCross File and SQLite.

Uses ADB from AWS Device Farm custom Appium-Python test host; no Appium driver
or accessibility hierarchy required. Only test-owned /sdcard paths are touched.
The test deliberately records unexpected denials without granting automatically
in the first phase. Device Farm runs at most one explicitly selected device.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import unittest
import sys
import xml.etree.ElementTree as ET

PACKAGE = "totalcross.apprvks"
PREFIX = "TC_SQLITE_JSON "
EXTERNAL_DB = "/sdcard/tc-sqlite-7_3_0-external-probe.db"
EXISTING_DB = "/sdcard/tc-sqlite-7_3_0-existing-probe.db"
ROOT = Path(os.environ.get("DEVICEFARM_LOG_DIR", "/tmp/devicefarm-android"))
ROOT.mkdir(parents=True, exist_ok=True)
INTERNAL = {"memory", "file-create", "file-reopen", "plaintext-header"}
EXTERNAL = {"external-dir", "external-sqlite-create",
            "external-sqlite-reopen", "external-existing-db",
            "external-sqlite-header", "external-result"}


def sh(argv, timeout=45):
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, errors="replace", timeout=timeout)
        return {"rc": p.returncode, "text": p.stdout}
    except subprocess.TimeoutExpired:
        return {"rc": 124, "text": "Timed out: " + " ".join(argv)}


def save(name, data):
    path = ROOT / name
    if isinstance(data, (dict, list)):
        data = json.dumps(data, indent=2, default=str)
    path.write_text(str(data), encoding="utf-8", errors="replace")


def record(name, argv, timeout=45):
    r = sh(argv, timeout)
    save(name, "$ " + " ".join(argv) + "\n" + r["text"]
         + "\nEXIT_CODE=" + str(r["rc"]) + "\n")
    return r


def parse_events(raw, app_pid):
    """Only accept events from the application process launched for this phase.

    The Device Farm host can retain old logcat entries even after adb logcat -c.
    A previous phase's PASS must never be credited to a new process.
    """
    records = []
    seen = set()
    for line in raw.splitlines():
        if PREFIX not in line:
            continue
        # This probe requests 'adb logcat -v threadtime': date time PID TID ...
        fields = line.split(None, 5)
        if len(fields) < 6 or not fields[2].isdigit() or int(fields[2]) != app_pid:
            continue
        try:
            v = json.loads(line.split(PREFIX, 1)[1].strip())
        except ValueError:
            continue
        identity = (v.get("stage"), v.get("status"), v.get("detail"))
        if identity not in seen:
            seen.add(identity)
            records.append(v)
    return records


def check_permissions(label):
    for name, args in [
        ("package", ["adb", "shell", "dumpsys", "package", PACKAGE]),
        ("appops", ["adb", "shell", "appops", "get", PACKAGE]),
        ("permissions", ["adb", "shell", "pm", "list", "permissions", "-d", "-g"]),
        ("focus", ["adb", "shell", "dumpsys", "window"]),
    ]:
        record(label + "-" + name + ".txt", args, timeout=35)


def fixture():
    p = ROOT / "existing-probe-fixture.db"
    with sqlite3.connect(str(p)) as c:
        c.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        c.execute("INSERT INTO fixture VALUES (1, 'preexisting-from-python')")
        c.commit()
    save("fixture-sha256.txt", hashlib.sha256(p.read_bytes()).hexdigest())
    return p


def prepare_phase(label, source):
    sh(["adb", "shell", "am", "force-stop", PACKAGE])
    # Only ever remove paths owned by this smoke test.
    record(label + "-remove-created-db.txt",
           ["adb", "shell", "rm", "-f", EXTERNAL_DB])
    push = record(label + "-fixture-push.txt",
                  ["adb", "push", str(source), EXISTING_DB], timeout=60)
    if push["rc"] != 0:
        raise RuntimeError("Could not push external SQLite fixture: "
                           + push["text"][:900])
    record(label + "-clear-logcat.txt", ["adb", "logcat", "-c"])


def launched_app_pid(wait_seconds=15):
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        value = sh(["adb", "shell", "pidof", "-s", PACKAGE], timeout=8)
        tokens = value["text"].strip().split()
        if value["rc"] == 0 and tokens and tokens[0].isdigit():
            return int(tokens[0])
        time.sleep(0.5)
    raise RuntimeError("Cannot identify the new TotalCross process PID; phase inconclusive")


def observe(label, seconds=90):
    start = time.monotonic()
    launch = record(label + "-launch.txt",
                    ["adb", "shell", "monkey", "-p", PACKAGE,
                     "-c", "android.intent.category.LAUNCHER", "1"], 45)
    if launch["rc"] != 0 or "Events injected: 1" not in launch["text"]:
        raise RuntimeError("APK launch failed: " + launch["text"][:1500])
    app_pid = launched_app_pid()
    evidence = {"phase": label, "appPid": app_pid, "events": [], "failures": [],
                "device": os.environ.get("DEVICEFARM_DEVICE_NAME"),
                "osVersion": os.environ.get("DEVICEFARM_DEVICE_OS_VERSION"),
                "focusedWindows": [], "permissionDialogObserved": False,
                "permissionDialogDismissed": False}
    last_focus = ""
    while time.monotonic() - start < seconds:
        time.sleep(2)
        logs = sh(["adb", "logcat", "-d", "-v", "threadtime"], timeout=25)
        if logs["rc"] == 0:
            save(label + "-runtime.logcat", logs["text"])
            evidence["events"] = parse_events(logs["text"], app_pid)
        focus = sh(["adb", "shell", "dumpsys", "window"], timeout=15)["text"]
        current = " ".join(line.strip() for line in focus.splitlines()
                           if "mCurrentFocus" in line or "mFocusedApp" in line)
        if current and current != last_focus:
            evidence["focusedWindows"].append({
                "elapsed": round(time.monotonic() - start, 1), "focus": current})
            last_focus = current
        # Permission or all-files Settings dialogs may need a human gesture.
        # Record the screen and dismiss them once to see whether the app resumes.
        if (not evidence["permissionDialogDismissed"]
                and time.monotonic() - start >= 9
                and any(term in current.lower() for term in
                        ("permissioncontroller", "packageinstaller",
                         "com.android.settings"))):
            evidence["permissionDialogObserved"] = True
            record(label + "-permission-screen.txt",
                   ["adb", "shell", "uiautomator", "dump", "/sdcard/window.xml"], 20)
            record(label + "-permission-back.txt",
                   ["adb", "shell", "input", "keyevent", "KEYCODE_BACK"], 15)
            evidence["permissionDialogDismissed"] = True
        if any(x.get("stage") == "external-result" for x in evidence["events"]):
            break
        if any(x.get("stage") == "result" and x.get("status") == "FAIL"
               for x in evidence["events"]):
            break

    passed = {x.get("stage") for x in evidence["events"]
              if x.get("status") == "PASS"}
    failed = [x for x in evidence["events"] if x.get("status") == "FAIL"]
    evidence.update({
        "elapsed": round(time.monotonic() - start, 2),
        "internalPassed": INTERNAL.issubset(passed),
        "missingInternal": sorted(INTERNAL - passed),
        "externalPassed": EXTERNAL.issubset(passed),
        "externalStatuses": {s: next((x.get("status")
            for x in evidence["events"] if x.get("stage") == s), "NOT_REACHED")
            for s in sorted(EXTERNAL)},
        "failures": failed,
        "eventsCount": len(evidence["events"]),
    })
    save(label + "-events.json", evidence["events"])
    save(label + "-summary.json", evidence)
    check_permissions(label + "-after")
    return evidence


class PhysicalTotalCrossStorage(unittest.TestCase):
    def test_native_storage_permission_regression(self):
        outcome = {"result": "INCOMPLETE",
                   "package": PACKAGE, "phases": {},
                   "expectedSourceSha": "5464c21e3107e3f1ce9c287b724829e2bb870c1d",
                   "expectedOriginalApkSha256":
                   "8c6190fc5425a8f33db48900e7c9e7f8b1a2b9ff13a3d4667fe9cfc1325e685a"}
        try:
            device = sh(["adb", "shell", "getprop", "ro.build.version.sdk"])
            version = sh(["adb", "shell", "getprop", "ro.build.version.release"])
            model = sh(["adb", "shell", "getprop", "ro.product.model"])
            abis = sh(["adb", "shell", "getprop", "ro.product.cpu.abilist"])
            api = int(device["text"].strip())
            outcome.update({"api": api, "release": version["text"].strip(),
                            "model": model["text"].strip(),
                            "abis": abis["text"].strip()})
            expected_file = Path(os.environ.get("DEVICEFARM_TEST_PACKAGE_PATH", ".")) / "expected-api.txt"
            expected = int(os.environ.get("EXPECTED_ANDROID_API") or
                           expected_file.read_text(encoding="utf-8").strip())
            self.assertEqual(api, expected, "AWS selected the wrong Android API")
            self.assertIn("arm64-v8a", outcome["abis"],
                          "Selected physical device cannot load native libtcvm.so")
            image = os.environ.get("DEVICEFARM_APP_PATH")
            if image and Path(image).is_file():
                outcome["deviceFarmAppSha256"] = hashlib.sha256(
                    Path(image).read_bytes()).hexdigest()
            # AWS may re-sign the APK; the local APK hash will then differ
            # from the official source artifact, without changing code.
            installed = record("installed-package.txt",
                               ["adb", "shell", "pm", "path", PACKAGE])
            if "package:" not in installed["text"]:
                if not image:
                    raise RuntimeError("APK missing and Device Farm APP_PATH unset")
                install = record("adb-install.txt",
                                 ["adb", "install", "-r", image], timeout=180)
                if install["rc"] or "Success" not in install["text"]:
                    raise RuntimeError("APK install failed: " + install["text"][:1300])
            pkg = record("initial-package.txt", ["adb", "shell", "dumpsys",
                                                 "package", PACKAGE])
            if PACKAGE not in pkg["text"]:
                raise RuntimeError("Package unavailable after Device Farm install")
            # Clear app data before first launch, without touching unrelated files.
            record("reset-app.txt", ["adb", "shell", "pm", "clear", PACKAGE])
            check_permissions("initial")
            source = fixture()
            # Positive control FIRST: on Android 8/10 the permission UI
            # can remain foreground after a denial and prevent the next
            # launch from ever reaching TotalCross's Java/SQLite code.
            if api < 30:
                outcome["grantLegacyWrite"] = record(
                    "grant-write.txt", ["adb", "shell", "pm", "grant", PACKAGE,
                                        "android.permission.WRITE_EXTERNAL_STORAGE"])
                # Some Android 8/10 APKs also list READ as a runtime
                # permission; log the outcome rather than assuming that
                # granting WRITE grants READ on every device.
                outcome["grantLegacyRead"] = record(
                    "grant-read.txt", ["adb", "shell", "pm", "grant", PACKAGE,
                                       "android.permission.READ_EXTERNAL_STORAGE"])
                granted = "legacy-write-granted"
            else:
                outcome["grantAllFiles"] = record(
                    "grant-all-files.txt", ["adb", "shell", "appops", "set",
                                            PACKAGE, "MANAGE_EXTERNAL_STORAGE", "allow"])
                granted = "all-files-granted"
            prepare_phase(granted, source)
            outcome["phases"][granted] = observe(granted)

            # Preserve the negative control after the positive measurement.
            if api < 30:
                outcome["revokeLegacyWrite"] = record(
                    "revoke-write.txt", ["adb", "shell", "pm", "revoke", PACKAGE,
                                        "android.permission.WRITE_EXTERNAL_STORAGE"])
                outcome["revokeLegacyRead"] = record(
                    "revoke-read.txt", ["adb", "shell", "pm", "revoke", PACKAGE,
                                       "android.permission.READ_EXTERNAL_STORAGE"])
            else:
                outcome["revokeAllFiles"] = record(
                    "deny-all-files.txt", ["adb", "shell", "appops", "set",
                                           PACKAGE, "MANAGE_EXTERNAL_STORAGE", "ignore"])
            prepare_phase("denied", source)
            outcome["phases"]["denied"] = observe("denied")

            permitted = outcome["phases"][granted]
            if not permitted["internalPassed"]:
                outcome["result"] = "INCONCLUSIVE" if not permitted["eventsCount"] else "FAIL"
                self.fail("No successful private SQLite in granted phase; see evidence")
            outcome["result"] = "PASS" if permitted["externalPassed"] else "FAIL"
            self.assertTrue(permitted["externalPassed"],
                            "External storage failed WITH applicable permission pre-granted; "
                            "this is a measured denial, not a follow-on permission dialog")
        except BaseException as exc:
            outcome["error"] = repr(exc)
            raise
        finally:
            check_permissions("final")
            save("android-devicefarm-summary.json", outcome)
            print("PHYSICAL_ANDROID_STORAGE_RESULT", json.dumps({
                "api": outcome.get("api"), "result": outcome["result"],
                "phases": {k: {"internal": v["internalPassed"],
                               "external": v["externalPassed"],
                               "stages": v["externalStatuses"]}
                           for k, v in outcome["phases"].items()}
            }), flush=True)


if __name__ == "__main__":
    # Produce a real JUnit report so Device Farm can distinguish a successful
    # assertion suite from its own test framework reporting failure.
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PhysicalTotalCrossStorage)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    failures = result.failures + result.errors
    root = ET.Element("testsuite", name="TotalCrossAndroidStorage",
                      tests=str(result.testsRun),
                      failures=str(len(result.failures)),
                      errors=str(len(result.errors)),
                      skipped=str(len(result.skipped)))
    for _, problem in failures:
        case = ET.SubElement(root, "testcase",
                             name="test_native_storage_permission_regression",
                             classname="PhysicalTotalCrossStorage")
        ET.SubElement(case, "failure", message=problem.splitlines()[-1]).text = problem
    if not failures:
        ET.SubElement(root, "testcase",
                      name="test_native_storage_permission_regression",
                      classname="PhysicalTotalCrossStorage")
    ET.ElementTree(root).write(ROOT / "junit-results.xml",
                               encoding="utf-8", xml_declaration=True)
    sys.exit(0 if result.wasSuccessful() else 1)
