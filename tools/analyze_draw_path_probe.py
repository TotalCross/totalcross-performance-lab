# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

"""Validate a saved draw-path probe without launching another application."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runners import run
from tools.packaging.official_runtime import validate_packaged_provenance

LEGACY_PROBE_COMMIT = "b9506e892b407813e73756c6b44dde8ffb803bc4"


def recover_legacy_record(record: dict) -> dict:
    """Repair only the known benchmark encoding defect, retaining emitted fields."""
    if record.get("benchmarkSourceCommit") != LEGACY_PROBE_COMMIT:
        raise run.RunnerError("legacy recovery requires the original draw-path probe commit")
    recovered = copy.deepcopy(record)
    measurements = recovered["measurements"]
    for sample in [measurements["aggregate"], *measurements["perControl"]]:
        status = sample["rawStatus"]
        # Integer4D.toHexString emits exactly four uppercase hex digits.
        if sample["statusHex"] != "0x%04X" % (status & 0xffff):
            raise run.RunnerError("status text does not match the known Integer4D encoding defect")
        sample["emittedStatusHex"] = sample["statusHex"]
        sample["statusHex"] = hex(status)
        expected = run.draw_path_classification(sample["counters"], sample["statusFlags"])
        # The original helper used the Image getter, which stayed zero for copyRect.
        original = expected.copy()
        if sample["counters"]["identityFallbacks"] == 0 and "identity fallback" in original:
            original.remove("identity fallback")
        if sample["classification"] != original:
            raise run.RunnerError("classification does not match the known original helper")
        sample["emittedClassification"] = sample["classification"]
        sample["classification"] = expected
    return recovered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--dataset-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recover-legacy-status", action="store_true")
    args = parser.parse_args()
    stdout = args.stdout.read_text()
    record, _ = run.parse_protocol(stdout, "scroll", "scroll", "default", 1, "measured")
    manifest = run.read_json(args.package_manifest)
    provenance = manifest["runtimeProvenance"]
    validate_packaged_provenance(provenance, args.package_manifest.parent, ["default"])
    if (record["runtimeSourceCommit"] != provenance["workflowHeadSha"]
            or record["benchmarkSourceCommit"] != manifest["benchmarkSourceCommit"]):
        raise run.RunnerError("saved run provenance differs from the verified package")
    preflight = run.parse_preflight(stdout, "scroll", "scroll", "default")
    run.validate_scroll_preflight(preflight, manifest["dataset"], 540, 960,
                                 require_default=True, scroll_driver="draw-path-probe")
    if (preflight["runtimeSourceCommit"] != record["runtimeSourceCommit"]
            or preflight["benchmarkSourceCommit"] != record["benchmarkSourceCommit"]
            or preflight["runtimeIdentity"] != record["runtimeIdentity"]
            or record["dataset"] != manifest["dataset"]):
        raise run.RunnerError("saved preflight/run identity differs")
    if args.recover_legacy_status:
        record = recover_legacy_record(record)
    entries = run.read_json(args.dataset_cache / "objects/manifest.json")["files"]
    run.validate_draw_path_result(record, 540, 960, entries)
    result = {"record": record, "sourceLog": str(args.stdout.resolve()),
              "sourceLogSha256": hashlib.sha256(args.stdout.read_bytes()).hexdigest(),
              "legacyStatusRecovery": args.recover_legacy_status,
              "packageManifest": str(args.package_manifest.resolve()), "status": "validated"}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "validated", "output": str(args.output),
                      "legacyStatusRecovery": args.recover_legacy_status}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
