import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
TIMING_SOURCE = ROOT / "benchmarks/image-rendering/src/totalcross/bench/imagerendering/ScrollTiming.java"


class ScrollTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        javac = shutil.which("javac")
        java = shutil.which("java")
        if not javac or not java:
            raise unittest.SkipTest("a JDK is required to exercise the Java scroll timing helper")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name)
        harness = cls.output / "ScrollTimingTestHarness.java"
        harness.write_text(
            "package totalcross.bench.imagerendering;\n"
            "public final class ScrollTimingTestHarness {\n"
            "  public static void main(String[] args) {\n"
            "    System.out.println(ScrollTiming.historicalTarget(100, 1100, 0));\n"
            "    System.out.println(ScrollTiming.historicalTarget(100, 1100, 1500000000L));\n"
            "    System.out.println(ScrollTiming.historicalTarget(100, 1100, 2999999999L));\n"
            "    System.out.println(ScrollTiming.historicalTarget(100, 1100, 3000000000L));\n"
            "    System.out.println(ScrollTiming.historicalTarget(100, 1100, 4000000000L));\n"
            "    System.out.println(ScrollTiming.boundedSleepMillis(1L));\n"
            "    System.out.println(ScrollTiming.boundedSleepMillis(9000000L));\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        subprocess.run(
            [javac, "--release", "8", "-d", str(cls.output), str(TIMING_SOURCE), str(harness)],
            check=True, capture_output=True, text=True,
        )
        cls.java = java

    @classmethod
    def tearDownClass(cls):
        temporary = getattr(cls, "temporary", None)
        if temporary is not None:
            temporary.cleanup()

    def test_time_interpolation_and_endpoint_clamping(self):
        result = subprocess.run(
            [self.java, "-cp", str(self.output), "totalcross.bench.imagerendering.ScrollTimingTestHarness"],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(["100", "600", "1099", "1100", "1100", "1", "4"],
                         result.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
