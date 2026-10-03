import unittest
from pathlib import Path

from runners import run
from tools.packaging import build_windows


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering"
PROFILE_RULES = {
    "Default": (),
    "TargetColor": ("targetColorConversion = RuntimeFeatureState.ENABLED",),
    "PhysicalVariant": ("physicalVariantCache = RuntimeFeatureState.ENABLED",),
    "RasterVariants": ("targetColorConversion = RuntimeFeatureState.ENABLED",
                       "physicalVariantCache = RuntimeFeatureState.ENABLED"),
    "Compact": ("storage = ImageStorageProfile.COMPACT",),
    "ScrollReuse": ("scrollRasterReuse = RuntimeFeatureState.ENABLED",),
    "PreparedLegacy": ("prefetchWorker = ImagePrefetchWorkerMode.LEGACY_PER_ENTRY_THREAD",),
    "PreparedSemaphore": ("prefetchWorker = ImagePrefetchWorkerMode.SEMAPHORE_PROCESS_WORKER",),
    "CombinedStandard": ("storage = ImageStorageProfile.STANDARD",
                         "targetColorConversion = RuntimeFeatureState.ENABLED",
                         "physicalVariantCache = RuntimeFeatureState.ENABLED",
                         "scrollRasterReuse = RuntimeFeatureState.ENABLED",
                         "prefetchWorker = ImagePrefetchWorkerMode.SEMAPHORE_PROCESS_WORKER"),
    "CombinedCompact": ("storage = ImageStorageProfile.COMPACT",
                        "targetColorConversion = RuntimeFeatureState.ENABLED",
                        "physicalVariantCache = RuntimeFeatureState.ENABLED",
                        "scrollRasterReuse = RuntimeFeatureState.ENABLED",
                        "prefetchWorker = ImagePrefetchWorkerMode.SEMAPHORE_PROCESS_WORKER"),
}


