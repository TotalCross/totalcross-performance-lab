#!/usr/bin/env python3
"""Compile, deploy, run, and validate the persistent image ownership smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile


APP_NAME = "ImageOwnershipSmoke"
ENTRY_CLASS = "totalcross.ui.image.ImageOwnershipLifecycleProbe"
RESULT_PREFIX = "TC_IMAGE_OWNERSHIP_JSON "
FAILURE_PREFIX = "TC_IMAGE_OWNERSHIP_FAIL "
TARGETS = {
    "macos": ("macos", "macos", "Launcher", "libtcvm.dylib"),
    "linux-amd64": ("linux", "linux", "Launcher", "libtcvm.so"),
    "windows": ("win32", "win32", "Launcher.exe", "tcvm.dll"),
    "android": ("android", "android", None, None),
}


class SmokeError(Exception):
    pass


def pe_machine(path: Path) -> int:
    try:
        with path.open("rb") as executable:
            if executable.read(2) != b"MZ":
                raise SmokeError("Windows executable has no DOS header: " + str(path))
            executable.seek(0x3C)
            pe_offset = struct.unpack("<I", executable.read(4))[0]
            executable.seek(pe_offset)
            if executable.read(4) != b"PE\0\0":
                raise SmokeError("Windows executable has no PE signature: " + str(path))
            return struct.unpack("<H", executable.read(2))[0]
    except (OSError, struct.error) as error:
        raise SmokeError("cannot inspect Windows executable: " + str(path)) from error


def require_windows_x64(path: Path) -> None:
    machine = pe_machine(path)
    if machine != 0x8664:
        raise SmokeError("Windows runtime artifact is not AMD64: " + str(path)
                         + " (PE machine 0x%04x)" % machine)


def zip_member(path: Path, suffix: str) -> tuple[str, bytes]:
    try:
        with zipfile.ZipFile(path) as archive:
            matches = [name for name in archive.namelist() if name.endswith(suffix)]
            if len(matches) != 1:
                raise SmokeError("expected one " + suffix + " entry in " + str(path)
                                 + "; found " + str(len(matches)))
            return matches[0], archive.read(matches[0])
    except (OSError, zipfile.BadZipFile) as error:
        raise SmokeError("cannot inspect runtime archive: " + str(path)) from error


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SmokeError("cannot read provenance JSON: " + str(path)) from error


def verify_provenance(path: Path, expected_commit: str, expected_tree: str, label: str,
                      allow_dirty_source: bool = False) -> dict:
    manifest = read_json(path)
    source = manifest.get("source", {})
    if str(manifest.get("repository", "")).lower() != "totalcross/totalcross":
        raise SmokeError(label + " artifact was built from an unexpected repository")
    if source.get("commit") != expected_commit or source.get("tree") != expected_tree:
        raise SmokeError(label + " artifact source identity does not match this workflow run")
    if source.get("dirty") is not False and not (
            allow_dirty_source and source.get("dirty") is True):
        raise SmokeError(label + " artifact was not built from a clean source tree")
    return manifest


def locate_one(root: Path, name: str) -> Path:
    matches = sorted(path for path in root.rglob(name) if path.is_file())
    if not matches:
        raise SmokeError("required platform artifact is missing: " + name)
    return matches[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_logged(command: list[str], cwd: Path, log_path: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=600, check=False)
    log_path.write_text(result.stdout, encoding="utf-8", errors="replace")
    if result.returncode:
        raise SmokeError("command failed (%d): %s; see %s" %
                         (result.returncode, command[0], log_path))


def prepare(arguments) -> None:
    if arguments.target not in TARGETS:
        raise SmokeError("unsupported smoke target: " + arguments.target)
    output = arguments.output.resolve()
    runtime_home = arguments.runtime_home.resolve()
    platform_artifact = arguments.platform_artifact.resolve()
    lab_root = arguments.lab_root.resolve()
    sdk_manifest = verify_provenance(arguments.sdk_provenance.resolve(),
                                     arguments.source_commit, arguments.source_tree, "SDK",
                                     arguments.allow_dirty_source)
    platform_manifest = verify_provenance(arguments.platform_provenance.resolve(),
                                          arguments.source_commit, arguments.source_tree,
                                          arguments.target, arguments.allow_dirty_source)
    if not output.is_dir() or not runtime_home.is_dir() or not platform_artifact.is_dir():
        raise SmokeError("SDK output, runtime home, and platform artifact must be directories")
    if subprocess.run(["git", "-C", str(lab_root), "status", "--porcelain"],
                      text=True, capture_output=True, check=False).stdout.strip():
        raise SmokeError("performance-lab source checkout is dirty")
    lab_commit = subprocess.run(["git", "-C", str(lab_root), "rev-parse", "HEAD"],
                                text=True, capture_output=True, check=True).stdout.strip()
    if lab_commit != arguments.lab_commit:
        raise SmokeError("performance-lab checkout does not match the pinned workflow commit")

    platform_folder, target_flag, launcher_name, vm_name = TARGETS[arguments.target]
    runtime_files = []
    windows_runtime_artifact = None
    android_runtime_library = None
    if arguments.target == "android":
        android_template = locate_one(platform_artifact, "TotalCross.aab")
        library_member, library_bytes = zip_member(
            android_template, "lib/arm64-v8a/libtcvm.so")
        android_runtime_library = {
            "abi": "arm64-v8a",
            "archiveMember": library_member,
            "sha256": hashlib.sha256(library_bytes).hexdigest(),
        }
        destination = runtime_home / "dist/vm/android/TotalCross.aab"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(android_template, destination)
        runtime_files.append(android_template)
    else:
        launcher = locate_one(platform_artifact, launcher_name)
        vm = locate_one(platform_artifact, vm_name)
        launcher_destination = runtime_home / "etc/launchers" / platform_folder / launcher_name
        vm_destination = runtime_home / "dist/vm" / platform_folder / vm_name
        launcher_destination.parent.mkdir(parents=True, exist_ok=True)
        vm_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(launcher, launcher_destination)
        shutil.copy2(vm, vm_destination)
        if arguments.target == "windows":
            require_windows_x64(launcher)
            require_windows_x64(vm)
            windows_runtime_artifact = {
                "machine": "AMD64",
                "launcherSha256": sha256(launcher),
                "vmSha256": sha256(vm),
            }
        runtime_files.extend((launcher, vm))

    java = shutil.which("java")
    javac = shutil.which("javac")
    jar = shutil.which("jar")
    if not java or not javac or not jar:
        raise SmokeError("JDK java, javac, and jar commands are required")
    sdk_jars = sorted((runtime_home / "dist").glob("totalcross-sdk*.jar"))
    libraries = runtime_home / "dist/libs"
    if not sdk_jars or not libraries.is_dir():
        raise SmokeError("packaged SDK jars or dist/libs are missing")
    classes = output / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    source = lab_root / "tests/image-ownership/src/totalcross/ui/image/ImageOwnershipLifecycleProbe.java"
    if not source.is_file():
        raise SmokeError("ownership smoke Java source is missing")
    classpath = os.pathsep.join([str(sdk_jars[0]), str(libraries / "*")])
    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(runtime_home)
    compile_log = output / "compile.log"
    run_logged([javac, "--release", "8", "-cp", classpath, "-d", str(classes), str(source)],
               output, compile_log, env)

    jar_path = output / (ENTRY_CLASS.rsplit(".", 1)[-1] + ".jar")
    run_logged([jar, "cf", str(jar_path), "-C", str(classes), "."], output,
               output / "jar.log", env)
    deploy_classpath = os.pathsep.join([str(sdk_jars[0]), str(libraries / "*")])
    deploy_log = output / "deploy.log"
    run_logged([java, "-cp", deploy_classpath, "tc.Deploy", str(jar_path),
                "-" + target_flag, "/p", "/n", APP_NAME], output, deploy_log, env)

    install_root = output / "install" / platform_folder
    if arguments.target == "android":
        package = install_root / (APP_NAME + ".apk")
    else:
        executable = APP_NAME + (".exe" if arguments.target == "windows" else "")
        package = install_root / executable
    if not package.is_file():
        raise SmokeError("deployer output is missing: " + str(package))

    provenance = {
        "schemaVersion": 1,
        "target": arguments.target,
        "totalcrossSourceCommit": sdk_manifest["source"]["commit"],
        "totalcrossSourceTree": sdk_manifest["source"]["tree"],
        "performanceLabCommit": lab_commit,
        "totalcrossSourceDirty": sdk_manifest["source"].get("dirty"),
        "buildRuns": {"sdk": sdk_manifest.get("producer"),
                      "platform": platform_manifest.get("producer")},
        "sdkBuildIdentity": sdk_manifest.get("build", {}).get("id")
        or sdk_manifest.get("compatibility"),
        "sdkArtifact": {"path": str(arguments.sdk_provenance), "sha256": sha256(arguments.sdk_provenance)},
        "sdkBuildArchive": {"path": str(arguments.sdk_archive.resolve()),
                            "sha256": sha256(arguments.sdk_archive.resolve())},
        "platformArtifact": {"path": str(arguments.platform_provenance),
                             "sha256": sha256(arguments.platform_provenance)},
        "platformRuntimeArtifacts": [
            {"path": str(path), "sha256": sha256(path)} for path in runtime_files
        ],
        "smokeAppJar": {"path": str(jar_path), "sha256": sha256(jar_path)},
        "deployedPackage": {"path": str(package), "sha256": sha256(package)},
    }
    if windows_runtime_artifact is not None:
        provenance["windowsRuntimeArtifact"] = windows_runtime_artifact
    if android_runtime_library is not None:
        provenance["androidRuntimeLibrary"] = android_runtime_library
    (output / "image-ownership-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "prepared", "target": arguments.target,
                      "package": str(package), "sourceCommit": arguments.source_commit,
                      "performanceLabCommit": lab_commit}, sort_keys=True))


def parse_result(log: str) -> dict:
    for line in log.splitlines():
        marker = line.find(RESULT_PREFIX)
        if marker >= 0:
            try:
                return json.loads(line[marker + len(RESULT_PREFIX):].strip())
            except json.JSONDecodeError as error:
                raise SmokeError("smoke result marker is not valid JSON") from error
    failures = [line for line in log.splitlines() if FAILURE_PREFIX in line]
    detail = failures[-1] if failures else "result marker was not emitted"
    raise SmokeError(detail)


def validate_result(result: dict) -> None:
    expected = {
        "status": "PASS",
        "screenCycles": 2,
        "controlsPerCycle": 1510,
        "distinctImagesPerCycle": 1510,
        "ownersAfterDetach": 0,
        "directParentsPreserved": True,
        "mutationsWhileDetached": True,
        "ownersRestoredAfterReattach": True,
        "activeReparentOwnerCount": 1,
        "activeReparentCachePreserved": True,
        "maxSharedOwners": 3,
        "rasterRetainedUntilFinalOwner": True,
        "pipelineReplacementOwners": 3,
        "cacheReusedWhileOwned": True,
        "cacheEvictedAfterDetach": True,
        "drawPixelRgb": 16711680,
        "png": "image-ownership-render.png",
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise SmokeError("ownership smoke assertion failed for " + key)


def host_output(binary: Path, stdout: str, target: str) -> str:
    if target == "windows" and RESULT_PREFIX not in stdout:
        debug_console = binary.parent / "DebugConsole.txt"
        if debug_console.is_file():
            return stdout + "\n" + debug_console.read_text(encoding="utf-8", errors="replace")
    return stdout


def result_provenance(output: Path) -> dict:
    provenance = read_json(output / "image-ownership-provenance.json")
    return {
        "totalcrossSourceCommit": provenance["totalcrossSourceCommit"],
        "totalcrossSourceTree": provenance["totalcrossSourceTree"],
        "performanceLabCommit": provenance["performanceLabCommit"],
        "target": provenance["target"],
        "deployedPackage": provenance["deployedPackage"],
    }


def run_host(arguments) -> None:
    output = arguments.output.resolve()
    platform_folder, _, _, _ = TARGETS[arguments.target]
    executable = APP_NAME + (".exe" if arguments.target == "windows" else "")
    binary = output / "install" / platform_folder / executable
    if not binary.is_file():
        raise SmokeError("deployed native executable is missing: " + str(binary))
    windows_runtime = None
    if arguments.target == "windows":
        require_windows_x64(binary)
        deployed_vm = binary.parent / "tcvm.dll"
        if not deployed_vm.is_file():
            raise SmokeError("deployed native Windows VM is missing: " + str(deployed_vm))
        require_windows_x64(deployed_vm)
        provenance = read_json(output / "image-ownership-provenance.json")
        runtime_artifacts = provenance.get("platformRuntimeArtifacts", [])
        source_vm = next((Path(item["path"]) for item in runtime_artifacts
                          if Path(item["path"]).name.lower() == "tcvm.dll"), None)
        source_launcher = next((Path(item["path"]) for item in runtime_artifacts
                                if Path(item["path"]).name.lower() == "launcher.exe"), None)
        if source_vm is None or source_launcher is None:
            raise SmokeError("Windows runtime artifact provenance is incomplete")
        if sha256(source_vm) != sha256(deployed_vm):
            raise SmokeError("deployed tcvm.dll does not match the same-run Windows artifact")
        windows_runtime = {
            "machine": "AMD64",
            "deployedLauncherSha256": sha256(binary),
            "sourceLauncherSha256": sha256(source_launcher),
            "deployedVmSha256": sha256(deployed_vm),
            "sourceVmSha256": sha256(source_vm),
            "vmArtifactMatches": True,
        }
    env = os.environ.copy()
    if arguments.target == "linux-amd64":
        env["LD_LIBRARY_PATH"] = str(binary.parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    elif arguments.target == "macos":
        env["DYLD_PRINT_LIBRARIES"] = "1"
    else:
        env["PATH"] = str(binary.parent) + os.pathsep + env.get("PATH", "")
    if arguments.target == "macos":
        otool = subprocess.run(["otool", "-L", str(binary)], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=30, check=False)
        (output / "otool-macos.txt").write_text(otool.stdout, encoding="utf-8",
                                                errors="replace")
        if otool.returncode:
            raise SmokeError("otool -L failed for the deployed macOS executable")
        try:
            result = subprocess.run([str(binary)], cwd=binary.parent, env=env,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=180, check=False)
            stdout, stderr, returncode = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            (output / "runtime-stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
            (output / "runtime-stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
            raise SmokeError("native macOS process exceeded 180 seconds; captured partial output") from error
        (output / "runtime-stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
        (output / "runtime-stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
        runtime_output = host_output(binary, stdout + "\n" + stderr, arguments.target)
    else:
        try:
            result = subprocess.run([str(binary)], cwd=binary.parent, env=env,
                                    text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=180, check=False)
            returncode = result.returncode
            runtime_output = host_output(binary, result.stdout, arguments.target)
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            runtime_output = host_output(binary, stdout, arguments.target)
            (output / "runtime.log").write_text(runtime_output, encoding="utf-8",
                                                errors="replace")
            raise SmokeError("native " + arguments.target
                             + " process exceeded 180 seconds; captured partial output") from error
    log_path = output / "runtime.log"
    log_path.write_text(runtime_output, encoding="utf-8", errors="replace")
    outcome = {"status": "PASS", "target": arguments.target,
               "exitCode": returncode, "log": log_path.name,
               "provenance": result_provenance(output)}
    if windows_runtime is not None:
        outcome["windowsRuntime"] = windows_runtime
    try:
        assertions = parse_result(runtime_output)
        validate_result(assertions)
        outcome["assertions"] = assertions
        if returncode != 0:
            raise SmokeError("native app exited with status %d" % returncode)
        png = output / "install" / platform_folder / assertions["png"]
        if arguments.target == "macos":
            if not png.is_file() or png.stat().st_size == 0:
                raise SmokeError("native macOS PNG output is missing or empty")
            provenance = read_json(output / "image-ownership-provenance.json")
            runtime_artifacts = provenance["platformRuntimeArtifacts"]
            source_vm = next((Path(item["path"]) for item in runtime_artifacts
                              if Path(item["path"]).name == "libtcvm.dylib"), None)
            source_launcher = next((Path(item["path"]) for item in runtime_artifacts
                                   if Path(item["path"]).name == "Launcher"), None)
            deployed_vm = binary.parent / "libtcvm.dylib"
            if (source_vm is None or source_launcher is None or not source_vm.is_file()
                    or not source_launcher.is_file()):
                raise SmokeError("native runtime artifact provenance is incomplete")
            if not deployed_vm.is_file() or sha256(source_vm) != sha256(deployed_vm):
                raise SmokeError("deployed libtcvm.dylib does not match the freshly built library")
            if sha256(source_launcher) != sha256(binary):
                raise SmokeError("deployed executable does not match the freshly built Launcher")
            loaded_lines = [line for line in runtime_output.splitlines()
                            if "libtcvm.dylib" in line and str(deployed_vm.resolve()) in line]
            if not loaded_lines:
                raise SmokeError("dyld output does not prove loading the deployed libtcvm.dylib")
            outcome["macosRuntime"] = {
                "executable": str(binary),
                "launcherSha256": sha256(binary),
                "sourceDylibSha256": sha256(source_vm),
                "deployedDylibSha256": sha256(deployed_vm),
                "loadedDylibLine": loaded_lines[-1],
                "otoolLog": "otool-macos.txt",
                "stdoutLog": "runtime-stdout.log",
                "stderrLog": "runtime-stderr.log",
                "png": {"path": str(png), "sha256": sha256(png)},
            }
    except SmokeError as error:
        outcome["status"] = "FAIL"
        outcome["error"] = str(error)
        (output / "image-ownership-result.json").write_text(
            json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    (output / "image-ownership-result.json").write_text(
        json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(outcome, sort_keys=True))


def run_android(arguments) -> None:
    output = arguments.output.resolve()
    apk = output / "install/android" / (APP_NAME + ".apk")
    android_home = Path(os.environ.get("ANDROID_HOME", os.environ.get("ANDROID_SDK_ROOT", "")))
    build_tools = sorted((android_home / "build-tools").glob("*/aapt"))
    aapt = shutil.which("aapt") or (build_tools[-1] if build_tools else None)
    adb = shutil.which("adb")
    if not apk.is_file() or not aapt or not adb:
        raise SmokeError("Android APK, aapt, or adb is missing")
    badging = subprocess.run([str(aapt), "dump", "badging", str(apk)],
                             text=True, capture_output=True, check=True).stdout
    package_match = re.search(r"^package: name='([^']+)'", badging, re.MULTILINE)
    if not package_match:
        raise SmokeError("cannot identify Android package name from APK")
    package_name = package_match.group(1)
    package_hash = sha256(apk)
    provenance = read_json(output / "image-ownership-provenance.json")
    if provenance.get("deployedPackage", {}).get("sha256") != package_hash:
        raise SmokeError("Android APK hash differs from its prepared provenance")
    expected_library = provenance.get("androidRuntimeLibrary", {})
    apk_library_member, apk_library_bytes = zip_member(apk, "lib/arm64-v8a/libtcvm.so")
    apk_library_hash = hashlib.sha256(apk_library_bytes).hexdigest()
    if (expected_library.get("abi") != "arm64-v8a"
            or expected_library.get("sha256") != apk_library_hash):
        raise SmokeError("APK arm64-v8a libtcvm.so does not match the same-run Android AAB")

    device_api = subprocess.run([adb, "shell", "getprop", "ro.build.version.sdk"],
                                text=True, capture_output=True, check=True).stdout.strip()
    device_abi = subprocess.run([adb, "shell", "getprop", "ro.product.cpu.abi"],
                                text=True, capture_output=True, check=True).stdout.strip()
    device_model = subprocess.run([adb, "shell", "getprop", "ro.product.model"],
                                  text=True, capture_output=True, check=True).stdout.strip()
    if not device_api.isdigit():
        raise SmokeError("cannot determine Android emulator API level")
    if arguments.expected_api is not None and int(device_api) != arguments.expected_api:
        raise SmokeError("Android emulator API level %s does not match expected %d"
                         % (device_api, arguments.expected_api))
    if arguments.expected_abi is not None and device_abi != arguments.expected_abi:
        raise SmokeError("Android emulator ABI %s does not match expected %s"
                         % (device_abi, arguments.expected_abi))

    subprocess.run([adb, "uninstall", package_name], check=False, timeout=30,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([adb, "logcat", "-c"], check=True, stdout=subprocess.DEVNULL)
    install = subprocess.run([adb, "install", str(apk)], text=True, capture_output=True,
                             check=True, timeout=180)
    subprocess.run([adb, "shell", "monkey", "-p", package_name, "1"],
                   check=True, timeout=60, stdout=subprocess.DEVNULL)
    deadline = time.monotonic() + arguments.timeout
    log = ""
    while time.monotonic() < deadline:
        log = subprocess.run([adb, "logcat", "-d", "-v", "raw"],
                             text=True, capture_output=True, check=True).stdout
        if RESULT_PREFIX in log or FAILURE_PREFIX in log:
            break
        time.sleep(2)
    (output / "runtime-android-logcat.txt").write_text(log, encoding="utf-8", errors="replace")
    outcome = {"status": "PASS", "target": "android", "packageName": package_name,
               "log": "runtime-android-logcat.txt", "provenance": result_provenance(output),
               "device": {"apiLevel": int(device_api), "abi": device_abi,
                          "model": device_model},
               "installation": {"status": "installed", "apkSha256": package_hash,
                                "output": install.stdout.strip()},
               "nativeLibrary": {"abi": "arm64-v8a", "archiveMember": apk_library_member,
                                 "sha256": apk_library_hash},
               "applicationCompletion": "PASS result marker observed; app calls MainWindow.exit(0)"}
    try:
        crash_pattern = re.compile(
            r"FATAL EXCEPTION|Fatal signal|SIG(?:SEGV|ABRT|BUS)|native crash|"
            r"persistent.{0,30}owner.{0,20}underflow", re.IGNORECASE)
        crash_lines = [line for line in log.splitlines() if crash_pattern.search(line)]
        if crash_lines:
            raise SmokeError("Android logcat contains crash/underflow diagnostics: "
                             + " | ".join(crash_lines[-8:]))
        assertions = parse_result(log)
        validate_result(assertions)
        outcome["assertions"] = assertions
        outcome["processIdAfterCompletion"] = subprocess.run(
            [adb, "shell", "pidof", package_name], text=True, capture_output=True,
            check=False, timeout=15).stdout.strip() or None
    except SmokeError as error:
        outcome["status"] = "FAIL"
        outcome["error"] = str(error)
        (output / "image-ownership-result.json").write_text(
            json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    (output / "image-ownership-result.json").write_text(
        json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(outcome, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--target", choices=TARGETS, required=True)
    prepare_parser.add_argument("--runtime-home", type=Path, required=True)
    prepare_parser.add_argument("--platform-artifact", type=Path, required=True)
    prepare_parser.add_argument("--sdk-provenance", type=Path, required=True)
    prepare_parser.add_argument("--platform-provenance", type=Path, required=True)
    prepare_parser.add_argument("--sdk-archive", type=Path, required=True)
    prepare_parser.add_argument("--source-commit", required=True)
    prepare_parser.add_argument("--source-tree", required=True)
    prepare_parser.add_argument("--lab-root", type=Path, required=True)
    prepare_parser.add_argument("--lab-commit", required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--allow-dirty-source", action="store_true")
    host_parser = subparsers.add_parser("run-host")
    host_parser.add_argument("--target", choices=("macos", "linux-amd64", "windows"), required=True)
    host_parser.add_argument("--output", type=Path, required=True)
    android_parser = subparsers.add_parser("run-android")
    android_parser.add_argument("--output", type=Path, required=True)
    android_parser.add_argument("--timeout", type=int, default=120)
    android_parser.add_argument("--expected-api", type=int)
    android_parser.add_argument("--expected-abi")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "prepare":
            prepare(arguments)
        elif arguments.command == "run-host":
            run_host(arguments)
        else:
            run_android(arguments)
    except (OSError, subprocess.SubprocessError, SmokeError) as error:
        output = getattr(arguments, "output", None)
        if output is not None and Path(output).is_dir():
            failure = {"status": "FAIL", "phase": arguments.command, "error": str(error)}
            (Path(output) / "image-ownership-result.json").write_text(
                json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("image ownership smoke error: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
