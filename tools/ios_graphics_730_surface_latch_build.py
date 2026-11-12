#!/usr/bin/env python3
"""Build unchanged iOS graphics smoke against the 7.3.0 surface-latch experiment.

The artifact comes from the 7.3.0 diagnostics plus the iOS-only no-op
screenChange latch release. The original graphics Java application and
Appium screenshot assertions remain identical to the control.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import sys
import zipfile

from sqlite_smoke import extract, invoke, sha
from inspect_ios_ipa import enable_documents_file_sharing

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/ios-graphics/src/totalcross/lab/graphics/GraphicsSmokeProbe.java"
APP_NAME = "ios-graphics-smoke"
SOURCE_SHA = "901966ea900e61eb238d5bc9a1153650a0da46b9"
SDK_RUN_ID = 43324910947
SDK_BASE_SHA = "5464c21e3107e3f1ce9c287b724829e2bb870c1d"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("ios-graphics-results"))
    parser.add_argument("--enable-file-sharing", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    home, dist = extract(args.package.resolve(), out / "official-sdk", out)
    # sqlite_smoke.extract() contains 7.3.0's ORIGINAL package identifiers.
    # Replace that shared-helper metadata with the actual experiment provenance.
    (out / "provenance.json").write_text(json.dumps({
        "workflowRunId": SDK_RUN_ID,
        "sdkVersion": "7.3.0",
        "sourceSha": SOURCE_SHA,
        "baseSourceSha": SDK_BASE_SHA,
        "artifactZip": str(args.package.resolve()),
        "artifactZipSha256": sha(args.package.resolve()),
        "sdkJarSha256": sha(dist / "totalcross-sdk-7.3.0.jar"),
        "variant": "surface-change-latch-release-with-guard-tracing",
    }, indent=2) + "\n")
    sdk_jar = dist / "totalcross-sdk-7.3.0.jar"
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
            "sdkVersion": "7.3.0",
            "sdkSourceSha": SOURCE_SHA,
            "sdkBaseSourceSha": SDK_BASE_SHA,
            "sdkWorkflowRunId": SDK_RUN_ID,
            "variant": "surface-change-latch-release-with-guard-tracing",
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
