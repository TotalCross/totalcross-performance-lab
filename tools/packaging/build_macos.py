#!/usr/bin/env python3
"""Deploy all image-rendering profiles against a tested macOS TotalCross build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
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
from tools.packaging.official_runtime import (
    OFFICIAL_ARTIFACT_IDENTITY,
    OFFICIAL_PACKAGE_FILES,
    safe_relative_path,
    validate_github_records,
    validate_packaged_provenance,
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


def verify_official_package(home: Path, artifact_archive: Path, package_zip: Path,
                            provenance_path: Path, artifact_metadata_path: Path,
                            workflow_run_path: Path) -> tuple[dict, Path, dict[str, Path], dict, dict]:
    def read_record(path: Path, label: str) -> dict:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PackageError("cannot read " + label + ": " + str(error)) from error
        if not isinstance(value, dict):
            raise PackageError(label + " must be a JSON object")
        return value

    provenance = read_record(provenance_path, "official artifact provenance")
    artifact_metadata = read_record(artifact_metadata_path, "GitHub artifact metadata")
    workflow_run = read_record(workflow_run_path, "GitHub workflow run metadata")
    try:
        validate_github_records(provenance, artifact_metadata, workflow_run)
    except ValueError as error:
        raise PackageError(str(error)) from error

    home = home.resolve()
    if home.name != OFFICIAL_ARTIFACT_IDENTITY["packageRoot"] or not home.is_dir():
        raise PackageError("official extracted package root is missing or unexpected")
    if artifact_archive.stat().st_size != OFFICIAL_ARTIFACT_IDENTITY["artifactSizeBytes"]:
        raise PackageError("GitHub artifact ZIP size does not match pinned metadata")
    if sha256(artifact_archive) != OFFICIAL_ARTIFACT_IDENTITY["outerArtifactSha256"]:
        raise PackageError("GitHub artifact ZIP SHA-256 does not match the pinned digest")
    if sha256(package_zip) != OFFICIAL_ARTIFACT_IDENTITY["packageZipSha256"]:
        raise PackageError("contained TotalCross ZIP SHA-256 does not match the pinned digest")

    try:
        with zipfile.ZipFile(artifact_archive) as artifact:
            outer_members = [item for item in artifact.infolist() if not item.is_dir()]
            if len(outer_members) != 1 or outer_members[0].filename != OFFICIAL_ARTIFACT_IDENTITY["packageZipPath"]:
                raise PackageError("GitHub artifact ZIP does not contain exactly the pinned TotalCross package")
            if outer_members[0].file_size != package_zip.stat().st_size:
                raise PackageError("contained package ZIP size differs from the downloaded package")
            with artifact.open(outer_members[0]) as stream:
                if sha256_stream(stream) != OFFICIAL_ARTIFACT_IDENTITY["packageZipSha256"]:
                    raise PackageError("contained package ZIP bytes do not match their pinned SHA-256")

        expected_files = set()
        with zipfile.ZipFile(package_zip) as package:
            for item in package.infolist():
                if item.is_dir():
                    continue
                parts = Path(item.filename).parts
                if not parts or parts[0] != OFFICIAL_ARTIFACT_IDENTITY["packageRoot"] or ".." in parts:
                    raise PackageError("package ZIP contains a path outside the pinned package root")
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise PackageError("official package ZIP contains a symlink")
                relative = Path(*parts[1:]).as_posix()
                extracted = safe_relative_path(home, relative)
                if not extracted.is_file() or extracted.is_symlink():
                    raise PackageError("official extracted package is missing a regular file: " + relative)
                with package.open(item) as stream:
                    if sha256_stream(stream) != sha256(extracted):
                        raise PackageError("extracted package file differs from the official ZIP: " + relative)
                expected_files.add(relative)
        actual_files = {path.relative_to(home).as_posix() for path in home.rglob("*") if path.is_file()}
        if actual_files != expected_files or any(path.is_symlink() for path in home.rglob("*")):
            raise PackageError("extracted package tree does not exactly match the pinned package ZIP")
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise PackageError("official package ZIP validation failed: " + str(error)) from error

    source_files = {}
    for name, item in OFFICIAL_PACKAGE_FILES.items():
        relative = item["path"]
        path = safe_relative_path(home, relative)
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise PackageError("official package file hash validation failed: " + relative)
        source_files[name] = path
    libraries = home / "dist/libs"
    if not libraries.is_dir() or not any(path.is_file() for path in libraries.iterdir()):
        raise PackageError("official package is missing dist/libs dependencies")
    for required_directory in (home / "etc", home / "dist/vm"):
        if not required_directory.is_dir():
            raise PackageError("official package is missing " + required_directory.relative_to(home).as_posix())
    return provenance, home, source_files, artifact_metadata, workflow_run


def sha256_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def verify_release_arm64(paths: list[Path]) -> None:
    lipo = shutil.which("lipo")
    if not lipo:
        raise PackageError("lipo is required to validate macOS runtime architecture")
    for path in paths:
        result = subprocess.run([lipo, "-archs", str(path)], text=True, capture_output=True, check=False)
        if result.returncode or "arm64" not in result.stdout.split():
            raise PackageError("official macOS runtime artifact is not arm64: " + str(path))


def parse_profiles(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return tuple(PROFILE_CLASSES)
    values = tuple(raw.split(","))
    if not values or any(value not in PROFILE_CLASSES for value in values) or len(set(values)) != len(values):
        raise PackageError("invalid profile list; use unique names from the package profile inventory")
    return values


def selected_java_sources(source_root: Path, profiles: tuple[str, ...]) -> list[Path]:
    profile_root = source_root / "profiles"
    shared = sorted(path for path in source_root.rglob("*.java") if profile_root not in path.parents)
    # Package-private SDK accounting is accessed only by this benchmark source.
    shared += sorted((source_root.parents[1] / "ui/image").glob("ImageDrawPathProbeAccess.java"))
    selected = []
    for profile in profiles:
        entry = profile_root / (PROFILE_CLASSES[profile] + ".java")
        if not entry.is_file():
            raise PackageError("selected profile source is missing: " + str(entry))
        selected.append(entry)
    return shared + selected


def build(arguments) -> Path:
    if sys.platform != "darwin":
        raise PackageError("the macOS package must be built on macOS")
    official_mode = arguments.official_package_home is not None
    if official_mode:
        if not all((arguments.official_artifact_archive, arguments.official_package_zip,
                    arguments.official_artifact_provenance, arguments.official_artifact_metadata,
                    arguments.official_workflow_run)):
            raise PackageError("official package mode requires the artifact ZIP, package ZIP, and all provenance records")
        if any((arguments.runtime_source, arguments.sdk_home, arguments.native_build_dir,
                arguments.runtime_artifact_commit, arguments.build_sdk)):
            raise PackageError("official package mode cannot use a source checkout or local native build")
        source = None
        official_home = arguments.official_package_home.resolve()
        provenance, runtime_home, official_files, artifact_metadata, workflow_run = verify_official_package(
            official_home, arguments.official_artifact_archive.resolve(),
            arguments.official_package_zip.resolve(), arguments.official_artifact_provenance.resolve(),
            arguments.official_artifact_metadata.resolve(), arguments.official_workflow_run.resolve())
        source_commit = provenance["workflowHeadSha"]
        sdk_home = runtime_home
        build_dir = runtime_home / "dist/vm/macos"
        launcher = official_files["launcher"]
        library = official_files["libtcvm"]
        sdk_jar = official_files["sdkJar"]
        verify_release_arm64([launcher, library])
        runtime_mode = "github-actions-package"
    else:
        source_arg = arguments.runtime_source or (
            Path(os.environ["TOTALCROSS_SOURCE"]) if os.environ.get("TOTALCROSS_SOURCE") else None)
        if source_arg is None:
            raise PackageError("set TOTALCROSS_SOURCE or pass --runtime-source")
        if arguments.native_build_dir is None or arguments.runtime_artifact_commit is None:
            raise PackageError("local source mode requires --native-build-dir and --runtime-artifact-commit")
        source = source_arg.resolve()
        official_home = None
        provenance = None
        official_files = {}
        artifact_metadata = None
        workflow_run = None
        sdk_home = (arguments.sdk_home or source / "TotalCrossSDK").resolve()
        build_dir = arguments.native_build_dir.resolve()
        source_commit = git(source, "rev-parse", "HEAD")
        if git(source, "status", "--porcelain"):
            raise PackageError("TotalCross source checkout is dirty")
        if arguments.runtime_artifact_commit != source_commit:
            raise PackageError("macOS runtime artifact commit must equal the TotalCross source commit")
        launcher = build_dir / "Launcher"
        library = build_dir / "libtcvm.dylib"
        sdk_jar = sdk_home / "dist/totalcross-sdk.jar"
        verify_native_build(source, build_dir, launcher, library)
        runtime_mode = "local-release-build"
    output = arguments.output.resolve()
    if output.exists():
        raise PackageError("output already exists; choose a new path: " + str(output))
    benchmark_commit = git(ROOT, "rev-parse", "HEAD")
    if git(ROOT, "status", "--porcelain"):
        raise PackageError("benchmark repository is dirty; commit the benchmark source before packaging")
    dataset_cache = (arguments.dataset_cache or ROOT / ".local-data/datasets/image-scroll/v1").resolve()
    descriptor, dataset_identity, dataset_files = verified_dataset_cache(dataset_cache)
    libraries = sdk_home / "dist/libs"
    if not arguments.build_sdk and (not sdk_jar.is_file() or not libraries.is_dir()):
        raise PackageError("SDK is not built; run with --build-sdk or pass a built --sdk-home")
    if arguments.build_sdk:
        wrapper = sdk_home / "gradlew-agent"
        if not wrapper.is_file():
            raise PackageError("SDK agent wrapper is missing: " + str(wrapper))
    java = shutil.which("java")
    javac = shutil.which("javac")
    if not java or not javac:
        raise PackageError("a JDK with java and javac is required")
    selected_profiles = parse_profiles(arguments.profiles)
    sources = selected_java_sources(ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering",
                                    selected_profiles)
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
        if official_mode:
            env.pop("TOTALCROSS_SOURCE", None)
            env.pop("TOTALCROSS_HOME", None)
            env.pop("DYLD_LIBRARY_PATH", None)
            env.pop("DYLD_FALLBACK_LIBRARY_PATH", None)
        profile_manifest = {}
        binary_manifest = {}
        with log_path.open("x", encoding="utf-8") as log:
            if arguments.build_sdk:
                run_logged([str(wrapper), "dist", "-x", "test"], sdk_home, env, log)
            if not sdk_jar.is_file() or not libraries.is_dir() or not (sdk_home / "etc").is_dir() or not (sdk_home / "dist/vm").is_dir():
                raise PackageError("SDK output is incomplete; expected jar, libraries, etc, and dist/vm")
            if official_mode:
                runtime_home = official_home
            else:
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
            if official_mode:
                provenance_dir = package_root / "provenance"
                provenance_dir.mkdir(parents=True, exist_ok=True)
                artifact_metadata_destination = provenance_dir / "github-artifact-metadata.json"
                workflow_run_destination = provenance_dir / "github-workflow-run.json"
                shutil.copy2(arguments.official_artifact_metadata, artifact_metadata_destination)
                shutil.copy2(arguments.official_workflow_run, workflow_run_destination)
                packaged_source_files = {}
                for name, source_path in official_files.items():
                    relative_source = OFFICIAL_PACKAGE_FILES[name]["path"]
                    destination = package_root / "provenance/source" / provenance["packageRoot"] / relative_source
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, destination)
                    packaged_source_files[name] = {
                        "path": destination.relative_to(package_root).as_posix(),
                        "officialPackagePath": relative_source,
                        "sha256": sha256(destination),
                    }
                sdk_libraries = []
                for path in sorted((runtime_home / "dist/libs").iterdir()):
                    if path.is_symlink() or not path.is_file():
                        raise PackageError("official SDK dist/libs must contain only regular files: " + str(path))
                    sdk_libraries.append({
                        "officialPackagePath": path.relative_to(runtime_home).as_posix(),
                        "sha256": sha256(path),
                    })
                official_runtime_provenance = {
                    "schemaVersion": 1,
                    "mode": "github-actions-package",
                    "repository": provenance["repository"],
                    "workflowRunId": provenance["workflowRunId"],
                    "workflowName": provenance["workflowName"],
                    "workflowHeadBranch": provenance["workflowHeadBranch"],
                    "workflowHeadSha": provenance["workflowHeadSha"],
                    "workflowConclusion": provenance["workflowConclusion"],
                    "artifactId": provenance["artifactId"],
                    "artifactName": provenance["artifactName"],
                    "githubArtifactDigest": provenance["githubArtifactDigest"],
                    "outerArtifactSha256": provenance["outerArtifactSha256"],
                    "artifactSizeBytes": provenance["artifactSizeBytes"],
                    "packageZipPath": provenance["packageZipPath"],
                    "packageZipSha256": provenance["packageZipSha256"],
                    "packageRoot": provenance["packageRoot"],
                    "sourcePackageHome": str(official_home),
                    "artifactMetadata": {
                        "path": artifact_metadata_destination.relative_to(package_root).as_posix(),
                        "sha256": sha256(artifact_metadata_destination),
                    },
                    "workflowRunMetadata": {
                        "path": workflow_run_destination.relative_to(package_root).as_posix(),
                        "sha256": sha256(workflow_run_destination),
                    },
                    "sourceFiles": packaged_source_files,
                    "sdkLibraries": sdk_libraries,
                    "deployedArtifactsByProfile": {},
                }
            else:
                official_runtime_provenance = None
            for profile in selected_profiles:
                entry = PROFILE_CLASSES[profile]
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
                if official_mode:
                    profile_jar_copy = package_root / "provenance/input" / profile / (entry + ".jar")
                    profile_jar_copy.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(jar_path, profile_jar_copy)
                    deployed_libs = [path for path in destination.rglob("libtcvm.dylib") if path.is_file()]
                    deployed_tcz = [path for path in destination.rglob(prefix + ".tcz") if path.is_file()]
                    if len(deployed_libs) != 1 or len(deployed_tcz) != 1:
                        raise PackageError("deployed package must contain one libtcvm.dylib and one application TCZ")
                    if sha256(executable) != sha256(official_files["launcher"]):
                        raise PackageError("deployed executable differs from the official packaged Launcher")
                    if sha256(deployed_libs[0]) != sha256(official_files["libtcvm"]):
                        raise PackageError("deployed libtcvm.dylib differs from the official packaged runtime")
                    official_runtime_provenance["deployedArtifactsByProfile"][profile] = {
                        "profileJar": {
                            "path": profile_jar_copy.relative_to(package_root).as_posix(),
                            "sha256": sha256(profile_jar_copy),
                        },
                        "executable": {
                            "path": executable.relative_to(package_root).as_posix(),
                            "sha256": sha256(executable),
                        },
                        "applicationTcz": {
                            "path": deployed_tcz[0].relative_to(package_root).as_posix(),
                            "sha256": sha256(deployed_tcz[0]),
                        },
                        "libtcvm": {
                            "path": deployed_libs[0].relative_to(package_root).as_posix(),
                            "sha256": sha256(deployed_libs[0]),
                        },
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
                "runtimeArtifactSourceCommit": source_commit if official_mode else arguments.runtime_artifact_commit,
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
                    "runtimeArtifactMode": runtime_mode,
                    "sdkBuildCommand": ["gradlew-agent", "dist", "-x", "test"] if arguments.build_sdk else [],
                    "javaCompileRelease": 8,
                },
                "profileInventory": list(selected_profiles),
                "profiles": profile_manifest,
                "runtimeBinaries": sorted(binary_manifest.values(), key=lambda item: item["path"]),
            }
            if official_runtime_provenance is not None:
                try:
                    validate_packaged_provenance(official_runtime_provenance, package_root,
                                                 list(selected_profiles))
                except ValueError as error:
                    raise PackageError("official package provenance validation failed: " + str(error)) from error
                manifest["runtimeProvenance"] = official_runtime_provenance
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
    parser.add_argument("--runtime-source", type=Path,
                        help="TotalCross checkout for local-release-build mode only")
    parser.add_argument("--sdk-home", type=Path)
    parser.add_argument("--native-build-dir", type=Path)
    parser.add_argument("--dataset-cache", type=Path, default=ROOT / ".local-data/datasets/image-scroll/v1",
                        help="verified image-scroll/v1 cache to embed in each profile package")
    parser.add_argument("--runtime-artifact-commit",
                        help="source SHA used to build the supplied macOS runtime artifacts")
    parser.add_argument("--official-package-home", type=Path,
                        help="extracted TotalCross-7.2.2 package root; selects pinned GitHub artifact mode")
    parser.add_argument("--official-artifact-archive", type=Path,
                        help="outer GitHub Actions artifact ZIP")
    parser.add_argument("--official-package-zip", type=Path,
                        help="contained TotalCross-7.2.2.zip")
    parser.add_argument("--official-artifact-provenance", type=Path,
                        help="pinned artifact and source-file identity record")
    parser.add_argument("--official-artifact-metadata", type=Path,
                        help="raw GitHub artifact metadata JSON")
    parser.add_argument("--official-workflow-run", type=Path,
                        help="raw GitHub workflow run JSON")
    parser.add_argument("--profiles", help="comma-separated profile names; defaults to all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-sdk", action="store_true", help="run the SDK dist build before deploying apps")
    args = parser.parse_args(argv)
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
