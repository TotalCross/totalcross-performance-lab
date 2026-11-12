#!/usr/bin/env python3
"""Build isolated TotalCross 7.3.0 iOS graphics probe and inspect its IPA.

Consumes the same immutable official 7.3.0 SDK used by SQLite verification.
Only the IPA Info.plist is modified to enable Device Farm file extraction;
the TotalCross native executable is not rebuilt or patched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import sys
import zipfile

from sqlite_smoke import extract, invoke
from inspect_ios_ipa import enable_documents_file_sharing

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/ios-graphics/src/totalcross/lab/graphics/GraphicsSmokeProbe.java"
APP_NAME = "ios-graphics-smoke"
SOURCE_SHA = "5464c21e3107e3f1ce9c287b724829e2bb870c1d"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("ios-graphics-results"))
    parser.add_argument("--enable-file-sharing", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    home, dist = extract(args.package.resolve(), out / "official-sdk", out)
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
    jar = out / (APP_NAME + ".jar")
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
        if not any(name.endswith("/" + APP_NAME + ".tcz") for name in archive.namelist()):
            raise RuntimeError("Missing embedded graphics-test TCZ")
        if args.enable_file_sharing and info.get("UIFileSharingEnabled") is not True:
            raise RuntimeError("Cannot collect app-private log: file sharing is disabled")
        metadata = {
            "test": "iOS Skia/Graphics primitives + Label/Edit/Button",
            "sdkVersion": "7.3.0",
            "sdkSourceSha": SOURCE_SHA,
            "ipa": str(ipa.relative_to(out)),
            "ipaSha256": hashlib.sha256(ipa.read_bytes()).hexdigest(),
            "ipaBytes": ipa.stat().st_size,
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
