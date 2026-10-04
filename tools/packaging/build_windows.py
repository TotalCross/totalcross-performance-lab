#!/usr/bin/env python3
"""Build a reproducible Windows image-rendering package from a TotalCross checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.datasets import image_scroll

PROFILE_CLASSES = {
    "default": "Default",
    "target-color": "TargetColor",
    "physical-variant": "PhysicalVariant",
    "raster-variants": "RasterVariants",
    "compact": "Compact",
    "scroll-reuse": "ScrollReuse",
    "prepared-legacy": "PreparedLegacy",
    "prepared-semaphore": "PreparedSemaphore",
    "combined-standard": "CombinedStandard",
    "combined-compact": "CombinedCompact",
}


class PackageError(Exception):
    pass


def git(source: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(source), *args], text=True, capture_output=True)
    if result.returncode:
        raise PackageError("cannot read Git identity from " + str(source))
    return result.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_logged(command: list[str], cwd: Path, env: dict[str, str], log) -> None:
    log.write("$ " + subprocess.list2cmdline(command) + "\n")
    log.flush()
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    log.write(result.stdout)
    log.flush()
    if result.returncode:
        raise PackageError("command failed with exit code %d: %s" % (result.returncode, command[0]))


def package_files(profile_dir: Path, executable: Path) -> list[dict[str, str]]:
    files = []
    for path in sorted(item for item in profile_dir.rglob("*") if item.is_file() and item != executable):
        files.append({"path": path.relative_to(profile_dir.parent.parent).as_posix(), "sha256": sha256(path)})
    if not files:
        raise PackageError("deployer produced no runtime files for " + profile_dir.name)
    return files


def verified_dataset_cache(cache: Path) -> tuple[dict, dict, Path]:
    try:
        _, descriptor = image_scroll.load_descriptor(ROOT, "image-scroll/v1")
        result = image_scroll.verify_cache(cache, descriptor)
    except image_scroll.DatasetError as error:
        raise PackageError("a verified image-scroll/v1 cache is required: " + str(error)) from error
    return descriptor, result, cache / "files"


def write_profile_jar(classes: Path, entry_class: str, destination: Path,
                      dataset_files: Path | None = None) -> None:
    entry_relative = Path("totalcross/bench/imagerendering/profiles") / (entry_class + ".class")
    selected = []
    for path in sorted(classes.rglob("*.class")):
        relative = path.relative_to(classes)
        if relative.parent == entry_relative.parent and relative != entry_relative:
            continue
        selected.append((path, relative.as_posix()))
    if not any(relative == entry_relative.as_posix() for _, relative in selected):
        raise PackageError("compiled profile entry class is missing: " + entry_class)
    archive_entries = [(relative, path) for path, relative in selected]
    if dataset_files is not None:
        if not dataset_files.is_dir():
            raise PackageError("verified dataset payload directory is missing: " + str(dataset_files))
        for path in dataset_files.rglob("*"):
            if path.is_file():
                relative = "image-scroll/" + path.relative_to(dataset_files).as_posix()
                archive_entries.append((relative, path))
    archive_entries.sort(key=lambda item: item[0])
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, path in archive_entries:
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def build(arguments) -> Path:
    source = arguments.runtime_source.resolve()
    sdk_home = (arguments.sdk_home or source / "TotalCrossSDK").resolve()
    runtime_home = (arguments.runtime_home or sdk_home).resolve()
    output = arguments.output.resolve()
    if output.exists():
        raise PackageError("output already exists; choose a new path: " + str(output))
    if not source.is_dir() or not sdk_home.is_dir() or not runtime_home.is_dir():
        raise PackageError("runtime source, SDK home, and runtime home must be existing directories")
    source_commit = git(source, "rev-parse", "HEAD")
    if git(source, "status", "--porcelain"):
        raise PackageError("TotalCross source checkout is dirty")
    if arguments.runtime_artifact_commit != source_commit:
        raise PackageError("Windows runtime artifact commit must equal the TotalCross source commit")
    benchmark_commit = git(ROOT, "rev-parse", "HEAD")
    if git(ROOT, "status", "--porcelain"):
        raise PackageError("benchmark repository is dirty; commit the benchmark source before packaging")
    dataset_cache = (arguments.dataset_cache or ROOT / ".local-data/datasets/image-scroll/v1").resolve()
    descriptor, dataset_identity, dataset_files = verified_dataset_cache(dataset_cache)
    java = shutil.which("java")
    javac = shutil.which("javac")
    if not java or not javac:
        raise PackageError("a JDK with java and javac is required")
    sources = sorted((ROOT / "benchmarks/image-rendering/src").rglob("*.java"))
    if not sources:
        raise PackageError("image-rendering benchmark Java sources are missing")
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_name(output.name + ".build.log")
    if log_path.exists():
        raise PackageError("build log already exists; move it before retrying: " + str(log_path))
    stage_parent = output.parent
    with tempfile.TemporaryDirectory(prefix="image-rendering-win-", dir=stage_parent) as temporary:
        stage = Path(temporary)
        package_root = stage / "package"
        package_root.mkdir()
        classes = stage / "classes"
        classes.mkdir()
        runtime_files = [(runtime_home / "etc/launchers/win32/Launcher.exe"),
                         (runtime_home / "dist/vm/win32/tcvm.dll")]
        missing = [str(path) for path in runtime_files if not path.is_file()]
        if missing:
            raise PackageError("Windows runtime package is incomplete: " + ", ".join(missing))
        env = os.environ.copy()
        env["TOTALCROSS3_HOME"] = str(runtime_home)
        with log_path.open("x", encoding="utf-8") as log:
            if arguments.build_sdk:
                wrapper = sdk_home / ("gradlew.bat" if os.name == "nt" else "gradlew-agent")
                if not wrapper.is_file():
                    raise PackageError("SDK Gradle wrapper is missing: " + str(wrapper))
                gradle = (["cmd", "/c", str(wrapper)] if os.name == "nt" else [str(wrapper)])
                run_logged(gradle + ["dist", "-x", "test", "--console=plain"], sdk_home, env, log)
            sdk_jar = sdk_home / "dist/totalcross-sdk.jar"
            libraries = sdk_home / "dist/libs"
            if not sdk_jar.is_file() or not libraries.is_dir():
                raise PackageError("SDK is not built; run with --build-sdk or pass a built --sdk-home")
            compile_cp = os.pathsep.join((str(sdk_jar), str(libraries / "*")))
            run_logged([javac, "--release", "8", "-cp", compile_cp, "-d", str(classes),
                        *map(str, sources)], ROOT, env, log)
            app_cp = os.pathsep.join((str(classes), str(sdk_jar), str(libraries / "*")))
            profile_manifest = {}
            binary_manifest = {}
            for profile, entry in PROFILE_CLASSES.items():
                prefix = "image-rendering-" + profile
                jar_path = stage / "inputs" / profile / (entry + ".jar")
                jar_path.parent.mkdir(parents=True)
                write_profile_jar(classes, entry, jar_path, dataset_files)
                deployment = stage / "deploy" / profile
                deployment.mkdir(parents=True)
                command = [java, "-cp", app_cp, "tc.Deploy", str(jar_path),
                           "-win32", "/p", "/n", prefix, "/o", str(deployment) + os.sep]
                run_logged(command, deployment, env, log)
                deployed = deployment / "win32"
                executable = deployed / (prefix + ".exe")
                if not executable.is_file():
                    raise PackageError("deployer did not create " + str(executable))
                destination = package_root / "profiles" / profile
                shutil.copytree(deployed, destination)
                executable = destination / executable.name
                files = package_files(destination, executable)
                profile_manifest[profile] = {
                    "entryClass": "totalcross.bench.imagerendering.profiles." + entry,
                    "executable": executable.relative_to(package_root).as_posix(),
                    "workingDirectory": destination.relative_to(package_root).as_posix(),
                    "runtimeFiles": files,
                }
                for path in destination.rglob("*"):
                    if path.is_file() and path.suffix.lower() in (".dll", ".exe"):
                        relative = path.relative_to(package_root).as_posix()
                        binary_manifest[relative] = {"path": relative, "sha256": sha256(path)}
            version_result = subprocess.run([java, "-version"], text=True, capture_output=True, check=False)
            java_version = next(iter((version_result.stderr or version_result.stdout).splitlines()), "unavailable")
            manifest = {
                "schemaVersion": 1,
                "packageType": "image-rendering-windows",
                "platform": "windows",
                "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "totalcrossSourceCommit": source_commit,
                "runtimeArtifactSourceCommit": arguments.runtime_artifact_commit,
                "benchmarkSourceCommit": benchmark_commit,
                "benchmarkWorkingTreeDirty": False,
                "dataset": {"id": descriptor["id"], "version": descriptor["version"],
                            "manifestSha256": dataset_identity["manifestSha256"]},
                "buildConfiguration": {
                    "jdk": java_version,
                    "sdkHome": str(sdk_home),
                    "nativeRuntimeDirectory": str(runtime_home),
                    "deployTarget": "win32",
                    "sdkBuildCommand": ["gradlew.bat", "dist", "-x", "test", "--console=plain"] if arguments.build_sdk else [],
                    "javaCompileRelease": 8,
                },
                "profileInventory": list(PROFILE_CLASSES),
                "profiles": profile_manifest,
                "runtimeBinaries": sorted(binary_manifest.values(), key=lambda item: item["path"]),
            }
            sys.path.insert(0, str(ROOT))
            from runners.run import read_json, validate_schema
            schema_dir = ROOT / "schemas"
            validate_schema(manifest, read_json(schema_dir / "benchmark-package-v1.schema.json"), schema_dir)
            (package_root / "package-manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if output.exists():
            raise PackageError("output appeared during build; refusing to replace it: " + str(output))
        shutil.move(str(package_root), output)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source_default = os.environ.get("TOTALCROSS_SOURCE")
    parser.add_argument("--runtime-source", type=Path, default=Path(source_default) if source_default else None)
    parser.add_argument("--sdk-home", type=Path)
    parser.add_argument("--runtime-home", type=Path,
                        help="built TotalCross runtime home containing etc and dist/vm Windows assets")
    parser.add_argument("--dataset-cache", type=Path, default=ROOT / ".local-data/datasets/image-scroll/v1",
                        help="verified image-scroll/v1 cache to embed in each profile package")
    parser.add_argument("--runtime-artifact-commit", required=True,
                        help="source SHA used to build the supplied Windows runtime artifacts")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-sdk", action="store_true", help="run the SDK dist build before deploying apps")
    args = parser.parse_args(argv)
    if args.runtime_source is None:
        parser.error("set TOTALCROSS_SOURCE or pass --runtime-source")
    try:
        result = build(args)
    except (OSError, KeyError, ValueError, PackageError) as error:
        print("package error: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps({"status": "success", "package": str(result),
                      "manifest": str(result / "package-manifest.json"),
                      "buildLog": str(result.with_name(result.name + ".build.log"))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
