# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_runner_contract import paint_preparation_record
from tools.packaging import historical_paint_probe as probe


class HistoricalPaintProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entries = [{"path": "image%03d.jpg" % i, "format": "jpeg"} for i in range(663)]
        manifest_path = self.root / "manifest.json"
        probe.write_json(manifest_path, {"files": self.entries})
        probe.write_json(self.root / "tcbench-run.json", {"datasetManifestPath": str(manifest_path)})
        self.manifest = {"workingDirectory": str(self.root)}
        self.record = paint_preparation_record()
        self.record.update(runtimeSourceCommit=probe.RUNTIME_SHA, configuredMask=32799, effectiveMask=32799)
        self.record["measurements"]["historicalVisibleIdentity"] = {
            "sameImageInstances": True, "sameControlInstances": True, "sameRowInstances": True,
            "scrollPosition": 0,
            "controls": [{"manifestIndex": i, "rowIndex": i // 3,
                          "path": entry["path"], "format": entry["format"]}
                         for i, entry in enumerate(self.entries[:18])],
        }

    def test_valid_like_for_like_result(self):
        probe.validate_historical_result(self.record, self.manifest)

    def test_configuration_and_instance_changes_reject_comparison(self):
        for key, value in (("runtimeSourceCommit", "a" * 40), ("configuredMask", 31), ("effectiveMask", 31)):
            record = copy.deepcopy(self.record)
            record[key] = value
            with self.subTest(key=key), self.assertRaises(probe.PackageError):
                probe.validate_historical_result(record, self.manifest)
        for key in ("sameImageInstances", "sameControlInstances", "sameRowInstances"):
            record = copy.deepcopy(self.record)
            record["measurements"]["historicalVisibleIdentity"][key] = False
            with self.subTest(key=key), self.assertRaises(probe.PackageError):
                probe.validate_historical_result(record, self.manifest)

    def test_manifest_order_mismatch_rejects_comparison(self):
        record = copy.deepcopy(self.record)
        controls = record["measurements"]["historicalVisibleIdentity"]["controls"]
        controls[0], controls[1] = controls[1], controls[0]
        with self.assertRaisesRegex(probe.PackageError, "manifest ordering"):
            probe.validate_historical_result(record, self.manifest)

    def test_different_static_geometry_rejects_comparison(self):
        record = paint_preparation_record(position_mismatch=True)
        record.update(runtimeSourceCommit=probe.RUNTIME_SHA, configuredMask=32799, effectiveMask=32799)
        record["measurements"]["historicalVisibleIdentity"] = self.record["measurements"]["historicalVisibleIdentity"]
        with self.assertRaisesRegex(probe.PackageError, "viewport equivalence"):
            probe.validate_historical_result(record, self.manifest)

    def test_launch_guard_prevents_another_process_even_after_failure(self):
        probe.write_json(self.root / "launch-attempt.json", {"processCount": 1})
        with patch.object(probe.subprocess, "run") as spawn:
            with self.assertRaisesRegex(probe.PackageError, "already attempted"):
                probe.run(SimpleNamespace(package=self.root))
            spawn.assert_not_called()

    def test_staged_workload_keeps_every_shared_method_unchanged(self):
        source = (probe.SOURCE / "ScrollWorkload.java").read_text()
        staged = probe.historical_scroll_source(source)
        restored = staged.replace(probe.IDENTITY_METHOD + "\n", "")
        for name in ("RuntimeDiagnostics", "RuntimeDiagnosticSnapshot"):
            restored = restored.replace("import totalcross.bench.imagerendering.historical." + name + ";",
                                        "import totalcross.sys." + name + ";")
        self.assertEqual(source, restored)
        # Adapters cannot shadow SDK/runtime classes in a deployed package.
        for path in probe.HISTORICAL.rglob("*.java"):
            self.assertNotIn("package totalcross.sys", path.read_text())


if __name__ == "__main__":
    unittest.main()
