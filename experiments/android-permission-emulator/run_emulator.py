#!/usr/bin/env python3
"""Run a TotalCross 7.3.0 permission coordinator experiment on an Android emulator.

Host-side orchestration only. Does not use AWS or run a TotalCross VM.
The application logs real Android File / Android SQLite behavior by its PID.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

PACKAGE = "totalcross.permissionprobe"
COMPONENT = PACKAGE + "/totalcross.android.ProbeActivity"
PREFIX = "TC_PROBE_JSON "
RUNTIME = ("android.permission.READ_EXTERNAL_STORAGE",
           "android.permission.WRITE_EXTERNAL_STORAGE")


def cmd(*args, timeout=45):
    try:
        completed = subprocess.run(args, text=True, errors="replace",
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=timeout)
        return {"exit": completed.returncode, "text": completed.stdout}
    except subprocess.TimeoutExpired as e:
        return {"exit": 124, "text": "TIMEOUT " + repr(args) + " " + str(e)}


def adb(*args, timeout=45):
    return cmd("adb", *args, timeout=timeout)


def save(where, label, content):
    target = where / label
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content if isinstance(content, str)
                      else json.dumps(content, indent=2, ensure_ascii=False, default=str) + "\n")
    return target


def current_state(where, label):
    data = {}
    for name, arguments in (
        ("dumpsys-package", ("shell", "dumpsys", "package", PACKAGE)),
        ("appops", ("shell", "appops", "get", PACKAGE)),
        ("focused-window", ("shell", "dumpsys", "window")),
    ):
        result = adb(*arguments, timeout=30)
        data[name] = result
        save(where, label + "-" + name + ".txt", result["text"])
    return data


def parse_events(logs, pid):
    events = []
    for line in logs.splitlines():
        if PREFIX not in line:
            continue
        fields = line.split(None, 5)
        if len(fields) < 6 or not fields[2].isdigit() or int(fields[2]) != pid:
            continue
        try:
            events.append(json.loads(line.split(PREFIX, 1)[1].strip()))
        except ValueError:
            continue
    return events


def process_pid():
    res = adb("shell", "pidof", "-s", PACKAGE, timeout=10)
    value = res["text"].strip().split()
    return int(value[0]) if value and value[0].isdigit() else None


def permission_ui():
    # UI dump can take several seconds. No fixed-position or language-specific taps.
    res = adb("shell", "uiautomator", "dump", "/sdcard/tc-permission-window.xml",
              timeout=18)
    if res["exit"]:
        return {"dump": res["text"], "action": "dump failed"}
    view = adb("shell", "cat", "/sdcard/tc-permission-window.xml", timeout=10)
    xml = view["text"]
    at = xml.find("<?xml")
    if at < 0:
        return {"dump": xml[:2500], "action": "missing XML"}
    try:
        root = ET.fromstring(xml[at:])
    except ET.ParseError as exc:
        return {"dump": xml[:2500], "action": "invalid XML " + str(exc)}
    candidates = []
    for node in root.iter("node"):
        label = (node.get("text", "") + " " + node.get("content-desc", "")).lower()
        identifier = node.get("resource-id", "").lower()
        if ("permission_allow_button" in identifier or
                re.search(r"\ballow\b|\bpermit\b", label)):
            bounds = re.findall(r"\[(\d+),(\d+)\]", node.get("bounds", ""))
            if len(bounds) == 2:
                x = (int(bounds[0][0]) + int(bounds[1][0])) // 2
                y = (int(bounds[0][1]) + int(bounds[1][1])) // 2
                candidates.append({"text": label, "id": identifier,
                                   "x": x, "y": y})
    if not candidates:
        return {"action": "no Allow element", "xml": xml[:6000]}
    target = candidates[0]
    tapped = adb("shell", "input", "tap", str(target["x"]), str(target["y"]),
                 timeout=12)
    return {"action": "tap" if tapped["exit"] == 0 else "tap failed",
            "candidate": target, "allCandidates": candidates, "exit": tapped["exit"]}


def grant_state(where, label, grant, revoke):
    changes = {}
    for permission in revoke:
        changes["revoke-" + permission] = adb(
            "shell", "pm", "revoke", PACKAGE, permission)
    for permission in grant:
        changes["grant-" + permission] = adb(
            "shell", "pm", "grant", PACKAGE, permission)
    save(where, label + "-changes.json", changes)
    return changes


def execute(where, label, mode, timeout=32, answer_ui=False):
    adb("shell", "am", "force-stop", PACKAGE, timeout=15)
    clear = adb("logcat", "-c", timeout=12)
    started = adb("shell", "am", "start", "-n", COMPONENT,
                  "--es", "mode", mode, timeout=25)
    save(where, label + "-launch.txt", started["text"])
    if started["exit"]:
        return {"error": "failed to start app", "launch": started}
    began = time.monotonic()
    pid = None
    events = []
    gestures = []
    last_ui_scan = 0
    log = ""
    while time.monotonic() - began < timeout:
        if pid is None:
            pid = process_pid()
        fetched = adb("logcat", "-d", "-v", "threadtime",
                      "-s", "TC_PERMISSION_PROBE:I", "*:S", timeout=15)
        log = fetched["text"]
        if pid is not None:
            events = parse_events(log, pid)
        if any(e.get("stage") == "complete" for e in events):
            break
        if answer_ui and time.monotonic() - began >= 3 and not gestures:
            result = permission_ui()
            gestures.append(result)
            save(where, label + "-permission-ui.json", result)
        time.sleep(1)
    # Collect final logcat, including stale entries for audit. Filter only own PID.
    final = adb("logcat", "-d", "-v", "threadtime", timeout=25)
    save(where, label + "-logcat.txt", final["text"])
    if pid is not None:
        events = parse_events(final["text"], pid)
    states = current_state(where, label + "-end")
    summary = {
        "label": label, "mode": mode, "pid": pid,
        "elapsedSeconds": round(time.monotonic() - began, 2),
        "status": "COMPLETED" if any(e.get("stage") == "complete" for e in events)
                  else "INCONCLUSIVE",
        "events": events, "ui": gestures,
        "grants": [
            e for e in events
            if e.get("stage", "").startswith("permissions-")
               or e.get("stage") == "permission-callback"
        ],
        "appops": states["appops"]["text"],
        "focusedWindow": states["focused-window"]["text"][-2200:],
        "logcatClear": clear,
    }
    save(where, label + "-summary.json", summary)
    print(label, summary["status"],
          [(e.get("stage"), e.get("status"), e.get("detail"))
           for e in events if (e.get("stage") in (
               "permission-callback", "permission-return", "external-file-before",
               "external-sqlite-before", "external-file-after", "external-sqlite-after",
               "private-sqlite", "permissions-before", "permissions-after-request"))],
          flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--target-sdk", type=int, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    meta = {"apk": str(args.apk), "targetSdk": args.target_sdk,
            "sdk": adb("shell", "getprop", "ro.build.version.sdk")["text"].strip(),
            "android": adb("shell", "getprop", "ro.build.version.release")["text"].strip()}
    assert meta["sdk"].isdigit(), "Emulator not booted"
    install = adb("install", "-r", str(args.apk.resolve()), timeout=180)
    save(out, "install.txt", install["text"])
    assert install["exit"] == 0, install
    save(out, "apk-manifest.txt",
         cmd("aapt", "dump", "badging", str(args.apk.resolve()))["text"])
    # Use target-specific independent subprocesses and exact runtime state.
    grant_state(out, "denied", grant=[], revoke=list(RUNTIME))
    state_before = current_state(out, "denied-before")
    runs = []
    runs.append(execute(out, "denied-direct", "direct", timeout=25))

    # Isolate the API29 selection defect: READ is already granted; WRITE denied.
    grant_state(out, "read-only", grant=[RUNTIME[0]], revoke=[RUNTIME[1]])
    runs.append(execute(out, "read-only-recovery", "request", timeout=32))

    grant_state(out, "denied-again", grant=[], revoke=list(RUNTIME))
    runs.append(execute(out, "interactive-recovery", "request", timeout=38,
                        answer_ui=True))

    # Positive control: both ADB permissions pre-granted, same APK and OS.
    grant_state(out, "all-granted", grant=list(RUNTIME), revoke=[])
    runs.append(execute(out, "pregranted-direct", "direct", timeout=25))

    meta["runs"] = runs
    save(out, "summary.json", meta)
    if any(r["status"] == "INCONCLUSIVE" for r in runs):
        print("Some scenarios were inconclusive; see uploaded evidence.")
    if not all(any(e.get("stage") == "private-sqlite" and
                   e.get("status") == "PASS" for e in r["events"]) for r in runs):
        raise RuntimeError("Private SQLite control failed: inspect emulator evidence")
    if meta["sdk"] == "29":
        # Report the measured storage result; do not mislabel a scoped-storage
        # restriction or a UI timeout as a VM regression.
        successes = [any(e.get("stage") == "external-sqlite-before"
                         and e.get("status") == "PASS" for e in run["events"])
                     for run in runs]
        print("API29 external SQLite before recovery:",
              dict(zip([r["label"] for r in runs], successes)))
    print("EMULATOR_PERMISSION_EXPERIMENT_COMPLETE", out / "summary.json")


if __name__ == "__main__":
    main()
