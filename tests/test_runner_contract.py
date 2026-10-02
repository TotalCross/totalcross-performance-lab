import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from runners import run
from tools.packaging import build_windows
from tools.packaging import build_macos


ENVIRONMENT = {
    "hostOs": "macOS test",
    "hostArchitecture": "arm64",
    "javaVersion": "17-test",
    "totalcrossBuild": "source:0123456789abcdef",
    "hostName": "test-host",
    "sessionType": None,
    "benchmarkWorkingTreeDirty": False,
}


def records(family="scroll", workload="scroll", profile="default", round_number=1, phase="measured"):
    run_record = {
        "schemaVersion": 1,
        "recordType": "run",
        "family": family,
        "workload": workload,
        "profile": profile,
        "runtimeSourceCommit": "0123456789abcdef0123456789abcdef01234567",
        "benchmarkSourceCommit": "89abcdef0123456789abcdef0123456789abcdef",
        "dataset": None,
        "environment": ENVIRONMENT,
        "runtimeIdentity": "source:0123456789abcdef;artifact-sha256:abc",
        "logicalDimensions": {"width": 540, "height": 960},
        "drawableDimensions": None,
        "renderer": "Raster",
        "diagnosticsSupported": False,
        "diagnosticsEnabled": False,
        "runtimeConfigurationReport": "Runtime configuration test snapshot",
        "round": round_number,
        "phase": phase,
        "durationsNs": {"wallTime": 500},
        "measurements": {"axes": {}, "frameIntervalsNs": [10, 20, 30]},
    }
    summary = {
        "schemaVersion": 1,
        "recordType": "summary",
        "family": family,
        "workload": workload,
        "profile": profile,
        "dataset": None,
        "runtimeSourceCommit": run_record["runtimeSourceCommit"],
        "benchmarkSourceCommit": run_record["benchmarkSourceCommit"],
        "rounds": [run_record],
        "failures": 0,
        "statistics": {"wallTimeNs": {"median": 500}},
        "environment": ENVIRONMENT,
    }
    return run_record, summary


def protocol_text(run_record, summary):
    return "launcher diagnostic\n" + run.PREFIX + json.dumps(run_record) + "\n" + run.PREFIX + json.dumps(summary) + "\n"


