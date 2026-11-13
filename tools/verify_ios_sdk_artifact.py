#!/usr/bin/env python3
"""Validate and download a TotalCross SDK artifact from a source-pinned GH run.

No AWS access. Only a successful iOS build + Package TotalCross may be used.
The complete workflow may still have unrelated macOS/desktop tests queued.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

UPSTREAM_REPO = "TotalCross/totalcross"


def gh_api(path, binary=False, destination=None):
    command = ["gh", "api", "repos/" + UPSTREAM_REPO + "/" + path]
    if binary:
        with open(destination, "wb") as output:
            subprocess.run(command, stdout=output, check=True)
        return None
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return "sha256:" + digest.hexdigest()


def check_jobs(run_id):
    jobs = gh_api("actions/runs/" + str(run_id) + "/jobs?per_page=100")["jobs"]
    required = ("build / Build `iOS`", "Package TotalCross")
    pending = []
    for label in required:
        matching = [job for job in jobs if job["name"] == label]
        if not matching:
            pending.append(label + " (not created)")
            continue
        if len(matching) != 1:
            raise RuntimeError("Ambiguous upstream job: " + label)
        job = matching[0]
        if job["status"] != "completed":
            pending.append(label + " (" + job["status"] + ")")
        elif job["conclusion"] != "success":
            raise RuntimeError("Upstream job failed: " + label + ", "
                               + str(job["conclusion"]))
    return pending, [{"name": job["name"], "id": job["id"],
                      "conclusion": job["conclusion"]} for job in jobs
                     if job["name"] in required]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk-run-id", type=int, required=True)
    parser.add_argument("--sdk-source-sha", required=True)
    parser.add_argument("--sdk-version", required=True)
    parser.add_argument("--sdk-artifact-id", default="", help="Optional exact ID")
    parser.add_argument("--expected-digest", default="", help="Optional sha256:<hex>")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-fA-F0-9]{40}", args.sdk_source_sha):
        parser.error("--sdk-source-sha must be 40 hex characters")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.sdk_version):
        parser.error("--sdk-version must be like 7.3.0")
    if args.sdk_run_id <= 0 or args.wait_seconds < 0:
        parser.error("Invalid run ID or wait interval")
    if args.sdk_artifact_id and not re.fullmatch(r"[0-9]+", args.sdk_artifact_id):
        parser.error("--sdk-artifact-id must be numeric")
    if args.expected_digest and not re.fullmatch(
            r"sha256:[0-9a-fA-F]{64}", args.expected_digest):
        parser.error("--expected-digest must be sha256:<64 hex>")
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("GH_TOKEN required to access upstream CI metadata")
    args.out.mkdir(parents=True, exist_ok=True)
    run = gh_api("actions/runs/" + str(args.sdk_run_id))
    if run["id"] != args.sdk_run_id or run["head_sha"].lower() != args.sdk_source_sha.lower():
        raise RuntimeError("Upstream workflow source SHA mismatch")
    if run["name"] != "Packages `totalcross`":
        raise RuntimeError("Expected TotalCross SDK package workflow, got "
                           + str(run["name"]))

    deadline = time.monotonic() + args.wait_seconds
    while True:
        pending, verified_jobs = check_jobs(args.sdk_run_id)
        if not pending:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Upstream iOS/package jobs not yet successful: "
                               + ", ".join(pending))
        print("Waiting for upstream package:", ", ".join(pending), flush=True)
        time.sleep(min(30, max(1, deadline - time.monotonic())))

    artifacts = gh_api("actions/runs/" + str(args.sdk_run_id)
                       + "/artifacts?per_page=100")["artifacts"]
    selected = [item for item in artifacts
                if item["name"] == "TotalCross-" + args.sdk_version
                and not item["expired"]
                and (not args.sdk_artifact_id
                     or str(item["id"]) == args.sdk_artifact_id)]
    if len(selected) != 1:
        raise RuntimeError("Expected one matching, unexpired SDK artifact; got "
                           + str([(item["id"], item["name"]) for item in selected]))
    artifact = selected[0]
    provenance = artifact.get("workflow_run") or {}
    if (provenance.get("id") != args.sdk_run_id or
            (provenance.get("head_sha") or "").lower() != args.sdk_source_sha.lower()):
        raise RuntimeError("SDK artifact provenance does not match requested run")
    expected = artifact.get("digest")
    if not expected or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", expected):
        raise RuntimeError("GitHub artifact missing valid SHA-256 digest")
    if args.expected_digest and expected.lower() != args.expected_digest.lower():
        raise RuntimeError("SDK artifact digest differs from requested digest")

    destination = args.out / "official-artifact.zip"
    gh_api("actions/artifacts/" + str(artifact["id"]) + "/zip",
           binary=True, destination=destination)
    actual = get_hash(destination)
    if actual.lower() != expected.lower():
        raise RuntimeError("Downloaded SDK artifact SHA-256 mismatch: "
                           + actual + " vs " + expected)
    with zipfile.ZipFile(destination) as z:
        if z.testzip() is not None:
            raise RuntimeError("Corrupted SDK GitHub artifact ZIP")
        entries = [name for name in z.namelist() if not name.endswith("/")]
        if entries != ["TotalCross-" + args.sdk_version + ".zip"]:
            raise RuntimeError("Unexpected SDK archive contents: " + str(entries))
    (args.out / "sdk-run.json").write_text(
        json.dumps({"id": run["id"], "head_sha": run["head_sha"],
                    "name": run["name"], "verifiedJobs": verified_jobs},
                   indent=2) + "\n")
    (args.out / "sdk-artifact.json").write_text(
        json.dumps({key: artifact.get(key) for key in
                    ("id", "name", "digest", "size_in_bytes", "expired")},
                   indent=2) + "\n")
    print("Verified SDK", args.sdk_version, "source", args.sdk_source_sha,
          "run", args.sdk_run_id, "artifact", artifact["id"],
          "digest", actual, flush=True)


if __name__ == "__main__":
    sys.exit(main())
