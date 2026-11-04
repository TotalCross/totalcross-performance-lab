#!/usr/bin/env python3
"""Run the official TotalCross 7.3.0 plaintext SQLite APK on a booted Android Emulator."""
import argparse
import hashlib
import sqlite3
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

PREFIX = "TC_SQLITE_JSON "
REQUIRED = {"memory", "file-create", "file-reopen", "plaintext-header", "result"}


def command(args, timeout=60, check=True):
    p = subprocess.run(args, capture_output=True, text=True, errors="replace",
                       timeout=timeout, check=False)
    if check and p.returncode:
        raise RuntimeError("{} failed ({}): {}".format(" ".join(args), p.returncode, p.stdout + p.stderr))
    return p.stdout + p.stderr


def find_aapt():
    result = shutil.which("aapt")
    if result:
        return result
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if sdk:
        build_tools = Path(sdk) / "build-tools"
        matches = sorted(build_tools.glob("*/aapt"), reverse=True)
        if matches:
            return str(matches[0])
    raise RuntimeError("aapt is missing from Android SDK build-tools")


def parse_events(log):
    events = []
    unique = set()
    for line in log.splitlines():
        if PREFIX not in line:
            continue
        payload = line.split(PREFIX, 1)[1].strip()
        try:
            entry = json.loads(payload)
        except ValueError:
            continue
        ident = (entry.get("stage"), entry.get("status"), entry.get("detail"))
        if ident not in unique:
            events.append(entry)
            unique.add(ident)
    return events


def write_text(out, name, value):
    (out / name).write_text(value, encoding="utf-8", errors="replace")


def capture(out, package):
    for name, args in [
        ("device-properties.txt", ["adb", "shell", "getprop"]),
        ("activity.txt", ["adb", "shell", "dumpsys", "activity", "activities"]),
        ("crashes.logcat", ["adb", "logcat", "-b", "crash", "-d", "-v", "threadtime"]),
    ]:
        try:
            write_text(out, name, command(args, timeout=30, check=False))
        except Exception as ex:
            write_text(out, name, "capture failed: " + str(ex))
    if package:
        try:
            write_text(out, "package-diagnostics.txt",
                       command(["adb", "shell", "dumpsys", "package", package], timeout=30, check=False))
        except Exception as ex:
            write_text(out, "package-diagnostics.txt", str(ex))
    try:
        screenshot = subprocess.run(["adb", "exec-out", "screencap", "-p"],
                                    capture_output=True, timeout=20, check=False)
        if screenshot.returncode == 0 and screenshot.stdout.startswith(b"\x89PNG"):
            (out / "emulator-screen.png").write_bytes(screenshot.stdout)
    except Exception:
        pass


def appop(out, package, mode):
    if mode not in ("ignore", "allow"):
        raise ValueError(mode)
    state = command(["adb", "shell", "appops", "set", package,
                     "MANAGE_EXTERNAL_STORAGE", mode], timeout=30)
    readback = command(["adb", "shell", "appops", "get", package,
                        "MANAGE_EXTERNAL_STORAGE"], timeout=30)
    write_text(out, "appops-" + mode + ".txt", state + "\\n" + readback)
    if mode not in readback:
        raise RuntimeError("MANAGE_EXTERNAL_STORAGE appop was not set to " +
                           mode + ": " + readback)
    return readback


