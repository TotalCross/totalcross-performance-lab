# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

"""Validate the causal protocol without asserting the predicted outcome."""

from pathlib import Path
import subprocess

BASE_RUNTIME = "5a44f503bf6fa1bec350f1218f4d501a70fc4812"
EXPERIMENT_RUNTIME = "fc08c39499dead73b327ad259a992ab34ec42870"
IMMEDIATE_RUNTIME = "f95c280db3d6856d17582ea31d47aaded6a0e492"
WRITEPIXELS_RUNTIME = "18baece1f199ab5d2e7cad6d864c40c188bd1bab"
EXPERIMENTS = {
    "writepixels-warm-path-probe": (WRITEPIXELS_RUNTIME, "WritePixelsWarmDefault", "p12-writepixels-warm"),
    "copyrect-causal-probe": (EXPERIMENT_RUNTIME, "CausalDefault", "p12-copyrect-causal"),
    "immediate-admission-probe": (IMMEDIATE_RUNTIME, "ImmediateAdmissionDefault", "p12-immediate-admission"),
}


def is_experiment_package(manifest, source, driver="copyrect-causal-probe"):
    if driver not in EXPERIMENTS:
        return False
    revision, entry, directory = EXPERIMENTS[driver]
    if source is None or manifest.get("profileInventory") != ["default"]:
        return False
    if manifest.get("profiles", {}).get("default", {}).get("entryClass") != "totalcross.bench.imagerendering.profiles." + entry:
        return False
    expected = manifest.get("runtimeArtifactSourceCommit", "")
    if expected != revision or manifest.get("totalcrossSourceCommit") != expected:
        return False
    if manifest.get("buildConfiguration", {}).get("runtimeArtifactMode") != "local-release-build":
        return False
    patch = Path(__file__).parents[1] / "experiments" / directory / "runtime.patch"
    actual = subprocess.run(["git", "-C", str(source), "diff", BASE_RUNTIME, expected, "--binary", "--unified=0"],
                            text=True, capture_output=True, check=False)
    if actual.returncode != 0 or actual.stdout != patch.read_text():
        return False
    if driver in ("immediate-admission-probe", "writepixels-warm-path-probe"):
        parent = IMMEDIATE_RUNTIME if driver == "writepixels-warm-path-probe" else EXPERIMENT_RUNTIME
        delta = subprocess.run(["git", "-C", str(source), "diff", parent, expected,
                                "--binary", "--unified=0"], text=True, capture_output=True, check=False)
        return delta.returncode == 0 and delta.stdout == patch.with_name(
            "writepixels.patch" if driver == "writepixels-warm-path-probe" else "admission.patch").read_text()
    return True


def classify(c):
    result = []
    for field, label in (("cachedFinalRasterHits", "cached-final hit"),
                         ("cachedFinalRasterMisses", "cached-final miss"),
                         ("physicalCopyAttempts", "physical copy attempted"),
                         ("physicalCopyHits", "physical copy hit"),
                         ("physicalCopyFallbacks", "physical copy fallback"),
                         ("identityFallbacks", "identity fallback"),
                         ("genericGeometryDraws", "direct generic geometry"),
                         ("smoothResampleDraws", "direct smooth resample"),
                         ("resolveForDrawingCalls", "resolveForDrawing"),
                         ("nativeGeometryMaterializations", "offscreen geometry materialized"),
                         ("materializedVariantObservations", "variant observed"),
                         ("materializedVariantAdmissions", "variant admitted")):
        if c[field]:
            result.append(label)
    return result


def validate_result(record, entries):
    from runners import run
    if (record.get("profile") != "default" or record.get("family") != "scroll"
            or record.get("renderer") != "RASTER" or record.get("diagnosticsEnabled") is not False
            or record.get("logicalDimensions") != {"width": 540, "height": 960}
            or record.get("drawableDimensions") != {"width": 1080, "height": 1920}):
        raise run.RunnerError("causal probe runtime axes/profile differ from P12")
    m = record["measurements"]
    schema = {"writepixels-warm-path-probe": "writepixels-warm-path-probe-v1.schema.json",
              "immediate-admission-probe": "immediate-admission-probe-v1.schema.json"}.get(
                  m.get("scrollDriver"), "copyrect-causal-probe-v1.schema.json")
    run.validate_schema(m, run.read_json(run.SCHEMA_DIR / schema), run.SCHEMA_DIR)
    if m["runtimeConfigurationBefore"] != m["runtimeConfigurationAfter"]:
        raise run.RunnerError("causal probe changed runtime defaults")
    if m["viewportOrder"] != [{"datasetIndex": i, "path": entries[i]["path"]} for i in range(18)]:
        raise run.RunnerError("causal probe differs from retained manifest viewport order")
    for i, sample in enumerate([m["stabilization"], *m["samples"]]):
        if sample["sample"] != i or sample["timed"] != (i != 0) or (sample["paintTreeNs"] is None) != (i == 0):
            raise run.RunnerError("causal probe must have one untimed stabilization and five ordered timed samples")
        c = sample["counters"]
        if (c["cachedFinalRasterProbes"] != c["cachedFinalRasterHits"] + c["cachedFinalRasterMisses"]
                or c["copyRectPlanAttempts"] != c["copyRectPlanHandled"] + c["copyRectPlanFallbacks"]):
            raise run.RunnerError("causal probe counters do not conserve probes/attempts")
        if m["scrollDriver"] == "writepixels-warm-path-probe":
            validate_writepixels(c["writePixels"])
        # Preserve unexpected but valid outcomes for causal analysis. No time,
        # admission, generic-path or cache-hit prediction is an acceptance gate.


def validate_writepixels(wp):
    """Conserve captured evidence; do not require hits or a predicted time."""
    from runners import run
    draws = wp["draws"]
    if (wp["attempts"] != wp["hits"] + wp["fallbacks"] or len(draws) != wp["attempts"]
            or wp["hits"] != sum(d["hit"] for d in draws)
            or wp["fallbacks"] != sum(wp["rejections"].values())
            or wp["fallbackDraws"] != wp["fallbacks"]
            or wp["copiedBytes"] != sum(d["copiedBytes"] for d in draws)
            or wp["clippedHits"] != sum(d["hit"] and d["clipped"] for d in draws)):
        raise run.RunnerError("writePixels counters/records do not conserve attempts, bytes or rejections")
    for reason, count in wp["rejections"].items():
        if count != sum(d["rejection"] == reason for d in draws):
            raise run.RunnerError("writePixels rejection counts differ from draw records")
    for field in ("attemptNs", "writeNs", "fallbackNs"):
        if wp[field] != sum(d[field] for d in draws):
            raise run.RunnerError("writePixels timing totals differ from draw records")
    for d in draws:
        if d["hit"]:
            a, b = d["clippedSourcePhysical"], d["clippedDestinationDevice"]
            if (d["rejection"] != "none" or d["sourceFormat"] != 0 or d["opacityAfter"] != 1
                    or a is None or b is None or a[2]-a[0] != b[2]-b[0]
                    or a[3]-a[1] != b[3]-b[1] or d["copiedBytes"] != (a[2]-a[0])*(a[3]-a[1])*4):
                raise run.RunnerError("writePixels hit lacks matching physical rectangles/opaque RGBA bytes")
        elif d["rejection"] == "none" or d["copiedBytes"]:
            raise run.RunnerError("writePixels fallback must preserve an explicit rejection with zero copied bytes")
