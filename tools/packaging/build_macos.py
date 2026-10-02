#!/usr/bin/env python3
"""Deploy all image-rendering profiles against a tested macOS TotalCross build."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.packaging.build_windows import (
    PROFILE_CLASSES,
    PackageError,
    git,
    package_files,
    run_logged,
    sha256,
    verified_dataset_cache,
    write_profile_jar,
)


def read_cmake_cache(build_dir: Path) -> dict[str, str]:
    cache = build_dir / "CMakeCache.txt"
    if not cache.is_file():
        raise PackageError("CMake build directory has no CMakeCache.txt: " + str(build_dir))
    result = {}
    for line in cache.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("//") or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split("=", 1)
        name, _, _kind = key.partition(":")
        result[name] = value
    return result


def verify_native_build(source: Path, build_dir: Path, launcher: Path, library: Path) -> None:
    cache = read_cmake_cache(build_dir)
    expected_source = (source / "TotalCrossVM").resolve()
    if Path(cache.get("CMAKE_HOME_DIRECTORY", "")).resolve() != expected_source:
        raise PackageError("native build directory was configured from a different TotalCrossVM source")
    if cache.get("CMAKE_BUILD_TYPE") != "Release":
        raise PackageError("native build must use CMAKE_BUILD_TYPE=Release")
    if "arm64" not in cache.get("CMAKE_OSX_ARCHITECTURES", "").split(";"):
        raise PackageError("native build must target macOS arm64")
    lipo = shutil.which("lipo")
    if not lipo:
        raise PackageError("lipo is required to validate macOS runtime architecture")
    for path in (launcher, library):
        if not path.is_file():
            raise PackageError("native runtime artifact is missing: " + str(path))
        result = subprocess.run([lipo, "-archs", str(path)], text=True, capture_output=True, check=False)
        if result.returncode or "arm64" not in result.stdout.split():
            raise PackageError("native runtime artifact is not a valid arm64 binary: " + str(path))


def build(arguments) -> Path:
    if sys.platform != "darwin":
        raise PackageError("the macOS package must be built on macOS")
    source = arguments.runtime_source.resolve()
    sdk_home = (arguments.sdk_home or source / "TotalCrossSDK").resolve()
    build_dir = arguments.native_build_dir.resolve()
    output = arguments.output.resolve()
    if output.exists():
        raise PackageError("output already exists; choose a new path: " + str(output))
    source_commit = git(source, "rev-parse", "HEAD")
    if git(source, "status", "--porcelain"):
        raise PackageError("TotalCross source checkout is dirty")
    if arguments.runtime_artifact_commit != source_commit:
        raise PackageError("macOS runtime artifact commit must equal the TotalCross source commit")
    benchmark_commit = git(ROOT, "rev-parse", "HEAD")
    if git(ROOT, "status", "--porcelain"):
        raise PackageError("benchmark repository is dirty; commit the benchmark source before packaging")
    dataset_cache = (arguments.dataset_cache or ROOT / ".local-data/datasets/image-scroll/v1").resolve()
    descriptor, dataset_identity, dataset_files = verified_dataset_cache(dataset_cache)
    sdk_jar = sdk_home / "dist/totalcross-sdk.jar"
    libraries = sdk_home / "dist/libs"
    if not arguments.build_sdk and (not sdk_jar.is_file() or not libraries.is_dir()):
        raise PackageError("SDK is not built; run with --build-sdk or pass a built --sdk-home")
    launcher = build_dir / "Launcher"
    library = build_dir / "libtcvm.dylib"
    verify_native_build(source, build_dir, launcher, library)
    java = shutil.which("java")
    javac = shutil.which("javac")
    if not java or not javac:
        raise PackageError("a JDK with java and javac is required")
    sources = sorted((ROOT / "benchmarks/image-rendering/src").rglob("*.java"))
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_name(output.name + ".build.log")
    if log_path.exists():
        raise PackageError("build log already exists; move it before retrying: " + str(log_path))
    with tempfile.TemporaryDirectory(prefix="image-rendering-macos-", dir=output.parent) as temporary:
        stage = Path(temporary)
        package_root = stage / "package"
        package_root.mkdir()
        classes = stage / "classes"
        classes.mkdir()
        env = os.environ.copy()
        profile_manifest = {}
        binary_manifest = {}
        with log_path.open("x", encoding="utf-8") as log:
            if arguments.build_sdk:
                wrapper = sdk_home / "gradlew-agent"
                if not wrapper.is_file():
                    raise PackageError("SDK agent wrapper is missing: " + str(wrapper))
                run_logged([str(wrapper), "dist", "-x", "test"], sdk_home, env, log)
                if not sdk_jar.is_file():
                    raise PackageError("SDK build completed without totalcross-sdk.jar")
            if not sdk_jar.is_file() or not libraries.is_dir() or not (sdk_home / "etc").is_dir() or not (sdk_home / "dist/vm").is_dir():
                raise PackageError("SDK output is incomplete; expected jar, libraries, etc, and dist/vm")
            runtime_home = stage / "runtime"
            shutil.copytree(sdk_home / "etc", runtime_home / "etc")
            shutil.copytree(sdk_home / "dist/vm", runtime_home / "dist/vm")
            launcher_assets = runtime_home / "etc/launchers/macos"
            launcher_assets.mkdir(parents=True, exist_ok=True)
            shutil.copy2(launcher, launcher_assets / "Launcher")
            native_dir = runtime_home / "dist/vm/macos"
            native_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(library, native_dir / "libtcvm.dylib")
            env["TOTALCROSS3_HOME"] = str(runtime_home)
            compile_cp = os.pathsep.join((str(sdk_jar), str(libraries / "*")))
            run_logged([javac, "--release", "8", "-cp", compile_cp, "-d", str(classes),
                        *map(str, sources)], ROOT, env, log)
            app_cp = os.pathsep.join((str(classes), str(sdk_jar), str(libraries / "*")))
            for profile, entry in PROFILE_CLASSES.items():
                prefix = "image-rendering-" + profile
                jar_path = stage / "inputs" / profile / (entry + ".jar")
                jar_path.parent.mkdir(parents=True)
                write_profile_jar(classes, entry, jar_path, dataset_files)
                deployment = stage / "deploy" / profile
                deployment.mkdir(parents=True)
                command = [java, "-cp", app_cp, "tc.Deploy", str(jar_path),
                           "-macos", "/p", "/n", prefix, "/o", str(deployment) + os.sep]
                run_logged(command, runtime_home, env, log)
                deployed = deployment / "install/macos"
                executable = deployed / prefix
                if not executable.is_file():
                    raise PackageError("deployer did not create " + str(executable))
                destination = package_root / "profiles" / profile
                shutil.copytree(deployed, destination)
                executable = destination / executable.name
                profile_manifest[profile] = {
                    "entryClass": "totalcross.bench.imagerendering.profiles." + entry,
                    "executable": executable.relative_to(package_root).as_posix(),
                    "workingDirectory": destination.relative_to(package_root).as_posix(),
                    "runtimeFiles": package_files(destination, executable),
                }
                for path in destination.rglob("*"):
                    if path.is_file() and (path.suffix.lower() in (".dylib", ".so", ".dll", ".exe") or path == executable):
                        relative = path.relative_to(package_root).as_posix()
                        binary_manifest[relative] = {"path": relative, "sha256": sha256(path)}
            version_result = subprocess.run([java, "-version"], text=True, capture_output=True, check=False)
            java_version = next(iter((version_result.stderr or version_result.stdout).splitlines()), "unavailable")
            manifest = {
                "schemaVersion": 1,
                "packageType": "image-rendering-macos",
                "platform": "macos",
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
                    "nativeRuntimeDirectory": str(build_dir),
                    "deployTarget": "macos",
                    "architecture": "arm64",
                    "sdkBuildCommand": ["gradlew-agent", "dist", "-x", "test"] if arguments.build_sdk else [],
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
    parser.add_argument("--native-build-dir", type=Path, required=True)
    parser.add_argument("--dataset-cache", type=Path, default=ROOT / ".local-data/datasets/image-scroll/v1",
                        help="verified image-scroll/v1 cache to embed in each profile package")
    parser.add_argument("--runtime-artifact-commit", required=True,
                        help="source SHA used to build the supplied macOS runtime artifacts")
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
