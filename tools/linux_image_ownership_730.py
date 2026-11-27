#!/usr/bin/env python3
"""Prepare and run the Linux ImageDrawingBridge ownership acceptance probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/functional-validation/totalcross/ui/image/ImageOwnershipLifecycleProbe.java"
APP_NAME = "ImageOwnershipSmoke"
ENTRY = "TC_IMAGE_OWNERSHIP_JSON "
FAILURE = "TC_IMAGE_OWNERSHIP_FAIL "


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
        if (jar.is_file() and (home / "etc").is_dir()
                and (home / "dist/libs").is_dir()):
            with zipfile.ZipFile(jar) as archive:
                if "tc/Deploy.class" not in archive.namelist():
                    raise ProbeError("SDK jar does not contain tc.Deploy: " + str(jar))
            return home.resolve(), jar.resolve()
    raise ProbeError("SDK root must contain dist/totalcross-sdk.jar, dist/libs, and etc/")


def logged(command: list[str], cwd: Path, env: dict[str, str], log: Path,
           timeout: int = 1800) -> subprocess.CompletedProcess:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as output:
        output.write("$ " + " ".join(command) + "\n")
        output.flush()
        result = subprocess.run(command, cwd=cwd, env=env, stdout=output,
                                stderr=subprocess.STDOUT, timeout=timeout, check=False)
        output.write("\nEXIT_CODE=" + str(result.returncode) + "\n")
    if result.returncode:
        raise ProbeError("command failed with exit %d; see %s" % (result.returncode, log))
    return result


def prepare(args: argparse.Namespace) -> dict:
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ProbeError("refusing to overwrite non-empty output directory: " + str(out))
    out.mkdir(parents=True, exist_ok=True)
    home, sdk_jar = locate_sdk(args.sdk_root.resolve())
    native_dir = args.native_dir.resolve()
    library = native_dir / "libtcvm.so"
    launcher = native_dir / "Launcher"
    if not library.is_file() or not launcher.is_file():
        raise ProbeError("native directory must contain libtcvm.so and Launcher")
    vm_dir = home / "dist/vm/linux"
    launcher_dir = home / "etc/launchers/linux"
    vm_dir.mkdir(parents=True, exist_ok=True)
    launcher_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(library, vm_dir / library.name)
    deployed_launcher = launcher_dir / launcher.name
    shutil.copy2(launcher, deployed_launcher)
    deployed_launcher.chmod(deployed_launcher.stat().st_mode | 0o111)

    java = shutil.which("java")
    javac = shutil.which("javac")
    jar = shutil.which("jar")
    if not java or not javac or not jar:
        raise ProbeError("JDK java, javac, and jar are required")
    if not SOURCE.is_file():
        raise ProbeError("ownership probe source is missing: " + str(SOURCE))
    classes = out / "classes"
    classes.mkdir()
    if args.mode == "baseline":
        (classes / "tcapp.prop").write_text("diagnostic.mode=baseline\n", encoding="utf-8")
    classpath = os.pathsep.join((str(sdk_jar), str(home / "dist/libs/*")))
    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(home)
    logged([javac, "--release", "8", "-cp", classpath, "-d", str(classes), str(SOURCE)],
           ROOT, env, out / "compile.log")
    app_jar = out / (APP_NAME + ".jar")
    logged([jar, "cf", str(app_jar), "-C", str(classes), "."], ROOT, env,
           out / "jar.log")
    deployed = out / "deployed"
    deployed.mkdir()
    logged([java, "-cp", classpath, "tc.Deploy", str(app_jar), "-linux", "/p", "/n",
            APP_NAME, "/o", str(deployed) + os.sep], ROOT, env, out / "deploy.log")
    install = deployed / "install/linux"
    executable = install / APP_NAME
    if not executable.is_file():
        raise ProbeError("deployer did not create " + str(executable))
    executable.chmod(executable.stat().st_mode | 0o111)
    record = {
        "mode": args.mode,
        "sourceCommit": args.source_commit,
        "sourceTree": args.source_tree,
        "runtimeSourceCommit": args.runtime_source_commit,
        "runtimeSourceTree": args.runtime_source_tree,
        "runtimeSourceSubtree": args.runtime_source_subtree,
        "runtimeNativeBridgesSha256": args.runtime_native_bridges_sha256,
        "runtimeSourceSubtreeMatchesCandidate": args.runtime_subtree_matches_candidate,
        "probeSourceCommit": args.probe_source_commit,
        "sdkJarSha256": sha256(sdk_jar),
        "launcherSha256": sha256(launcher),
        "libtcvmSha256": sha256(library),
        "appJarSha256": sha256(app_jar),
        "executableSha256": sha256(executable),
        "sdkHome": str(home),
        "installDir": str(install),
    }
    (out / "prepared.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def validate_assertions(assertions: dict, mode: str) -> None:
    common = {
        "screenCycles": 2,
        "controlsPerCycle": 1510,
        "distinctImagesPerCycle": 1510,
        "highestCompletedStage": 7,
        "drawPixelRgb": 16711680,
        "png": "image-ownership-render.png",
    }
    for key, expected in common.items():
        if assertions.get(key) != expected:
            raise ProbeError("ownership result did not satisfy %s=%r" % (key, expected))
    if mode == "baseline":
        if assertions.get("status") != "BASELINE_OBSERVED" \
                or assertions.get("diagnosticMode") != "baseline":
            raise ProbeError("baseline diagnostic marker is missing")
        if not isinstance(assertions.get("ownershipMismatches"), int):
            raise ProbeError("baseline result omitted ownership mismatch count")
    else:
        expected = {
            "status": "PASS",
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
            "diagnosticMode": "fixed",
            "ownershipMismatches": 0,
        }
        for key, value in expected.items():
            if assertions.get(key) != value:
                raise ProbeError("corrected ownership assertion failed for " + key)


def run(args: argparse.Namespace) -> dict:
    out = args.out.resolve()
    prepared = json.loads((out / "prepared.json").read_text(encoding="utf-8"))
    install = Path(prepared["installDir"])
    executable = install / APP_NAME
    if not executable.is_file():
        raise ProbeError("deployed Linux executable is missing")
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(install) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    command = ["xvfb-run", "-a", "env", str(executable)]
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=install, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=args.timeout, check=False)
        output = result.stdout
        exit_code = result.returncode
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        (out / "runtime.log").write_text(output, encoding="utf-8", errors="replace")
        raise ProbeError("Linux ownership process exceeded %d seconds" % args.timeout) from error
    elapsed = int((time.monotonic() - started) * 1000)
    (out / "runtime.log").write_text(output, encoding="utf-8", errors="replace")
    if exit_code != 0:
        failures = [line for line in output.splitlines() if FAILURE in line]
        detail = failures[-1] if failures else "native app exit code %d" % exit_code
        raise ProbeError("ownership probe failed: " + detail)
    result_line = next((line.split(ENTRY, 1)[1].strip() for line in output.splitlines()
                        if ENTRY in line), None)
    if result_line is None:
        raise ProbeError("native app emitted no ownership result marker")
    try:
        assertions = json.loads(result_line)
    except json.JSONDecodeError as error:
        raise ProbeError("ownership result marker is invalid JSON") from error
    validate_assertions(assertions, args.mode)
    png = install / assertions["png"]
    if not png.is_file() or png.stat().st_size == 0:
        raise ProbeError("ownership render PNG is missing or empty")
    record = {
        "status": "BASELINE_OBSERVED" if args.mode == "baseline" else "PASS",
        "mode": args.mode,
        "exitCode": exit_code,
        "durationMilliseconds": elapsed,
        "assertions": assertions,
        "renderedPngSha256": sha256(png),
        "runtimeLog": "runtime.log",
        "prepared": prepared,
    }
    (out / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, sort_keys=True))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--sdk-root", type=Path, required=True)
    prepare_parser.add_argument("--native-dir", type=Path, required=True)
    prepare_parser.add_argument("--mode", choices=("baseline", "fixed"), required=True)
    prepare_parser.add_argument("--source-commit", required=True)
    prepare_parser.add_argument("--source-tree", required=True)
    prepare_parser.add_argument("--runtime-source-commit", required=True)
    prepare_parser.add_argument("--runtime-source-tree", required=True)
    prepare_parser.add_argument("--runtime-source-subtree", required=True)
    prepare_parser.add_argument("--runtime-native-bridges-sha256", required=True)
    prepare_parser.add_argument("--runtime-subtree-matches-candidate", action="store_true")
    prepare_parser.add_argument("--probe-source-commit", required=True)
    prepare_parser.add_argument("--out", type=Path, required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--mode", choices=("baseline", "fixed"), required=True)
    run_parser.add_argument("--timeout", type=int, default=180)
    run_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            print(json.dumps(prepare(args), sort_keys=True))
        else:
            run(args)
    except (OSError, ProbeError, subprocess.TimeoutExpired, zipfile.BadZipFile) as error:
        print(str(error), file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
