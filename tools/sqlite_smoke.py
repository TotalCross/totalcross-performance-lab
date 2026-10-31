#!/usr/bin/env python3
"""Build/deploy and run the exact TotalCross 7.3.0 package SQLite smoke test."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import zipfile

RUN_ID = 40878222908
ARTIFACT_ID = 12899147776
SOURCE_SHA = "5464c21e3107e3f1ce9c287b724829e2bb870c1d"
PREFIX = "sqlite-plaintext-smoke"
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/sqlite-plaintext/src/totalcross/lab/sqlite/SQLitePlaintextProbe.java"
TARGETS = {"windows": "win32", "macos": "macos", "linux-x64": "linux",
           "linux-arm64": "linux_arm", "linux-arm32": "linux_arm",
           "android": "android", "ios": "ios"}
DESKTOP = {"windows": ".exe", "macos": "", "linux-x64": ""}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def invoke(args, cwd, log, env=None, timeout=900):
    with open(log, "a", encoding="utf-8") as f:
        f.write("$ " + " ".join(map(str, args)) + "\n")
        f.flush()
        try:
            p = subprocess.run(list(map(str, args)), cwd=str(cwd), env=env, text=True,
                               stdout=f, stderr=subprocess.STDOUT, timeout=timeout, check=False)
            f.write("\nEXIT_CODE=" + str(p.returncode) + "\n")
            if p.returncode:
                raise RuntimeError("Command failed (" + str(p.returncode) + "); inspect " + str(log))
            return p
        except subprocess.TimeoutExpired:
            f.write("\nTIMEOUT after " + str(timeout) + " seconds\n")
            raise


def find_sdk(root):
    matches = sorted(p.parent for p in root.rglob("totalcross-sdk-7.3.0.jar")
                     if "dist" in p.parts)
    if not matches:
        matches = sorted(p.parent for p in root.rglob("totalcross-sdk.jar") if "dist" in p.parts)
    for dist in matches:
        home = dist.parent
        if (home / "etc").is_dir() and (dist / "libs").is_dir():
            return home, dist
    raise RuntimeError("SDK layout invalid: expected dist/*.jar, dist/libs and etc")


def extract(package_zip, target, out):
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(package_zip) as z:
        for entry in z.infolist():
            dest = (target / entry.filename).resolve()
            if not dest.is_relative_to(target.resolve()):
                raise RuntimeError("unsafe archive path: " + entry.filename)
        z.extractall(target)
    home, dist = find_sdk(target)
    inventory = {
        "workflowRunId": RUN_ID, "artifactId": ARTIFACT_ID, "sourceSha": SOURCE_SHA,
        "artifactZip": str(package_zip), "artifactZipSha256": sha(package_zip),
        "sdkHome": str(home), "sdkJar": str(dist),
        "sdkJarSha256": sha(dist / "totalcross-sdk-7.3.0.jar"
                            if (dist / "totalcross-sdk-7.3.0.jar").is_file()
                            else dist / "totalcross-sdk.jar"),
    }
    (out / "provenance.json").write_text(json.dumps(inventory, indent=2))
    return home, dist


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["build", "execute"])
    p.add_argument("--target", choices=sorted(TARGETS), required=True)
    p.add_argument("--package", type=Path)
    p.add_argument("--out", type=Path, default=Path("sqlite-smoke-results"))
    args = p.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {"target": args.target, "mode": args.mode, "host": platform.platform(),
              "python": sys.version, "sourceSha": SOURCE_SHA, "runId": RUN_ID,
              "status": "FAIL", "started": time.time()}
    try:
        if args.mode == "build":
            if not args.package:
                p.error("--package required to build")
            home, dist = extract(args.package.resolve(), out / "official-sdk", out)
            sdkjar = dist / "totalcross-sdk-7.3.0.jar"
            if not sdkjar.is_file():
                sdkjar = dist / "totalcross-sdk.jar"
            libs = dist / "libs"
            env = os.environ.copy()
            env["TOTALCROSS3_HOME"] = str(home)
            classes = out / "classes"
            classes.mkdir(exist_ok=True)
            cp = os.pathsep.join([str(sdkjar), str(libs / "*")])
            invoke(["javac", "--release", "8", "-cp", cp, "-d", classes, SOURCE],
                   out, out / "compile.log", env)
            jar = out / (PREFIX + ".jar")
            invoke(["jar", "cf", jar, "-C", classes, "."], out, out / "compile.log", env)
            deployed = out / "deployed"
            deployed.mkdir(exist_ok=True)
            cmd = ["java", "-cp", os.pathsep.join([str(classes), cp]), "tc.Deploy",
                   jar, "-" + TARGETS[args.target], "/p", "/n", PREFIX,
                   "/o", str(deployed) + os.sep]
            invoke(cmd, out, out / "deploy.log", env, timeout=1800)
            outputs = [f.relative_to(deployed).as_posix() for f in deployed.rglob("*") if f.is_file()]
            if not outputs:
                raise RuntimeError("Deployer returned success but produced no files")
            (out / "deployment-files.json").write_text(json.dumps(outputs, indent=2))
            report["outputFiles"] = len(outputs)
            report["status"] = "PASS"
        else:
            if args.target not in DESKTOP:
                raise RuntimeError("Execution only supported for desktop; mobile artifacts are deploy-only")
            path = out / "deployed" / TARGETS[args.target]
            executable = path / (PREFIX + DESKTOP[args.target])
            if not executable.is_file():
                raise RuntimeError("Missing native executable: " + str(executable))
            if args.target != "windows":
                executable.chmod(executable.stat().st_mode | 0o111)
            # The VM may write to its appPath; execute in a fresh isolated home.
            env = os.environ.copy()
            sandbox = out / "runtime-home"
            sandbox.mkdir(exist_ok=True)
            if args.target == "linux-x64":
                env["LD_LIBRARY_PATH"] = str(path) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
            if args.target == "macos":
                env["DYLD_LIBRARY_PATH"] = str(path) + os.pathsep + env.get("DYLD_LIBRARY_PATH", "")
            cmd = [str(executable)]
            if args.target == "linux-x64":
                cmd = ["xvfb-run", "-a", *cmd]
            log = out / "runtime.log"
            try:
                invoke(cmd, path, log, env, timeout=120)
            except Exception:
                pass  # Parse structured events even when the VM crashes or exits nonzero.
            output = log.read_text(encoding="utf-8", errors="replace")
            entries = []
            for line in output.splitlines():
                if "TC_SQLITE_JSON " in line:
                    payload = line.split("TC_SQLITE_JSON ", 1)[1]
                    try:
                        entries.append(json.loads(payload))
                    except json.JSONDecodeError:
                        entries.append({"unparseable": payload})
            (out / "events.json").write_text(json.dumps(entries, indent=2))
            required = {"memory", "file-create", "file-reopen", "plaintext-header", "result"}
            passing = {x.get("stage") for x in entries if x.get("status") == "PASS"}
            report["stagesPassed"] = sorted(passing)
            report["events"] = len(entries)
            if not required.issubset(passing) or any(x.get("status") == "FAIL" for x in entries):
                raise RuntimeError("SQLite probe did not produce successful events for " +
                                   ", ".join(sorted(required - passing)))
            report["status"] = "PASS"
    except BaseException as e:
        report["error"] = str(e)
        print("SQLite smoke failure:", e, file=sys.stderr)
    finally:
        report["finished"] = time.time()
        (out / ("build-summary.json" if args.mode == "build" else "execution-summary.json")).write_text(
            json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
