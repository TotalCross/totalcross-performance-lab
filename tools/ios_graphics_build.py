#!/usr/bin/env python3
"""Build pinned TotalCross 7.2.2 (2026-08-24) iOS graphics control IPA.

Uses the immutable official 24-Aug SDK; SQLite still uses 7.3.0.
Only the IPA Info.plist is modified to enable Device Farm file extraction;
the TotalCross native executable is not rebuilt or patched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys
import zipfile

from sqlite_smoke import invoke, sha
from inspect_ios_ipa import enable_documents_file_sharing

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/ios-graphics/src/totalcross/lab/graphics/GraphicsSmokeProbe.java"
APP_NAME = "ios-graphics-smoke"
SDK_VERSION = "7.2.2"
SDK_RUN_ID = 32682363876
SDK_ARTIFACT_ID = 9504578512
SOURCE_SHA = "452213ae7fdf483f443aa73153f0bdce6dcecf6f"
SDK_ARTIFACT_SHA256 = "15c614b62c580cfd3bc684c5be599d7ff15e133cb13147ea26a962723ecf919f"

def extract_historical_sdk(package_zip, target, out):
    """Unpack the pinned 7.2.2 SDK without changing SQLite's 7.3.0 helper."""
    actual_digest = sha(package_zip)
    if actual_digest != SDK_ARTIFACT_SHA256:
        raise RuntimeError("Historical SDK SHA-256 mismatch: " + actual_digest)

    def unpack(src, dest):
        with zipfile.ZipFile(src) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Corrupt SDK ZIP: " + str(src))
            for member in archive.infolist():
                resolved = (dest / member.filename).resolve()
                if not resolved.is_relative_to(dest.resolve()):
                    raise RuntimeError("Unsafe ZIP path: " + member.filename)
            archive.extractall(dest)

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    unpack(package_zip, target)
    nested = target / "TotalCross-7.2.2.zip"
    if not nested.is_file():
        raise RuntimeError("Expected nested TotalCross-7.2.2.zip")
    expanded = target / "package"
    expanded.mkdir()
    unpack(nested, expanded)
    jars = [p for p in expanded.rglob("totalcross-sdk-7.2.2.jar")
            if p.parent.name == "dist"]
    if len(jars) != 1:
        raise RuntimeError("Expected one 7.2.2 SDK JAR: " + str(jars))
    dist = jars[0].parent
    home = dist.parent
    if not (home / "etc").is_dir() or not (dist / "libs").is_dir():
        raise RuntimeError("SDK layout invalid: etc or dist/libs missing")
    provenance = {
        "workflowRunId": SDK_RUN_ID, "artifactId": SDK_ARTIFACT_ID,
        "sourceSha": SOURCE_SHA, "sdkVersion": SDK_VERSION,
        "officialArtifactSha256": actual_digest,
        "sdkJarSha256": sha(jars[0]), "sdkHome": str(home),
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return home, dist



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("ios-graphics-results"))
    parser.add_argument("--enable-file-sharing", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    home, dist = extract_historical_sdk(args.package.resolve(), out / "official-sdk", out)
    sdk_jar = dist / ("totalcross-sdk-" + SDK_VERSION + ".jar")
    if not sdk_jar.is_file():
        sdk_jar = dist / "totalcross-sdk.jar"
    cp = os.pathsep.join([str(sdk_jar), str(dist / "libs" / "*")])
    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(home)

    classes = out / "classes"
    classes.mkdir(exist_ok=True)
    invoke(["javac", "--release", "8", "-cp", cp, "-d", classes, SOURCE],
           out, out / "compile.log", env, timeout=120)
    # TotalCross deployer discovers MainWindow by the *input JAR basename*.
    # /n controls the packaged app name, not class detection.
    jar = out / "GraphicsSmokeProbe.jar"
    invoke(["jar", "cf", jar, "-C", classes, "."], out, out / "compile.log", env)
    deployed = out / "deployed"
    deployed.mkdir(exist_ok=True)
    invoke(["java", "-cp", os.pathsep.join([str(classes), cp]), "tc.Deploy",
            jar, "-ios", "/p", "/n", APP_NAME, "/o", str(deployed) + os.sep],
           out, out / "deploy.log", env, timeout=1800)

    apks = sorted((deployed / "install" / "ios").glob("*.ipa"))
    if len(apks) != 1:
        raise RuntimeError("Expected exactly one deployed iOS IPA: " + repr(apks))
    ipa = apks[0]
    if args.enable_file_sharing:
        enable_documents_file_sharing(ipa)

    with zipfile.ZipFile(ipa) as archive:
        if archive.testzip():
            raise RuntimeError("Corrupted iOS IPA")
        infos = [name for name in archive.namelist()
                 if name.startswith("Payload/") and name.endswith(".app/Info.plist")]
        if len(infos) != 1:
            raise RuntimeError("iOS app Info.plist missing or ambiguous")
        appdir = infos[0].rsplit("/", 1)[0]
        info = plistlib.loads(archive.read(infos[0]))
        executable = appdir + "/" + info["CFBundleExecutable"]
        if executable not in archive.namelist():
            raise RuntimeError("Native executable missing from IPA")
        native_bytes = archive.read(executable)
        if native_bytes[:4].hex() not in (
                "feedfacf", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca"):
            raise RuntimeError("Unrecognized native Mach-O")
        tcz_names = [name for name in archive.namelist()
                     if name.endswith("/" + APP_NAME + ".tcz")]
        if len(tcz_names) != 1:
            raise RuntimeError("Missing/ambiguous graphics-test TCZ")
        tcz_header = archive.read(tcz_names[0])[:4]
        if len(tcz_header) != 4:
            raise RuntimeError("Truncated graphics TCZ header")
        tcz_version = int.from_bytes(tcz_header[:2], "little")
        tcz_attributes = int.from_bytes(tcz_header[2:], "little")
        # TCZ.ATTR_HAS_MAINWINDOW is bit 0x2. A deployer warning alone is
        # not a reliable check; library-only TCZs can still produce an IPA.
        if tcz_version != 200 or not (tcz_attributes & 0x2):
            raise RuntimeError("Graphics TCZ is library-only (attr=0x%x); "
                               "main class GraphicsSmokeProbe was not detected"
                               % tcz_attributes)
        if args.enable_file_sharing and info.get("UIFileSharingEnabled") is not True:
            raise RuntimeError("Cannot collect app-private log: file sharing is disabled")
        metadata = {
            "test": "iOS Skia/Graphics primitives + Label/Edit/Button",
            "sdkVersion": SDK_VERSION,
            "sdkWorkflowRunId": SDK_RUN_ID,
            "sdkArtifactId": SDK_ARTIFACT_ID,
            "sdkSourceSha": SOURCE_SHA,
            "ipa": str(ipa.relative_to(out)),
            "ipaSha256": hashlib.sha256(ipa.read_bytes()).hexdigest(),
            "ipaBytes": ipa.stat().st_size,
            "tczVersion": tcz_version,
            "tczAttributes": tcz_attributes,
            "tczContainsMainWindow": bool(tcz_attributes & 0x2),
            "nativeExecutableSha256": hashlib.sha256(native_bytes).hexdigest(),
            "bundleIdentifier": info.get("CFBundleIdentifier"),
            "minIOS": info.get("MinimumOSVersion"),
            "documentsFileSharingEnabled": info.get("UIFileSharingEnabled") is True,
            "reSigning": "Device Farm must resign IPA built with SDK placeholder identity",
            "testedOnPhysicalDevice": False,
        }
    (out / "ios-graphics-ipa.json").write_text(json.dumps(metadata, indent=2)+"\n")
    print("Verified iOS graphics IPA:", ipa)
    print("Bundle:", metadata["bundleIdentifier"])
    print("File sharing:", metadata["documentsFileSharingEnabled"])
    print("Native executable SHA256:", metadata["nativeExecutableSha256"])


if __name__ == "__main__":
    sys.exit(main())
