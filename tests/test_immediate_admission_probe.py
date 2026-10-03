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
from tools.packaging.build_macos import selected_java_sources, PackageError
from tests.test_copyrect_causal_probe import fixture as second_observation_fixture

ROOT = Path(__file__).parents[1]


def fixture():
    record, entries = second_observation_fixture()
    m = record["measurements"]
    m.update(scrollDriver="immediate-admission-probe", admissionPolicy="immediate")
    m["stabilization"]["counters"]["materializedVariantAdmissions"] = 18
    cached = copy.deepcopy(m["samples"][1]["counters"])
    for s in [m["stabilization"], *m["samples"]]:
        if s["sample"]:
            s["counters"] = copy.deepcopy(cached)
            s["paintTreeNs"] = 3500000
        s["counters"]["immediateAdmissionEnabled"] = True
    return record, entries


class ImmediateAdmissionProbeTests(unittest.TestCase):
    def test_first_sample_warm_and_complete_protocol(self):
        record, entries = fixture()
        causal.validate_result(record, entries)
        self.assertEqual(18, record["measurements"]["stabilization"]["counters"]["materializedVariantAdmissions"])
        for s in record["measurements"]["samples"]:
            self.assertEqual(["cached-final hit"], causal.classify(s["counters"]))

    def test_surprising_cold_sample_is_preserved(self):
        record, entries = fixture()
        prior, _ = second_observation_fixture()
        record["measurements"]["samples"][0] = prior["measurements"]["samples"][0]
        record["measurements"]["samples"][0]["counters"]["immediateAdmissionEnabled"] = True
        causal.validate_result(record, entries)

    def test_policy_flag_and_five_samples_are_required(self):
        record, entries = fixture()
        for change in (lambda m: m.update(admissionPolicy="second-observation"),
                       lambda m: m["samples"].pop(),
                       lambda m: m["stabilization"]["counters"].update(immediateAdmissionEnabled=False),
                       lambda m: m["samples"][0]["counters"].pop("immediateAdmissionEnabled")):
            bad = copy.deepcopy(record); change(bad["measurements"])
            with self.assertRaises(run.RunnerError): causal.validate_result(bad, entries)

    def test_exact_runtime_and_admission_delta_required(self):
        m = dict(profileInventory=["default"], profiles={"default": {
            "entryClass": "totalcross.bench.imagerendering.profiles.ImmediateAdmissionDefault"}},
            runtimeArtifactSourceCommit=causal.IMMEDIATE_RUNTIME, totalcrossSourceCommit=causal.IMMEDIATE_RUNTIME,
            buildConfiguration=dict(runtimeArtifactMode="local-release-build"))
        exp = ROOT / "experiments/p12-immediate-admission"
        good = [SimpleNamespace(returncode=0, stdout=(exp / name).read_text())
                for name in ("runtime.patch", "admission.patch")]
        with patch.object(causal.subprocess, "run", side_effect=good):
            self.assertTrue(causal.is_experiment_package(m, Path("/source"), "immediate-admission-probe"))
        with patch.object(causal.subprocess, "run", side_effect=[good[0], SimpleNamespace(returncode=0, stdout="wrong")]):
            self.assertFalse(causal.is_experiment_package(m, Path("/source"), "immediate-admission-probe"))
        self.assertFalse(causal.is_experiment_package(m, Path("/source")))
        self.assertFalse(causal.is_experiment_package(m, None, "immediate-admission-probe"))

    def test_normal_sources_exclude_policy_hooks(self):
        root = ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering"
        normal = selected_java_sources(root, ("default",))
        prior = selected_java_sources(root, ("default",), True)
        immediate = selected_java_sources(root, ("default",), False, True)
        for sources in (normal, prior):
            self.assertFalse(any(p.name == "ImageImmediateAdmissionHooks.java" for p in sources))
        self.assertTrue(any(p.name == "ImageImmediateAdmissionHooks.java" for p in immediate))
        self.assertTrue(any(p.name == "ImageCausalProbeHooks.java" for p in immediate))
        self.assertTrue(any(p.name == "ImmediateAdmissionDefault.java" for p in immediate))
        with self.assertRaises(PackageError): selected_java_sources(root, ("default",), True, True)
        with self.assertRaises(PackageError): selected_java_sources(root, ("compact",), False, True)

    def test_only_admission_and_tests_change_relative_to_routing_parent(self):
        delta = (ROOT / "experiments/p12-immediate-admission/admission.patch").read_text()
        paths = [line.split()[2] for line in delta.splitlines() if line.startswith("diff --git")]
        self.assertEqual(["a/TotalCrossSDK/src/main/java/totalcross/ui/image/Image.java",
                          "a/TotalCrossSDK/src/test/java/totalcross/ui/image/ImageImmediateAdmissionExperimentTest.java"], paths)
        self.assertIn("immediateMaterializedAdmissionForTest != 0", delta)
        self.assertIn("copyRectPhysicalOnlyForTest != 0 && imageOperationAccountingForTest", delta)
        self.assertIn("failedMaterializationCannotObserveOrAdmit", delta)
        self.assertIn("changedDecodeGenerationStillRejects", delta)
        self.assertIn("invalidBackingStillRejects", delta)
        self.assertNotIn("ImagePipeline.java", delta)
        self.assertNotIn("TotalCrossVM/", delta)

    def test_one_process_driver_and_shared_exact_protocol(self):
        args = dict(scroll_driver="immediate-admission-probe", family="scroll", profiles="default", rounds=1,
                    warmups=0, diagnostics=False, width=540, height=960, require_default_scroll_preflight=True)
        run.validate_scroll_driver_arguments(SimpleNamespace(**args))
        for change in (dict(rounds=2), dict(warmups=1), dict(profiles="compact")):
            with self.assertRaises(run.RunnerError):
                run.validate_scroll_driver_arguments(SimpleNamespace(**{**args, **change}))
        source = (ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering/ScrollWorkload.java").read_text()
        self.assertIn("DRIVER_COPYRECT_CAUSAL.equals(scrollDriver) || DRIVER_IMMEDIATE_ADMISSION.equals(scrollDriver)", source)
        runner = (ROOT / "runners/run.py").read_text()
        start = runner.rindex('if getattr(arguments, "scroll_driver", "fixed-step") not in (')
        self.assertIn('"immediate-admission-probe"', runner[start:runner.index('launch_preflight(', start)])


if __name__ == "__main__":
    unittest.main()
