"""Non-device contract checks for filtering physical Android storage logs.

No AWS credentials, emulator or APK is needed. These checks catch stale
logcat events from the previous grant phase being reported as a PASS during
a newly launched, permission-denied process.
"""
import importlib.util
import json
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tests" / "test_sqlite_storage.py"
SPEC = importlib.util.spec_from_file_location("physical_storage_probe", MODULE_PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def event(pid, stage, status="PASS", detail="OK", tag="TotalCross"):
    payload = json.dumps({"stage": stage, "status": status, "detail": detail})
    return (
        f"11-16 20:40:34.381 {pid:5d} {pid + 1:5d} I {tag}: "
        f"TC_SQLITE_JSON {payload}\n"
    )


class LogcatPhaseIsolationTest(unittest.TestCase):
    def test_previous_phase_external_pass_cannot_satisfy_new_phase(self):
        old_pid, new_pid = 28693, 28804
        data = (
            event(old_pid, "startup")
            + event(old_pid, "external-dir")
            + event(old_pid, "external-result")
            + event(new_pid, "startup")
            + "11-16 20:40:37.344  1327  3498 I ActivityTaskManager: "
              "START android.content.pm.action.REQUEST_PERMISSIONS\n"
        )
        results = probe.parse_events(data, new_pid)
        self.assertEqual(["startup"], [x["stage"] for x in results])
        self.assertFalse(probe.EXTERNAL.issubset(
            {x["stage"] for x in results if x["status"] == "PASS"}
        ))

    def test_duplicate_tags_are_deduplicated_within_current_process(self):
        current_pid = 28804
        data = (
            event(current_pid, "external-dir", tag="totalcross.apprvks")
            + event(current_pid, "external-dir", tag="TotalCross")
        )
        self.assertEqual(1, len(probe.parse_events(data, current_pid)))

    def test_unscoped_or_unparseable_log_lines_cannot_count_as_pass(self):
        data = (
            'I TotalCross: TC_SQLITE_JSON {"stage":"external-dir","status":"PASS"}\n'
            + event(28693, "external-dir")
        )
        self.assertEqual([], probe.parse_events(data, 28804))


if __name__ == "__main__":
    unittest.main()
