import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.packaging import build_macos, official_runtime


def write_hashed(root: Path, relative: str, payload: bytes) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"path": relative, "sha256": hashlib.sha256(payload).hexdigest()}


class OfficialRuntimeProvenanceTests(unittest.TestCase):
    def test_profile_selection_is_unique_and_validated(self):
        self.assertEqual(("default",), build_macos.parse_profiles("default"))
        self.assertEqual(tuple(build_macos.PROFILE_CLASSES), build_macos.parse_profiles(None))
        with self.assertRaisesRegex(build_macos.PackageError, "invalid profile list"):
            build_macos.parse_profiles("default,default")
        with self.assertRaisesRegex(build_macos.PackageError, "invalid profile list"):
            build_macos.parse_profiles("default,not-a-profile")

    def test_official_identity_rejects_changes_to_artifact_or_runtime_hashes(self):
        record = dict(official_runtime.OFFICIAL_ARTIFACT_IDENTITY)
        record["files"] = official_runtime.OFFICIAL_PACKAGE_FILES
        official_runtime.validate_official_identity(record)
        record["artifactId"] += 1
        with self.assertRaisesRegex(ValueError, "artifactId"):
            official_runtime.validate_official_identity(record)

    def test_runner_provenance_validation_checks_copied_and_deployed_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_home = root / "source/TotalCross"
            package_root = root / "benchmark-package"
            fake_files = {}
            source_files = {}
            for name, item in official_runtime.OFFICIAL_PACKAGE_FILES.items():
                payload = ("official-" + name).encode("ascii")
                digest = hashlib.sha256(payload).hexdigest()
                fake_files[name] = {"path": item["path"], "sha256": digest}
                source = source_home / item["path"]
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(payload)
                packaged_path = "provenance/source/TotalCross/" + item["path"]
                write_hashed(package_root, packaged_path, payload)
                source_files[name] = {
                    "path": packaged_path,
                    "officialPackagePath": item["path"],
                    "sha256": digest,
                }

            library_relative = "dist/libs/dependency.jar"
            library = source_home / library_relative
            library.parent.mkdir(parents=True, exist_ok=True)
            library.write_bytes(b"official sdk dependency")
            library_sha = hashlib.sha256(library.read_bytes()).hexdigest()

            artifact = {
                "id": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["artifactId"],
                "name": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["artifactName"],
                "size_in_bytes": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["artifactSizeBytes"],
                "digest": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["githubArtifactDigest"],
                "expired": False,
                "workflow_run": {
                    "id": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["workflowRunId"],
                    "head_branch": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["workflowHeadBranch"],
                    "head_sha": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["workflowHeadSha"],
                },
            }
            workflow = {
                "databaseId": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["workflowRunId"],
                "workflowName": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["workflowName"],
                "headBranch": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["workflowHeadBranch"],
                "headSha": official_runtime.OFFICIAL_ARTIFACT_IDENTITY["workflowHeadSha"],
                "status": "completed",
                "conclusion": "success",
            }
            artifact_metadata = write_hashed(
                package_root, "provenance/github-artifact-metadata.json",
                json.dumps(artifact).encode("utf-8"))
            workflow_metadata = write_hashed(
                package_root, "provenance/github-workflow-run.json",
                json.dumps(workflow).encode("utf-8"))

            profile_jar = write_hashed(package_root, "provenance/input/default/Default.jar", b"profile jar")
            executable = write_hashed(package_root, "profiles/default/image-rendering-default", b"launcher")
            app_tcz = write_hashed(package_root, "profiles/default/image-rendering-default.tcz", b"application")
            lib_payload = source_files["libtcvm"]["sha256"]
            source_lib = source_home / fake_files["libtcvm"]["path"]
            libtcvm = write_hashed(package_root, "profiles/default/libtcvm.dylib", source_lib.read_bytes())
            self.assertEqual(lib_payload, libtcvm["sha256"])

            provenance = dict(official_runtime.OFFICIAL_ARTIFACT_IDENTITY)
            provenance.update({
                "schemaVersion": 1,
                "mode": "github-actions-package",
                "sourcePackageHome": str(source_home),
                "artifactMetadata": artifact_metadata,
                "workflowRunMetadata": workflow_metadata,
                "sourceFiles": source_files,
                "sdkLibraries": [{"officialPackagePath": library_relative, "sha256": library_sha}],
                "deployedArtifactsByProfile": {"default": {
                    "profileJar": profile_jar,
                    "executable": executable,
                    "applicationTcz": app_tcz,
                    "libtcvm": libtcvm,
                }},
            })

            with patch.object(official_runtime, "OFFICIAL_PACKAGE_FILES", fake_files):
                paths = official_runtime.validate_packaged_provenance(provenance, package_root, ["default"])
                self.assertIn((source_home / library_relative).resolve(), paths)
                app_path = package_root / app_tcz["path"]
                app_path.write_bytes(b"changed application")
                with self.assertRaisesRegex(ValueError, "applicationTcz hash"):
                    official_runtime.validate_packaged_provenance(provenance, package_root, ["default"])


if __name__ == "__main__":
    unittest.main()
