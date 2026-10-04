#!/usr/bin/env python3
# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

"""Build and run the isolated, single-process f5dad132 static paint probe."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runners.run import RunnerError, validate_paint_preparation_result
from tools.packaging.build_macos import read_cmake_cache, verify_native_build
from tools.packaging.build_windows import (
    PackageError, git, run_logged, sha256, verified_dataset_cache, write_profile_jar,
)

RUNTIME_SHA = "f5dad132cafea5c9086f6f946a6f44ca5bcb5f76"
SOURCE = ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering"
HISTORICAL = ROOT / "benchmarks/image-rendering/historical-src"

# This method runs outside every timed region. It retains references, without
# decoding, preparing, scaling, replacing or adopting any Image.
IDENTITY_METHOD = r'''
  private Image[] historicalImages;
  private ImageControl[] historicalControls;
  private Container[] historicalRows;

  JSONObject historicalVisibleIdentity() {
    boolean first = historicalImages == null;
    if (first) {
      historicalImages = new Image[controls.length];
      historicalControls = Arrays.copyOf(controls, controls.length);
      historicalRows = Arrays.copyOf(rows, rows.length);
      for (int i = 0; i < controls.length; i++) {
        historicalImages[i] = controls[i].getImage();
      }
    }
    requirePaintProbePosition(0);
    JSONArray visible = new JSONArray();
    for (int i = 0; i < controls.length; i++) {
      if (historicalControls[i] != controls[i] || historicalImages[i] != controls[i].getImage()
          || historicalRows[i / COLUMNS] != rows[i / COLUMNS]) {
        throw new IllegalStateException("historical probe changed a row, control or Image instance");
      }
      int top = 2 + (i / COLUMNS) * (tileWidth + 2);
      if (top < scroll.getRect().height && top + tileWidth > 0) {
        visible.put(BenchSupport.object("manifestIndex", i, "rowIndex", i / COLUMNS,
            "path", entries[i].path, "format", entries[i].format));
      }
    }
    if (visible.length() != 18) {
      throw new IllegalStateException("historical probe requires 18 visible controls in 6 rows");
    }
    return BenchSupport.object("controls", visible, "sameImageInstances", true,
        "sameControlInstances", true, "sameRowInstances", true, "scrollPosition", 0);
  }
'''


def historical_scroll_source(text: str) -> str:
    """Keep all workload/measurement methods; change only diagnostic imports."""
    for name in ("RuntimeDiagnostics", "RuntimeDiagnosticSnapshot"):
        old = "import totalcross.sys." + name + ";"
        if text.count(old) != 1:
            raise PackageError("shared workload diagnostic import changed: " + name)
        text = text.replace(old, "import totalcross.bench.imagerendering.historical." + name + ";")
    anchor = "  private final ImageRenderingBenchmarkApp app;"
    if text.count(anchor) != 1:
        raise PackageError("shared workload identity insertion point changed")
    return text.replace(anchor, IDENTITY_METHOD + "\n" + anchor)


def clean_historical_source(source: Path) -> None:
    if git(source, "rev-parse", "HEAD") != RUNTIME_SHA:
        raise PackageError("historical checkout must be pinned exactly to " + RUNTIME_SHA)
    if git(source, "status", "--porcelain"):
        raise PackageError("historical checkout must remain clean")


def probe_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("TOTALCROSS_SOURCE", "TOTALCROSS_HOME", "TOTALCROSS3_HOME",
                "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
        env.pop(key, None)
    return env


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dataset_metadata(descriptor: dict, verification: dict) -> dict:
    return {**verification, "id": descriptor["id"], "version": descriptor["version"]}


def protocol_records(stdout: str, debug: str) -> tuple[list[dict], list[dict]]:
    # Some native builds echo the same Java output to both channels. Use one
    # complete stream rather than counting duplicated records as extra runs.
    text = stdout if any(line.startswith("TCBENCH_JSON ") for line in stdout.splitlines()) else debug
    records = [json.loads(line.split("TCBENCH_JSON ", 1)[1]) for line in text.splitlines()
               if line.startswith("TCBENCH_JSON ")]
    preflights = [json.loads(line.split("TCBENCH_PREFLIGHT_JSON ", 1)[1]) for line in text.splitlines()
                  if line.startswith("TCBENCH_PREFLIGHT_JSON ")]
    return records, preflights


def build(args) -> None:
    source = args.runtime_source.resolve()
    native = args.native_build.resolve()
    output = args.output.resolve()
    clean_historical_source(source)
    launcher, library = native / "Launcher", native / "libtcvm.dylib"
    verify_native_build(source, native, launcher, library)
    cache = read_cmake_cache(native)
    for key, expected in (("TC_GRAPHICS_SOFTWARE", "ON"), ("TC_GRAPHICS_GLES", "OFF"),
                          ("TC_RENDERER_SKIA", "ON"), ("TC_WINDOWING_SDL", "ON")):
        if cache.get(key) != expected:
            raise PackageError("historical raster build requires " + key + "=" + expected)
    depot = Path(cache["TCVM_DEPOT_TOOLS_DIR"])
    pin = next(line.strip() for line in (source / "TotalCrossVM/deps/totalcross-depot-tools.ref")
               .read_text().splitlines() if line.strip() and not line.startswith("#"))
    if git(depot, "rev-parse", "HEAD") != pin:
        raise PackageError("dependency checkout differs from historical depot-tools pin")
    descriptor, dataset, files = verified_dataset_cache(args.dataset_cache.resolve())
    dataset = dataset_metadata(descriptor, dataset)
    sdk = source / "TotalCrossSDK"
    sdk_jar = sdk / "dist/totalcross-sdk.jar"
    if not sdk_jar.is_file():
        raise PackageError("build historical SDK with ./gradlew-agent dist -x test first")
    output.mkdir() # Never overwrite a prior package, launch guard or raw result.
    classes = output / "classes"
    classes.mkdir()
    staged_source = output / "ScrollWorkload.java"
    staged_source.write_text(historical_scroll_source((SOURCE / "ScrollWorkload.java").read_text()))
    sources = [SOURCE / "BenchSupport.java", SOURCE / "ScrollTiming.java", SOURCE / "profiles/Default.java", staged_source,
               *sorted(HISTORICAL.rglob("*.java"))]
    runtime_home = output / "runtime"
    shutil.copytree(sdk / "etc", runtime_home / "etc")
    shutil.copytree(sdk / "dist/vm", runtime_home / "dist/vm")
    (runtime_home / "etc/launchers/macos").mkdir(parents=True, exist_ok=True)
    shutil.copy2(launcher, runtime_home / "etc/launchers/macos/Launcher")
    (runtime_home / "dist/vm/macos").mkdir(parents=True, exist_ok=True)
    shutil.copy2(library, runtime_home / "dist/vm/macos/libtcvm.dylib")
    env = probe_environment()
    env["TOTALCROSS3_HOME"] = str(runtime_home)
    compile_cp = os.pathsep.join((str(sdk_jar), str(sdk / "dist/libs/*")))
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        raise PackageError("a JDK with javac and java is required")
    compile_command = [javac, "--release", "8", "-cp", compile_cp, "-d", str(classes), *map(str, sources)]
    jar = output / "Default.jar"
    deployment = output / "deploy"
    deployment.mkdir()
    app_cp = os.pathsep.join((str(classes), compile_cp))
    deploy_command = [java, "-cp", app_cp, "tc.Deploy", str(jar), "-macos", "/p", "/n",
                      "historical-static-paint", "/o", str(deployment) + os.sep]
    with (output / "build.log").open("x") as log:
        run_logged(compile_command, ROOT, env, log)
        write_profile_jar(classes, "Default", jar, files)
        run_logged(deploy_command, runtime_home, env, log)
    package = deployment / "install/macos"
    executable = package / "historical-static-paint"
    deployed_library = package / "libtcvm.dylib"
    if sha256(executable) != sha256(launcher) or sha256(deployed_library) != sha256(library):
        raise PackageError("deployed runtime differs from freshly built historical binaries")
    config = {
        "profile": "default", "family": "scroll", "workload": "scroll",
        "scrollDriver": "paint-preparation-probe", "width": 540, "height": 960,
        "round": 1, "phase": "measured", "preflight": False, "diagnosticsEnabled": False,
        "runtimeSourceCommit": RUNTIME_SHA, "benchmarkSourceCommit": git(ROOT, "rev-parse", "HEAD"),
        "datasetRoot": str(files),
        "datasetManifestPath": str(args.dataset_cache.resolve() / "objects/manifest.json"),
        "dataset": dataset,
    }
    write_json(package / "tcbench-run.json", config)
    manifest = {
        "runtimeSourceCommit": RUNTIME_SHA, "benchmarkSourceCommit": config["benchmarkSourceCommit"],
        "runtimeSource": str(source), "nativeBuild": str(native), "depotToolsCommit": pin,
        "sdkJarSha256": sha256(sdk_jar), "launcherSha256": sha256(launcher),
        "libtcvmSha256": sha256(library), "dataset": dataset,
        "manifestSha256": descriptor["integrity"]["manifestSha256"],
        "compileCommand": compile_command, "deployCommand": deploy_command,
        "launchCommand": [str(executable), "/scr", "-2,-2,540,960"],
        "workingDirectory": str(package), "sdkBuildCommand": "./gradlew-agent dist -x test --rerun-tasks",
        "nativeConfiguration": {key: value for key, value in cache.items()
                                if key in ("CMAKE_BUILD_TYPE", "CMAKE_OSX_ARCHITECTURES", "CMAKE_HOME_DIRECTORY",
                                           "TCVM_DEPOT_TOOLS_DIR", "SQLITE3_RELEASE_TAG", "QRCODEGEN_RELEASE_TAG")},
        "files": {str(p.relative_to(output)): sha256(p) for p in package.rglob("*") if p.is_file()},
        "sharedSourceSha256": {name: sha256(SOURCE / name)
                               for name in ("ScrollWorkload.java", "BenchSupport.java", "ScrollTiming.java", "profiles/Default.java")},
        "historicalSourceSha256": {str(p.relative_to(ROOT)): sha256(p) for p in HISTORICAL.rglob("*.java")},
        "stagedScrollSourceSha256": sha256(staged_source),
    }
    write_json(output / "package.json", manifest)
    clean_historical_source(source)
    print("historical package built: " + str(output / "package.json"))


def validate_historical_result(record: dict, manifest: dict) -> None:
    validate_paint_preparation_result(record, 540, 960)
    if (record.get("runtimeSourceCommit") != RUNTIME_SHA
            or record.get("configuredMask") != 32799 or record.get("effectiveMask") != 32799):
        raise PackageError("historical result source or natural masks mismatch")
    measurements = record["measurements"]
    identity = measurements.get("historicalVisibleIdentity", {})
    if any(identity.get(key) is not True for key in (
            "sameImageInstances", "sameControlInstances", "sameRowInstances")):
        raise PackageError("historical row/control/Image identity was not retained")
    if identity.get("scrollPosition") != 0 or not measurements["timingComparisonValid"]:
        raise PackageError("historical viewport equivalence failed")
    config = json.loads((Path(manifest["workingDirectory"]) / "tcbench-run.json").read_text())
    entries = json.loads(Path(config["datasetManifestPath"]).read_text())["files"]
    expected = [{"manifestIndex": i, "rowIndex": i // 3, "path": entry["path"], "format": entry["format"]}
                for i, entry in enumerate(entries[:18])]
    if identity.get("controls") != expected:
        raise PackageError("historical visible controls differ from current manifest ordering")
    for name in ("unpreparedPaintTree", "preparedPaintTree"):
        for sample in measurements[name]["samples"]:
            if sample["rowPaintCount"] != 6 or sample["imagePaintCount"] != 18 or sample["scrollPosition"] != 0:
                raise PackageError("historical sample must paint exactly six rows/eighteen images at zero")


def run(args) -> None:
    output = args.package.resolve()
    if (output / "launch-attempt.json").exists():
        raise PackageError("one historical launch was already attempted; inspect preserved evidence")
    manifest = json.loads((output / "package.json").read_text())
    clean_historical_source(Path(manifest["runtimeSource"]))
    if git(ROOT, "status", "--porcelain", "--untracked-files=no"):
        raise PackageError("commit benchmark tooling before the measured process")
    for relative, expected in manifest["sharedSourceSha256"].items():
        if sha256(SOURCE / relative) != expected:
            raise PackageError("shared workload changed since compilation: " + relative)
    for relative, expected in manifest["historicalSourceSha256"].items():
        if sha256(ROOT / relative) != expected:
            raise PackageError("historical controller changed since compilation: " + relative)
    for relative, expected in manifest["files"].items():
        if sha256(output / relative) != expected:
            raise PackageError("historical deployed artifact changed: " + relative)
    config_path = Path(manifest["workingDirectory"]) / "tcbench-run.json"
    config = json.loads(config_path.read_text())
    config["benchmarkSourceCommit"] = git(ROOT, "rev-parse", "HEAD")
    write_json(config_path, config)
    manifest["benchmarkSourceCommit"] = config["benchmarkSourceCommit"]
    manifest["files"][str(config_path.relative_to(output))] = sha256(config_path)
    write_json(output / "package.json", manifest)
    # Exclusive guard is written before spawn and retained on failure/timeout.
    with (output / "launch-attempt.json").open("x") as guard:
        json.dump({"command": manifest["launchCommand"], "processCount": 1}, guard, indent=2)
    with (output / "stdout.log").open("x") as stdout, (output / "stderr.log").open("x") as stderr:
        child = subprocess.run(manifest["launchCommand"], cwd=manifest["workingDirectory"],
                               env=probe_environment(), stdout=stdout, stderr=stderr, timeout=180)
    write_json(output / "process.json", {"exitCode": child.returncode, "processCount": 1})
    if child.returncode:
        raise PackageError("historical process failed with exit %d; see stdout.log/stderr.log" % child.returncode)
    stdout_text = (output / "stdout.log").read_text()
    # SDL builds can direct Java output to DebugConsole rather than stdout.
    debug = Path(manifest["workingDirectory"]) / "DebugConsole.txt"
    debug_text = ""
    if debug.exists():
        shutil.copy2(debug, output / "DebugConsole.txt")
        debug_text = debug.read_text()
    records, preflights = protocol_records(stdout_text, debug_text)
    if (len(records) != 1 or len(preflights) != 1
            or preflights[0].get("configuredMask") != 32799 or preflights[0].get("effectiveMask") != 32799):
        raise PackageError("expected one measured result and one inline historical default check")
    record = records[0]
    validate_historical_result(record, manifest)
    write_json(output / "result.json", record)
    m = record["measurements"]
    print(json.dumps({"status": "passed", "processes": 1, "samplesPerPhase": 5,
                      "callbacks": m["callbackCompletions"], "prepareWaitMs": m["prepareWaitNs"] / 1e6,
                      "beforeP50Ms": m["unpreparedPaintTree"]["statistics"]["p50Ns"] / 1e6,
                      "afterP50Ms": m["preparedPaintTree"]["statistics"]["p50Ns"] / 1e6,
                      "result": str(output / "result.json")}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build")
    for name in ("runtime-source", "native-build", "dataset-cache", "output"):
        builder.add_argument("--" + name, type=Path, required=True)
    runner = commands.add_parser("run")
    runner.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    try:
        (build if args.command == "build" else run)(args)
    except (PackageError, RunnerError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("historical probe: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
