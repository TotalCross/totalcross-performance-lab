#!/usr/bin/env python3
"""Run one pinned TotalCross 7.3.0 SQLite APK on real Android emulator APIs.

This is an observational regression matrix, not a mock permission test.
Unexpected denials are *reported* rather than interpreted as CI success.
The job fails if we cannot install, launch, or run the internal SQLite probe.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile

PREFIX = "TC_SQLITE_JSON "
REQUIRED_INTERNAL = {"memory", "file-create", "file-reopen", "plaintext-header"}
REQUIRED_EXTERNAL = {
    "external-dir", "external-sqlite-create", "external-sqlite-reopen",
    "external-sqlite-header", "external-existing-db", "external-result",
}
DB_EXISTING = "/sdcard/tc-sqlite-7_3_0-existing-probe.db"
DB_CREATED = "/sdcard/tc-sqlite-7_3_0-external-probe.db"


def cmd(args, timeout=45, required=False):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        if required:
            raise RuntimeError("Timed out: " + " ".join(args)) from error
        return {"rc": 124, "output": "timeout"}
    result = {"rc": p.returncode, "output": p.stdout}
    if required and p.returncode:
        raise RuntimeError("Command failed: {}\n{}".format(" ".join(args), p.stdout[-3500:]))
    return result


def write(path, text):
    path.write_text(str(text), encoding="utf-8", errors="replace")


def record(out, name, argv, timeout=45):
    result = cmd(argv, timeout=timeout)
    write(out / name, "$ " + " ".join(argv) + "\n" + result["output"]
          + "\nEXIT_CODE=" + str(result["rc"]) + "\n")
    return result


def find_aapt():
    if shutil.which("aapt"):
        return "aapt"
    root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT", "")
    matches = sorted((Path(root) / "build-tools").glob("*/aapt"), reverse=True)
    if not matches:
        raise RuntimeError("aapt missing")
    return str(matches[0])


def parse_events(log):
    events, used = [], set()
    for line in log.splitlines():
        if PREFIX not in line:
            continue
        try:
            item = json.loads(line.split(PREFIX, 1)[1].strip())
        except ValueError:
            continue
        identity = (item.get("stage"), item.get("status"), item.get("detail"))
        if identity not in used:
            events.append(item)
            used.add(identity)
    return events


def observe_permission(out, package, phase):
    observations = []
    for label, args in [
        ("package", ["adb", "shell", "dumpsys", "package", package]),
        ("storage-appops", ["adb", "shell", "appops", "get", package]),
        ("runtime-permissions", ["adb", "shell", "pm", "list", "permissions", "-g", "-d"]),
        ("mounts", ["adb", "shell", "ls", "-lad", "/sdcard", "/storage/emulated/0"]),
    ]:
        r = record(out, phase + "-" + label + ".txt", args, timeout=35)
        observations.append({"name": label, "exit": r["rc"]})
    return observations


def make_fixture(out):
    file = out / "fixture-original.db"
    if file.exists():
        file.unlink()
    with sqlite3.connect(str(file)) as db:
        db.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("INSERT INTO fixture VALUES (1, 'preexisting-from-python')")
        db.commit()
    return file


def launch_phase(out, package, name, fixture, timeout):
    # Never leave files from another phase to hide a CREATE failure.
    cmd(["adb", "shell", "am", "force-stop", package], required=False)
    cmd(["adb", "shell", "rm", "-f", DB_CREATED], required=False)
    record(out, name + "-fixture-push.txt",
           ["adb", "push", str(fixture), DB_EXISTING], timeout=45)
    cmd(["adb", "logcat", "-c"], required=True)
    launch = record(out, name + "-launch.txt",
                    ["adb", "shell", "monkey", "-p", package, "-c",
                     "android.intent.category.LAUNCHER", "1"], timeout=40)
    if launch["rc"] != 0 or "Events injected: 1" not in launch["output"]:
        raise RuntimeError("Cannot launch probe in phase " + name + ": " + launch["output"])

    began = time.monotonic()
    last_focus = ""
    focus_trace = []
    events = []
    while time.monotonic() - began < timeout:
        time.sleep(2)
        logs = cmd(["adb", "logcat", "-d", "-v", "threadtime"], timeout=30)
        write(out / (name + "-runtime.logcat"), logs["output"])
        events = parse_events(logs["output"])
        if any(e.get("stage") == "external-result" for e in events):
            break
        if any(e.get("stage") == "result" and e.get("status") == "FAIL" for e in events):
            break
        focus = cmd(["adb", "shell", "dumpsys", "window"], timeout=15)
        match = [x.strip() for x in focus["output"].splitlines()
                 if "mCurrentFocus" in x or "mFocusedApp" in x]
        current = " ".join(match)
        if current != last_focus:
            focus_trace.append({"at": round(time.monotonic()-began, 1), "focus": current})
            last_focus = current
        # Dismiss a dialog without granting; this tests whether the engine
        # resumes after denial instead of hanging on a permissions/settings UI.
        permission_ui = ("com.android.settings", "permissioncontroller",
                         "packageinstaller")
        if any(x in current.lower() for x in permission_ui):
            record(out, name + "-permission-dialog.txt",
                   ["adb", "shell", "dumpsys", "window"], timeout=20)
            cmd(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"], timeout=15)

    passed = {e.get("stage") for e in events if e.get("status") == "PASS"}
    failed = [e for e in events if e.get("status") == "FAIL"]
    external = "PASS" if REQUIRED_EXTERNAL.issubset(passed) and not failed else (
        "FAIL" if any(e.get("stage") == "external-result" for e in failed) else "INCONCLUSIVE")
    internal = REQUIRED_INTERNAL.issubset(passed)
    result = {
        "phase": name, "elapsedSeconds": round(time.monotonic()-began, 1),
        "internalPassed": internal, "externalResult": external,
        "passedStages": sorted(passed), "failedEvents": failed,
        "eventCount": len(events), "focusHistory": focus_trace,
        "sawPermissionUI": any(any(p in str(x).lower() for p in
                                   ("com.android.settings", "permissioncontroller", "packageinstaller"))
                               for x in focus_trace),
    }
    write(out / (name + "-events.json"), json.dumps(events, indent=2))
    write(out / (name + "-summary.json"), json.dumps(result, indent=2))
    observe_permission(out, package, name)
    return result


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--api-level", type=int, choices=(24, 29, 35), required=True)
    arg.add_argument("--out", type=Path, default=Path("sqlite-smoke-results"))
    arg.add_argument("--timeout", type=int, default=55)
    args = arg.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = {"status": "INCOMPLETE", "requestedApi": args.api_level,
              "sdkRun": 40878222908, "sdkSource": "5464c21e3107e3f1ce9c287b724829e2bb870c1d",
              "apkSourceArtifact": 14007058527, "phases": {}, "startedAt": time.time()}
    package = None
    try:
        apklist = sorted((out / "deployed" / "install" / "android").glob("*.apk"))
        if len(apklist) != 1:
            raise RuntimeError("Expected exactly one pinned APK, found " + str(apklist))
        apk = apklist[0]
        result["apkSha256"] = hashlib.sha256(apk.read_bytes()).hexdigest()
        with zipfile.ZipFile(apk) as z:
            abis = sorted({p.split("/")[1] for p in z.namelist()
                           if p.startswith("lib/") and p.endswith(".so")})
        result["apkAbis"] = abis
        with zipfile.ZipFile(apk) as z:
            native_abis = sorted({p.split("/")[1] for p in z.namelist()
                                  if p.startswith("lib/") and p.endswith("/libtcvm.so")})
        result["nativeVmAbis"] = native_abis
        aapt = find_aapt()
        badging = record(out, "apk-badging.txt", [aapt, "dump", "badging", str(apk)])
        permissions = record(out, "apk-permissions.txt", [aapt, "dump", "permissions", str(apk)])
        if badging["rc"] or permissions["rc"]:
            raise RuntimeError("Cannot inspect APK manifest")
        p = re.search(r"^package: name='([^']+)'", badging["output"], re.M)
        if not p:
            raise RuntimeError("APK package name not found")
        package = p.group(1)
        result["package"] = package
        result["manifest"] = {
            "readExternal": "android.permission.READ_EXTERNAL_STORAGE" in permissions["output"],
            "writeExternal": "android.permission.WRITE_EXTERNAL_STORAGE" in permissions["output"],
            "manageExternal": "android.permission.MANAGE_EXTERNAL_STORAGE" in permissions["output"],
            "minSdk": re.search(r"sdkVersion:'([^']+)'", badging["output"]).group(1),
            "targetSdk": re.search(r"targetSdkVersion:'([^']+)'", badging["output"]).group(1),
        }
        device_api = cmd(["adb", "shell", "getprop", "ro.build.version.sdk"], required=True)["output"].strip()
        device_version = cmd(["adb", "shell", "getprop", "ro.build.version.release"], required=True)["output"].strip()
        device_abis = cmd(["adb", "shell", "getprop", "ro.product.cpu.abilist"], required=True)["output"].strip().split(",")
        result["device"] = {"api": device_api, "release": device_version, "abis": device_abis}
        if int(device_api) != args.api_level:
            raise RuntimeError("Emulator API mismatch, got " + device_api)
        selected = next((abi for abi in device_abis if abi in native_abis), None)
        if not selected:
            raise RuntimeError("No native VM ABI available: VM=" + str(native_abis) + " emulator=" + str(device_abis))
        result["installedAbi"] = selected
        install = record(out, "install.txt",
                         ["adb", "install", "--abi", selected, "-r", str(apk)], timeout=160)
        if install["rc"] or "Success" not in install["output"]:
            raise RuntimeError("APK install failed: " + install["output"])
        observe_permission(out, package, "after-install")
        fixture = make_fixture(out)

        # Clean install, all relevant storage permissions denied.
        if args.api_level >= 30:
            record(out, "deny-all-files.txt",
                   ["adb", "shell", "appops", "set", package, "MANAGE_EXTERNAL_STORAGE", "ignore"])
        if result["manifest"]["writeExternal"]:
            record(out, "revoke-write.txt",
                   ["adb", "shell", "pm", "revoke", package, "android.permission.WRITE_EXTERNAL_STORAGE"])
        if result["manifest"]["readExternal"]:
            record(out, "revoke-read.txt",
                   ["adb", "shell", "pm", "revoke", package, "android.permission.READ_EXTERNAL_STORAGE"])
        result["phases"]["denied"] = launch_phase(out, package, "denied", fixture, args.timeout)

        if args.api_level <= 29:
            # Android 7 and Android 10 use runtime WRITE_EXTERNAL_STORAGE.
            # No declaration of READ_EXTERNAL_STORAGE is artificially inserted.
            grant = record(out, "grant-write.txt",
                           ["adb", "shell", "pm", "grant", package,
                            "android.permission.WRITE_EXTERNAL_STORAGE"])
            result["manualWriteGrant"] = grant
            result["phases"]["write-granted"] = launch_phase(out, package,
                                                            "write-granted", fixture, args.timeout)
        else:
            grant = record(out, "grant-all-files.txt",
                           ["adb", "shell", "appops", "set", package,
                            "MANAGE_EXTERNAL_STORAGE", "allow"])
            result["manualManageGrant"] = grant
            result["phases"]["all-files-granted"] = launch_phase(out, package,
                                                                "all-files-granted", fixture, args.timeout)

        if not any(phase["internalPassed"] for phase in result["phases"].values()):
            raise RuntimeError("No successful internal File/SQLite stages; inspect runtime logs")
        if all(phase["externalResult"] == "INCONCLUSIVE" for phase in result["phases"].values()):
            raise RuntimeError("No conclusive external-storage stage; inspect permission dialogs / crashes")
        result["status"] = "COMPLETE"
        print("OBSERVED_STORAGE_MATRIX " + json.dumps({
            "api": args.api_level, "apkSha256": result["apkSha256"],
            "phases": {k: {"internal": v["internalPassed"],
                            "external": v["externalResult"],
                            "prompt": v["sawPermissionUI"]}
                       for k, v in result["phases"].items()}
        }))
    except Exception as e:
        result["status"] = "INCOMPLETE"
        result["error"] = str(e)
        print("Android API matrix could not complete: " + str(e), file=sys.stderr)
    finally:
        if package:
            record(out, "final-package.txt", ["adb", "shell", "dumpsys", "package", package], timeout=30)
            record(out, "final-appops.txt", ["adb", "shell", "appops", "get", package], timeout=30)
        result["finishedAt"] = time.time()
        write(out / "android-api-matrix-summary.json", json.dumps(result, indent=2))
    return 0 if result["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
