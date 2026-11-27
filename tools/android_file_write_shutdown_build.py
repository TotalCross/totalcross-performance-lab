#!/usr/bin/env python3
"""Build isolated I04/I05 Android probes with the official TotalCross 7.3.0 SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODES = {
    "I04": ("standard", "external", "race"),
    "I05": ("normal", "worker", "file-io", "sqlite", "external"),
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(args, cwd, env, log):
    with log.open("w", encoding="utf-8") as stream:
        stream.write("$ " + " ".join(map(str, args)) + "\n")
        stream.flush()
        p = subprocess.run(list(map(str, args)), cwd=str(cwd), env=env,
                           stdout=stream, stderr=subprocess.STDOUT, check=False)
        stream.write("\nEXIT_CODE=" + str(p.returncode) + "\n")
    if p.returncode:
        raise RuntimeError("command failed with exit " + str(p.returncode)
                           + "; see " + str(log))


def build(mode_group, mode, template, home, out, env):
    name = (mode_group.lower() + mode.replace("-", "")).lower()
    work = out / name
    source_dir = work / "src"
    classes = work / "classes"
    deployed = work / "deployed"
    source_dir.mkdir(parents=True, exist_ok=True)
    classes.mkdir(parents=True, exist_ok=True)
    deployed.mkdir(parents=True, exist_ok=True)
    text = template.read_text(encoding="utf-8")
    if text.count("@@MODE@@") != 1:
        raise RuntimeError("expected exactly one @@MODE@@ token in " + str(template))
    source = source_dir / "Main.java"
    source.write_text(text.replace("@@MODE@@", mode), encoding="utf-8")
    jar = work / "Main.jar"
    classpath = os.pathsep.join((
        str(home / "dist" / "totalcross-sdk-7.3.0.jar"),
        str(home / "dist" / "libs" / "*"),
    ))
    run(["javac", "--release", "8", "-cp", classpath,
         "-d", classes, source], work, env, work / "compile.log")
    run(["jar", "cf", jar, "-C", classes, "."], work, env, work / "compile.log")
    cmd = ["java", "-cp", os.pathsep.join((str(classes), classpath)), "tc.Deploy",
           jar, "-android", "/p", "/n", name, "/o", str(deployed) + os.sep,
           "/android_manage_external_storage"]
    run(cmd, work, env, work / "deploy.log")
    apks = sorted(deployed.rglob("*.apk"))
    if len(apks) != 1:
        raise RuntimeError("expected one APK for " + name + "; found " + repr(apks))
    apk = apks[0]
    badging = subprocess.check_output([env["ANDROID_AAPT"], "dump", "badging", str(apk)],
                                      text=True)
    package_match = re.search(r"^package: name='([^']+)'", badging, re.M)
    activity_match = re.search(r"^launchable-activity: name='([^']+)'", badging, re.M)
    if not package_match or not activity_match:
        raise RuntimeError("APK metadata missing package or launcher: " + str(apk))
    lib = subprocess.check_output(["unzip", "-p", str(apk),
                                   "lib/arm64-v8a/libtcvm.so"])
    return {
        "group": mode_group,
        "mode": mode,
        "appName": name,
        "package": package_match.group(1),
        "launcherActivity": activity_match.group(1),
        "apk": str(apk),
        "apkSha256": digest(apk),
        "apkBytes": apk.stat().st_size,
        "androidLibtcvmSha256": hashlib.sha256(lib).hexdigest(),
        "sdkJarSha256": digest(home / "dist" / "totalcross-sdk-7.3.0.jar"),
        "sourceSha256": digest(source),
        "deployLog": str(work / "deploy.log"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk-home", type=Path, required=True,
                        help="extracted official TotalCross 7.3.0 SDK directory")
    parser.add_argument("--android-sdk", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--groups", nargs="+", choices=sorted(MODES),
                        default=sorted(MODES))
    args = parser.parse_args()
    home = args.sdk_home.resolve()
    out = args.out.resolve()
    if not (home / "dist" / "totalcross-sdk-7.3.0.jar").is_file():
        parser.error("SDK home is missing dist/totalcross-sdk-7.3.0.jar")
    aapts = sorted((args.android_sdk.resolve() / "build-tools").glob("*/aapt"))
    if not aapts:
        parser.error("Android build-tools aapt was not found")
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(home)
    env["ANDROID_HOME"] = str(args.android_sdk.resolve())
    env["ANDROID_AAPT"] = str(aapts[-1])
    result = {"sdkJarSha256": digest(home / "dist" / "totalcross-sdk-7.3.0.jar"),
              "modes": []}
    for group in args.groups:
        modes = MODES[group]
        template = ROOT / "investigations" / "7.3.0-functional" / "cases" \
                   / ("android-file-write" if group == "I04" else "android-shutdown") \
                   / "Main.java"
        for mode in modes:
            try:
                result["modes"].append(build(group, mode, template, home, out, env))
            except Exception as failure:
                print("build failed for", group, mode, ":", failure, file=sys.stderr)
                raise
    (out / "build-summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Built", len(result["modes"]), "Android probes; summary:", out / "build-summary.json")


if __name__ == "__main__":
    main()
