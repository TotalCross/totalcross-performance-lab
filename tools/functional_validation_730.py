#!/usr/bin/env python3
"""Build probes and capture Linux runtime observations for the 7.3.0 campaign."""
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
PNG_FIXTURES = ROOT / "investigations/7.3.0-functional/cases/png-decoding/fixtures"
STARTUP_SOURCE = ROOT / "tests/functional-validation/LinuxStartupProbe.java"
PNG_SOURCE = ROOT / "tests/functional-validation/LinuxPngDecodeProbe.java"
CONFIG = ROOT / "investigations/7.3.0-functional/campaign-run.json"
FROZEN_MASTER = "6b915883dd202f6db891990f6c3af26fb645ecc7"
APP_NAMES = {"startup": "LinuxStartupProbe", "png": "LinuxPngDecodeProbe"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination):
                raise RuntimeError("unsafe archive path: " + item.filename)
        bundle.extractall(destination)


def find_sdk(root):
    root = Path(root)
    candidates = [root] if (root / "dist").is_dir() else []
    candidates += [entry.parent.parent for entry in root.rglob("totalcross-sdk*.jar")
                   if entry.parent.name == "dist"]
    for home in candidates:
        if (home / "dist").is_dir() and (home / "etc").is_dir():
            jar = home / "dist" / "totalcross-sdk.jar"
            if not jar.is_file():
                matches = sorted(home.glob("dist/totalcross-sdk-*.jar"))
                matches = [p for p in matches if not p.name.endswith(("-sources.jar", "-javadoc.jar"))]
                if matches:
                    jar = matches[0]
            if jar.is_file():
                return home.resolve(), jar.resolve()
    raise RuntimeError("SDK root must contain dist/*.jar and etc/")


def extract_package(package, out):
    package = Path(package).resolve()
    home, _ = find_sdk(package) if package.is_dir() else (None, None)
    if home:
        return home
    extraction = Path(out) / "package"
    if extraction.exists():
        raise RuntimeError("refusing to overwrite existing package extraction: " + str(extraction))
    safe_extract(package, extraction)
    try:
        return find_sdk(extraction)[0]
    except RuntimeError:
        nested = list(extraction.rglob("TotalCross-7.3.0.zip"))
        if len(nested) != 1:
            raise RuntimeError("package archive did not contain a TotalCross SDK layout")
        expanded = Path(out) / "package-nested"
        safe_extract(nested[0], expanded)
        return find_sdk(expanded)[0]


def copy_native_runtime(home, native_dir):
    if native_dir is None:
        return
    native_dir = Path(native_dir).resolve()
    library = native_dir / "libtcvm.so"
    launcher = native_dir / "Launcher"
    if not library.is_file() or not launcher.is_file():
        raise RuntimeError("native directory must contain libtcvm.so and Launcher")
    vm_dir = Path(home) / "dist/vm/linux"
    launcher_dir = Path(home) / "etc/launchers/linux"
    vm_dir.mkdir(parents=True, exist_ok=True)
    launcher_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(library, vm_dir / library.name)
    launcher_target = launcher_dir / launcher.name
    shutil.copy2(launcher, launcher_target)
    launcher_target.chmod(launcher_target.stat().st_mode | 0o111)


