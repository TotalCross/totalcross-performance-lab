#!/usr/bin/env python3
# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only
"""Build and run the TotalCross 7.3.0 Image(String) fallback probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/functional-validation/totalcross/ui/image/ImageStringFallbackProbe.java"
FIXTURES = ROOT / "investigations/7.3.0-functional/cases/image-string-fallback/fixtures"
APP = "ImageStringFallbackProbe"
ENTRY = "totalcross.ui.image.ImageStringFallbackProbe"
RESULT_MARKER = "TC_I07_RESULT "


class ProbeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate_sdk(root: Path) -> tuple[Path, Path]:
    candidates = [root] if (root / "dist").is_dir() else []
    candidates.extend(path.parent.parent for path in root.rglob("totalcross-sdk*.jar")
                      if path.parent.name == "dist")
    for home in candidates:
        jar = home / "dist/totalcross-sdk.jar"
        if not jar.is_file():
            jar = home / "dist/totalcross-sdk-7.3.0.jar"
        if jar.is_file() and (home / "dist/libs").is_dir() and (home / "etc").is_dir():
            with zipfile.ZipFile(jar) as archive:
                if "tc/Deploy.class" not in archive.namelist():
                    raise ProbeError("SDK jar does not contain tc.Deploy: " + str(jar))
            return home.resolve(), jar.resolve()
    raise ProbeError("SDK root must contain dist/totalcross-sdk*.jar, dist/libs, and etc/")


def run_logged(command: list[str], cwd: Path, env: dict[str, str], log: Path,
               timeout: int = 1800) -> subprocess.CompletedProcess:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as output:
        output.write("$ " + subprocess.list2cmdline(command) + "\n")
        output.flush()
        result = subprocess.run(command, cwd=cwd, env=env, stdout=output,
                                stderr=subprocess.STDOUT, timeout=timeout, check=False)
        output.write("\nEXIT_CODE=" + str(result.returncode) + "\n")
    if result.returncode:
        raise ProbeError("command failed with exit %d; see %s" % (result.returncode, log))
    return result


def decode_pe_machine(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 64 or data[:2] != b"MZ":
        raise ProbeError("expected a PE image: " + str(path))
    offset = int.from_bytes(data[0x3C:0x40], "little")
    if offset + 6 > len(data) or data[offset:offset + 4] != b"PE\0\0":
        raise ProbeError("invalid PE header: " + str(path))
    return int.from_bytes(data[offset + 4:offset + 6], "little")


def java_byte_source() -> str:
    small = (FIXTURES / "tcz-small.jpg").read_bytes().hex()
    large = (FIXTURES / "filesystem-large.jpg").read_bytes().hex()
    return """package totalcross.ui.image;
