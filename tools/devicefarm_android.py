#!/usr/bin/env python3
"""Controlled physical Device Farm run for TC 7.3.0 Android storage regression.

Only approved four physical devices, a maximum of ONE device per ScheduleRun,
one immutable APK, and one test suite. Scheduling requires --execute and
DEVICEFARM_APPROVED_EXECUTE=true. Re-running with the same GitHub SHA + device
does not book another session; an existing run is collected instead.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen
import zipfile

import boto3
from botocore.exceptions import ClientError

from devicefarm_ios import get_details, dump, paginate

REGION = "us-west-2"
APK_SHA = "8c6190fc5425a8f33db48900e7c9e7f8b1a2b9ff13a3d4667fe9cfc1325e685a"
SOURCE_SHA = "5464c21e3107e3f1ce9c287b724829e2bb870c1d"
DEVICE_MATRIX = {
    "pixel2xl-8": {
        "arn": "arn:aws:devicefarm:us-west-2::device:F070C2816A9A444EB28ED624EDE7F789",
        "api": 27, "android": "8", "model": "Google Pixel 2 XL"},
    "pixel4-10": {
        "arn": "arn:aws:devicefarm:us-west-2::device:ECE1E6B96465457EB276CCBA1448C1B4",
        "api": 29, "android": "10", "model": "Google Pixel 4 (Unlocked)"},
    "pixel5-12": {
        "arn": "arn:aws:devicefarm:us-west-2::device:11E27BF80323455C855874FC3CC710DA",
        "api": 31, "android": "12", "model": "Google Pixel 5 (Unlocked)"},
    "pixel8-15": {
        "arn": "arn:aws:devicefarm:us-west-2::device:DE5BD47FF3BD42C3A14BF7A6EFB1BFE7",
        "api": 35, "android": "15", "model": "Google Pixel 8"},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_input(apk, generic_zip, spec, selection):
    if sha(apk) != APK_SHA:
        raise ValueError("Wrong official 7.3.0 APK; expected SHA256 " + APK_SHA
                         + ", received " + sha(apk))
    with zipfile.ZipFile(apk) as z:
        paths = set(z.namelist())
        if not any("lib/arm64-v8a/libtcvm.so" == name for name in paths):
            raise ValueError("Original APK missing arm64-v8a/libtcvm.so")
    with zipfile.ZipFile(generic_zip) as z:
        if z.testzip() is not None:
            raise ValueError("Invalid test package ZIP")
        if "tests/test_sqlite_storage.py" not in z.namelist():
            raise ValueError("Expected test script missing")
    content = spec.read_text()
    if "android_test_host:" not in content or "unittest discover" not in content:
        raise ValueError("Device Farm custom test spec incomplete")
    if selection not in DEVICE_MATRIX:
        raise ValueError("Device outside approved four-device matrix")


def make_device_zip(source_zip, out, api):
    with zipfile.ZipFile(source_zip) as source, zipfile.ZipFile(
            out, "w", compression=zipfile.ZIP_DEFLATED) as dest:
        for entry in source.infolist():
            if entry.filename == "expected-api.txt":
                continue
            dest.writestr(entry, source.read(entry.filename))
        dest.writestr("expected-api.txt", str(api) + "\n")
    with zipfile.ZipFile(out) as z:
        if z.testzip() is not None or z.read("expected-api.txt").strip() != str(api).encode():
            raise ValueError("Bad device-specific test package")


def upload(client, project, file, type):
    mime = ("application/octet-stream" if file.suffix == ".apk" else
            "application/zip" if file.suffix == ".zip" else "text/yaml")
    obj = client.create_upload(projectArn=project, name=file.name, type=type,
                               contentType=mime)["upload"]
    # Pre-signed URL is a credential. Never print or store it.
    request = Request(obj["url"], data=file.read_bytes(), method="PUT",
                      headers={"Content-Type": mime})
    with urlopen(request, timeout=180) as response:
        if response.status not in (200, 201):
            raise RuntimeError("Upload HTTP " + str(response.status))
    for _ in range(60):
        state = client.get_upload(arn=obj["arn"])["upload"]
        if state.get("status") == "SUCCEEDED":
            print("Device Farm upload verified:", type, obj["arn"], flush=True)
            return obj["arn"]
        if state.get("status") == "FAILED":
            raise RuntimeError(type + " upload failed: " + str(state.get("message")))
        time.sleep(3)
    raise TimeoutError(type + " upload did not become SUCCEEDED")


def live_device(client, selection):
    device = DEVICE_MATRIX[selection]
    found = paginate(client, "list_devices", "devices",
                     filters=[{"attribute": "ARN", "operator": "EQUALS",
                               "values": [device["arn"]]}])
    if len(found) != 1 or found[0]["arn"] != device["arn"]:
        raise RuntimeError("Selected pinned device is no longer in the AWS catalog")
    info = found[0]
    name = str(info.get("name") or "")
    os_version = str(info.get("os") or "")
    availability = str(info.get("availability") or "")
    if not os_version.startswith(device["android"] + ".") and os_version != device["android"]:
        raise RuntimeError("Pinned device OS changed: " + os_version)
    if device["model"].lower() not in name.lower():
        raise RuntimeError("Pinned device model changed: " + name)
    if info.get("platform") not in (None, "ANDROID"):
        raise RuntimeError("Selected device is not an Android device")
    if availability not in ("AVAILABLE", "HIGHLY_AVAILABLE"):
        raise RuntimeError("Selected device not available: " + availability)
    print("Validated physical device:", name, os_version, availability, flush=True)
    return {"name": name, "version": os_version,
            "availability": availability, "arn": info["arn"]}


def wait(client, arn, out, report):
    deadline = time.monotonic() + 48 * 60
    while time.monotonic() < deadline:
        r = client.get_run(arn=arn)["run"]
        report.update({"runStatus": r.get("status"), "runResult": r.get("result")})
        dump(out / "android-devicefarm-run.json", report)
        print("AWS Device Farm:", r.get("status"), r.get("result"), flush=True)
        if r.get("status") == "COMPLETED":
            return r
        time.sleep(20)
    raise TimeoutError("Device Farm run exceeded monitoring window: " + arn)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("validate", "run", "collect"))
    parser.add_argument("--device", choices=sorted(DEVICE_MATRIX), required=True)
    parser.add_argument("--project-arn", default=os.getenv("AWS_DEVICE_FARM_PROJECT_ARN"))
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--test-package", type=Path)
    parser.add_argument("--test-spec", type=Path)
    parser.add_argument("--out", type=Path, default=Path("devicefarm-android-results"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--run-arn")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    summary = {"status": "INCOMPLETE", "operation": args.operation,
               "selection": args.device, "approvedMaxDevices": 1,
               "originalApkSha256": APK_SHA, "sourceSha": SOURCE_SHA,
               "costAuthorized": args.execute,
               "githubSha": os.environ.get("GITHUB_SHA")}
    code = 1
    try:
        if not args.project_arn or ":project:" not in args.project_arn:
            raise ValueError("Missing valid AWS_DEVICE_FARM_PROJECT_ARN")
        client = boto3.client("devicefarm", region_name=REGION)
        client.get_project(arn=args.project_arn)
        if args.operation in ("validate", "run"):
            summary["device"] = live_device(client, args.device)
        if args.operation == "validate":
            summary["status"] = "PASS"
            code = 0
        elif args.operation == "run":
            if not args.execute or os.getenv("DEVICEFARM_APPROVED_EXECUTE") != "true":
                raise PermissionError("Scheduling requires --execute and DEVICEFARM_APPROVED_EXECUTE=true")
            if not args.apk or not args.test_package or not args.test_spec:
                raise ValueError("APK, test package and spec required")
            verify_input(args.apk, args.test_package, args.test_spec, args.device)
            commit = os.environ.get("GITHUB_SHA", "")
            if len(commit) < 12:
                raise RuntimeError("GITHUB_SHA required for unique one-shot run name")
            run_name = ("TC730-AndroidStorage-" + args.device + "-" + commit[:12])
            summary["name"] = run_name
            # Never schedule a second paid session under this commit/device,
            # including after workflow/job retries. Read first, then collect.
            past = paginate(client, "list_runs", "runs", arn=args.project_arn)
            matches = [r for r in past if r.get("name") == run_name]
            if matches:
                summary["runArn"] = matches[0]["arn"]
                summary["existingRunReused"] = True
                print("Existing paid run detected; not scheduling again:", matches[0]["arn"],
                      flush=True)
            else:
                device_zip = out / ("tc730-" + args.device + "-appium-tests.zip")
                make_device_zip(args.test_package, device_zip,
                                DEVICE_MATRIX[args.device]["api"])
                app_arn = upload(client, args.project_arn, args.apk, "ANDROID_APP")
                test_arn = upload(client, args.project_arn, device_zip,
                                  "APPIUM_PYTHON_TEST_PACKAGE")
                spec_arn = upload(client, args.project_arn, args.test_spec,
                                  "APPIUM_PYTHON_TEST_SPEC")
                summary["uploads"] = {"app": app_arn, "test": test_arn, "spec": spec_arn}
                # Exact ARN (not an OS-wide dynamic selection) guarantees
                # a single approved device per paid AWS ScheduleRun call.
                requested = {"projectArn": args.project_arn,
                             "appArn": app_arn, "name": run_name,
                             "deviceSelectionConfiguration": {
                                 "maxDevices": 1,
                                 "filters": [{"attribute": "ARN", "operator": "EQUALS",
                                              "values": [DEVICE_MATRIX[args.device]["arn"]]}]},
                             "test": {"type": "APPIUM_PYTHON",
                                      "testPackageArn": test_arn,
                                      "testSpecArn": spec_arn},
                             "executionConfiguration": {
                                 "jobTimeoutMinutes": 22, "videoCapture": False}}
                print("SCHEDULING APPROVED PHYSICAL DEVICE:", args.device,
                      requested["deviceSelectionConfiguration"], flush=True)
                scheduled = client.schedule_run(**requested)["run"]
                summary["runArn"] = scheduled["arn"]
                dump(out / "android-devicefarm-run.json", summary)
                print("BILLABLE RUN SCHEDULED:", scheduled["arn"], flush=True)
            result = wait(client, summary["runArn"], out, summary)
            details = get_details(client, summary["runArn"], out)
            summary["deviceFarmResult"] = result.get("result")
            summary["physicalJobCount"] = len(details.get("jobs", []))
            summary["status"] = "PASS" if result.get("result") == "PASSED" else "FAIL"
            code = 0 if summary["status"] == "PASS" else 1
        else:
            if not args.run_arn or ":run:" not in args.run_arn:
                raise ValueError("collect needs an existing run ARN")
            summary["runArn"] = args.run_arn
            result = wait(client, args.run_arn, out, summary)
            get_details(client, args.run_arn, out)
            summary["status"] = "PASS" if result.get("result") == "PASSED" else "FAIL"
            code = 0 if summary["status"] == "PASS" else 1
    except Exception as exc:
        summary["status"] = "FAIL"
        summary["error"] = str(exc)[:3000]
        print("Device Farm Android operation failed:", str(exc), file=sys.stderr)
    finally:
        dump(out / "android-devicefarm-run.json", summary)
    return code


if __name__ == "__main__":
    sys.exit(main())