class ImageRenderingSourceContractTests(unittest.TestCase):
    def test_named_entries_are_direct_main_windows_with_typed_rules(self):
        self.assertEqual(set(run.PROFILES), set(build_windows.PROFILE_CLASSES))
        for class_name, rules in PROFILE_RULES.items():
            with self.subTest(profile=class_name):
                path = SOURCE / "profiles" / (class_name + ".java")
                text = path.read_text(encoding="utf-8")
                profile = class_name[0].lower() + class_name[1:]
                if class_name == "TargetColor":
                    profile = "target-color"
                elif class_name == "PhysicalVariant":
                    profile = "physical-variant"
                elif class_name == "RasterVariants":
                    profile = "raster-variants"
                elif class_name == "ScrollReuse":
                    profile = "scroll-reuse"
                elif class_name == "PreparedLegacy":
                    profile = "prepared-legacy"
                elif class_name == "PreparedSemaphore":
                    profile = "prepared-semaphore"
                elif class_name == "CombinedStandard":
                    profile = "combined-standard"
                elif class_name == "CombinedCompact":
                    profile = "combined-compact"
                self.assertIn("public final class " + class_name + " extends MainWindow", text)
                self.assertIn("setUIStyle(Settings.ANDROID_UI)", text)
                self.assertIn('ImageRenderingBenchmarkApp.start(this, "' + profile + '")', text)
                if rules:
                    self.assertIn("@RuntimeConfiguration", text)
                    self.assertIn("@ImageRuntimeRule(when = @RuntimeWhen()", text)
                    for rule in rules:
                        self.assertIn(rule, text)
                else:
                    self.assertNotIn("@ImageRuntimeRule", text)

    def test_workload_dispatch_and_measurement_shapes_stay_supported(self):
        app = (SOURCE / "ImageRenderingBenchmarkApp.java").read_text(encoding="utf-8")
        decode = (SOURCE / "DecodeWorkload.java").read_text(encoding="utf-8")
        support = (SOURCE / "BenchSupport.java").read_text(encoding="utf-8")
        scroll = (SOURCE / "ScrollWorkload.java").read_text(encoding="utf-8")
        pacing = (SOURCE / "PacingWorkload.java").read_text(encoding="utf-8")
        for family in ("decode", "scroll", "preparation", "pacing"):
            self.assertIn('"' + family + '".equals(family)', app)
        self.assertIn("import totalcross.ui.ScrollContainer;", scroll)
        self.assertIn("scroll.prepareForDisplay(", scroll)
        self.assertIn('"cold-forward"', scroll)
        self.assertIn('"warm-reverse"', scroll)
        self.assertIn('"warm-forward"', scroll)
        self.assertIn("SCROLL_STEP = 120", scroll)
        self.assertIn("new Container[entries.length / COLUMNS]", scroll)
        self.assertIn("Color.darker(Color.GREEN)", scroll)
        self.assertIn("getSmoothScaledInstance(tileWidth, tileWidth)", scroll)
        self.assertIn("scrollMaximum <= scrollMinimum", scroll)
        self.assertIn("holdForVisualValidation", scroll)
        self.assertIn("new Flick(target)", pacing)
        self.assertNotIn("setScrollDistance", pacing)
        self.assertIn("production Flick completed without callback interval samples", pacing)
        self.assertIn("randomState ^= randomState << 13", decode)
        self.assertIn("new Image(file)", support)
        self.assertIn("BenchSupport.loadFilesystemImage", scroll)
        self.assertIn('"synthetic-16ms"', pacing)
        self.assertIn('"synthetic-16.667ms"', pacing)
        self.assertIn("RuntimeDiagnosticSnapshot.Domain.SCHEDULING", pacing)
        self.assertNotIn("PacingDriver", pacing)
        self.assertNotIn("updateListenerTriggered", pacing)

    def test_historical_scroll_probe_keeps_fixed_step_default_and_records_explicit_work(self):
        app = (SOURCE / "ImageRenderingBenchmarkApp.java").read_text(encoding="utf-8")
        scroll = (SOURCE / "ScrollWorkload.java").read_text(encoding="utf-8")
        timing = (SOURCE / "ScrollTiming.java").read_text(encoding="utf-8")
        runner = (ROOT / "runners/run.py").read_text(encoding="utf-8")
        self.assertIn('"historical-driver"', scroll)
        self.assertIn('"fixed-step"', scroll)
        self.assertIn("DRIVER_HISTORICAL.equals(scrollDriver)", scroll)
        self.assertIn("runHistoricalPass();", scroll)
        self.assertIn('"passCount", 1', scroll)
        self.assertIn('"passDirection", "top-to-bottom"', scroll)
        self.assertIn("ScrollTiming.historicalTarget(minimum, endpoint, elapsedNs)", scroll)
        self.assertIn("scroll.scrollContent(0, requestedDelta, true)", scroll)
        self.assertIn("scroll.repaintNow();", scroll)
        for field in ("frameIndex", "elapsedNs", "targetScroll", "actualScroll", "requestedDelta",
                      "frameIntervalNs", "scrollWorkNs", "paintWorkNs", "workTimeNs",
                      "frameCount", "totalPassWallTimeNs", "frameIntervalStatistics",
                      "scrollWorkStatistics", "paintWorkStatistics", "workTimeStatistics",
                      "finalScrollPosition"):
            self.assertIn('"' + field + '"', scroll)
        self.assertIn("HISTORICAL_DURATION_NS = 3000000000L", timing)
        self.assertIn("HISTORICAL_CADENCE_NS = 16000000L", timing)
        self.assertIn('"--scroll-driver"', runner)
        self.assertIn('"scrollDriver", config.getString("scrollDriver")', app)

    def test_active_benchmark_sources_do_not_reintroduce_raw_masks(self):
        active_paths = [ROOT / "runners/run.py", ROOT / "tools/packaging/build_windows.py"]
        active_paths.extend(SOURCE.rglob("*.java"))
        for path in active_paths:
            text = path.read_text(encoding="utf-8")
            for forbidden in ("--image-optimization", "32799", "mask 6", "mask 38"):
                with self.subTest(path=path.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
