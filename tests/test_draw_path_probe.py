# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

import copy
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from runners import run
from tools.packaging import build_macos, build_windows

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering"
HELPER = ROOT / "benchmarks/image-rendering/src/totalcross/ui/image/ImageDrawPathProbeAccess.java"


def draw_path_record():
    schema = run.read_json(run.SCHEMA_DIR / "image-draw-path-probe-v1.schema.json")
    counters = {name: 0 for name in schema["$defs"]["counters"]["required"]}
    counters.update(copyRectPlanAttempts=1, copyRectPlanHandled=1, cachedFinalRasterProbes=1,
                    cachedFinalRasterMisses=1, identityAttempts=1, identityFallbacks=1,
                    genericGeometryDraws=1, smoothResampleDraws=1, copyRectPlanLastStatus=0x3000b)
    flags = {name: False for name in schema["$defs"]["control"]["properties"]["statusFlags"]["required"]}
    flags.update(handled=True, identityAttempted=True, identityFallback=True, genericGeometry=True, smoothResample=True)
    tags = ["cached-final miss", "identity attempted", "identity fallback", "physical-copy no hit",
            "generic geometry", "smooth resample", "draw handled"]
    controls = [{"datasetIndex": i, "rowIndex": i // 3, "path": "image%03d.jpg" % i, "format": "jpeg",
                 "imageControlPaintNs": 100 + i, "rowPaintCount": 0, "rowPaintNs": 0,
                 "imagePaintCount": 1, "imagePaintNs": 95 + i, "scrollPosition": 0,
                 "counters": copy.deepcopy(counters), "rawStatus": 0x3000b, "statusHex": "0x3000b",
                 "statusFlags": copy.deepcopy(flags), "classification": tags.copy(),
                 "copyRectAttemptsExceedOne": False} for i in range(18)]
    aggregate = copy.deepcopy(controls[0])
    aggregate.update(paintTreeNs=2000, rowPaintCount=6, imagePaintCount=18)
    aggregate["counters"] = {name: value if name == "copyRectPlanLastStatus" else value * 18
                             for name, value in counters.items()}
    return {"family": "scroll", "profile": "default", "renderer": "RASTER", "diagnosticsEnabled": False,
            "logicalDimensions": {"width": 540, "height": 960}, "measurements": {
                "scrollDriver": "draw-path-probe", "imageControls": 663, "rows": 221, "columns": 3,
                "tileWidth": 179, "scrollPosition": 0, "stabilizationRepaints": 1, "aggregateSamples": 1,
                "perControlSamples": 18, "prepareRequests": 0, "preparation": False,
                "sameImageInstances": True, "sameControlInstances": True, "sameRowInstances": True,
                "physicalCopyAccounting": "hit-only; attempt/fallback counters unavailable",
                "lastStatusScope": "last copyRect plan attempt in each accounting sample",
                "aggregate": aggregate, "perControl": controls, "unexpectedDisabledPathActivity": False,
                "individualTimingNs": {"min": 100, "median": 108.5, "max": 117, "sum": sum(range(100, 118))},
            }}