def run_command(command, cwd, log, env=None, timeout=900):
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write("$ " + " ".join(map(str, command)) + "\n")
        stream.flush()
        result = subprocess.run(list(map(str, command)), cwd=str(cwd), env=env,
                                stdout=stream, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
        stream.write("\nEXIT_CODE=" + str(result.returncode) + "\n")
    if result.returncode:
        raise RuntimeError("command failed with exit " + str(result.returncode) + "; see " + str(log))
    return result


def validate_config(path=CONFIG):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1 or data.get("platform") != "linux-x86_64":
        raise ValueError("campaign config must select schema 1 and linux-x86_64")
    if data.get("frozenMasterSha") != FROZEN_MASTER:
        raise ValueError("campaign config frozen master does not match the recorded SHA")
    if set(data.get("cases", {})) - {"I01-B", "I02"}:
        raise ValueError("this workflow slice implements only I01-B and I02")
    if set(data.get("prohibitedRuntimePlatforms", [])) != {
            "windows-amd64", "ios", "android-actions"}:
        raise ValueError("campaign config must keep prohibited runtime platforms excluded")
    for case in data["cases"].values():
        if "windows-amd64" in case.get("scenarios", []):
            raise ValueError("a runtime platform must not appear as a scenario")
    return data


def build_probe(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.sdk_root:
        home, sdk_jar = find_sdk(args.sdk_root)
    else:
        home = extract_package(args.package, out)
        home, sdk_jar = find_sdk(home)
    copy_native_runtime(home, args.native_dir)

    app_name = APP_NAMES[args.kind]
    source = STARTUP_SOURCE if args.kind == "startup" else PNG_SOURCE
    classes = out / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    dist = home / "dist"
    classpath = str(sdk_jar) + os.pathsep + str(dist / "libs" / "*")
    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(home)
    run_command(["javac", "--release", "8", "-cp", classpath, "-d", classes, source],
                ROOT, out / "compile.log", env)
    if args.kind == "png":
        resource = classes / "fixtures"
        resource.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PNG_FIXTURES / "tcz-png.png", resource / "tcz-png.png")
    app_jar = out / (app_name + ".jar")
    run_command(["jar", "cf", app_jar, "-C", classes, "."], ROOT, out / "jar.log", env)

    deployed = out / "deployed"
    deployed.mkdir(exist_ok=True)
    command = ["java", "-cp", classpath, "tc.Deploy", str(app_jar),
               "-linux", "/p", "/n", app_name, "/o", str(deployed) + os.sep]
    run_command(command, ROOT, out / "deploy.log", env, timeout=1800)
    install = deployed / "install/linux"
    executable = install / app_name
    if not executable.is_file():
        raise RuntimeError("deployer did not create " + str(executable))
    executable.chmod(executable.stat().st_mode | 0o111)
    if args.kind == "png":
        for name in ("comparison-png.png", "comparison-control.jpg", "alpha.png",
                     "indexed.png", "invalid.bin"):
            shutil.copy2(PNG_FIXTURES / name, install / name)
    report = {
        "kind": args.kind,
        "appName": app_name,
        "sdkHome": str(home),
        "sdkJarSha256": sha256(sdk_jar),
        "linuxLibtcvmSha256": sha256(home / "dist/vm/linux/libtcvm.so"),
        "linuxLauncherSha256": sha256(home / "etc/launchers/linux/Launcher"),
        "applicationJarSha256": sha256(app_jar),
        "installPath": str(install),
    }
    (out / "prepared.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


def make_long_path(base, min_length=1200):
    path = Path(base).resolve()
    path.mkdir(parents=True, exist_ok=True)
    index = 0
    while len(str(path / "install" / APP_NAMES["startup"])) < min_length:
        component = "segment_" + str(index).zfill(2) + "_" + ("x" * 105)
        if len(component) > 255:
            raise ValueError("path segment exceeds the portable component limit")
        path = path / component
        path.mkdir()
        index += 1
    return path / "install"


def scenario_install(install, scenario, out):
    install = Path(install).resolve()
    roots = Path(out) / "paths"
    roots.mkdir(parents=True, exist_ok=True)
    if scenario == "normal-path":
        return install, len(str(install / APP_NAMES["startup"]))
    if scenario == "short-path":
        target = roots / "short" / "install"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(install, target)
        return target, len(str(target / APP_NAMES["startup"]))
    if scenario == "long-path":
        target = make_long_path(roots / "long")
        shutil.copytree(install, target)
        return target, len(str(target / APP_NAMES["startup"]))
    if scenario == "symlink":
        alias = roots / "symlink" / "install"
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(install, target_is_directory=True)
        return alias, len(str(alias / APP_NAMES["startup"]))
    raise ValueError("unknown startup scenario: " + scenario)


def run_runtime(executable, cwd, log, timeout, shim=None, ld_debug=False):
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(cwd) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    debug_prefix = None
    app_environment = []
    if shim:
        app_environment.append("LD_PRELOAD=" + str(Path(shim).resolve()))
    if ld_debug:
        debug_prefix = Path(log).with_name("ld-debug-raw")
        app_environment.extend(("LD_DEBUG=bindings", "LD_DEBUG_OUTPUT=" + str(debug_prefix)))
    started = time.time()
    timed_out = False
    launch_path = Path(executable).absolute()
    command = ["xvfb-run", "-a", "env", *app_environment, str(launch_path)]
    try:
        result = subprocess.run(command,
                                cwd=str(Path(cwd).resolve()), env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout, check=False)
        output = result.stdout.decode("utf-8", errors="replace")
        returncode = result.returncode
    except subprocess.TimeoutExpired as failure:
        timed_out = True
        raw = failure.stdout or b""
        output = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        returncode = None
    log.write_text(output, encoding="utf-8")
    if ld_debug:
        raw_files = sorted(log.parent.glob(debug_prefix.name + ".*"))
        binding_lines = []
        for raw_file in raw_files:
            binding_lines.extend(raw_file.read_text(encoding="utf-8", errors="replace").splitlines())
            raw_file.unlink()
        selected = [line for line in binding_lines
                    if re.search(r"png|zlib|inflate|crc|tcvm", line, re.IGNORECASE)]
        (log.parent / "ld-debug-targets.log").write_text("\n".join(selected) + "\n", encoding="utf-8")
    return {
        "processReturnCode": returncode,
        "shellExitCode": (128 + abs(returncode)) if returncode is not None and returncode < 0 else returncode,
        "signal": -returncode if returncode is not None and returncode < 0 else None,
        "timedOut": timed_out,
        "durationSeconds": round(time.time() - started, 3),
        "workingDirectory": str(Path(cwd).resolve()),
        "launchPath": str(launch_path),
        "startupMarker": "TC_STARTUP_MARKER" in output,
        "pngCompletionMarker": "TC_PNG_RESULT complete=true" in output,
        "pngCases": [line for line in output.splitlines() if line.startswith("TC_PNG case=")],
    }


def run_startup(args):
    work_dir = args.work_dir if args.work_dir else args.out
    install, path_length = scenario_install(args.install_dir, args.scenario, work_dir)
    executable = install / APP_NAMES["startup"]
    result = run_runtime(executable, install, Path(args.out) / args.scenario / "runtime.log", args.timeout)
    report = {
        "case": "I01-B",
        "scenario": args.scenario,
        "installPathLength": path_length,
        "observed": result,
        "observationStatus": "CAPTURED" if not result["timedOut"] else "TIMEOUT",
    }
    out = Path(args.out) / args.scenario
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


def run_png(args):
    install = Path(args.install_dir).resolve()
    result = run_runtime(install / APP_NAMES["png"], install,
                         Path(args.out) / "runtime.log", args.timeout,
                         shim=args.shim, ld_debug=args.ld_debug)
    report = {
        "case": "I02",
        "runtimeShim": str(Path(args.shim).resolve()) if args.shim else None,
        "ldDebugBindings": bool(args.ld_debug),
        "observed": result,
        "observationStatus": "CAPTURED" if not result["timedOut"] else "TIMEOUT",
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    config_parser = subparsers.add_parser("validate-config")
    config_parser.add_argument("--config", type=Path, default=CONFIG)

    build = subparsers.add_parser("build-probe")
    build.add_argument("--kind", choices=sorted(APP_NAMES), required=True)
    source_group = build.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--sdk-root", type=Path)
    source_group.add_argument("--package", type=Path)
    build.add_argument("--native-dir", type=Path)
    build.add_argument("--out", type=Path, required=True)

    startup = subparsers.add_parser("run-startup")
    startup.add_argument("--install-dir", type=Path, required=True)
    startup.add_argument("--scenario", choices=["normal-path", "short-path", "long-path", "symlink"], required=True)
    startup.add_argument("--out", type=Path, required=True)
    startup.add_argument("--work-dir", type=Path)
    startup.add_argument("--timeout", type=int, default=90)

    png = subparsers.add_parser("run-png")
    png.add_argument("--install-dir", type=Path, required=True)
    png.add_argument("--out", type=Path, required=True)
    png.add_argument("--timeout", type=int, default=90)
    png.add_argument("--shim", type=Path)
    png.add_argument("--ld-debug", action="store_true")
    args = parser.parse_args()

    try:
        if args.command == "validate-config":
            config = validate_config(args.config)
            print(json.dumps({"status": "valid", "sequence": config["sequence"],
                              "cases": list(config["cases"])}))
        elif args.command == "build-probe":
            build_probe(args)
        elif args.command == "run-startup":
            run_startup(args)
        else:
            run_png(args)
    except Exception as failure:
        print("functional-validation harness failure: " + str(failure), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
