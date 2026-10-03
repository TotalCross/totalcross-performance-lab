# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

"""Validate the causal protocol without asserting the predicted outcome."""

from pathlib import Path
import subprocess

BASE_RUNTIME = "5a44f503bf6fa1bec350f1218f4d501a70fc4812"
EXPERIMENT_RUNTIME = "fc08c39499dead73b327ad259a992ab34ec42870"


def is_experiment_package(manifest, source):
    if source is None or manifest.get("profileInventory") != ["default"]:
        return False
    if manifest.get("profiles", {}).get("default", {}).get("entryClass") != "totalcross.bench.imagerendering.profiles.CausalDefault":
        return False
    expected = manifest.get("runtimeArtifactSourceCommit", "")
    if expected != EXPERIMENT_RUNTIME or manifest.get("totalcrossSourceCommit") != expected:
        return False
    if manifest.get("buildConfiguration", {}).get("runtimeArtifactMode") != "local-release-build":
        return False
    patch = Path(__file__).parents[1] / "experiments/p12-copyrect-causal/runtime.patch"
    actual = subprocess.run(["git", "-C", str(source), "diff", BASE_RUNTIME, expected, "--binary", "--unified=0"],
                            text=True, capture_output=True, check=False)
    return actual.returncode == 0 and actual.stdout == patch.read_text()


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
    run.validate_schema(m, run.read_json(run.SCHEMA_DIR / "copyrect-causal-probe-v1.schema.json"), run.SCHEMA_DIR)
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
        # Preserve unexpected but valid outcomes for causal analysis. No time,
        # admission, generic-path or cache-hit prediction is an acceptance gate.
