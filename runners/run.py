#!/usr/bin/env python3
"""Run fresh-process TotalCross image-rendering benchmarks and validate output."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
sys.path.insert(0, str(ROOT))
from tools.packaging.official_runtime import validate_packaged_provenance

PREFIX = "TCBENCH_JSON "
PREFLIGHT_PREFIX = "TCBENCH_PREFLIGHT_JSON "
PROFILES = (
    "default", "target-color", "physical-variant", "raster-variants", "compact",
    "scroll-reuse", "prepared-legacy", "prepared-semaphore", "combined-standard", "combined-compact",
)
DEFAULT_PROFILES = {
    "decode": ("default", "compact"),
    "scroll": ("default", "target-color", "physical-variant", "raster-variants", "scroll-reuse",
               "combined-standard", "combined-compact"),
    "preparation": ("default", "prepared-legacy", "prepared-semaphore", "combined-standard", "combined-compact"),
    "pacing": ("default",),
}
PACING_WORKLOADS = ("flick-40", "flick-60", "synthetic-16ms", "synthetic-16.667ms")


class RunnerError(Exception):
    """Invalid runner configuration, process failure, or protocol output."""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_schema_ref(reference: str, schema_dir: Path, current: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    filename, _, fragment = reference.partition("#")
    root = read_json(schema_dir / filename) if filename else current
    schema = root
    if fragment:
        for part in fragment.removeprefix("/").split("/"):
            if part:
                key = part.replace("~1", "/").replace("~0", "~")
                schema = schema[key]
    return schema, root


def validate_schema(value: Any, schema: dict[str, Any], schema_dir: Path, location: str = "$", current=None) -> None:
    current = schema if current is None else current
    if "$ref" in schema:
        referenced, reference_root = resolve_schema_ref(schema["$ref"], schema_dir, current)
        validate_schema(value, referenced, schema_dir, location, reference_root)
        return
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if types and not any(checks[kind](value) for kind in types):
        raise RunnerError(location + " must be " + " or ".join(types))
    if "const" in schema and value != schema["const"]:
        raise RunnerError(location + " must equal " + repr(schema["const"]))
    if "enum" in schema and value not in schema["enum"]:
        raise RunnerError(location + " is not an allowed value")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise RunnerError(location + " is missing required field " + key)
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                validate_schema(item, props[key], schema_dir, location + "." + key, current)
            elif additional is False:
                raise RunnerError(location + " has unexpected field " + key)
            elif isinstance(additional, dict):
                validate_schema(item, additional, schema_dir, location + "." + key, current)
        if len(value) < schema.get("minProperties", 0):
            raise RunnerError(location + " has too few properties")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise RunnerError(location + " has too few items")
        if "items" in schema:
            for index, item in enumerate(value):
                validate_schema(item, schema["items"], schema_dir, location + "[" + str(index) + "]", current)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise RunnerError(location + " is too short")
        if "pattern" in schema:
            import re
            if not re.fullmatch(schema["pattern"], value):
                raise RunnerError(location + " has an invalid format")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", -math.inf) or value <= schema.get("exclusiveMinimum", -math.inf):
            raise RunnerError(location + " is below its minimum")


def parse_protocol(stdout: str, family: str, workload: str, profile: str, round_number: int, phase: str) -> tuple[dict[str, Any], dict[str, Any]]:
    records = []
    for line_number, line in enumerate(stdout.splitlines(), 1):
        if line.startswith(PREFIX):
            try:
                record = json.loads(line[len(PREFIX):])
            except json.JSONDecodeError as error:
                raise RunnerError("malformed TCBENCH_JSON at stdout line " + str(line_number)) from error
            if not isinstance(record, dict):
                raise RunnerError("TCBENCH_JSON records must be JSON objects")
            records.append(record)
    if not records or records[-1].get("recordType") != "summary":
        raise RunnerError("child output is missing its final TCBENCH_JSON summary")
    if sum(1 for item in records if item.get("recordType") == "summary") != 1:
        raise RunnerError("child output must contain exactly one final summary")
    if records[0].get("recordType") != "run":
        raise RunnerError("child output must contain exactly one run record")
    if len(records) != 2:
        raise RunnerError("child output must contain exactly one run and one final summary")
    run, summary = records[0], records[-1]
    validate_schema(run, read_json(SCHEMA_DIR / "benchmark-run-v1.schema.json"), SCHEMA_DIR)
    validate_schema(summary, read_json(SCHEMA_DIR / "benchmark-summary-v1.schema.json"), SCHEMA_DIR)
    identity = ("family", family), ("workload", workload), ("profile", profile), ("round", round_number), ("phase", phase)
    for key, expected in identity:
        if run.get(key) != expected:
            raise RunnerError("run record " + key + " does not match the requested cell")
    if summary.get("family") != family or summary.get("workload") != workload or summary.get("profile") != profile:
        raise RunnerError("final summary identity does not match the requested cell")
    if summary.get("rounds") != [run]:
        raise RunnerError("final summary must contain exactly the emitted run record")
    return run, summary


def java_version() -> str:
    java = shutil.which("java")
    if not java:
        return "unavailable"
    result = subprocess.run([java, "-version"], text=True, capture_output=True, check=False)
    text = (result.stderr or result.stdout).splitlines()
    return text[0].strip() if text else "unavailable"


def git_value(directory: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(directory), *args], text=True, capture_output=True, check=False)
    if result.returncode:
        raise RunnerError("cannot read Git identity for " + str(directory))
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise RunnerError("cannot summarize an empty sample")
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def comma_values(raw: str | None, default: tuple[str, ...], allowed: tuple[str, ...], name: str) -> tuple[str, ...]:
    values = tuple(raw.split(",")) if raw else default
    if not values or any(value not in allowed for value in values) or len(set(values)) != len(values):
        raise RunnerError("invalid " + name + " list")
    return tuple(value for value in allowed if value in values)


def build_cells(arguments) -> list[dict[str, Any]]:
    profile_default = DEFAULT_PROFILES[arguments.family]
    profiles = comma_values(arguments.profiles, profile_default, PROFILES, "profile")
    cells = []
    if arguments.family == "decode":
        sources = comma_values(arguments.sources, ("filesystem", "tcz"), ("filesystem", "tcz"), "source")
        scales = comma_values(arguments.scales, ("full", "half"), ("full", "half"), "scale")
        orders = comma_values(arguments.orders, ("sequential", "seeded-random"), ("sequential", "seeded-random"), "order")
        for profile in profiles:
            for source in sources:
                for scale in scales:
                    for order in orders:
                        cells.append({"profile": profile, "workload": "decode", "source": source, "scale": scale, "order": order})
    elif arguments.family == "pacing":
        workloads = comma_values(arguments.workloads, PACING_WORKLOADS, PACING_WORKLOADS, "pacing workload")
        cells.extend({"profile": profile, "workload": workload} for profile in profiles for workload in workloads)
    else:
        cells.extend({"profile": profile, "workload": arguments.family} for profile in profiles)
    return cells


def validate_scroll_driver_arguments(arguments) -> None:
    driver = getattr(arguments, "scroll_driver", "fixed-step")
    if driver == "fixed-step":
        return
    if driver != "historical-driver":
        raise RunnerError("invalid scroll driver")
    profiles = comma_values(arguments.profiles, DEFAULT_PROFILES[arguments.family], PROFILES, "profile")
    if (arguments.family != "scroll" or profiles != ("default",) or arguments.rounds != 1
            or arguments.warmups != 0 or arguments.diagnostics or arguments.width != 540
            or arguments.height != 960):
        raise RunnerError("historical-driver requires one default scroll round at 540x960 with no warmup or diagnostics")


def dataset_info(cache: Path, dataset_ref: str) -> dict[str, Any] | None:
    if not dataset_ref:
        return None
    sys.path.insert(0, str(ROOT))
    from tools.datasets import image_scroll
    _, descriptor = image_scroll.load_descriptor(ROOT, dataset_ref)
    result = image_scroll.verify_cache(cache, descriptor)
    return {"id": descriptor["id"], "version": descriptor["version"], "manifestSha256": result["manifestSha256"]}


def runtime_hashes(paths: list[Path]) -> tuple[list[dict[str, str]], str]:
    hashes = []
    for path in sorted({path.resolve() for path in paths}, key=lambda item: str(item)):
        resolved = path.resolve()
        if not resolved.is_file():
            raise RunnerError("runtime/package file does not exist: " + str(path))
        hashes.append({"path": str(resolved), "sha256": sha256_file(resolved)})
    encoded = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashes, hashlib.sha256(encoded).hexdigest()


def parse_preflight(stdout: str, family: str, workload: str, profile: str) -> dict[str, Any]:
    records = []
    for line_number, line in enumerate(stdout.splitlines(), 1):
        if line.startswith(PREFLIGHT_PREFIX):
            try:
                value = json.loads(line[len(PREFLIGHT_PREFIX):])
            except json.JSONDecodeError as error:
                raise RunnerError("malformed TCBENCH_PREFLIGHT_JSON at stdout line " + str(line_number)) from error
            if not isinstance(value, dict):
                raise RunnerError("TCBENCH_PREFLIGHT_JSON must be an object")
            records.append(value)
    if len(records) != 1:
        raise RunnerError("scroll preflight must emit exactly one TCBENCH_PREFLIGHT_JSON record")
    record = records[0]
    expected = {"recordType": "preflight", "family": family, "workload": workload, "profile": profile}
    if any(record.get(key) != value for key, value in expected.items()):
        raise RunnerError("preflight identity does not match the requested cell")
    return record


def validate_scroll_preflight(record: dict[str, Any], dataset: dict[str, Any] | None,
                              width: int, height: int, require_default: bool = False,
                              scroll_driver: str = "fixed-step") -> None:
    fixture = record.get("fixture")
    if not isinstance(fixture, dict):
        raise RunnerError("scroll preflight is missing its fixture configuration")
    if record.get("renderer") in (None, "", "unavailable"):
        raise RunnerError("scroll preflight did not identify its renderer")
    if record.get("scrollDriver", "fixed-step") != scroll_driver:
        raise RunnerError("scroll preflight driver does not match the requested driver")
    if not isinstance(record.get("diagnosticsRequested"), bool) or not isinstance(record.get("diagnosticsEnabled"), bool):
        raise RunnerError("scroll preflight did not report diagnostics state")
    if require_default and (record["diagnosticsRequested"] or record["diagnosticsEnabled"]):
        raise RunnerError("default scroll preflight diagnostics must be disabled")
    if fixture.get("dataset") != dataset:
        raise RunnerError("scroll preflight dataset identity does not match the verified cache")
    expected_dimensions = {"width": width, "height": height}
    if fixture.get("logicalDimensions") != expected_dimensions or fixture.get("runtimeLogicalDimensions") != expected_dimensions:
        raise RunnerError("scroll preflight logical resolution does not match the request")
    expected = {
        "imageControls": 663,
        "rows": 221,
        "columns": 3,
        "tileWidth": (width - 3) // 3,
    }
    if any(fixture.get(key) != value for key, value in expected.items()):
        raise RunnerError("scroll preflight fixture geometry does not match the historical workload")
    report = record.get("runtimeConfigurationReport")
    if not isinstance(report, str) or not report:
        raise RunnerError("scroll preflight did not report the effective runtime configuration")
    if not isinstance(fixture.get("explicitPreparationRequested"), bool):
        raise RunnerError("scroll preflight did not report explicit image preparation state")
    if require_default:
        if fixture["explicitPreparationRequested"]:
            raise RunnerError("default scroll preflight must not request explicit image preparation")
        if record.get("profile") != "default" or record.get("renderer") != "RASTER":
            raise RunnerError("default scroll preflight requires the RASTER renderer and default profile")
        required_report_lines = (
            "effective: STANDARD",
            "targetColorConversion: disabled",
            "physicalVariantCache: disabled",
            "scrollRasterReuse: disabled",
            "automaticPreparation: disabled",
            "prefetchWorker: LEGACY_PER_ENTRY_THREAD",
        )
        if any(line not in report for line in required_report_lines):
            raise RunnerError("effective runtime configuration differs from production defaults")


def child_environment(arguments) -> dict[str, str]:
    env = os.environ.copy()
    official_home = getattr(arguments, "official_runtime_home", None)
    if official_home:
        env["TOTALCROSS3_HOME"] = str(official_home)
        for name in ("TOTALCROSS_SOURCE", "TOTALCROSS_HOME", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
            env.pop(name, None)
    return env


def package_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise RunnerError("package manifest path escapes the package root") from error
    return candidate


def expand_cell_value(value: str, profile: str, workload: str, package: str = "") -> str:
    try:
        return value.format_map({"package": package, "profile": profile, "workload": workload})
    except KeyError as error:
        raise RunnerError("unknown command placeholder: " + str(error)) from error


def ensure_scroll_window_arguments(command: list[str], family: str, width: int, height: int) -> list[str]:
    if family not in ("scroll", "preparation") or any(item.lower() == "/scr" for item in command):
        return command
    return command + ["/scr", "-2,-2,%d,%d" % (width, height)]


def launch_one(arguments, cell: dict[str, Any], round_number: int, phase: str, index: int,
               dataset: dict[str, Any] | None, runtime_commit: str, benchmark_commit: str,
               runtime_files: list[dict[str, str]], runtime_hash: str, environment: dict[str, Any],
               output_dir: Path) -> dict[str, Any]:
    run_dir = output_dir / "processes" / ("%04d-%s-%s-%s" % (index, cell["profile"], phase, round_number))
    run_dir.mkdir(parents=True, exist_ok=False)
    config = {
        "schemaVersion": 1,
        "family": arguments.family,
        **cell,
        "scrollDriver": getattr(arguments, "scroll_driver", "fixed-step"),
        "round": round_number,
        "phase": phase,
        "preflight": False,
        "dataset": dataset,
        "datasetRoot": str(arguments.dataset_cache.resolve() / "files") if dataset else None,
        "datasetManifestPath": str(arguments.dataset_cache.resolve() / "objects" / "manifest.json") if dataset else None,
        "datasetTczPrefix": "image-scroll/" if dataset else None,
        "runtimeSourceCommit": runtime_commit,
        "benchmarkSourceCommit": benchmark_commit,
        "runtimeIdentity": getattr(arguments, "runtime_identity",
                                   "source:" + runtime_commit + ";artifact-sha256:" + runtime_hash),
        "runtimeFiles": runtime_files,
        "runtimeProvenance": getattr(arguments, "runtime_provenance", None),
        "environment": environment,
        "width": arguments.width,
        "height": arguments.height,
        "logicalDimensions": {"width": arguments.width, "height": arguments.height}
            if arguments.family in ("scroll", "preparation") else None,
        "drawableDimensions": None,
        "diagnosticsEnabled": arguments.diagnostics,
        "datasetAxes": {key: cell[key] for key in ("source", "scale", "order") if key in cell},
        "seed": 12012026 if cell.get("order") == "seeded-random" else None,
        "pacingWorkload": cell.get("workload") if arguments.family == "pacing" else None,
        "cacheDirectory": str(arguments.dataset_cache.resolve()),
        "resultProtocolPrefix": PREFIX,
        "appPackage": getattr(arguments, "app_package", None),
    }
    config_text = json.dumps(config, sort_keys=True)
    (run_dir / "tcbench-run.json").write_text(config_text, encoding="utf-8")
    launch_cwd = getattr(arguments, "launch_cwd", None) or run_dir
    launch_cwd.mkdir(parents=True, exist_ok=True)
    launch_config = launch_cwd / "tcbench-run.json"
    launch_config.write_text(config_text, encoding="utf-8")
    debug_console = launch_cwd / "DebugConsole.txt"
    if debug_console.exists():
        debug_console.unlink()
    started = time.monotonic_ns()
    try:
        child = subprocess.run(arguments.command, cwd=launch_cwd, env=child_environment(arguments),
                               text=True, capture_output=True,
                               timeout=arguments.timeout_seconds, check=False)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout or ""
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr or ""
        (run_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (run_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        if debug_console.is_file():
            shutil.copy2(debug_console, run_dir / "DebugConsole.txt")
        raise RunnerError("child process timed out after %d seconds" % arguments.timeout_seconds)
    wall_time_ns = time.monotonic_ns() - started
    (run_dir / "stdout.log").write_text(child.stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(child.stderr, encoding="utf-8")
    if debug_console.is_file():
        shutil.copy2(debug_console, run_dir / "DebugConsole.txt")
    if child.returncode:
        raise RunnerError("child exited with status %d" % child.returncode)
    run, _ = parse_protocol(child.stdout, arguments.family, cell["workload"], cell["profile"], round_number, phase)
    if run.get("runtimeSourceCommit") != runtime_commit or run.get("benchmarkSourceCommit") != benchmark_commit:
        raise RunnerError("run provenance commit does not match runner preflight")
    expected_identity = getattr(arguments, "runtime_identity", None)
    if expected_identity is not None and run.get("runtimeIdentity") != expected_identity:
        raise RunnerError("run runtime identity does not match the package provenance")
    if run.get("dataset") != dataset:
        raise RunnerError("run dataset identity does not match runner preflight")
    axes = run.get("measurements", {}).get("axes", {})
    for key in ("source", "scale", "order"):
        if key in cell and axes.get(key) != cell[key]:
            raise RunnerError("run record axis does not match the requested decode cell: " + key)
    run["runnerWallTimeNs"] = wall_time_ns
    run["runnerRuntimeFiles"] = runtime_files
    if getattr(arguments, "runtime_provenance", None) is not None:
        run["runtimeProvenance"] = arguments.runtime_provenance
    if getattr(arguments, "require_default_scroll_preflight", False):
        measurements = run.get("measurements", {})
        logical = run.get("logicalDimensions")
        measured_fixture = {
            "dataset": run.get("dataset"),
            "logicalDimensions": logical,
            "runtimeLogicalDimensions": {
                "width": measurements.get("logicalWindowWidth"),
                "height": measurements.get("logicalWindowHeight"),
            },
            "imageControls": measurements.get("imageControls"),
            "rows": measurements.get("rows"),
            "columns": measurements.get("columns"),
            "tileWidth": measurements.get("tileWidth"),
            "explicitPreparationRequested": measurements.get("preparation"),
        }
        validate_scroll_preflight({
            "profile": run.get("profile"),
            "renderer": run.get("renderer"),
            "scrollDriver": run.get("measurements", {}).get("scrollDriver", "fixed-step"),
            "diagnosticsRequested": False,
            "diagnosticsEnabled": run.get("diagnosticsEnabled"),
            "runtimeConfigurationReport": run.get("runtimeConfigurationReport"),
            "fixture": measured_fixture,
        }, dataset, arguments.width, arguments.height, require_default=True,
           scroll_driver=getattr(arguments, "scroll_driver", "fixed-step"))
    return run


def launch_preflight(arguments, cell: dict[str, Any], index: int, dataset, runtime_commit,
                     benchmark_commit, runtime_files, runtime_hash, environment, output_dir) -> None:
    run_dir = output_dir / "preflight" / ("%04d-%s-%s" % (index, cell["profile"], cell["workload"]))
    run_dir.mkdir(parents=True, exist_ok=False)
    config = {
        "schemaVersion": 1, "family": arguments.family, **cell,
        "scrollDriver": getattr(arguments, "scroll_driver", "fixed-step"), "round": 0, "phase": "preflight",
        "preflight": True, "dataset": dataset,
        "datasetRoot": str(arguments.dataset_cache.resolve() / "files") if dataset else None,
        "datasetManifestPath": str(arguments.dataset_cache.resolve() / "objects" / "manifest.json") if dataset else None,
        "datasetTczPrefix": "image-scroll/" if dataset else None,
        "runtimeSourceCommit": runtime_commit, "benchmarkSourceCommit": benchmark_commit,
        "runtimeIdentity": getattr(arguments, "runtime_identity",
                                   "source:" + runtime_commit + ";artifact-sha256:" + runtime_hash),
        "runtimeFiles": runtime_files,
        "runtimeProvenance": getattr(arguments, "runtime_provenance", None),
        "environment": environment,
        "width": arguments.width, "height": arguments.height,
        "logicalDimensions": {"width": arguments.width, "height": arguments.height}
            if arguments.family in ("scroll", "preparation") else None,
        "drawableDimensions": None, "diagnosticsEnabled": arguments.diagnostics,
        "datasetAxes": {key: cell[key] for key in ("source", "scale", "order") if key in cell},
        "seed": 12012026 if cell.get("order") == "seeded-random" else None,
        "cacheDirectory": str(arguments.dataset_cache.resolve()),
        "appPackage": getattr(arguments, "app_package", None),
    }
    config_text = json.dumps(config, sort_keys=True)
    (run_dir / "tcbench-run.json").write_text(config_text, encoding="utf-8")
    launch_cwd = getattr(arguments, "launch_cwd", None) or run_dir
    launch_cwd.mkdir(parents=True, exist_ok=True)
    (launch_cwd / "tcbench-run.json").write_text(config_text, encoding="utf-8")
    debug_console = launch_cwd / "DebugConsole.txt"
    if debug_console.exists():
        debug_console.unlink()
    try:
        child = subprocess.run(arguments.command, cwd=launch_cwd, env=child_environment(arguments),
                               text=True, capture_output=True,
                               timeout=arguments.timeout_seconds, check=False)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout or ""
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr or ""
        (run_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (run_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        if debug_console.is_file():
            shutil.copy2(debug_console, run_dir / "DebugConsole.txt")
        raise RunnerError("preflight timed out after %d seconds" % arguments.timeout_seconds)
    (run_dir / "stdout.log").write_text(child.stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(child.stderr, encoding="utf-8")
    if debug_console.is_file():
        shutil.copy2(debug_console, run_dir / "DebugConsole.txt")
    if child.returncode:
        raise RunnerError("preflight child exited with status %d" % child.returncode)
    if arguments.family == "scroll":
        record = parse_preflight(child.stdout, arguments.family, cell["workload"], cell["profile"])
        if record.get("runtimeSourceCommit") != runtime_commit or record.get("benchmarkSourceCommit") != benchmark_commit:
            raise RunnerError("scroll preflight provenance does not match the runner identity")
        if record.get("runtimeIdentity") != config["runtimeIdentity"]:
            raise RunnerError("scroll preflight runtime identity does not match the package provenance")
        validate_scroll_preflight(record, dataset, arguments.width, arguments.height,
                                  require_default=getattr(arguments, "require_default_scroll_preflight", False),
                                  scroll_driver=getattr(arguments, "scroll_driver", "fixed-step"))
        (run_dir / "preflight.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                                                  encoding="utf-8")


def execute(arguments) -> int:
    if arguments.sigbus_stress:
        if arguments.family != "preparation":
            raise RunnerError("--sigbus-stress is valid only for the preparation family")
        arguments.profiles = "prepared-legacy,prepared-semaphore"
        arguments.rounds = 10
        arguments.warmups = 0
        arguments.fail_fast = True
    if not arguments.command and not arguments.package_manifest:
        raise RunnerError("pass --package-manifest or a launcher command after --command")
    command_template = list(arguments.command) if arguments.command else None
    if arguments.rounds < 1 or arguments.warmups < 0 or arguments.timeout_seconds < 1:
        raise RunnerError("rounds and timeout must be positive; warmups must be non-negative")
    if arguments.width < 1 or arguments.height < 1:
        raise RunnerError("logical dimensions must be positive")
    validate_scroll_driver_arguments(arguments)
    benchmark_commit = git_value(ROOT, "rev-parse", "HEAD")
    dirty = bool(git_value(ROOT, "status", "--porcelain"))
    manifest_path = arguments.package_manifest.resolve() if arguments.package_manifest else None
    package_manifest = read_json(manifest_path) if manifest_path else None
    official_provenance = None
    official_provenance_files: list[Path] = []
    if package_manifest:
        if getattr(arguments, "working_directory", None):
            raise RunnerError("--working-directory cannot be combined with --package-manifest")
        validate_schema(package_manifest, read_json(SCHEMA_DIR / "benchmark-package-v1.schema.json"), SCHEMA_DIR)
        platform_names = {"macos": "darwin", "windows": "win32", "linux": "linux"}
        if platform_names.get(package_manifest.get("platform")) != sys.platform:
            raise RunnerError("package manifest platform does not match this host")
        official_provenance = package_manifest.get("runtimeProvenance")

    if official_provenance is not None:
        if arguments.runtime_source is not None:
            raise RunnerError("official package mode cannot select a TotalCross source checkout")
        try:
            from tools.packaging.official_runtime import validate_official_identity
            validate_official_identity(official_provenance)
            official_provenance_files = validate_packaged_provenance(
                official_provenance, manifest_path.parent, package_manifest.get("profileInventory"))
        except (ValueError, KeyError, OSError) as error:
            raise RunnerError("official package provenance validation failed: " + str(error)) from error
        runtime_commit = official_provenance["workflowHeadSha"]
        runtime_home = Path(official_provenance["sourcePackageHome"]).resolve()
        runtime_mode = package_manifest.get("buildConfiguration", {}).get("runtimeArtifactMode")
        if runtime_mode != "github-actions-package":
            raise RunnerError("official provenance requires github-actions-package build mode")
    else:
        source_arg = arguments.runtime_source or (
            Path(os.environ["TOTALCROSS_SOURCE"]) if os.environ.get("TOTALCROSS_SOURCE") else None)
        if source_arg is None:
            raise RunnerError("set TOTALCROSS_SOURCE or pass --runtime-source")
        runtime_source = source_arg.resolve()
        runtime_commit = git_value(runtime_source, "rev-parse", "HEAD")
        if git_value(runtime_source, "status", "--porcelain"):
            raise RunnerError("TotalCross source checkout is dirty; use a clean read-only checkout")
        runtime_home = None
        runtime_mode = None

    env = {
        "hostOs": platform.platform(),
        "hostArchitecture": platform.machine(),
        "javaVersion": java_version(),
        "totalcrossBuild": "source:" + runtime_commit,
        "hostName": platform.node() or "unavailable",
        "sessionType": "ssh" if os.environ.get("SSH_CONNECTION") else None,
        "benchmarkWorkingTreeDirty": dirty,
    }
    if official_provenance is not None:
        env["totalcrossBuild"] = "github-artifact:%s;sha256:%s" % (
            official_provenance["artifactName"], official_provenance["outerArtifactSha256"])
        env["totalcross3Home"] = str(runtime_home)
    dataset = None
    if arguments.family != "pacing":
        dataset = dataset_info(arguments.dataset_cache.resolve(), "image-scroll/v1")
    if package_manifest:
        if package_manifest.get("runtimeArtifactSourceCommit") != runtime_commit:
            raise RunnerError("package runtime artifacts were built from a different TotalCross source commit")
        if package_manifest.get("totalcrossSourceCommit") != runtime_commit:
            raise RunnerError("package and selected TotalCross source commits differ")
        if package_manifest.get("benchmarkSourceCommit") != benchmark_commit:
            raise RunnerError("package was built from a different benchmark source commit")
        if package_manifest.get("benchmarkWorkingTreeDirty"):
            raise RunnerError("package was built from a dirty benchmark working tree")
        inventory = package_manifest.get("profileInventory")
        package_profiles = package_manifest.get("profiles", {})
        if (not isinstance(inventory, list) or not inventory or len(inventory) != len(set(inventory))
                or any(profile not in PROFILES for profile in inventory)
                or set(package_profiles) != set(inventory)):
            raise RunnerError("package profile inventory is invalid or inconsistent")
        selected_profiles = comma_values(arguments.profiles, DEFAULT_PROFILES[arguments.family], PROFILES, "profile")
        if not set(selected_profiles).issubset(inventory):
            raise RunnerError("package manifest does not contain every requested profile")
        if arguments.require_default_scroll_preflight:
            if (official_provenance is None or arguments.family != "scroll" or selected_profiles != ("default",)
                    or arguments.rounds != 1 or arguments.warmups != 0 or arguments.width != 540
                    or arguments.height != 960 or arguments.diagnostics):
                raise RunnerError("production-default gate requires one official default 540x960 scroll with no warmup or diagnostics")
            if inventory != ["default"]:
                raise RunnerError("production-default gate requires a default-only official package")
            arguments.fail_fast = True
        if dataset and package_manifest.get("dataset", {}).get("manifestSha256") != dataset["manifestSha256"]:
            raise RunnerError("package and verified dataset manifest identities differ")
    output_base = arguments.results_dir.resolve()
    output_base.mkdir(parents=True, exist_ok=True)
    output_dir = output_base / (time.strftime("run-%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + str(os.getpid()))
    output_dir.mkdir(parents=True, exist_ok=False)
    cells = build_cells(arguments)
    all_records = []
    failures = []
    process_index = 0
    for cell in cells:
        cell_records = []
        replacements = {"profile": cell["profile"], "workload": cell["workload"], "package": ""}
        working_directory = getattr(arguments, "working_directory", None)
        if working_directory:
            working_directory = Path(expand_cell_value(str(working_directory), **replacements)).expanduser().resolve()
            if not working_directory.is_dir():
                raise RunnerError("working directory does not exist: " + str(working_directory))
        arguments.launch_cwd = working_directory
        arguments.app_package = None
        arguments.runtime_provenance = official_provenance
        arguments.official_runtime_home = runtime_home
        files = []
        for path in arguments.runtime_file:
            expanded = expand_cell_value(str(path), **replacements)
            files.append(Path(expanded).expanduser().resolve())
        if package_manifest:
            package_root = manifest_path.parent
            app_package = package_manifest.get("profiles", {}).get(cell["profile"])
            if not isinstance(app_package, dict):
                failures.append({"cell": cell, "phase": "package", "round": 0,
                                 "error": "package manifest has no profile " + cell["profile"]})
                if arguments.fail_fast:
                    break
                continue
            executable = package_path(package_root, app_package["executable"])
            launch_cwd = package_path(package_root, app_package.get("workingDirectory", "."))
            if not executable.is_file() or not launch_cwd.is_dir():
                failures.append({"cell": cell, "phase": "package", "round": 0,
                                 "error": "package executable or working directory is missing"})
                if arguments.fail_fast:
                    break
                continue
            arguments.launch_cwd = launch_cwd
            arguments.app_package = app_package
            for item in app_package.get("runtimeFiles", []):
                path = package_path(package_root, item["path"])
                if not path.is_file() or sha256_file(path) != item["sha256"]:
                    raise RunnerError("package runtime hash validation failed: " + str(path))
                files.append(path)
            files.append(executable)
            if command_template:
                arguments.command = [expand_cell_value(token, cell["profile"], cell["workload"], str(executable))
                                     for token in command_template]
            else:
                arguments.command = [str(executable)]
        else:
            expanded_command = [expand_cell_value(token, **replacements) for token in command_template or []]
            for token in expanded_command:
                candidate = Path(token).expanduser().resolve()
                if candidate.is_file():
                    files.append(candidate)
            arguments.command = expanded_command
        arguments.command = ensure_scroll_window_arguments(
            arguments.command, arguments.family, arguments.width, arguments.height)
        if official_provenance is not None:
            files.extend(official_provenance_files)
        runtime_files, runtime_hash = runtime_hashes(files)
        if not runtime_files:
            raise RunnerError("pass at least one launcher/application path with --runtime-file for hash provenance")
        if official_provenance is None:
            arguments.runtime_identity = "source:" + runtime_commit + ";artifact-sha256:" + runtime_hash
        else:
            arguments.runtime_identity = "github-artifact:%s;sha256:%s;runtime-files-sha256:%s" % (
                official_provenance["artifactName"], official_provenance["outerArtifactSha256"], runtime_hash)
        process_index += 1
        try:
            launch_preflight(arguments, cell, process_index, dataset, runtime_commit, benchmark_commit,
                             runtime_files, runtime_hash, env, output_dir)
        except RunnerError as error:
            failures.append({"cell": cell, "phase": "preflight", "round": 0, "error": str(error)})
            if arguments.fail_fast:
                break
            continue
        for phase, count in (("warmup", arguments.warmups), ("measured", arguments.rounds)):
            for ordinal in range(count):
                process_index += 1
                round_number = ordinal + 1
                try:
                    record = launch_one(arguments, cell, round_number, phase, process_index, dataset,
                                        runtime_commit, benchmark_commit, runtime_files, runtime_hash, env, output_dir)
                    cell_records.append(record)
                    all_records.append(record)
                except RunnerError as error:
                    failures.append({"cell": cell, "phase": phase, "round": round_number, "error": str(error)})
                    if arguments.fail_fast:
                        break
                    break
            if failures and arguments.fail_fast:
                break
            if failures and failures[-1]["cell"] == cell:
                break
        measured = [item for item in cell_records if item["phase"] == "measured"]
        if measured:
            walls = [int(item["durationsNs"].get("wallTime", item["runnerWallTimeNs"])) for item in measured]
            summary = {
                "schemaVersion": 1,
                "recordType": "summary",
                "family": arguments.family,
                "workload": cell["workload"],
                "profile": cell["profile"],
                "dataset": dataset,
                "runtimeSourceCommit": runtime_commit,
                "benchmarkSourceCommit": benchmark_commit,
                "rounds": measured,
                "failures": sum(1 for failure in failures if failure["cell"] == cell),
                "statistics": {"wallTimeNs": {"median": statistics.median(walls), "p50": percentile(walls, 0.50),
                                                    "p95": percentile(walls, 0.95), "p99": percentile(walls, 0.99),
                                                    "max": max(walls)}},
                "environment": env,
            }
            validate_schema(summary, read_json(SCHEMA_DIR / "benchmark-summary-v1.schema.json"), SCHEMA_DIR)
            name = "-".join(str(cell[key]) for key in ("profile", "workload", "source", "scale", "order") if key in cell)
            (output_dir / (name + ".summary.json")).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "runs.jsonl").write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in all_records), encoding="utf-8")
    (output_dir / "failures.json").write_text(json.dumps(failures, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cells": len(cells), "successfulRuns": len(all_records), "failures": len(failures), "results": str(output_dir)}, sort_keys=True))
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command_group", required=True)
    data_parser = commands.add_parser("dataset", help="fetch or verify the versioned image dataset")
    data_parser.add_argument("action", choices=("fetch", "verify"))
    data_parser.add_argument("dataset", help="for example image-scroll/v1")
    data_parser.add_argument("--force", action="store_true")
    render = commands.add_parser("image-rendering", help="run an independent image-rendering workload family")
    render.add_argument("family", choices=("decode", "scroll", "preparation", "pacing"))
    render.add_argument("--profile", dest="profiles", help="comma-separated named profiles")
    render.add_argument("--sources", help="decode sources in deterministic order: filesystem,tcz")
    render.add_argument("--scales", help="decode scales in deterministic order: full,half")
    render.add_argument("--orders", help="decode orders in deterministic order: sequential,seeded-random")
    render.add_argument("--workload", "--workloads", dest="workloads", help="pacing workload name(s)")
    render.add_argument("--rounds", type=int, default=3)
    render.add_argument("--warmups", type=int, default=1)
    render.add_argument("--timeout-seconds", type=int, default=300)
    render.add_argument("--width", type=int, default=540)
    render.add_argument("--height", type=int, default=960)
    render.add_argument("--diagnostics", action="store_true")
    render.add_argument("--scroll-driver", choices=("fixed-step", "historical-driver"), default="fixed-step",
                        help="scroll cadence and position driver; historical-driver is a single-pass probe")
    render.add_argument("--fail-fast", action="store_true")
    render.add_argument("--runtime-source", type=Path,
                        help="clean TotalCross checkout for locally built runtimes; not used with attested packages")
    render.add_argument("--dataset-cache", type=Path, default=ROOT / ".local-data/datasets/image-scroll/v1")
    render.add_argument("--runtime-file", action="append", default=[])
    render.add_argument("--working-directory", type=Path,
                        help="working directory for direct launcher commands; supports {profile} and {workload}")
    render.add_argument("--package-manifest", type=Path, help="generated package-manifest.json with profile launchers")
    render.add_argument("--sigbus-stress", action="store_true", help="run 10 fresh processes for each preparation worker")
    render.add_argument("--require-default-scroll-preflight", action="store_true",
                        help="require production-default config and historical 540x960 geometry before measuring")
    render.add_argument("--results-dir", type=Path, default=ROOT / "results/image-rendering/latest")
    render.add_argument("--command", nargs=argparse.REMAINDER,
                        help="launcher/app command; supports {package}, {profile}, and {workload}; place last")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command_group == "dataset":
            sys.path.insert(0, str(ROOT))
            from tools.datasets import image_scroll
            forwarded = [arguments.action, arguments.dataset]
            if arguments.force:
                forwarded.append("--force")
            return image_scroll.main(forwarded)
        return execute(arguments)
    except (RunnerError, OSError, ValueError, KeyError) as error:
        print("runner error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
