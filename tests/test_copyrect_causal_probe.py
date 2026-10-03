# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runners import run
from tools import copyrect_causal as causal

ROOT = Path(__file__).parents[1]


def fixture():
    schema = json.loads((ROOT / "schemas/copyrect-causal-probe-v1.schema.json").read_text())
    fields = schema["properties"]["stabilization"]["properties"]["counters"]["properties"]
    def sample(i):
        counters = {k: (True if k == "physicalOnlyEnabled" else 0) for k in fields}
        counters.update(cachedFinalRasterProbes=18, cachedFinalRasterMisses=18,
                        physicalCopyAttempts=18, physicalCopyFallbacks=18, identityAttempts=18,
                        identityFallbacks=18, copyRectPlanAttempts=18, copyRectPlanFallbacks=18,
                        resolveForDrawingCalls=18, materializedVariantObservations=18,
                        materializedVariantAdmissions=18 if i == 1 else 0,
                        nativeGeometryMaterializations=18)
        if i >= 2:
            counters = {k: (True if k == "physicalOnlyEnabled" else 0) for k in fields}
            counters.update(cachedFinalRasterProbes=18, cachedFinalRasterHits=18)
        return dict(sample=i, timed=i != 0, paintTreeNs=278000000 if i == 1 else 4000000 if i else None,
                    rowPaintCount=6, imagePaintCount=18, rowPaintNs=100, imagePaintNs=100,
                    scrollPosition=0, counters=counters)
    m = {k: v["const"] for k, v in schema["properties"].items() if "const" in v}
    entries = [{"path": "%d.jpg" % i} for i in range(663)]
    m.update(stabilization=sample(0), samples=[sample(i) for i in range(1, 6)],
             runtimeConfigurationBefore="production defaults", runtimeConfigurationAfter="production defaults",
             viewportOrder=[{"datasetIndex": i, "path": entries[i]["path"]} for i in range(18)],
             axes=dict(logicalViewportWidth=540, logicalViewportHeight=910, displayScale=2))
    return dict(profile="default", family="scroll", renderer="RASTER", diagnosticsEnabled=False,
                logicalDimensions=dict(width=540, height=960), drawableDimensions=dict(width=1080, height=1920),
                measurements=m), entries


