#!/usr/bin/env python3
"""Run customer's Main.java + TestPermission.java example on Android 15.

Phases preserve the original UI initialization, '/sdcard/asd' File.createDir
then File.delete. Build both unmodified Java and the same code with four debug
messages. Only the trace variant is used for machine-readable PASS/FAIL.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile


def command(args, timeout=35, check=True):
    p = subprocess.run([str(x) for x in args], capture_output=True, text=True,
                       errors="replace", timeout=timeout, check=False)
    output = p.stdout + p.stderr
    if check and p.returncode != 0:
        raise RuntimeError("%r failed (%s): %s" % (args, p.returncode, output[-2000:]))
    return output


def save(out, name, text):
    (out / name).write_text(text, encoding="utf-8", errors="replace")


def screenshot(out, name):
    try:
        p = subprocess.run(["adb", "exec-out", "screencap", "-p"],
                           capture_output=True, timeout=20)
        if p.returncode == 0 and p.stdout.startswith(b"\x89PNG"):
            (out / name).write_bytes(p.stdout)
    except (OSError, subprocess.TimeoutExpired):
        pass


def get_package(apk):
    aapt = shutil.which("aapt")
    if not aapt:
        import os
        sdk = Path(os.environ["ANDROID_HOME"])
        candidates = sorted((sdk / "build-tools").glob("*/aapt"), reverse=True)
        if not candidates:
            raise RuntimeError("Android build-tools aapt not available")
        aapt = str(candidates[0])
    badging = command([aapt, "dump", "badging", apk])
    match = re.search(r"^package: name='([^']+)'", badging, re.M)
    if not match:
        raise RuntimeError("Cannot identify APK package")
    return match.group(1), badging, command([aapt, "dump", "permissions", apk])


def appop(package, value):
    command(["adb", "shell", "appops", "set", package,
             "MANAGE_EXTERNAL_STORAGE", value])
    status = command(["adb", "shell", "appops", "get", package,
                      "MANAGE_EXTERNAL_STORAGE"], check=False)
    if value not in status:
        raise RuntimeError("AppOp " + value + " not applied: " + status)
    return status


def focused():
    output = command(["adb", "shell", "dumpsys", "window"], timeout=25, check=False)
    return [l.strip() for l in output.splitlines()
            if "mCurrentFocus" in l or "mFocusedApp" in l]


def pid(package):
    return command(["adb", "shell", "pidof", package], check=False).strip()


def run_phase(out, package, variant, phase, seconds):
    prefix = variant + "-" + phase
    permission = "allow" if phase == "granted-before-launch" else "ignore"
    command(["adb", "shell", "am", "force-stop", package], check=False)
    # Make sure the prior phase's Settings activity is not still on top.
    command(["adb", "shell", "am", "force-stop", "com.android.settings"], check=False)
    before_appop = appop(package, permission)
    command(["adb", "logcat", "-c"], check=False)
    started = time.monotonic()
    launch = command(["adb", "shell", "monkey", "-p", package, "-c",
                      "android.intent.category.LAUNCHER", "1"], timeout=35)
    save(out, prefix + "-launch.txt", launch)
    if "Events injected: 1" not in launch:
        raise RuntimeError(prefix + ": failed to start customer app: " + launch)
    original_pid = ""
    event_logs = []
    prompt_seen = False
    grant_applied = False
    back_count = 0
    focus_observations = []
    next_screenshot = started + 2
    while time.monotonic() - started < seconds:
        time.sleep(1)
        if not original_pid:
            original_pid = pid(package)
        focus = focused()
        focus_observations.append({"seconds": round(time.monotonic()-started, 2),
                                   "focus": focus})
        if len(focus_observations) > 35:
            focus_observations = focus_observations[-35:]
        log = command(["adb", "logcat", "-d", "-v", "threadtime"],
                      timeout=25, check=False)
        save(out, prefix + "-logcat.txt", log)
        event_logs = [line.strip() for line in log.splitlines()
                      if "TC_CLIENT_MAIN " in line]
        if any("com.android.settings" in l for l in focus):
            prompt_seen = True
            if back_count == 0 or time.monotonic()-started > 8 and back_count < 2:
                screenshot(out, prefix + "-settings.png")
                if phase == "grant-in-place" and not grant_applied:
                    appop(package, "allow")
                    grant_applied = True
                command(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"],
                        timeout=20, check=False)
                back_count += 1
        finished = (any("TC_CLIENT_MAIN DELETED" in l for l in event_logs)
                    or any("TC_CLIENT_MAIN FAIL" in l for l in event_logs))
        if variant == "trace" and finished:
            time.sleep(1)
            break
        if variant == "exact":
            if permission == "allow" and time.monotonic()-started > 5:
                break
            if prompt_seen and back_count and time.monotonic()-started > 7:
                break
        if time.monotonic() >= next_screenshot:
            screenshot(out, prefix + "-mid.png")
            next_screenshot = time.monotonic() + 10
    final_pid = pid(package)
    screenshot(out, prefix + "-final.png")
    log = command(["adb", "logcat", "-d", "-v", "threadtime"],
                  timeout=25, check=False)
    save(out, prefix + "-logcat.txt", log)
    event_logs = [line.strip() for line in log.splitlines() if "TC_CLIENT_MAIN " in line]
    save(out, prefix + "-focus.json", json.dumps(focus_observations, indent=2))
    result = {
        "variant": variant, "phase": phase, "elapsedSeconds": round(time.monotonic()-started, 2),
        "package": package, "originalPid": original_pid, "finalPid": final_pid,
        "sameProcess": bool(original_pid and original_pid == final_pid),
        "settingsPromptSeen": prompt_seen, "grantAppliedWhileSettingsOpen": grant_applied,
        "settingsBackCount": back_count,
        "nativeAccessAllowedInitially": permission == "allow",
        "fileDirCreated": any("TC_CLIENT_MAIN CREATED" in l for l in event_logs),
        "fileDirDeleted": any("TC_CLIENT_MAIN DELETED" in l for l in event_logs),
        "fileDirFailed": any("TC_CLIENT_MAIN FAIL" in l for l in event_logs),
        "debugEvents": event_logs,
        "lastFocus": focus_observations[-1] if focus_observations else {},
        "appopAfter": command(["adb", "shell", "appops", "get", package, "MANAGE_EXTERNAL_STORAGE"], check=False),
        "storageDirAfter": command(["adb", "shell", "ls", "-ld", "/sdcard/asd"], check=False),
    }
    save(out, prefix + "-summary.json", json.dumps(result, indent=2))
    print(variant, phase, "PID", original_pid, "->", final_pid,
          "prompt", prompt_seen, "grant", grant_applied,
          "created", result["fileDirCreated"],
          "deleted", result["fileDirDeleted"],
          "failed", result["fileDirFailed"], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("android-client-main-results"))
    parser.add_argument("--timeout", type=int, default=65)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    all_results = {"overall": "FAIL", "deviceSdk": None, "variants": {}, "phases": [],
                   "customerSource": "Main.zip: Main.java and TestPermission.java"}
    try:
        command(["adb", "wait-for-device"])
        all_results["deviceSdk"] = command(
            ["adb", "shell", "getprop", "ro.build.version.sdk"]).strip()
        for variant in ("exact", "trace"):
            apks = sorted((out / variant / "deployed").rglob("*.apk"))
            if len(apks) != 1:
                raise RuntimeError("Expected one APK for " + variant + ": " + repr(apks))
            apk = apks[0]
            package, badging, permissions = get_package(apk)
            save(out, variant + "-apk-badging.txt", badging)
            save(out, variant + "-apk-permissions.txt", permissions)
            if "android.permission.MANAGE_EXTERNAL_STORAGE" not in permissions:
                raise RuntimeError(variant + " does not declare MANAGE_EXTERNAL_STORAGE")
            command(["adb", "install", "--abi", "arm64-v8a", "-r", apk], timeout=120)
            all_results["variants"][variant] = {"apk": str(apk.relative_to(out)),
                                                  "package": package}
            phases = ("denied", "grant-in-place", "granted-before-launch") if variant == "trace" else (
                "denied", "grant-in-place", "granted-before-launch")
            for phase in phases:
                run_result = run_phase(out, package, variant, phase, args.timeout
                                       if variant == "trace" else min(args.timeout, 32))
                all_results["phases"].append(run_result)
        by = {(r["variant"], r["phase"]): r for r in all_results["phases"]}
        exact_denied = by[("exact", "denied")]
        exact_in_place = by[("exact", "grant-in-place")]
        trace_denied = by[("trace", "denied")]
        trace_resume = by[("trace", "grant-in-place")]
        trace_granted = by[("trace", "granted-before-launch")]
        checks = {
            "unmodifiedOriginalLaunched": bool(exact_denied["originalPid"] and exact_in_place["originalPid"]),
            "deniedShowsPermissionSettings": trace_denied["settingsPromptSeen"],
            "deniedReportedException": trace_denied["fileDirFailed"],
            "inPlaceGrantOpensSettings": trace_resume["settingsPromptSeen"],
            "inPlaceGrantApplied": trace_resume["grantAppliedWhileSettingsOpen"],
            "inPlaceRemainsSameProcess": trace_resume["sameProcess"],
            "inPlaceCreatedAndDeleted": trace_resume["fileDirCreated"] and trace_resume["fileDirDeleted"],
            "preGrantedCreatedAndDeleted": trace_granted["fileDirCreated"] and trace_granted["fileDirDeleted"],
            "noUnexpectedTraceFailures": not (trace_resume["fileDirFailed"] or trace_granted["fileDirFailed"]),
        }
        all_results["checks"] = checks
        all_results["overall"] = "PASS" if all(checks.values()) else "FAIL"
        if all_results["overall"] != "PASS":
            raise RuntimeError("Required controls failed: " +
                               ", ".join(k for k,v in checks.items() if not v))
    except Exception as exc:
        all_results["error"] = str(exc)
        print("Customer Main.zip Android test failure:", exc, file=sys.stderr)
    finally:
        save(out, "customer-main-execution-summary.json", json.dumps(all_results, indent=2))
    return 0 if all_results["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
