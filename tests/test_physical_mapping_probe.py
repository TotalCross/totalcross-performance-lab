# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

import copy
import unittest
from pathlib import Path
from types import SimpleNamespace

from runners import run
from tools import physical_mapping as mapping


def plan():
    return dict(operationCount=1, operations=[1], parameters=[179, 179, 0, 0], dimensions=[179, 179],
                rootWidth=1000, rootHeight=1000, rootLogicalWidth=1000, rootLogicalHeight=1000,
                rootFrameCount=1, rootWidthOfAllFrames=0, currentFrame=0,
                rootContentScale=1, rootHwScaleW=1, rootHwScaleH=1, outputWidth=179, outputHeight=179,
                destinationScale=2, outputContentScale=2, hwScaleW=1, hwScaleH=1,
                alphaMask=255, materializeAlphaMask=255, outputAlphaMask=255,
                backingType="totalcross.ui.image.NativeImageBacking", backingNative=True, backingValid=True,
                backingWidth=1000, backingHeight=1000, sourceBackingStable=True,
                sourceMutationGeneration=0, backingMutationGeneration=0, sourceOpacityState=1,
                graphicsContentScale=2, drawableWidth=1080, drawableHeight=1920,
                graphicsTranslationX=1, graphicsTranslationY=40, clipX=0, clipY=0,
                clipWidth=179, clipHeight=179, drawX=0, drawY=0, inspectionMutationFree=True)


def fixture():
    entries = [dict(path="%d.jpg" % i, format="jpeg", width=1000, height=1000) for i in range(18)]
    controls = [dict(datasetIndex=i, rowIndex=i // 3, path=e["path"], format=e["format"],
                     intrinsicWidth=e["width"], intrinsicHeight=e["height"], plan=plan()) for i, e in enumerate(entries)]
    return dict(profile="default", family="scroll", renderer="RASTER", diagnosticsEnabled=False,
                logicalDimensions=dict(width=540, height=960), measurements=dict(
                    scrollDriver="physical-mapping-probe", imageControls=663, rows=221, columns=3,
                    tileWidth=179, scrollPosition=0, stabilizationRepaints=1, perControlSamples=18,
                    prepareRequests=0, preparation=False, timedPaintSamples=0,
                    sameImageInstances=True, sameControlInstances=True, sameRowInstances=True,
                    perControl=controls, canvasMatrixEvidence="native skia_setSurfaceScale resets matrix then scales by Graphics.getContentScale",
                    axes=dict(logicalViewportWidth=540, logicalViewportHeight=910, displayScale=2))), entries


