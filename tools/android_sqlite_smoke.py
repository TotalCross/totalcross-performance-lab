#!/usr/bin/env python3
"""Run the official TotalCross 7.3.0 plaintext SQLite APK on a booted Android Emulator."""
import argparse
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("sqlite-smoke-results"))
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = {"status": "FAIL", "started": time.time(), "apiLevel": 35,
              "emulatorImage": "google_apis/x86_64", "apkArchitecture": None}
    package = ""
    try:
        apks = sorted((out / "deployed" / "install" / "android").glob("*.apk"))
        if len(apks) != 1:
            raise RuntimeError("Expected exactly one deployed APK; got " + repr(apks))
        apk = apks[0]
        with zipfile.ZipFile(apk) as f:
            abis = sorted({item.split("/")[1] for item in f.namelist()
                           if item.startswith("lib/") and item.endswith(".so")})
        result["apkAbis"] = abis
        if "arm64-v8a" not in abis:
            raise RuntimeError("Official TotalCross APK does not contain arm64-v8a native .so files")
        result["apkArchitecture"] = "arm64-v8a"

        badging = command([find_aapt(), "dump", "badging", str(apk)])
        write_text(out, "apk-badging.txt", badging)
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
        write_text(out, "emulator-abi.txt", "SDK={}\nABILIST={}\nAPK_ABIS={}\n".format(sdk, abi_list, abis))
        if "arm64-v8a" not in abi_list.split(","):
            raise RuntimeError("Android emulator doesn't advertise arm64-v8a translation; install would be invalid")

        # Must use the unmodified APK from the exact TotalCross SDK artifact.
        # Official APK contains ABI folders beyond the native arm64 TCVM. Without
        # an override Android can select x86_64 and fail to load libtcvm.so.
        install = command(["adb", "install", "--abi", "arm64-v8a", "-r", str(apk)], timeout=120)
        package_info = command(["adb", "shell", "dumpsys", "package", package], timeout=30)
        write_text(out, "package-after-install.txt", package_info)
        selected = re.search(r"primaryCpuAbi=([^\\s]+)", package_info)
        result["installedPrimaryAbi"] = selected.group(1) if selected else "not-reported"
        if selected and selected.group(1) != "arm64-v8a":
            raise RuntimeError("Package Manager did not select arm64-v8a: " + selected.group(1))
        write_text(out, "install.log", install)
        command(["adb", "shell", "am", "force-stop", package], check=False)
        command(["adb", "logcat", "-c"], check=False)

        # Monkey uses manifest launch intent and avoids assuming TotalCross activity naming.
        launch = command(["adb", "shell", "monkey", "-p", package, "-c",
                          "android.intent.category.LAUNCHER", "1"], timeout=35)
        write_text(out, "launch.log", launch)
        if "Events injected: 1" not in launch:
            raise RuntimeError("The emulator didn't launch the TotalCross test activity")

        start = time.monotonic()
        events = []
        while time.monotonic() - start < args.timeout:
            time.sleep(3)
            logcat = command(["adb", "logcat", "-d", "-v", "threadtime"], timeout=35, check=False)
            write_text(out, "runtime-android.logcat", logcat)
            events = parse_events(logcat)
            write_text(out, "events.json", json.dumps(events, indent=2))
            status = {event.get("stage") for event in events if event.get("status") == "PASS"}
            failures = [event for event in events if event.get("status") == "FAIL"]
            if failures or REQUIRED.issubset(status):
                break
        result["events"] = len(events)
        result["passedStages"] = sorted({e.get("stage") for e in events if e.get("status") == "PASS"})
        result["failedStages"] = [e for e in events if e.get("status") == "FAIL"]
        result["elapsedSeconds"] = round(time.monotonic() - start, 1)
        if result["failedStages"]:
            raise RuntimeError("SQLite application reported failure: " + str(result["failedStages"]))
        missing = REQUIRED.difference(result["passedStages"])
        if missing:
            logcat = (out / "runtime-android.logcat").read_text(errors="replace")
            suspects = [line for line in logcat.splitlines() if
                        re.search(r"FATAL EXCEPTION|UnsatisfiedLinkError|dlopen failed|SIGSEGV|Fatal signal|SQLite|TC_SQLITE_EVENT", line, re.I)]
            write_text(out, "failure-hints.txt", "\n".join(suspects[-200:]))
            raise RuntimeError("SQLite result incomplete; missing " + ", ".join(sorted(missing))
                               + ". See runtime-android.logcat and failure-hints.txt")
        result["status"] = "PASS"
        print("Android SQLite plaintext PASS; stages: " + ", ".join(sorted(REQUIRED)))
    except Exception as ex:
        result["error"] = str(ex)
        print("Android SQLite smoke failure: " + str(ex), file=sys.stderr)
    finally:
        capture(out, package)
        result["finished"] = time.time()
        write_text(out, "android-execution-summary.json", json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
