#!/usr/bin/env python3
"""Build unmodified customer Main.zip Java sample on pinned TotalCross 7.3.0.

The source files in tests/android-client-main/original mirror Main.zip.
The trace variant differs ONLY by four Vm.debug markers, added to a temp copy
of TestPermission.java. The original APK (Main.apk) is NOT silently replaced:
both deploys rebuild customer source with the official 7.3.0 SDK.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from sqlite_smoke import extract, invoke


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "tests" / "android-client-main" / "original"
EXPECTED_FILES = ("Main.java", "TestPermission.java")
TRACED_MARKER = "TC_CLIENT_MAIN"


def instrument(source):
    source = source.replace(
        "import totalcross.sys.Settings;",
        "import totalcross.sys.Settings;\nimport totalcross.sys.Vm;",
        1,
    )
    before = 'String folderName = "asd";'
    source = source.replace(before, before + '\n\t\tVm.debug("TC_CLIENT_MAIN BEGIN /sdcard/asd");', 1)
    before = 'fileDir.createDir();'
    source = source.replace(before, before + '\n\t\t\tVm.debug("TC_CLIENT_MAIN CREATED /sdcard/asd");', 1)
    before = 'fileDir.delete();'
    source = source.replace(before, before + '\n\t\t\tVm.debug("TC_CLIENT_MAIN DELETED /sdcard/asd");', 1)
    before = 'e.printStackTrace();'
    source = source.replace(before, 'Vm.debug("TC_CLIENT_MAIN FAIL " + e.toString());\n\t\t\t' + before, 1)
    if source.count(TRACED_MARKER) != 4:
        # Four Vm.debug calls, no changed File operations
        raise RuntimeError("Instrumentation did not insert exactly 4 diagnostic markers")
    return source


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("android-client-main-results"))
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    home, dist = extract(args.package.resolve(), out / "official-sdk", out)
    jar = dist / "totalcross-sdk-7.3.0.jar"
    if not jar.is_file():
        jar = dist / "totalcross-sdk.jar"
    cp = os.pathsep.join([str(jar), str(dist / "libs" / "*")])
    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(home)
    report = {"source": "customer Main.zip Java", "sdk": "7.3.0",
              "variants": {}, "sources": {}}
    for name in EXPECTED_FILES:
        path = ORIGINAL / name
        report["sources"][name] = sha256(path)
    for variant in ("exact", "trace"):
        work = out / variant
        src = work / "src"
        src.mkdir(parents=True, exist_ok=True)
        for name in EXPECTED_FILES:
            shutil.copy2(ORIGINAL / name, src / name)
        if variant == "trace":
            target = src / "TestPermission.java"
            target.write_text(instrument(target.read_text(encoding="utf-8")),
                              encoding="utf-8")
        classes = work / "classes"
        classes.mkdir(parents=True, exist_ok=True)
        invoke(["javac", "--release", "8", "-cp", cp, "-d", classes,
                src / "Main.java", src / "TestPermission.java"],
               work, work / "compile.log", env)
        sample = work / "Main.jar"
        invoke(["jar", "cf", sample, "-C", classes, "."],
               work, work / "compile.log", env)
        deployed = work / "deployed"
        deployed.mkdir(exist_ok=True)
        app_name = "clientmain" + variant
        invoke(["java", "-cp", os.pathsep.join([str(classes), cp]), "tc.Deploy",
                sample, "-android", "/p", "/n", app_name,
                "/o", str(deployed) + os.sep,
                "/android_manage_external_storage"],
               work, work / "deploy.log", env, timeout=1800)
        apks = sorted(deployed.rglob("*.apk"))
        if len(apks) != 1:
            raise RuntimeError("Expected exactly one APK for " + variant +
                               ": " + repr(apks))
        report["variants"][variant] = {
            "apk": str(apks[0].relative_to(out)),
            "sha256": sha256(apks[0]),
            "bytes": apks[0].stat().st_size,
            "instrumented": variant == "trace",
        }
        print(variant, "APK:", apks[0], flush=True)
    (out / "build-summary.json").write_text(json.dumps(report, indent=2)+"\n")
    print("Source-identical and instrumentation-only variants compiled successfully")


if __name__ == "__main__":
    main()
