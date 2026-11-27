import tempfile
import sys
import unittest
from pathlib import Path

from tools.functional_validation_730 import (
    APP_NAMES,
    FROZEN_MASTER,
    make_long_path,
    validate_config,
)


class HarnessContractTest(unittest.TestCase):
    def test_campaign_config_is_pinned_and_linux_only(self):
        config = validate_config()
        self.assertEqual(FROZEN_MASTER, config["frozenMasterSha"])
        self.assertEqual("linux-x86_64", config["platform"])
        self.assertEqual({"I01-B", "I02"}, set(config["cases"]))
        self.assertNotIn("android", config["prohibitedRuntimePlatforms"])
        self.assertEqual(
            ["official-7.2.2", "official-7.3.0", "frozen-master"],
            config["cases"]["I01-B"]["revisionsToRun"],
        )

    def test_workflow_is_scoped_to_frozen_linux_campaign(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/functional-validation-730.yml")
        source = workflow.read_text(encoding="utf-8")
        self.assertIn("investigation/totalcross-7.3.0-functional-validation", source)
        self.assertNotIn("workflow_dispatch", source)
        self.assertIn("6b915883dd202f6db891990f6c3af26fb645ecc7", source)
        self.assertIn("totalcross/linux-amd64:v1.0.7", source)
        self.assertIn("runs-on: ubuntu-24.04", source)
        self.assertNotIn("windows-amd64", source)
        self.assertNotIn("android-emulator", source)
        self.assertNotIn("xcodebuild", source)

    @unittest.skipUnless(sys.platform.startswith("linux"), "long paths are exercised on the Linux Actions runner")
    def test_long_path_exceeds_realpath_buffer_without_long_components(self):
        with tempfile.TemporaryDirectory(prefix="tc730-contract-") as temp:
            install = make_long_path(Path(temp) / "long")
            executable = install / APP_NAMES["startup"]
            self.assertGreaterEqual(len(str(executable)), 1200)
            self.assertTrue(all(len(part) <= 255 for part in executable.parts))

    def test_config_rejects_wrong_platform(self):
        with tempfile.TemporaryDirectory(prefix="tc730-contract-") as temp:
            path = Path(temp) / "invalid.json"
            path.write_text('{"schemaVersion":1,"platform":"windows-amd64"}')
            with self.assertRaises((KeyError, ValueError)):
                validate_config(path)


if __name__ == "__main__":
    unittest.main()
