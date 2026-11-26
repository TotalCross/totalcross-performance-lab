# SPDX-License-Identifier: MIT

import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from tools.image_ownership_smoke import (
    SmokeError,
    deploy_sdk_jar,
    host_output,
    parse_result,
    pe_machine,
    require_windows_machine,
    require_windows_x64,
    validate_result,
    verify_provenance,
    zip_member,
)


def passing_record():
    return {
        "status": "PASS",
        "screenCycles": 2,
        "controlsPerCycle": 1510,
        "distinctImagesPerCycle": 1510,
        "ownersAfterDetach": 0,
        "directParentsPreserved": True,
        "mutationsWhileDetached": True,
        "ownersRestoredAfterReattach": True,
        "activeReparentOwnerCount": 1,
        "activeReparentCachePreserved": True,
        "maxSharedOwners": 3,
        "rasterRetainedUntilFinalOwner": True,
        "pipelineReplacementOwners": 3,
        "cacheReusedWhileOwned": True,
        "cacheEvictedAfterDetach": True,
        "drawPixelRgb": 16711680,
        "png": "image-ownership-render.png",
    }


class ImageOwnershipSmokeContractTest(unittest.TestCase):
    def test_accepts_the_native_application_result_record(self):
        record = passing_record()
        parsed = parse_result("VM startup\nTC_IMAGE_OWNERSHIP_JSON " + json.dumps(record))
        validate_result(parsed)

    def test_rejects_a_failing_ownership_assertion(self):
        record = passing_record()
        record["ownersAfterDetach"] = 1
        with self.assertRaisesRegex(SmokeError, "ownersAfterDetach"):
            validate_result(record)

    def test_rejects_an_incomplete_large_screen_cycle(self):
        record = passing_record()
        record["controlsPerCycle"] = 64
        with self.assertRaisesRegex(SmokeError, "controlsPerCycle"):
            validate_result(record)

    def test_accepts_baseline_differences_after_all_native_stages(self):
        record = {
            "status": "BASELINE_OBSERVED",
            "diagnosticMode": "baseline",
            "screenCycles": 2,
            "controlsPerCycle": 1510,
            "distinctImagesPerCycle": 1510,
            "ownershipMismatches": 12,
            "highestCompletedStage": 7,
            "drawPixelRgb": 16711680,
            "png": "image-ownership-render.png",
        }
        validate_result(record, diagnostic_mode="baseline")

    def test_rejects_baseline_that_does_not_reach_the_full_workload(self):
        record = {
            "status": "BASELINE_OBSERVED",
            "diagnosticMode": "baseline",
            "screenCycles": 2,
            "controlsPerCycle": 1510,
            "distinctImagesPerCycle": 1510,
            "ownershipMismatches": 4,
            "highestCompletedStage": 6,
            "drawPixelRgb": 16711680,
            "png": "image-ownership-render.png",
        }
        with self.assertRaisesRegex(SmokeError, "highestCompletedStage"):
            validate_result(record, diagnostic_mode="baseline")

    def test_fixed_diagnostics_still_require_all_ownership_assertions(self):
        record = passing_record()
        record.update({"diagnosticMode": "fixed", "ownershipMismatches": 0,
                       "highestCompletedStage": 7})
        validate_result(record, diagnostic_mode="fixed")

    def test_reads_windows_debug_console_when_stdout_has_no_result(self):
        record = passing_record()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "DebugConsole.txt").write_text(
                "TC_IMAGE_OWNERSHIP_JSON " + json.dumps(record), encoding="utf-8")
            output = host_output(directory / "ImageOwnershipSmoke.exe", "", "windows")
            validate_result(parse_result(output))

    def test_reads_the_durable_windows_result_marker(self):
        record = passing_record()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "tcdiag-result.txt").write_text(
                json.dumps(record), encoding="utf-8")
            output = host_output(directory / "ImageOwnershipSmoke.exe", "", "windows")
            validate_result(parse_result(output))

    def test_accepts_only_amd64_windows_runtime_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "Launcher.exe"
            image = bytearray(0x88)
            image[:2] = b"MZ"
            struct.pack_into("<I", image, 0x3C, 0x80)
            image[0x80:0x84] = b"PE\0\0"
            struct.pack_into("<H", image, 0x84, 0x8664)
            executable.write_bytes(image)
            self.assertEqual(pe_machine(executable), 0x8664)
            require_windows_x64(executable)
            struct.pack_into("<H", image, 0x84, 0x014C)
            executable.write_bytes(image)
            with self.assertRaisesRegex(SmokeError, "not AMD64"):
                require_windows_x64(executable)

    def test_accepts_only_the_requested_windows_runtime_architecture(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "Launcher.exe"
            image = bytearray(0x88)
            image[:2] = b"MZ"
            struct.pack_into("<I", image, 0x3C, 0x80)
            image[0x80:0x84] = b"PE\0\0"
            struct.pack_into("<H", image, 0x84, 0x014C)
            executable.write_bytes(image)
            require_windows_machine(executable, "I386")
            with self.assertRaisesRegex(SmokeError, "not AMD64"):
                require_windows_machine(executable, "AMD64")

    def test_reads_the_arm64_runtime_from_the_android_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "TotalCross.aab"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("base/lib/arm64-v8a/libtcvm.so", b"arm64 runtime")
            member, data = zip_member(bundle, "lib/arm64-v8a/libtcvm.so")
            self.assertEqual(member, "base/lib/arm64-v8a/libtcvm.so")
            self.assertEqual(data, b"arm64 runtime")

    def test_uses_the_canonical_sdk_jar_for_deployment(self):
        with tempfile.TemporaryDirectory() as temporary:
            dist = Path(temporary) / "dist"
            dist.mkdir()
            with zipfile.ZipFile(dist / "totalcross-sdk-7.2.2-javadoc.jar", "w"):
                pass
            with zipfile.ZipFile(dist / "totalcross-sdk-7.2.2-sources.jar", "w"):
                pass
            with zipfile.ZipFile(dist / "totalcross-sdk.jar", "w") as archive:
                archive.writestr("tc/Deploy.class", b"deployer")
            self.assertEqual(deploy_sdk_jar(Path(temporary)), dist / "totalcross-sdk.jar")

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

    def test_allows_explicit_local_dirty_source_with_matching_identity(self):
        manifest = {
            "repository": "totalcross/totalcross",
            "source": {"commit": "a" * 40, "tree": "b" * 40, "dirty": True},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "provenance.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            accepted = verify_provenance(path, "a" * 40, "b" * 40, "SDK",
                                         allow_dirty_source=True)
            self.assertTrue(accepted["source"]["dirty"])


if __name__ == "__main__":
    unittest.main()