class RunnerContractTests(unittest.TestCase):
    def test_parses_valid_run_and_final_summary(self):
        run_record, summary = records()
        parsed_run, parsed_summary = run.parse_protocol(protocol_text(run_record, summary), "scroll", "scroll", "default", 1, "measured")
        self.assertEqual(run_record, parsed_run)
        self.assertEqual(summary, parsed_summary)

    def test_rejects_malformed_tcb_record(self):
        with self.assertRaisesRegex(run.RunnerError, "malformed TCBENCH_JSON"):
            run.parse_protocol(run.PREFIX + "{broken\n", "scroll", "scroll", "default", 1, "measured")

    def test_rejects_missing_final_summary(self):
        run_record, _ = records()
        with self.assertRaisesRegex(run.RunnerError, "missing its final"):
            run.parse_protocol(run.PREFIX + json.dumps(run_record) + "\n", "scroll", "scroll", "default", 1, "measured")

    def test_rejects_duplicate_or_invalid_records(self):
        run_record, summary = records()
        with self.assertRaisesRegex(run.RunnerError, "exactly one run and one final summary"):
            duplicate = run.PREFIX + json.dumps(run_record) + "\n" + run.PREFIX + json.dumps(run_record) + "\n" + run.PREFIX + json.dumps(summary) + "\n"
            run.parse_protocol(duplicate,
                               "scroll", "scroll", "default", 1, "measured")
        bad = dict(run_record)
        bad.pop("runtimeSourceCommit")
        with self.assertRaisesRegex(run.RunnerError, "missing required field"):
            run.parse_protocol(protocol_text(bad, summary), "scroll", "scroll", "default", 1, "measured")

    def test_rejects_summary_identity_mismatch(self):
        run_record, summary = records()
        summary["workload"] = "other"
        with self.assertRaisesRegex(run.RunnerError, "summary identity"):
            run.parse_protocol(protocol_text(run_record, summary), "scroll", "scroll", "default", 1, "measured")

    def test_child_timeout_is_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(
                family="scroll", dataset_cache=root, width=540, height=960, diagnostics=False,
                command=[sys.executable, "-c", "import time; time.sleep(2)"], timeout_seconds=1,
            )
            with self.assertRaisesRegex(run.RunnerError, "timed out"):
                run.launch_one(args, {"profile": "default", "workload": "scroll"}, 1, "measured", 1,
                               None, "0123456789abcdef", "89abcdef01234567", [], "abc", ENVIRONMENT, root)

    def test_child_exit_code_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(
                family="scroll", dataset_cache=root, width=540, height=960, diagnostics=False,
                command=[sys.executable, "-c", "raise SystemExit(9)"], timeout_seconds=3,
            )
            with self.assertRaisesRegex(run.RunnerError, "status 9"):
                run.launch_one(args, {"profile": "default", "workload": "scroll"}, 1, "measured", 1,
                               None, "0123456789abcdef", "89abcdef01234567", [], "abc", ENVIRONMENT, root)

    def test_scroll_preflight_config_contains_requested_dimensions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(
                family="scroll", dataset_cache=root / "dataset", width=540, height=960,
                diagnostics=False,
                command=[sys.executable, "-c",
                         "import json; c=json.load(open('tcbench-run.json')); "
                         "assert c['width']==540 and c['height']==960"],
                timeout_seconds=3, launch_cwd=None,
            )
            run.launch_preflight(args, {"profile": "default", "workload": "scroll"}, 1, None,
                                 "0123456789abcdef", "89abcdef01234567", [], "abc", ENVIRONMENT, root)

    def test_percentile_math(self):
        self.assertEqual(25, run.percentile([10, 20, 30, 40], 0.5))
        self.assertEqual(38.5, run.percentile([10, 20, 30, 40], 0.95))

    def test_seeded_decode_matrix_order_is_stable(self):
        args = SimpleNamespace(
            family="decode", profiles="default,compact", sources="filesystem,tcz",
            scales="full,half", orders="sequential,seeded-random",
        )
        cells = run.build_cells(args)
        self.assertEqual(16, len(cells))
        self.assertEqual({"profile": "default", "workload": "decode", "source": "filesystem",
                          "scale": "full", "order": "sequential"}, cells[0])
        self.assertEqual("compact", cells[-1]["profile"])
        self.assertEqual("tcz", cells[-1]["source"])
        self.assertEqual("half", cells[-1]["scale"])
        self.assertEqual("seeded-random", cells[-1]["order"])

    def test_scroll_matrix_includes_combined_profiles_and_pacing_order_is_stable(self):
        scroll = run.build_cells(SimpleNamespace(family="scroll", profiles=None))
        self.assertEqual("combined-standard", scroll[-2]["profile"])
        self.assertEqual("combined-compact", scroll[-1]["profile"])
        pacing = run.build_cells(SimpleNamespace(family="pacing", profiles=None, workloads=None))
        self.assertEqual(["flick-40", "flick-60", "synthetic-16ms", "synthetic-16.667ms"],
                         [cell["workload"] for cell in pacing])

    def test_direct_launcher_templates_expand_profile_and_workload(self):
        self.assertEqual("/bench/profiles/default/image-rendering-default-flick-60",
                         run.expand_cell_value("/bench/profiles/{profile}/image-rendering-{profile}-{workload}",
                                               "default", "flick-60"))
        with self.assertRaisesRegex(run.RunnerError, "unknown command placeholder"):
            run.expand_cell_value("/bench/{unknown}", "default", "flick-60")

    def test_scroll_families_pass_requested_logical_window_to_launcher(self):
        self.assertEqual(["launcher", "/scr", "-2,-2,540,960"],
                         run.ensure_scroll_window_arguments(["launcher"], "scroll", 540, 960))
        self.assertEqual(["launcher", "/scr", "-2,-2,800,1200"],
                         run.ensure_scroll_window_arguments(["launcher"], "preparation", 800, 1200))
        self.assertEqual(["launcher"], run.ensure_scroll_window_arguments(["launcher"], "pacing", 540, 960))
        self.assertEqual(["launcher", "/scr", "custom"],
                         run.ensure_scroll_window_arguments(["launcher", "/scr", "custom"], "scroll", 540, 960))

    def test_windows_runner_passes_requested_logical_window_to_launcher(self):
        runner = (Path(__file__).parents[1] / "runners/windows/run-image-rendering-benchmark.ps1").read_text(
            encoding="utf-8")
        self.assertIn("$processInfo.Arguments = \"/scr -2,-2,$Width,$Height\"", runner)

    def test_macos_package_builder_targets_matching_release_arm64_runtime(self):
        self.assertEqual(list(run.PROFILES), list(build_macos.PROFILE_CLASSES))
        source = (Path(__file__).parents[1] / "tools/packaging/build_macos.py").read_text(encoding="utf-8")
        for token in ("CMAKE_HOME_DIRECTORY", "CMAKE_BUILD_TYPE", "CMAKE_OSX_ARCHITECTURES",
                      "lipo", '"-macos"', '"install/macos"', "runtimeArtifactSourceCommit"):
            self.assertIn(token, source)

    def test_package_manifest_schema_and_safe_paths(self):
        schema_dir = Path(run.SCHEMA_DIR)
        profiles = {}
        binaries = []
        for profile in run.PROFILES:
            executable = "profiles/" + profile + "/app.exe"
            digest = "a" * 64
            profiles[profile] = {
                "entryClass": "bench." + profile,
                "executable": executable,
                "workingDirectory": "profiles/" + profile,
                "runtimeFiles": [{"path": "profiles/" + profile + "/tcvm.dll", "sha256": digest}],
            }
            binaries.append({"path": executable, "sha256": digest})
        manifest = {
            "schemaVersion": 1,
            "packageType": "image-rendering-windows",
            "platform": "windows",
            "generatedAt": "2026-10-02T12:00:00Z",
            "totalcrossSourceCommit": "1" * 40,
            "runtimeArtifactSourceCommit": "1" * 40,
            "benchmarkSourceCommit": "2" * 40,
            "benchmarkWorkingTreeDirty": False,
            "dataset": {"id": "image-scroll", "version": "v1", "manifestSha256": "3" * 64},
            "buildConfiguration": {
                "jdk": "17 test", "sdkHome": "sdk", "nativeRuntimeDirectory": "runtime",
                "deployTarget": "win32", "sdkBuildCommand": [], "javaCompileRelease": 8,
            },
            "profileInventory": list(run.PROFILES),
            "profiles": profiles,
            "runtimeBinaries": binaries,
        }
        run.validate_schema(manifest, run.read_json(schema_dir / "benchmark-package-v1.schema.json"), schema_dir)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual((root / "profiles/default/app.exe").resolve(), run.package_path(root, "profiles/default/app.exe"))
            with self.assertRaisesRegex(run.RunnerError, "escapes"):
                run.package_path(root, "../outside.exe")

    def test_windows_runner_contract_is_powershell_only(self):
        runner_path = Path(__file__).parents[1] / "runners/windows/run-image-rendering-benchmark.ps1"
        dataset_path = Path(__file__).parents[1] / "runners/windows/dataset.ps1"
        runner = runner_path.read_text(encoding="utf-8")
        dataset = dataset_path.read_text(encoding="utf-8")
        for token in ("$process.ExitCode", "WaitForExit", "RedirectStandardOutput", "RedirectStandardError",
                      "DebugConsole.txt", "TCBENCH_JSON", "Assert-RunRecord", "failures.json"):
            self.assertIn(token, runner)
        self.assertNotIn("python.exe", runner.lower())
        self.assertNotIn("python3", runner.lower())
        for token in ("Get-FileHash", "Assert-SafeDatasetPath", "OpenRead", "Test-ImageScrollPayload"):
            self.assertIn(token, dataset)

    def test_windows_package_profile_inventory_and_runtime_hashes(self):
        self.assertEqual(list(run.PROFILES), list(build_windows.PROFILE_CLASSES))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile_dir = root / "package/profiles/default"
            profile_dir.mkdir(parents=True)
            executable = profile_dir / "image.exe"
            runtime = profile_dir / "tcvm.dll"
            executable.write_bytes(b"launcher")
            runtime.write_bytes(b"runtime")
            result = build_windows.package_files(profile_dir, executable)
            self.assertEqual(["profiles/default/tcvm.dll"], [item["path"] for item in result])
            self.assertEqual(hashlib.sha256(b"runtime").hexdigest(), result[0]["sha256"])

    def test_profile_jar_contains_only_selected_entry_and_has_reproducible_metadata(self):
        import zipfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            classes = root / "classes/totalcross/bench/imagerendering/profiles"
            classes.mkdir(parents=True)
            (classes / "Default.class").write_bytes(b"default")
            (classes / "Compact.class").write_bytes(b"compact")
            shared = root / "classes/totalcross/bench/imagerendering/BenchSupport.class"
            shared.parent.mkdir(parents=True, exist_ok=True)
            shared.write_bytes(b"shared")
            dataset_files = root / "dataset"
            dataset_files.mkdir()
            (dataset_files / "photo.jpg").write_bytes(b"image payload")
            jar_path = root / "Default.jar"
            build_windows.write_profile_jar(root / "classes", "Default", jar_path, dataset_files)
            with zipfile.ZipFile(jar_path) as archive:
                self.assertEqual(
                    ["image-scroll/photo.jpg",
                     "totalcross/bench/imagerendering/BenchSupport.class",
                     "totalcross/bench/imagerendering/profiles/Default.class"],
                    sorted(archive.namelist()),
                )
                self.assertEqual((1980, 1, 1, 0, 0, 0), archive.getinfo(archive.namelist()[0]).date_time)
                self.assertEqual(b"image payload", archive.read("image-scroll/photo.jpg"))


if __name__ == "__main__":
    unittest.main()