class PhysicalMappingTests(unittest.TestCase):
    def test_exact_smooth_transform_and_first_ordered_failure(self):
        e = mapping.evaluate(plan())
        self.assertEqual(1000 / 179, e["transform"]["a"])
        self.assertEqual(1000 / 179, e["transform"]["d"])
        self.assertEqual(9, e["firstFailingGate"])
        self.assertTrue(all(g["pass"] for g in e["gates"][:8]))
        self.assertTrue(e["gates"][8]["reached"])
        self.assertFalse(e["gates"][9]["reached"])
        self.assertFalse(e["gates"][9]["pass"])
        self.assertEqual(5, mapping.evaluate(plan(), False)["firstFailingGate"])

    def test_composition_uses_root_scale_hardware_scale_and_order(self):
        p = plan()
        p.update(rootContentScale=2, rootHwScaleW=2, rootHwScaleH=4,
                 operationCount=2, operations=[0, 1], parameters=[0] * 8, dimensions=[500, 250, 179, 179])
        t = mapping.compile_geometry(p)
        self.assertEqual((1000 / 500) * (500 / 179), t["a"])
        self.assertEqual((.5 * (1000 / 250)) * (250 / 179), t["d"])

    def test_earlier_gates_take_precedence_and_later_checks_remain_visible(self):
        for changes, expected in ((dict(sourceBackingStable=False), 1),
                                  (dict(sourceMutationGeneration=1), 2),
                                  (dict(rootWidth=0), 3), (dict(outputContentScale=1), 5)):
            p = plan(); p.update(changes)
            with self.subTest(changes=changes):
                e = mapping.evaluate(p)
                self.assertEqual(expected, e["firstFailingGate"])
                self.assertEqual(list(range(1, 16)), [g["number"] for g in e["gates"]])

    def test_true_one_to_one_mapping_and_counterfactual_height_rejection(self):
        p = plan(); p.update(rootWidth=358, rootHeight=358, rootLogicalWidth=358, rootLogicalHeight=358,
                            backingWidth=358, backingHeight=358)
        self.assertIsNone(mapping.evaluate(p)["firstFailingGate"])
        p["rootLogicalHeight"] = 716
        e = mapping.evaluate(p)
        self.assertEqual(10, e["firstFailingGate"])
        self.assertFalse(e["gates"][10]["pass"])

    def test_clipping_explains_visible_work_without_changing_root_transform(self):
        p = plan(); p.update(clipHeight=3, graphicsTranslationY=947)
        e = mapping.evaluate(p)
        self.assertEqual(3, e["copyRect"]["visibleHeight"])
        self.assertEqual([1.0 * 2, 947.0 * 2, 180.0 * 2, 950.0 * 2], e["deviceDestination"])
        self.assertEqual(1000 / 179, e["transform"]["a"])

    def test_unknown_chain_is_not_approximated(self):
        p = plan(); p["operations"] = [2]
        with self.assertRaisesRegex(ValueError, "exact native"):
            mapping.evaluate(p)

    def test_complete_metadata_contract_and_negative_cases(self):
        record, entries = fixture()
        mapping.validate_result(record, entries)
        self.assertEqual(9, record["measurements"]["perControl"][0]["evaluation"]["firstFailingGate"])
        for change in (lambda r: r["measurements"].update(prepareRequests=1),
                       lambda r: r["measurements"].update(timedPaintSamples=1),
                       lambda r: r.update(profile="other"),
                       lambda r: r["measurements"]["perControl"].pop(),
                       lambda r: r["measurements"]["perControl"][0]["plan"].pop("rootHwScaleW"),
                       lambda r: r["measurements"]["perControl"][0]["plan"].update(inspectionMutationFree=False),
                       lambda r: r["measurements"]["perControl"][0].update(datasetIndex=1),
                       lambda r: r["measurements"]["perControl"][0]["evaluation"].update(firstFailingGate=1)):
            bad = copy.deepcopy(record); change(bad)
            with self.assertRaises(run.RunnerError): mapping.validate_result(bad, entries)

    def test_default_only_single_process_mode(self):
        args = dict(scroll_driver="physical-mapping-probe", family="scroll", profiles="default", rounds=1,
                    warmups=0, diagnostics=False, width=540, height=960, require_default_scroll_preflight=True)
        run.validate_scroll_driver_arguments(SimpleNamespace(**args))
        for bad in (dict(profiles="compact"), dict(rounds=2), dict(warmups=1), dict(diagnostics=True),
                    dict(require_default_scroll_preflight=False), dict(width=539)):
            with self.assertRaises(run.RunnerError): run.validate_scroll_driver_arguments(SimpleNamespace(**{**args, **bad}))

    def test_probe_has_no_preparation_or_timing_paints_and_helper_is_read_only(self):
        root = Path(__file__).parents[1] / "benchmarks/image-rendering/src/totalcross"
        scroll = (root / "bench/imagerendering/ScrollWorkload.java").read_text()
        body = scroll[scroll.index("private void runPhysicalMappingProbe()"):scroll.index("private void runDrawPathProbe()")]
        self.assertEqual(1, body.count("scroll.repaintNow();"))
        self.assertNotIn("onPaint(", body)
        self.assertNotIn("prepareForDisplay", body)
        self.assertNotIn("scrollContent", body)
        helper = (root / "ui/image/ImageDrawPathProbeAccess.java").read_text()
        capture = helper[helper.index("public static JSONObject mappingMetadata"):helper.index("private static JSONArray integers")]
        self.assertNotIn("readPixels", capture)
        self.assertNotIn("resolveForDrawing", capture)
        self.assertNotIn("setAccessible", capture)
        self.assertIn("backingGeneration != 0", capture)


if __name__ == "__main__":
    unittest.main()
