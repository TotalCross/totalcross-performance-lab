#!/usr/bin/env python3
"""Compile the iOS graphics probe against a verified, arbitrary TotalCross SDK.

Inputs describe the exact GitHub Actions source commit and artifact. They are
provenance, not hardcoded constants. The archive digest is checked separately
by verify_ios_sdk_artifact.py before this script is called.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

from inspect_ios_ipa import enable_documents_file_sharing

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/ios-graphics/src/totalcross/lab/graphics/GraphicsSmokeProbe.java"
APP_NAME = "ios-graphics-smoke"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def invoke(command, cwd, logfile, env=None, timeout=900):
    with open(logfile, "a", encoding="utf-8") as log:
        log.write("$ " + " ".join(map(str, command)) + "\n")
        log.flush()
        proc = subprocess.run([str(item) for item in command],
                              cwd=str(cwd), env=env, stdout=log,
                              stderr=subprocess.STDOUT, timeout=timeout)
        log.write("EXIT_CODE=" + str(proc.returncode) + "\n")
        if proc.returncode:
            raise RuntimeError("Command failed (" + str(proc.returncode)
                               + "): see " + str(logfile))


def unpack(archive_path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Corrupt SDK ZIP: " + str(archive_path))
        for info in archive.infolist():
            target = (root / info.filename).resolve()
            if not target.is_relative_to(root):
                raise RuntimeError("Unsafe SDK ZIP path: " + info.filename)
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise RuntimeError("SDK symlink not allowed: " + info.filename)
        archive.extractall(destination)


def extract_sdk(archive_path, target, sdk_version):
    if not sdk_version or any(ch not in "0123456789." for ch in sdk_version):
        raise ValueError("Invalid SDK version")
    if target.exists():
        shutil.rmtree(target)
    unpack(archive_path, target)
    nested = sorted(target.rglob("TotalCross-" + sdk_version + ".zip"))
    if len(nested) == 1:
        unpack(nested[0], target / "expanded")
    elif len(nested) > 1:
        raise RuntimeError("Ambiguous nested SDK archives")
    jars = list(target.rglob("totalcross-sdk-" + sdk_version + ".jar"))
    if not jars:
        jars = list(target.rglob("totalcross-sdk.jar"))
    candidates = [(jar.parent.parent, jar.parent, jar) for jar in jars
                  if jar.parent.name == "dist"
                  and (jar.parent.parent / "etc").is_dir()
                  and (jar.parent / "libs").is_dir()]
    if len(candidates) != 1:
        raise RuntimeError("Expected a unique SDK layout; found "
                           + repr([str(item[2]) for item in candidates]))
    return candidates[0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("ios-graphics-results"))
    p.add_argument("--sdk-version", required=True)
    p.add_argument("--sdk-run-id", required=True, type=int)
    p.add_argument("--sdk-source-sha", required=True)
    p.add_argument("--sdk-artifact-id", required=True, type=int)
    p.add_argument("--test-ref", required=True)
    p.add_argument("--test-sha", required=True)
    p.add_argument("--required-markers", default="",
                   help="Optional comma-separated native executable strings")
    p.add_argument("--enable-file-sharing", action="store_true")
    args = p.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    home, dist, sdk_jar = extract_sdk(
        args.package.resolve(), out / "official-sdk", args.sdk_version)
    provenance = {
        "workflowRunId": args.sdk_run_id,
        "artifactId": args.sdk_artifact_id,
        "sourceSha": args.sdk_source_sha,
        "sdkVersion": args.sdk_version,
        "testRef": args.test_ref,
        "testCommitSha": args.test_sha,
        "artifactZipSha256": sha(args.package.resolve()),
        "sdkJarSha256": sha(sdk_jar),
    }
    (out / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(home)
    cp = os.pathsep.join([str(sdk_jar), str(dist / "libs" / "*")])
    classes = out / "classes"
    classes.mkdir(exist_ok=True)
    invoke(["javac", "--release", "8", "-cp", cp, "-d", classes, SOURCE],
           out, out / "compile.log", env, timeout=120)
    jar = out / "GraphicsSmokeProbe.jar"
    invoke(["jar", "cf", jar, "-C", classes, "."],
           out, out / "compile.log", env)
    deployed = out / "deployed"
    deployed.mkdir(exist_ok=True)
    invoke(["java", "-cp", os.pathsep.join([str(classes), cp]), "tc.Deploy",
            jar, "-ios", "/p", "/n", APP_NAME, "/o", str(deployed) + os.sep],
           out, out / "deploy.log", env, timeout=1800)

    files = sorted((deployed / "install" / "ios").glob("*.ipa"))
    if len(files) != 1:
        raise RuntimeError("Expected one deployed IPA: " + repr(files))
    ipa = files[0]
    if args.enable_file_sharing:
        enable_documents_file_sharing(ipa)

    with zipfile.ZipFile(ipa) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Corrupted IPA")
        infos = [entry for entry in archive.namelist()
                 if entry.startswith("Payload/") and entry.endswith(".app/Info.plist")]
        if len(infos) != 1:
            raise RuntimeError("Missing or ambiguous IPA Info.plist")
        appdir = infos[0].rsplit("/", 1)[0]
        info = plistlib.loads(archive.read(infos[0]))
        native_path = appdir + "/" + info["CFBundleExecutable"]
        if native_path not in archive.namelist():
            raise RuntimeError("Missing native executable")
        executable = archive.read(native_path)
        if executable[:4].hex() not in (
                "feedfacf", "cffaedfe", "cafebabe",
                "bebafeca", "cafebabf", "bfbafeca"):
            raise RuntimeError("Native executable is not a recognized Mach-O")
        markers = [item.strip().encode("ascii")
                   for item in args.required_markers.split(",") if item.strip()]
        missing = [item.decode("ascii") for item in markers
                   if item not in executable]
        if missing:
            raise RuntimeError("Required native markers not found: " + repr(missing))
        tczs = [entry for entry in archive.namelist()
                if entry.endswith("/" + APP_NAME + ".tcz")]
        if len(tczs) != 1:
            raise RuntimeError("Missing or ambiguous application TCZ")
        header = archive.read(tczs[0])[:4]
        if len(header) != 4:
            raise RuntimeError("Truncated TCZ header")
        tcz_version = int.from_bytes(header[:2], "little")
        tcz_attributes = int.from_bytes(header[2:], "little")
        if tcz_version != 200 or not (tcz_attributes & 0x2):
            raise RuntimeError("TCZ does not contain a MainWindow: "
                               + hex(tcz_attributes))
        if args.enable_file_sharing and info.get("UIFileSharingEnabled") is not True:
            raise RuntimeError("App-private log sharing was not enabled")

    metadata = dict(provenance)
    metadata.update({
        "test": "iOS graphics: panels and Label/Edit/Button",
        "sdkVersion": args.sdk_version,
        "sdkSourceSha": args.sdk_source_sha,
        "sdkWorkflowRunId": args.sdk_run_id,
        "sdkArtifactId": args.sdk_artifact_id,
        "testRef": args.test_ref,
        "testCommitSha": args.test_sha,
        "nativeDiagnosticMarkers": [x.decode("ascii") for x in markers],
        "ipa": str(ipa.relative_to(out)),
        "ipaSha256": sha(ipa),
        "ipaBytes": ipa.stat().st_size,
        "nativeExecutableSha256": hashlib.sha256(executable).hexdigest(),
        "tczVersion": tcz_version,
        "tczAttributes": tcz_attributes,
        "tczContainsMainWindow": True,
        "bundleIdentifier": info.get("CFBundleIdentifier"),
        "minIOS": info.get("MinimumOSVersion"),
        "documentsFileSharingEnabled": info.get("UIFileSharingEnabled") is True,
        "testedOnPhysicalDevice": False,
    })
    (out / "ios-graphics-ipa.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print("Verified iOS graphics IPA:", ipa)
    print("SDK source:", args.sdk_source_sha)
    print("Test commit:", args.test_sha)
    print("Native executable:", metadata["nativeExecutableSha256"])


if __name__ == "__main__":
    sys.exit(main())
