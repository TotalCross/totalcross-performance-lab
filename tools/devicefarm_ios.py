#!/usr/bin/env python3
"""AWS Device Farm iOS probe: validate, package, schedule, poll and archive.

Scheduling requires an explicit --execute switch; validation/upload never
consumes physical-device minutes. Credentials come only from GitHub OIDC.
No AWS key, presigned URL or customer data is written to Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen
import zipfile

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests/devicefarm-ios"
REGION = "us-west-2"
FINAL = {"COMPLETED", "STOPPING"}
DONE_UPLOAD = {"SUCCEEDED", "FAILED"}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))[:100]


def make_package(out):
    target = out / "devicefarm-appium-python.zip"
    paths = [TEST_ROOT / "requirements.txt"]
    paths += sorted((TEST_ROOT / "tests").glob("test_*.py"))
    wheels = sorted((TEST_ROOT / "wheelhouse").glob("*.whl"))
    if not wheels:
        raise RuntimeError("wheelhouse missing; run pip download before packaging")
    incompatible = [p.name for p in wheels if not p.name.endswith("-none-any.whl")]
    if incompatible:
        raise RuntimeError("Non-portable wheels would fail on macOS Device Farm: "
                           + str(incompatible))
    paths.extend(wheels)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(TEST_ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        assert "requirements.txt" in names and "tests/test_ios_probe.py" in names
        assert archive.testzip() is None
    print("Appium Python test bundle:", target, "(", len(wheels), "wheels )")
    return target


def get_client():
    return boto3.client("devicefarm", region_name=REGION)


def verify_project_and_pool(client, project_arn, pool_arn):
    prefix = "arn:aws:devicefarm:" + REGION + ":"
    if not project_arn.startswith(prefix) or ":project:" not in project_arn:
        raise ValueError("Invalid us-west-2 project ARN")
    if not pool_arn.startswith(prefix) or ":devicepool:" not in pool_arn:
        raise ValueError("Invalid us-west-2 device pool ARN")
    if project_arn.split(":")[4] != pool_arn.split(":")[4]:
        raise ValueError("Device Pool and Project must be in the same AWS account")
    project = client.get_project(arn=project_arn)["project"]
    print("Device Farm project:", project.get("name"), project["arn"])
    pools = []
    cursor = None
    while True:
        kwargs = {"arn": project_arn}
        if cursor:
            kwargs["nextToken"] = cursor
        response = client.list_device_pools(**kwargs)
        pools += response.get("devicePools", [])
        cursor = response.get("nextToken")
        if not cursor:
            break
    match = [pool for pool in pools if pool.get("arn") == pool_arn]
    if not match:
        print("Provided device pool ARN is not valid for this project:", pool_arn)
        print("Available pools:", [(p.get("name"), p.get("arn")) for p in pools])
        preferred = [p for p in pools if p.get("name", "").lower() == "iphone"]
        suggestion = preferred[0].get("arn") if len(preferred) == 1 else None
        raise RuntimeError("Device pool mismatch; choose a project-specific iOS pool"
                           + (". Suggested 'iphone' pool: " + suggestion if suggestion else "")
                           + ". Update GitHub AWS_DEVICE_FARM_DEVICE_POOL_ARN and the IAM ScheduleRun policy.")
    pool_max = match[0].get("maxDevices")
    print("Selected device pool:", match[0].get("name"), pool_arn,
          "maxDevices:", pool_max, "type:", match[0].get("type"))
    return {"projectArn": project_arn, "projectName": project.get("name"),
            "devicePoolArn": pool_arn,
            "devicePoolName": match[0].get("name"),
            "poolMaxDevices": pool_max,
            "poolListedForProject": True,
            "awsRegion": REGION}


def upload(client, project, source, upload_type):
    print("Creating Device Farm upload:", upload_type, source.name)
    mime_type = ("application/octet-stream" if source.suffix == ".ipa"
                 else "application/zip" if source.suffix == ".zip"
                 else "text/yaml")
    obj = client.create_upload(projectArn=project, name=source.name,
                               type=upload_type, contentType=mime_type)["upload"]
    url = obj["url"]
    # Never log/persist this presigned S3 URL. Match the Content-Type signed by S3.
    req = Request(url, data=source.read_bytes(), method="PUT",
                  headers={"Content-Type": mime_type})
    with urlopen(req, timeout=180) as response:
        if response.status not in (200, 201):
            raise RuntimeError("Upload PUT failed: HTTP " + str(response.status))
    arn = obj["arn"]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        status = client.get_upload(arn=arn)["upload"]
        if status.get("status") in DONE_UPLOAD:
            if status["status"] != "SUCCEEDED":
                raise RuntimeError(upload_type + " upload failed: " + str(status.get("message"))
                                   + " (" + arn + ")")
            print(upload_type, "uploaded successfully:", arn)
            return arn
        time.sleep(4)
    raise TimeoutError("Timed out waiting for " + upload_type + ": " + arn)


def paginate(client, op, key, **kwargs):
    token = None
    output = []
    while True:
        args = dict(kwargs)
        if token:
            args["nextToken"] = token
        response = getattr(client, op)(**args)
        output.extend(response.get(key, []))
        token = response.get("nextToken")
        if not token:
            return output


def artifact_dump(client, arn, out, kind, index):
    entries = []
    for typ in ("FILE", "LOG", "SCREENSHOT"):
        try:
            values = paginate(client, "list_artifacts", "artifacts", arn=arn, type=typ)
        except ClientError as error:
            entries.append({"type": typ, "error": str(error)})
            continue
        for n, item in enumerate(values):
            # URL is a presigned credential: never retain it in public artifacts.
            meta = {"name": item.get("name"), "type": item.get("type"),
                    "extension": item.get("extension"), "arn": item.get("arn")}
            url = item.get("url")
            if not url:
                entries.append(dict(meta, error="No download URL"))
                continue
            filename = ("%s_%03d_%s.%s" %
                        (typ.lower(), n, safe_name(item.get("name", "artifact")),
                         safe_name(item.get("extension") or "bin")))
            dest = out / kind / str(index) / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                with urlopen(url, timeout=100) as stream, dest.open("wb") as target:
                    import shutil
                    shutil.copyfileobj(stream, target)
                entries.append(dict(meta, localPath=str(dest.relative_to(out)),
                                    bytes=dest.stat().st_size))
            except Exception as error:
                entries.append(dict(meta, error=str(error)))
    return entries


def get_details(client, run_arn, out):
    summaries = {}
    for op, field, arg in [
        ("get_run", "run", run_arn),
    ]:
        try:
            item = getattr(client, op)(arn=arg)[field]
            item.pop("networkProfile", None)
            summaries[field] = item
        except ClientError as error:
            summaries[field + "Error"] = str(error)
    jobs = paginate(client, "list_jobs", "jobs", arn=run_arn)
    summaries["jobs"] = jobs
    summaries["artifacts"] = {"run": artifact_dump(client, run_arn, out, "run", 0)}
    summaries["artifacts"]["jobs"] = {}
    for i, job in enumerate(jobs):
        job_arn = job["arn"]
        summaries["artifacts"]["jobs"][job_arn] = artifact_dump(client, job_arn, out, "job", i)
        try:
            suites = paginate(client, "list_suites", "suites", arn=job_arn)
            summaries.setdefault("suites", {})[job_arn] = suites
        except ClientError as error:
            summaries.setdefault("suiteErrors", {})[job_arn] = str(error)
            continue
        for j, suite in enumerate(suites):
            suite_arn = suite["arn"]
            summaries["artifacts"].setdefault("suites", {})[suite_arn] = artifact_dump(
                client, suite_arn, out, "suite", i * 1000 + j)
            try:
                tests = paginate(client, "list_tests", "tests", arn=suite_arn)
                summaries.setdefault("tests", {})[suite_arn] = tests
            except ClientError as error:
                summaries.setdefault("testErrors", {})[suite_arn] = str(error)
                continue
            for k, test in enumerate(tests):
                test_arn = test["arn"]
                summaries["artifacts"].setdefault("tests", {})[test_arn] = artifact_dump(
                    client, test_arn, out, "test", i * 100000 + j * 100 + k)
    dump(out / "devicefarm-results.json", summaries)
    return summaries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("validate", "package", "run"))
    parser.add_argument("--project-arn", default=os.getenv("AWS_DEVICE_FARM_PROJECT_ARN"))
    parser.add_argument("--pool-arn", default=os.getenv("AWS_DEVICE_FARM_DEVICE_POOL_ARN"))
    parser.add_argument("--ipa", type=Path)
    parser.add_argument("--out", type=Path, default=Path("sqlite-smoke-results"))
    parser.add_argument("--execute", action="store_true",
                        help="Mandatory explicit approval before billable Device Farm execution")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    summary = {"operation": args.operation, "status": "FAIL"}
    try:
        if args.operation == "package":
            summary["package"] = str(make_package(out))
            summary["status"] = "PASS"
            return 0
        if not args.project_arn or not args.pool_arn:
            raise RuntimeError("Missing AWS_DEVICE_FARM_PROJECT_ARN or AWS_DEVICE_FARM_DEVICE_POOL_ARN")
        client = get_client()
        summary.update(verify_project_and_pool(client, args.project_arn, args.pool_arn))
        if args.operation == "validate":
            summary["status"] = "PASS"
            print("OIDC and project/device-pool access verified. No device run scheduled.")
            return 0
        if not args.execute:
            raise RuntimeError("Paid device test requires explicit --execute")
        if summary.get("poolMaxDevices") != 1:
            raise RuntimeError("For cost protection, the selected pool must have maxDevices=1 "
                               "(currently %r). Set Max devices to 1 in AWS Device Farm."
                               % summary.get("poolMaxDevices"))
        if not args.ipa or not args.ipa.is_file():
            raise RuntimeError("IPA missing; build from the pinned 7.3.0 SDK first")
        bundle = out / "devicefarm-appium-python.zip"
        if not bundle.is_file():
            raise RuntimeError("Appium package missing; execute 'package' first")
        spec = TEST_ROOT / "devicefarm-test-spec.yml"
        app_arn = upload(client, args.project_arn, args.ipa, "IOS_APP")
        test_arn = upload(client, args.project_arn, bundle, "APPIUM_PYTHON_TEST_PACKAGE")
        spec_arn = upload(client, args.project_arn, spec, "APPIUM_PYTHON_TEST_SPEC")
        summary["uploads"] = {"app": app_arn, "tests": test_arn, "testSpec": spec_arn}
        run = client.schedule_run(
            projectArn=args.project_arn,
            devicePoolArn=args.pool_arn,
            appArn=app_arn,
            name="TotalCross-7.3.0-iOS-File-SQLite",
            test={"type": "APPIUM_PYTHON", "testPackageArn": test_arn,
                  "testSpecArn": spec_arn},
            executionConfiguration={"jobTimeoutMinutes": 15,
                                    "videoCapture": True,
                                    "skipAppResign": False},
        )["run"]
        run_arn = run["arn"]
        summary["runArn"] = run_arn
        # Save the run identifier immediately, even if the runner later times out.
        dump(out / "devicefarm-run.json", summary)
        print("Scheduled physical iOS Device Farm test:", run_arn, flush=True)
        deadline = time.monotonic() + 40 * 60
        while time.monotonic() < deadline:
            state = client.get_run(arn=run_arn)["run"]
            summary["runStatus"] = state.get("status")
            summary["runResult"] = state.get("result")
            dump(out / "devicefarm-run.json", summary)
            print("Device Farm:", state.get("status"), state.get("result"), flush=True)
            if state.get("status") == "COMPLETED":
                break
            time.sleep(20)
        else:
            raise TimeoutError("Device Farm run took >40 minutes; run ARN: " + run_arn)
        details = get_details(client, run_arn, out)
        result = details.get("run", {}).get("result")
        summary["status"] = "PASS" if result == "PASSED" else "FAIL"
        if result != "PASSED":
            summary["error"] = "Device Farm returned " + str(result)
        print("Physical iOS Device Farm result:", result)
        return 0 if summary["status"] == "PASS" else 1
    except Exception as exc:
        summary["error"] = str(exc)
        print("Device Farm error:", exc, file=sys.stderr)
        return 1
    finally:
        summary["finished"] = time.time()
        dump(out / "devicefarm-summary.json", summary)
        path = os.getenv("GITHUB_STEP_SUMMARY")
        if path:
            with open(path, "a", encoding="utf-8") as stream:
                stream.write("### iOS Device Farm\n\n")
                stream.write("- Operation: `%s`\n" % args.operation)
                stream.write("- Status: **%s**\n" % summary["status"])
                if summary.get("runArn"):
                    stream.write("- Run ARN: `%s`\n" % summary["runArn"])
                if summary.get("error"):
                    stream.write("- Error: `%s`\n" % summary["error"])


if __name__ == "__main__":
    sys.exit(main())