def run_phase(out, package, phase, timeout):
    # Each launch starts in a fresh logging window; the app itself runs twice
    # against its internal fixture, which it safely resets between launches.
    command(["adb", "shell", "am", "force-stop", package], check=False)
    command(["adb", "logcat", "-c"])
    launch = command(["adb", "shell", "monkey", "-p", package, "-c",
                      "android.intent.category.LAUNCHER", "1"], timeout=35)
    write_text(out, "launch-" + phase + ".log", launch)
    if "Events injected: 1" not in launch:
        raise RuntimeError(phase + ": failed to launch application: " + launch)

    started = time.monotonic()
    events = []
    while time.monotonic() - started < timeout:
        time.sleep(2)
        logcat = command(["adb", "logcat", "-d", "-v", "threadtime"],
                         timeout=35, check=False)
        write_text(out, "runtime-android-" + phase + ".logcat", logcat)
        events = parse_events(logcat)
        write_text(out, "events-" + phase + ".json",
                   json.dumps(events, indent=2))
        if any(e.get("stage") == "external-result" for e in events):
            break
        if any(e.get("stage") == "result" and e.get("status") == "FAIL"
               for e in events):
            break

    passed = {e.get("stage") for e in events if e.get("status") == "PASS"}
    failed = [e for e in events if e.get("status") == "FAIL"]
    summary = {"phase": phase, "elapsedSeconds": round(time.monotonic() - started, 1),
               "eventCount": len(events), "passedStages": sorted(passed),
               "failedEvents": failed}
    write_text(out, "summary-" + phase + ".json",
               json.dumps(summary, indent=2))
    return summary, events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("sqlite-smoke-results"))
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = {"status": "FAIL", "started": time.time(), "apiLevel": 35,
              "emulatorImage": "google_apis/x86_64", "apkArchitecture": None,
              "case": "client /sdcard/asd directory and SQLite at /sdcard"}
    package = ""
    try:
        apks = sorted((out / "deployed" / "install" / "android").glob("*.apk"))
        if len(apks) != 1:
            raise RuntimeError("Expected exactly one deployed APK; got " + repr(apks))
        apk = apks[0]
        with zipfile.ZipFile(apk) as archive:
            abis = sorted({item.split("/")[1] for item in archive.namelist()
                           if item.startswith("lib/") and item.endswith(".so")})
        result["apkAbis"] = abis
        if "arm64-v8a" not in abis:
            raise RuntimeError("APK does not contain ARM64 native libraries")
        result["apkArchitecture"] = "arm64-v8a"

        aapt = find_aapt()
        badging = command([aapt, "dump", "badging", str(apk)])
        write_text(out, "apk-badging.txt", badging)
        declared = command([aapt, "dump", "permissions", str(apk)])
        write_text(out, "apk-permissions.txt", declared)
        if "android.permission.MANAGE_EXTERNAL_STORAGE" not in declared:
            raise RuntimeError("APK does not declare MANAGE_EXTERNAL_STORAGE; check /android_manage_external_storage")
        match = re.search(r"^package: name='([^']+)'", badging, re.M)
        if not match:
            raise RuntimeError("aapt cannot identify APK application ID")
        package = match.group(1)
        result["package"] = package
        result["apkPath"] = str(apk)

        command(["adb", "wait-for-device"])
        abi_list = command(["adb", "shell", "getprop", "ro.product.cpu.abilist"]).strip()
        sdk = command(["adb", "shell", "getprop", "ro.build.version.sdk"]).strip()
        result["deviceAbis"] = abi_list
        result["deviceSdk"] = sdk
        write_text(out, "emulator-abi.txt",
                   "SDK={}\\nABILIST={}\\nAPK_ABIS={}\\n".format(sdk, abi_list, abis))
        if "arm64-v8a" not in abi_list.split(","):
            raise RuntimeError("Emulator does not support arm64-v8a translation")

        install = command(["adb", "install", "--abi", "arm64-v8a", "-r", str(apk)],
                          timeout=120)
        write_text(out, "install.log", install)
        package_info = command(["adb", "shell", "dumpsys", "package", package], timeout=30)
        write_text(out, "package-after-install.txt", package_info)
        selected = re.search(r"primaryCpuAbi=([A-Za-z0-9_-]+)", package_info)
        result["installedPrimaryAbi"] = selected.group(1) if selected else "not-reported"
        if selected and selected.group(1) != "arm64-v8a":
            raise RuntimeError("Android installed the wrong ABI: " + selected.group(1))

        # Push a *pre-existing* standard plaintext SQLite file into shared
        # storage before denying access. It is created independently of TCVM.
        fixture = out / "preexisting-before.db"
        if fixture.exists():
            fixture.unlink()
        with sqlite3.connect(str(fixture)) as db:
            db.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT INTO fixture (id, value) VALUES (1, 'preexisting-from-python')")
            db.commit()
        image_path = "/sdcard/tc-sqlite-7_3_0-existing-probe.db"
        pushed = command(["adb", "push", str(fixture), image_path], timeout=45)
        write_text(out, "preexisting-push.log", pushed)
        write_text(out, "preexisting-source.json", json.dumps({
            "hostFileSha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "fileSize": fixture.stat().st_size,
            "devicePath": image_path,
            "expectedBefore": "preexisting-from-python",
            "expectedAfter": "updated-by-totalcross"
        }, indent=2))

        # Phase 1: special permission explicitly unavailable. Captures the
        # client's exact mkdir/delete call and any SQLite error on /sdcard.
        result["deniedAppOp"] = appop(out, package, "ignore")
        denied, denied_events = run_phase(out, package, "denied", args.timeout)
        result["denied"] = denied
        if "external-result" in denied["passedStages"]:
            raise RuntimeError("Negative control unexpectedly accessed external storage")
        denied_fail_stages = {e.get("stage") for e in denied["failedEvents"]}
        if "external-result" not in denied_fail_stages:
            raise RuntimeError("Negative control inconclusive: no external-result FAIL event")

        # Phase 2: MANAGE_EXTERNAL_STORAGE granted via appops, without changing
        # the APK or TCVM. No manual Settings UI automation is implied.
        result["grantedAppOp"] = appop(out, package, "allow")
        granted, granted_events = run_phase(out, package, "granted", args.timeout)
        result["granted"] = granted
        required = REQUIRED | {
            "external-dir", "external-sqlite-create", "external-sqlite-reopen",
            "external-sqlite-header", "external-existing-db", "external-result"}
        missing = required.difference(granted["passedStages"])
        if granted["failedEvents"] or missing:
            throwables = [e for e in granted_events if e.get("status") == "FAIL"]
            write_text(out, "failure-hints.txt", json.dumps(throwables, indent=2))
            raise RuntimeError("With MANAGE_EXTERNAL_STORAGE, SQLite smoke failed: "
                               + ", ".join(sorted(missing))
                               + "; failing events=" + str(throwables))

        # Independently read back the modified shared-storage database with
        # host Python SQLite. This validates actual persistence/interoperability.
        readback = out / "preexisting-after.db"
        command(["adb", "pull", image_path, str(readback)], timeout=45)
        with sqlite3.connect(str(readback)) as db:
            rows = db.execute("SELECT value FROM fixture WHERE id=1").fetchall()
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        result["externalDatabaseReadback"] = {"rows": rows, "integrity": integrity,
            "sha256": hashlib.sha256(readback.read_bytes()).hexdigest()}
        if rows != [("updated-by-totalcross",)] or integrity != "ok":
            raise RuntimeError("Shared-storage SQLite readback mismatch: " + str(rows)
                               + "; integrity=" + integrity)
        result["status"] = "PASS"
        print("Android external SQLite PASS: denied without permission, all "
              "filesystem and SQLite tests passed with MANAGE_EXTERNAL_STORAGE")
    except Exception as ex:
        result["error"] = str(ex)
        print("Android external SQLite smoke failed: " + str(ex), file=sys.stderr)
    finally:
        try:
            result["finalAppOp"] = command(
                ["adb", "shell", "appops", "get", package,
                 "MANAGE_EXTERNAL_STORAGE"], timeout=20, check=False) if package else ""
            write_text(out, "storage-paths.txt", command(
                ["adb", "shell", "ls", "-lad", "/sdcard", "/sdcard/asd",
                 "/sdcard/tc-sqlite-7_3_0-external-probe.db",
                 "/sdcard/tc-sqlite-7_3_0-existing-probe.db"],
                timeout=25, check=False))
        except Exception as ex:
            result["diagnosticError"] = str(ex)
        capture(out, package)
        result["finished"] = time.time()
        write_text(out, "android-execution-summary.json", json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