class DrawPathProbeTests(unittest.TestCase):
    def test_probe_is_one_default_run_without_warmups_or_diagnostics(self):
        args = SimpleNamespace(scroll_driver="draw-path-probe", family="scroll", profiles="default",
                               rounds=1, warmups=0, diagnostics=False, width=540, height=960,
                               require_default_scroll_preflight=True)
        run.validate_scroll_driver_arguments(args)
        for changes in ({"profiles": "target-color"}, {"family": "preparation"}, {"rounds": 2},
                        {"warmups": 1}, {"diagnostics": True}, {"width": 539}, {"height": 959},
                        {"require_default_scroll_preflight": False}):
            with self.subTest(changes=changes), self.assertRaises(run.RunnerError):
                run.validate_scroll_driver_arguments(SimpleNamespace(**{**vars(args), **changes}))

    def test_valid_complete_result_and_manifest_order(self):
        record = draw_path_record()
        entries = [{"path": sample["path"], "format": sample["format"]}
                   for sample in record["measurements"]["perControl"]]
        run.validate_draw_path_result(record, 540, 960, entries)
        entries.reverse()
        with self.assertRaisesRegex(run.RunnerError, "manifest order"):
            run.validate_draw_path_result(record, 540, 960, entries)

    def test_aggregate_counter_schema_rejects_missing_or_invalid_values(self):
        for name in run.read_json(run.SCHEMA_DIR / "image-draw-path-probe-v1.schema.json")["$defs"]["counters"]["required"]:
            for bad in (None, -1, True):
                record = draw_path_record()
                record["measurements"]["aggregate"]["counters"][name] = bad
                with self.subTest(name=name, bad=bad), self.assertRaises(run.RunnerError):
                    run.validate_draw_path_result(record, 540, 960)
        record = draw_path_record()
        del record["measurements"]["aggregate"]["counters"]["smoothResampleDraws"]
        with self.assertRaises(run.RunnerError):
            run.validate_draw_path_result(record, 540, 960)

    def test_eighteen_controls_and_zero_preparation_are_mandatory(self):
        for changes in ({"prepareRequests": 1}, {"aggregateSamples": 2}, {"sameImageInstances": False},
                        {"preparation": True}, {"stabilizationRepaints": 2}):
            record = draw_path_record()
            record["measurements"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(run.RunnerError):
                run.validate_draw_path_result(record, 540, 960)
        for count in (17, 19):
            record = draw_path_record()
            samples = record["measurements"]["perControl"]
            record["measurements"]["perControl"] = (samples + samples[:1])[:count]
            with self.subTest(count=count), self.assertRaises(run.RunnerError):
                run.validate_draw_path_result(record, 540, 960)

    def test_per_control_status_order_and_timing_must_be_consistent(self):
        mutations = (lambda m: m["perControl"][0].update(datasetIndex=1),
                     lambda m: m["perControl"][0].update(rawStatus=0),
                     lambda m: m["perControl"][0]["statusFlags"].update(identityHit=True),
                     lambda m: m["perControl"][0].update(classification=["identity hit"]),
                     lambda m: m["individualTimingNs"].update(sum=0),
                     lambda m: m["perControl"][0].update(copyRectAttemptsExceedOne=True))
        for mutate in mutations:
            record = draw_path_record()
            mutate(record["measurements"])
            with self.assertRaises(run.RunnerError):
                run.validate_draw_path_result(record, 540, 960)

    def test_unexpected_disabled_feature_attempt_is_reported_not_forced_away(self):
        record = draw_path_record()
        sample = record["measurements"]["perControl"][0]
        sample["counters"]["copyRectPlanLastStatus"] |= 16
        sample.update(rawStatus=0x3001b, statusHex="0x3001b")
        sample["statusFlags"]["targetColorAttempted"] = True
        sample["classification"].insert(4, "target-color attempted")
        record["measurements"]["unexpectedDisabledPathActivity"] = True
        run.validate_draw_path_result(record, 540, 960)

    def test_accounting_helper_is_compiled_and_packaged_as_benchmark_code(self):
        self.assertIn(HELPER, build_macos.selected_java_sources(SOURCE, ("default",)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("totalcross/ui/image/ImageDrawPathProbeAccess.class",
                         "totalcross/bench/imagerendering/profiles/Default.class"):
                path = root / "classes" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"test class")
            jar = root / "Default.jar"
            build_windows.write_profile_jar(root / "classes", "Default", jar)
            with zipfile.ZipFile(jar) as archive:
                self.assertIn("totalcross/ui/image/ImageDrawPathProbeAccess.class", archive.namelist())
        helper = HELPER.read_text()
        self.assertIn("package totalcross.ui.image;", helper)
        self.assertIn("ImageRasterFeatureBridge.resetDrawAccountingForTest();", helper)
        self.assertIn("Image.resetImageOperationAccountingForTest();", helper)
        self.assertNotIn("setMask", helper)

    def test_draw_path_branch_contains_no_preparation_or_scroll_driver(self):
        scroll = (SOURCE / "ScrollWorkload.java").read_text()
        body = scroll[scroll.index("private void runDrawPathProbe()"):scroll.index("private void runPaintSplitProbe()")]
        self.assertEqual(1, body.count("scroll.repaintNow();"))
        self.assertEqual(1, body.count("((MeasuredScrollContainer) scroll).paintTreeOnly();"))
        self.assertIn("visibleControls[i].onPaint(visibleControls[i].getGraphics());", body)
        self.assertIn("ImageDrawPathProbeAccess.snapshot();", body)
        self.assertNotIn("prepareForDisplay", body)
        self.assertNotIn("scroll.scrollContent", body)
        app = (SOURCE / "ImageRenderingBenchmarkApp.java").read_text()
        self.assertIn('"draw-path-probe".equals(scrollDriver)', app)


if __name__ == "__main__":
    unittest.main()