class CausalProbeTests(unittest.TestCase):
    def test_predicted_sequence_and_protocol(self):
        record, entries = fixture()
        causal.validate_result(record, entries)
        self.assertIn("variant admitted", causal.classify(record["measurements"]["samples"][0]["counters"]))
        self.assertEqual(["cached-final hit"], causal.classify(record["measurements"]["samples"][1]["counters"]))

    def test_surprising_valid_sequence_is_not_rejected(self):
        record, entries = fixture()
        for sample in record["measurements"]["samples"]:
            sample["paintTreeNs"] = 999999999
            sample["counters"].update(cachedFinalRasterProbes=18, cachedFinalRasterHits=0,
                                      cachedFinalRasterMisses=18, genericGeometryDraws=18, smoothResampleDraws=18)
        causal.validate_result(record, entries)

    def test_exact_sampling_geometry_masks_and_instances(self):
        record, entries = fixture()
        mutations = [lambda m: m["samples"].pop(), lambda m: m.update(prepareRequests=1),
                     lambda m: m.update(sameImageInstances=False), lambda m: m.update(runtimeDefaultsUnchanged=False),
                     lambda m: m["samples"][0].update(sample=2),
                     lambda m: m["stabilization"].update(paintTreeNs=1),
                     lambda m: m["samples"][0].update(imagePaintCount=663),
                     lambda m: m["viewportOrder"][0].update(path="wrong.jpg"),
                     lambda m: m["samples"][0]["counters"].pop("resolveForDrawingCalls"),
                     lambda m: m["samples"][0]["counters"].update(cachedFinalRasterHits=1)]
        for mutate in mutations:
            bad = copy.deepcopy(record); mutate(bad["measurements"])
            with self.assertRaises(run.RunnerError): causal.validate_result(bad, entries)
        bad = copy.deepcopy(record); bad["drawableDimensions"]["width"] = 540
        with self.assertRaises(run.RunnerError): causal.validate_result(bad, entries)

    def test_single_process_arguments_and_inline_preflight(self):
        args = dict(scroll_driver="copyrect-causal-probe", family="scroll", profiles="default", rounds=1,
                    warmups=0, diagnostics=False, width=540, height=960, require_default_scroll_preflight=True)
        run.validate_scroll_driver_arguments(SimpleNamespace(**args))
        for changes in (dict(rounds=2), dict(warmups=1), dict(profiles="compact"), dict(diagnostics=True)):
            with self.assertRaises(run.RunnerError):
                run.validate_scroll_driver_arguments(SimpleNamespace(**{**args, **changes}))
        source = (ROOT / "runners/run.py").read_text()
        # Inline-only list immediately guards the separate preflight launcher.
        start = source.rindex('if getattr(arguments, "scroll_driver", "fixed-step") not in (')
        self.assertIn('"copyrect-causal-probe"', source[start:source.index('launch_preflight(', start)])

    def test_runtime_identity_and_patch_are_required(self):
        m = dict(profileInventory=["default"], profiles={"default": {"entryClass": "totalcross.bench.imagerendering.profiles.CausalDefault"}},
                 runtimeArtifactSourceCommit=causal.EXPERIMENT_RUNTIME,
                 totalcrossSourceCommit=causal.EXPERIMENT_RUNTIME,
                 buildConfiguration=dict(runtimeArtifactMode="local-release-build"))
        runtime_patch = (ROOT / "experiments/p12-copyrect-causal/runtime.patch").read_text()
        with patch.object(causal.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=runtime_patch)):
            self.assertTrue(causal.is_experiment_package(m, Path("/source")))
            self.assertFalse(causal.is_experiment_package({**m, "runtimeArtifactSourceCommit": causal.BASE_RUNTIME}, Path("/source")))
            self.assertFalse(causal.is_experiment_package(m, None))
        with patch.object(causal.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="wrong")):
            self.assertFalse(causal.is_experiment_package(m, Path("/source")))

    def test_experimental_sources_are_excluded_from_normal_package(self):
        from tools.packaging.build_macos import selected_java_sources, PackageError
        root = ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering"
        normal = selected_java_sources(root, ("default",))
        special = selected_java_sources(root, ("default",), True)
        self.assertFalse(any("experiments" in p.parts for p in normal))
        self.assertTrue(any(p.name == "CausalDefault.java" for p in special))
        self.assertTrue(any(p.name == "ImageCausalProbeHooks.java" for p in special))
        self.assertFalse(any(p.name == "Default.java" for p in special))
        with self.assertRaises(PackageError): selected_java_sources(root, ("compact",), True)

    def test_runtime_patch_is_narrow_and_admission_untouched(self):
        source = (ROOT / "experiments/p12-copyrect-causal/runtime.patch").read_text()
        self.assertIn("if (allowPhysicalCopy && physicalOnlyForTest)", source)
        self.assertIn("causalResolveCallsForTest++", source)
        self.assertIn("causalVariantObservationsForTest++", source)
        self.assertIn("causalVariantAdmissionsForTest++", source)
        self.assertNotIn("diff --git a/TotalCrossSDK/src/main/java/totalcross/ui/image/ImagePipeline.java", source)
        self.assertNotIn("diff --git a/TotalCrossSDK/src/main/java/totalcross/ui/gfx/Graphics.java", source)
        self.assertNotIn("ImageOptimizationSettings", source)

    def test_probe_enables_switch_only_before_one_stabilization(self):
        source = (ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering/ScrollWorkload.java").read_text()
        body = source[source.index("  private void runCopyRectCausalProbe()"):source.index("  private void runPhysicalMappingProbe()")]
        self.assertEqual(1, body.count("scroll.repaintNow();"))
        self.assertEqual(1, body.count("paintTreeOnly();"))
        self.assertIn("sample <= 5", body)
        self.assertLess(body.index("startCausalExperiment();"), body.index("scroll.repaintNow();"))
        self.assertNotIn("prepareForDisplay", body)
        self.assertNotIn("scrollContent", body)


if __name__ == "__main__":
    unittest.main()
