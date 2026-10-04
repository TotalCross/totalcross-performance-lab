"""Pinned identity and file validation for the official TotalCross 7.2.2 package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


OFFICIAL_PACKAGE_FILES = {
    "sdkJar": {
        "path": "dist/totalcross-sdk-7.2.2.jar",
        "sha256": "389204c26d4377a5964d529ed6aaac0b751dd39c5546c6310918d085bb9baf49",
    },
    "launcher": {
        "path": "etc/launchers/macos/Launcher",
        "sha256": "3439082ff2b6e7bab37d7049b5860b6d4743297536bb7c9ba6806a2b45445884",
    },
    "libtcvm": {
        "path": "dist/vm/macos/libtcvm.dylib",
        "sha256": "421f957d551a75022a92db21638620732614e6d033a6f417ada09c6867cb8f24",
    },
}

OFFICIAL_ARTIFACT_IDENTITY = {
    "repository": "TotalCross/totalcross",
    "workflowRunId": 37076804175,
    "workflowName": "Packages `totalcross`",
    "workflowHeadBranch": "master",
    "workflowHeadSha": "5a44f503bf6fa1bec350f1218f4d501a70fc4812",
    "workflowConclusion": "success",
    "artifactId": 11256633898,
    "artifactName": "TotalCross-7.2.2",
    "githubArtifactDigest": "sha256:4eed292bc20af56ef55cbb7397ffc090c3690b1b1d8f41d75cfbb70ebe6cec41",
    "outerArtifactSha256": "4eed292bc20af56ef55cbb7397ffc090c3690b1b1d8f41d75cfbb70ebe6cec41",
    "artifactSizeBytes": 130346296,
    "packageZipPath": "TotalCross-7.2.2.zip",
    "packageZipSha256": "dddbc50ffae0ce3a1b6f3b315d99cf971190238524c960cd06035066cab337dd",
    "packageRoot": "TotalCross",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("official package paths must be non-empty POSIX relative paths")
    candidate_path = Path(relative)
    if candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise ValueError("official package path is absolute or escapes its root")
    root = root.resolve()
    candidate = (root / candidate_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("official package path escapes its root") from error
    return candidate


def validate_official_identity(provenance: dict) -> None:
    for key, expected in OFFICIAL_ARTIFACT_IDENTITY.items():
        if provenance.get(key) != expected:
            raise ValueError("official artifact provenance does not match the pinned " + key)
    if "files" in provenance:
        if provenance["files"] != OFFICIAL_PACKAGE_FILES:
            raise ValueError("official artifact provenance does not match the pinned SDK/runtime file hashes")
    else:
        source_files = provenance.get("sourceFiles")
        if not isinstance(source_files, dict):
            raise ValueError("official artifact provenance has no pinned SDK/runtime file hashes")
        for name, expected in OFFICIAL_PACKAGE_FILES.items():
            item = source_files.get(name)
            if (not isinstance(item, dict) or item.get("officialPackagePath") != expected["path"]
                    or item.get("sha256") != expected["sha256"]):
                raise ValueError("official artifact provenance does not match the pinned SDK/runtime file hashes")


def validate_github_records(provenance: dict, artifact_metadata: dict, workflow_run: dict) -> None:
    validate_official_identity(provenance)
    workflow_artifact = artifact_metadata.get("workflow_run")
    if not isinstance(workflow_artifact, dict):
        raise ValueError("GitHub artifact metadata has no workflow run identity")
    expected_artifact = {
        "id": OFFICIAL_ARTIFACT_IDENTITY["artifactId"],
        "name": OFFICIAL_ARTIFACT_IDENTITY["artifactName"],
        "size_in_bytes": OFFICIAL_ARTIFACT_IDENTITY["artifactSizeBytes"],
        "digest": OFFICIAL_ARTIFACT_IDENTITY["githubArtifactDigest"],
        "expired": False,
    }
    for key, expected in expected_artifact.items():
        if artifact_metadata.get(key) != expected:
            raise ValueError("GitHub artifact metadata does not match the pinned " + key)
    for key, expected in (("id", OFFICIAL_ARTIFACT_IDENTITY["workflowRunId"]),
                          ("head_branch", OFFICIAL_ARTIFACT_IDENTITY["workflowHeadBranch"]),
                          ("head_sha", OFFICIAL_ARTIFACT_IDENTITY["workflowHeadSha"])):
        if workflow_artifact.get(key) != expected:
            raise ValueError("GitHub artifact workflow reference does not match the pinned " + key)
    expected_workflow = {
        "databaseId": OFFICIAL_ARTIFACT_IDENTITY["workflowRunId"],
        "workflowName": OFFICIAL_ARTIFACT_IDENTITY["workflowName"],
        "headBranch": OFFICIAL_ARTIFACT_IDENTITY["workflowHeadBranch"],
        "headSha": OFFICIAL_ARTIFACT_IDENTITY["workflowHeadSha"],
        "status": "completed",
        "conclusion": "success",
    }
    for key, expected in expected_workflow.items():
        if workflow_run.get(key) != expected:
            raise ValueError("GitHub workflow run record does not match the pinned " + key)


def validate_packaged_provenance(provenance: dict, package_root: Path,
                                 profiles: list[str] | None = None) -> list[Path]:
    """Verify official source copies and deployed files, returning every attested input path."""
    validate_official_identity(provenance)
    package_root = package_root.resolve()
    source_home = Path(provenance.get("sourcePackageHome", "")).resolve()
    if not source_home.is_dir():
        raise ValueError("official extracted package home is missing")

    paths: list[Path] = []

    def verify_file(root: Path, item: dict, label: str) -> Path:
        if not isinstance(item, dict) or not {"path", "sha256"}.issubset(item):
            raise ValueError(label + " provenance is malformed")
        path = safe_relative_path(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(label + " hash validation failed")
        paths.append(path)
        return path

    artifact_path = verify_file(package_root, provenance.get("artifactMetadata"), "GitHub artifact metadata")
    workflow_path = verify_file(package_root, provenance.get("workflowRunMetadata"), "GitHub workflow metadata")
    try:
        artifact_metadata = json.loads(artifact_path.read_text(encoding="utf-8"))
        workflow_run = json.loads(workflow_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("copied GitHub metadata is not valid JSON") from error
    validate_github_records(provenance, artifact_metadata, workflow_run)

    source_files = provenance.get("sourceFiles")
    if not isinstance(source_files, dict) or set(source_files) != set(OFFICIAL_PACKAGE_FILES):
        raise ValueError("official source-file inventory is incomplete")
    for name, expected in OFFICIAL_PACKAGE_FILES.items():
        item = source_files[name]
        if item.get("officialPackagePath") != expected["path"] or item.get("sha256") != expected["sha256"]:
            raise ValueError("official source-file identity changed for " + name)
        packaged_path = verify_file(package_root, item, "packaged official " + name)
        original_path = safe_relative_path(source_home, item["officialPackagePath"])
        if not original_path.is_file() or sha256_file(original_path) != expected["sha256"]:
            raise ValueError("official extracted " + name + " no longer matches the pinned artifact")
        paths.append(original_path)
        if sha256_file(packaged_path) != sha256_file(original_path):
            raise ValueError("packaged official " + name + " differs from the extracted package")

    libraries = provenance.get("sdkLibraries")
    if not isinstance(libraries, list) or not libraries:
        raise ValueError("official SDK library inventory is missing")
    expected_library_paths = sorted(
        path.relative_to(source_home).as_posix()
        for path in (source_home / "dist/libs").iterdir()
        if path.is_file() and not path.is_symlink())
    actual_library_paths = [item.get("officialPackagePath") for item in libraries if isinstance(item, dict)]
    if actual_library_paths != expected_library_paths:
        raise ValueError("official SDK library inventory does not match dist/libs")
    for item in libraries:
        path = safe_relative_path(source_home, item["officialPackagePath"])
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError("official SDK library hash validation failed")
        paths.append(path)

    deployed = provenance.get("deployedArtifactsByProfile")
    if not isinstance(deployed, dict) or not deployed:
        raise ValueError("deployed official-package artifact inventory is missing")
    expected_profiles = profiles if profiles is not None else sorted(deployed)
    if set(deployed) != set(expected_profiles):
        raise ValueError("deployed official-package profiles do not match the package inventory")
    for profile in expected_profiles:
        record = deployed[profile]
        for key in ("profileJar", "executable", "applicationTcz", "libtcvm"):
            verify_file(package_root, record.get(key), profile + " " + key)
        if record["libtcvm"]["sha256"] != OFFICIAL_PACKAGE_FILES["libtcvm"]["sha256"]:
            raise ValueError("deployed libtcvm.dylib differs from the pinned official runtime")
    return paths
