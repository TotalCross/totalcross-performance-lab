# SPDX-License-Identifier: MIT

import json
from pathlib import Path
import tempfile
import unittest

from tools.image_ownership_smoke import SmokeError, parse_result, validate_result, verify_provenance


class ImageOwnershipSmokeContractTest(unittest.TestCase):
    def test_accepts_the_native_application_result_record(self):
        record = {
            "status": "PASS",
            "screenCycles": 64,
            "maxSharedOwners": 2,
            "ownersAfterDetach": 0,
            "cacheReusedWhileOwned": True,
            "cacheEvictedAfterDetach": True,
            "drawPixelRgb": 16711680,
        }
        parsed = parse_result("VM startup\nTC_IMAGE_OWNERSHIP_JSON " + json.dumps(record))
        validate_result(parsed)

    def test_rejects_a_failing_ownership_assertion(self):
        record = {
            "status": "PASS",
            "screenCycles": 64,
            "maxSharedOwners": 2,
            "ownersAfterDetach": 1,
            "cacheReusedWhileOwned": True,
            "cacheEvictedAfterDetach": True,
            "drawPixelRgb": 16711680,
        }
        with self.assertRaisesRegex(SmokeError, "ownersAfterDetach"):
            validate_result(record)

    def test_rejects_artifacts_from_another_source_tree(self):
        manifest = {
            "repository": "TotalCross/totalcross",
            "source": {"commit": "a" * 40, "tree": "b" * 40, "dirty": False},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "provenance.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(SmokeError, "source identity"):
                verify_provenance(path, "c" * 40, "d" * 40, "SDK")

    def test_rejects_dirty_source_artifacts(self):
        manifest = {
            "repository": "TotalCross/totalcross",
            "source": {"commit": "a" * 40, "tree": "b" * 40, "dirty": True},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "provenance.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(SmokeError, "clean source tree"):
                verify_provenance(path, "a" * 40, "b" * 40, "SDK")


if __name__ == "__main__":
    unittest.main()