final class ImageStringFallbackFixtures {
  static final byte[] SMALL_JPEG = fromHex(\"%s\");
  static final byte[] LARGE_JPEG = fromHex(\"%s\");
  static final byte[] INVALID_BYTES = new byte[] { 1, 2, 3, 4, 5, 6 };
  static final byte[] EMPTY_BYTES = new byte[0];
  private static byte[] fromHex(String value) {
    byte[] bytes = new byte[value.length() / 2];
    for (int i = 0; i < bytes.length; i++) {
      bytes[i] = (byte) Integer.parseInt(value.substring(i * 2, i * 2 + 2), 16);
    }
    return bytes;
  }
}
""" % (small, large)


def deploy_target(platform: str) -> str:
    return {"windows": "-win32", "linux": "-linux", "macos": "-macos",
            "android": "-android"}[platform]


def runtime_destinations(home: Path, platform: str) -> list[Path]:
    if platform == "windows":
        return [home / "etc/launchers/win32/Launcher.exe",
                home / "dist/vm/win32/tcvm.dll"]
    if platform == "linux":
        return [home / "etc/launchers/linux/Launcher",
                home / "dist/vm/linux/libtcvm.so"]
    if platform == "macos":
        return [home / "etc/launchers/macos/Launcher",
                home / "dist/vm/macos/libtcvm.dylib"]
    return []


def add_zip_file(archive: zipfile.ZipFile, name: str, path: Path) -> None:
    archive.write(path, name)


def prepare(args: argparse.Namespace) -> dict:
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ProbeError("refusing to overwrite non-empty output directory: " + str(out))
    out.mkdir(parents=True, exist_ok=True)
    home, sdk_jar = locate_sdk(args.sdk_root.resolve())
    runtime_files = []
    pe_machines = {}
    if args.platform != "android":
        if args.native_dir is None:
            raise ProbeError("--native-dir is required for desktop targets")
        native_dir = args.native_dir.resolve()
        if args.platform == "windows":
            sources = [native_dir / "Launcher.exe", native_dir / "tcvm.dll"]
        elif args.platform == "linux":
            sources = [native_dir / "Launcher", native_dir / "libtcvm.so"]
        else:
            sources = [native_dir / "Launcher", native_dir / "libtcvm.dylib"]
        missing = [str(path) for path in sources if not path.is_file()]
        if missing:
            raise ProbeError("native directory is missing: " + ", ".join(missing))
        destinations = runtime_destinations(home, args.platform)
        for source, destination in zip(sources, destinations):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            runtime_files.append({"path": str(destination), "sha256": sha256(destination)})
        if args.platform == "windows":
            for path in sources:
                machine = decode_pe_machine(path)
                pe_machines["source/" + path.name] = "0x%04x" % machine
                if machine != 0x014C:
                    raise ProbeError("Windows I07 requires I386 PE images; %s is 0x%04x"
                                     % (path.name, machine))

    java = shutil.which("java")
    javac = shutil.which("javac")
    if not java or not javac:
        raise ProbeError("JDK java and javac are required")
    classes = out / "classes"
    classes.mkdir()
    generated = out / "ImageStringFallbackFixtures.java"
    generated.write_text(java_byte_source(), encoding="utf-8")
    classpath = os.pathsep.join((str(sdk_jar), str(home / "dist/libs/*")))
    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(home)
    run_logged([javac, "--release", "8", "-cp", classpath, "-d", str(classes),
                str(SOURCE), str(generated)], ROOT, env, out / "compile.log")

    app_jar = out / (APP + ".jar")
    with zipfile.ZipFile(app_jar, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\n\r\n")
        for path in sorted(classes.rglob("*.class")):
            add_zip_file(archive, path.relative_to(classes).as_posix(), path)
        archive.write(FIXTURES / "tcz-small.jpg", "tcz-only.jpg")
        archive.write(FIXTURES / "tcz-small.jpg", "precedence.jpg")
        archive.writestr("malformed.jpg", bytes((1, 2, 3, 4, 5, 6)))
        archive.writestr("empty-tcz.jpg", b"")
        archive.write(FIXTURES / "tcz-small.jpg", "x" * 255)

    deployed = out / "deployed"
    deployed.mkdir()
    deploy_command = [java, "-cp", classpath, "tc.Deploy", str(app_jar),
                      deploy_target(args.platform), "/p", "/n", APP, "/o",
                      str(deployed) + os.sep]
    run_logged(deploy_command, ROOT, env, out / "deploy.log", timeout=1800)

    install_root = deployed / "install" / {
        "windows": "win32", "linux": "linux", "macos": "macos", "android": "android"
    }[args.platform]
    deployed_windows_files = []
    app_tcz = None
    if args.platform == "windows":
        executable = install_root / (APP + ".exe")
        if not executable.is_file():
            raise ProbeError("deployer did not create " + str(executable))
        pe_files = sorted(path for path in install_root.rglob("*")
                          if path.is_file() and path.suffix.lower() in (".exe", ".dll"))
        if not pe_files:
            raise ProbeError("deployed Windows package has no PE executables or DLLs")
        for path in pe_files:
            machine = decode_pe_machine(path)
            relative = path.relative_to(install_root).as_posix()
            pe_machines["deployed/" + relative] = "0x%04x" % machine
            if machine != 0x014C:
                raise ProbeError("deployed Windows file is not I386: " + relative)
            deployed_windows_files.append({"path": relative, "sha256": sha256(path)})
        source_vm_hash = next(item["sha256"] for item in runtime_files
                              if Path(item["path"]).name.lower() == "tcvm.dll")
        vm_copies = [path for path in pe_files if path.name.lower() == "tcvm.dll"]
        if not vm_copies or any(sha256(path) != source_vm_hash for path in vm_copies):
            raise ProbeError("deployed tcvm.dll does not match the verified Win32 runtime")
        app_tczs = [path for path in install_root.rglob("*.tcz")
                    if path.stem.casefold() == APP.casefold()]
        if len(app_tczs) != 1:
            raise ProbeError("expected exactly one deployed application TCZ; found "
                             + repr(app_tczs))
        app_tcz = {"path": str(app_tczs[0]), "sha256": sha256(app_tczs[0])}
    elif args.platform == "linux":
        executable = install_root / APP
        if not executable.is_file():
            raise ProbeError("deployer did not create " + str(executable))
        executable.chmod(executable.stat().st_mode | 0o111)
    elif args.platform == "macos":
        executable = next((path for path in install_root.rglob(APP)
                           if path.is_file() and path.parent.name == "MacOS"), None)
        if executable is None:
            executable = install_root / APP
        if not executable.is_file():
            raise ProbeError("deployer did not create a macOS app executable under "
                             + str(install_root))
        executable.chmod(executable.stat().st_mode | 0o111)
    else:
        apks = sorted(install_root.rglob("*.apk"))
        if len(apks) != 1:
            raise ProbeError("expected one deployed Android APK; found " + repr(apks))
        executable = apks[0]
        aapt = args.aapt or shutil.which("aapt")
        if not aapt:
            raise ProbeError("Android aapt is required to inspect the deployed APK")
        badging = subprocess.check_output([aapt, "dump", "badging", str(executable)], text=True)
        package_match = re.search(r"^package: name='([^']+)'", badging, re.M)
        activity_match = re.search(r"^launchable-activity: name='([^']+)'", badging, re.M)
        if not package_match or not activity_match:
            raise ProbeError("deployed Android APK has no package/launcher metadata")
        android_identity = {
            "package": package_match.group(1),
            "activity": activity_match.group(1),
        }
        with zipfile.ZipFile(executable) as apk:
            android_identity["arm64LibtcvmSha256"] = hashlib.sha256(
                apk.read("lib/arm64-v8a/libtcvm.so")).hexdigest()

    record = {
        "platform": args.platform,
        "sourceCommit": args.source_commit,
        "sourceTree": args.source_tree,
        "probeSourceCommit": args.probe_source_commit,
        "sdkJarSha256": sha256(sdk_jar),
        "applicationJarSha256": sha256(app_jar),
        "fixtureSha256": {
            "tczSmallJpeg": sha256(FIXTURES / "tcz-small.jpg"),
            "filesystemLargeJpeg": sha256(FIXTURES / "filesystem-large.jpg"),
        },
        "runtimeFiles": runtime_files,
        "peMachines": pe_machines,
        "deployedWindowsPefiles": deployed_windows_files,
        "applicationTcz": app_tcz,
        "installDir": str(install_root),
        "executableOrApk": str(executable),
        "executableOrApkSha256": sha256(executable),
        "android": android_identity if args.platform == "android" else None,
    }
    (out / "prepared.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, sort_keys=True))
    return record


def run_desktop(args: argparse.Namespace, prepared: dict) -> dict:
    platform_name = prepared["platform"]
    executable = Path(prepared["executableOrApk"])
    install = Path(prepared["installDir"])
    if not executable.is_file():
        raise ProbeError("deployed executable is missing: " + str(executable))
    env = os.environ.copy()
    if platform_name == "linux":
        env["LD_LIBRARY_PATH"] = str(install) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        if args.shim:
            env["LD_PRELOAD"] = str(args.shim.resolve()) + (os.pathsep + env["LD_PRELOAD"]
                                                              if env.get("LD_PRELOAD") else "")
    elif platform_name == "macos":
        env["DYLD_LIBRARY_PATH"] = str(install) + os.pathsep + env.get("DYLD_LIBRARY_PATH", "")
    started = time.monotonic()
    command = [str(executable)]
    if platform_name == "linux" and args.xvfb:
        command = ["xvfb-run", "-a", *command]
    try:
        process = subprocess.run(command, cwd=install, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 timeout=args.timeout, check=False)
        output = process.stdout
        exit_code = process.returncode
        timed_out = False
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        exit_code = None
        timed_out = True
    elapsed = int((time.monotonic() - started) * 1000)
    (args.out / "runtime.log").write_text(output, encoding="utf-8", errors="replace")
    marker = next((line.split(RESULT_MARKER, 1)[1].strip()
                   for line in output.splitlines() if RESULT_MARKER in line), None)
    report = json.loads(marker) if marker else None
    case_results = parse_case_results(output)
    cases_complete = case_results_match_summary(report, case_results)
    status = "INCOMPLETE"
    if report is not None:
        status = "PASS" if (exit_code == 0 and not timed_out and cases_complete
                             and report.get("status") == "PASS"
                             and report.get("failures") == 0) else "FAIL"
    record = {
        "status": status,
        "platform": platform_name,
        "processExitCode": exit_code,
        "timedOut": timed_out,
        "durationMilliseconds": elapsed,
        "conditionalRealpathShim": bool(args.shim),
        "applicationResult": report,
        "caseResults": case_results,
        "caseResultsComplete": cases_complete,
        "runtimeLog": "runtime.log",
        "prepared": prepared,
    }
    (args.out / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, sort_keys=True))
    if status != "PASS":
        raise ProbeError("I07 %s result on %s; see %s" %
                         (status.lower(), platform_name, args.out / "runtime.log"))
    return record


def run_android(args: argparse.Namespace, prepared: dict) -> dict:
    adb = args.adb or shutil.which("adb")
    if not adb:
        raise ProbeError("adb is required to run the Android probe")
    serial = args.serial or os.environ.get("ANDROID_SERIAL")
    if not serial:
        result = subprocess.run([adb, "devices"], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=30, check=False)
        if result.returncode:
            raise ProbeError("adb devices failed: " + result.stdout[-1000:])
        devices = [line.split()[0] for line in result.stdout.splitlines()[1:]
                   if len(line.split()) >= 2 and line.split()[1] == "device"]
        if len(devices) != 1:
            raise ProbeError("specify --serial when adb has multiple online devices")
        serial = devices[0]
    identity = prepared["android"]

    def adb_call(*command: str) -> str:
        result = subprocess.run([adb, "-s", serial, *command], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=30, check=False)
        if result.returncode:
            raise ProbeError("adb " + " ".join(command) + " failed: " + result.stdout[-1000:])
        return result.stdout

    device_state = adb_call("get-state").strip()
    abi = adb_call("shell", "getprop", "ro.product.cpu.abi").strip()
    if device_state != "device" or abi != "arm64-v8a":
        raise ProbeError("Android ARM64 emulator required; state=%s abi=%s" % (device_state, abi))
    adb_call("install", "-r", prepared["executableOrApk"])
    adb_call("shell", "am", "force-stop", identity["package"])
    adb_call("logcat", "-c")
    adb_call("shell", "am", "start", "-W", "-n",
             identity["package"] + "/" + identity["activity"])
    started = time.monotonic()
    output = ""
    completed = False
    while time.monotonic() - started < args.timeout:
        output = adb_call("logcat", "-d", "-v", "brief")
        if RESULT_MARKER in output:
            completed = True
            break
        time.sleep(2)
    elapsed = int((time.monotonic() - started) * 1000)
    (args.out / "runtime-android.logcat").write_text(output, encoding="utf-8", errors="replace")
    marker = next((line.split(RESULT_MARKER, 1)[1].strip()
                   for line in output.splitlines() if RESULT_MARKER in line), None)
    report = json.loads(marker) if marker else None
    case_results = parse_case_results(output)
    app_crashed = any(token in output for token in
                      ("FATAL EXCEPTION", "Fatal signal", "SIGSEGV", "SIGABRT"))
    cases_complete = case_results_match_summary(report, case_results)
    if app_crashed or (report is not None and report.get("status") != "PASS"):
        status = "FAIL"
    elif completed and report is not None and report.get("failures") == 0 and cases_complete:
        status = "PASS"
    else:
        status = "INCOMPLETE"
    record = {
        "status": status,
        "platform": "android-arm64",
        "deviceSerial": serial,
        "deviceAbi": abi,
        "completionMarkerObserved": completed,
        "nativeCrashObserved": app_crashed,
        "processExitCode": None,
        "durationMilliseconds": elapsed,
        "applicationResult": report,
        "caseResults": case_results,
        "caseResultsComplete": cases_complete,
        "runtimeLog": "runtime-android.logcat",
        "prepared": prepared,
    }
    (args.out / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, sort_keys=True))
    if status != "PASS":
        raise ProbeError("I07 %s result on Android ARM64; see " % status.lower()
                         + str(args.out / "runtime-android.logcat"))
    return record


def parse_case_results(output: str) -> list[dict]:
    results = []
    for line in output.splitlines():
        match = re.search(r"TC_I07 case=(\S+) status=(PASS|FAIL|SKIP) details=(.*)", line)
        if match:
            results.append({"name": match.group(1), "status": match.group(2),
                            "details": match.group(3)})
    return results


def case_results_match_summary(report: dict | None, cases: list[dict]) -> bool:
    if report is None:
        return False
    return (report.get("cases") == len(cases)
            and report.get("failures") == sum(case["status"] == "FAIL" for case in cases)
            and report.get("skips") == sum(case["status"] == "SKIP" for case in cases))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--sdk-root", type=Path, required=True)
    prepare_parser.add_argument("--native-dir", type=Path)
    prepare_parser.add_argument("--platform", choices=("windows", "linux", "macos", "android"),
                                required=True)
    prepare_parser.add_argument("--aapt")
    prepare_parser.add_argument("--source-commit", required=True)
    prepare_parser.add_argument("--source-tree", required=True)
    prepare_parser.add_argument("--probe-source-commit", required=True)
    prepare_parser.add_argument("--out", type=Path, required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--timeout", type=int, default=180)
    run_parser.add_argument("--shim", type=Path)
    run_parser.add_argument("--xvfb", action="store_true")
    run_parser.add_argument("--adb")
    run_parser.add_argument("--serial")
    run_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        args.out = args.out.resolve()
        if args.command == "prepare":
            prepare(args)
        else:
            prepared_path = args.out / "prepared.json"
            if not prepared_path.is_file():
                raise ProbeError("prepared.json is missing: " + str(prepared_path))
            prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
            if prepared["platform"] == "android":
                run_android(args, prepared)
            else:
                run_desktop(args, prepared)
    except (OSError, ProbeError, subprocess.TimeoutExpired, zipfile.BadZipFile,
            json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
