import tempfile
import sqlite3
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

from automotive_catia.runtime import Runtime
from automotive_catia.safety import PathPolicy, SafetyError, normalize_result, validate_finite


class SafetyTests(unittest.TestCase):
    def test_finite_recursive(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(SafetyError):
                validate_finite({"nested": [value]})
        validate_finite({"value": [0, -1, 2.5, None]})

    def test_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            root.mkdir()
            policy = PathPolicy([root])
            # Windows TemporaryDirectory may use an 8.3 alias (RUNNER~1).
            # Compare canonical paths on both sides; preserve the escape checks.
            self.assertEqual(policy.resolve("a/../b"), (root / "b").resolve())
            with self.assertRaises(SafetyError):
                policy.resolve("../escape")
            outside = Path(temp) / "outside"
            outside.mkdir()
            try:
                (root / "link").symlink_to(outside, target_is_directory=True)
            except OSError:
                return
            with self.assertRaises(SafetyError):
                policy.resolve("link/file")

    def test_no_effect_not_success(self):
        self.assertFalse(normalize_result("FEATURE_NO_EFFECT: pocket outside body")["ok"])
        self.assertFalse(normalize_result("Could not enumerate edges: COM error")["ok"])
        self.assertFalse(normalize_result("Could not enumerate faces: COM error")["ok"])
        self.assertFalse(normalize_result({"status": "no_material_removed"})["ok"])
        self.assertFalse(normalize_result({"result": {"error": "bad reference"}})["ok"])
        self.assertFalse(normalize_result({"results": ["ok", "Error: bad reference"]})["ok"])


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "journal.sqlite"
        self.runtime = Runtime(self.path, timeout=1)

    def tearDown(self):
        self.runtime.close(wait=True)
        self.temp.cleanup()

    def test_replay_and_conflict(self):
        calls = []
        first = self.runtime.call("pad", {"length": 3}, lambda: calls.append(1) or {"name": "Pad.1"}, request_id="r1", document_token="doc1")
        replay = self.runtime.call("pad", {"length": 3}, lambda: calls.append(2), request_id="r1", document_token="doc1")
        self.assertTrue(first["ok"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(calls, [1])
        conflict = self.runtime.call("pad", {"length": 4}, lambda: None, request_id="r1", document_token="doc1")
        self.assertEqual(conflict["error"]["code"], "REQUEST_ID_CONFLICT")
        conflict = self.runtime.call("pad", {"length": 3}, lambda: None, request_id="r1", document_token="doc2")
        self.assertEqual(conflict["error"]["code"], "REQUEST_ID_CONFLICT")

    def test_request_required_and_invalid_number(self):
        self.assertEqual(self.runtime.call("x", {}, lambda: None)["error"]["code"], "REQUEST_ID_REQUIRED")
        self.assertEqual(self.runtime.call("x", {"x": float("nan")}, lambda: None, request_id="x")["error"]["code"], "NONFINITE_NUMBER")

    def test_same_journal_exclusive_and_released_on_close(self):
        with self.assertRaisesRegex(RuntimeError, "locked"):
            Runtime(self.path)
        self.runtime.close(wait=True)
        self.runtime = Runtime(self.path)
        self.assertTrue(self.runtime.state()["idle"])

    def test_second_process_rejected_and_crash_releases_lock(self):
        script = "from automotive_catia.runtime import Runtime; import sys; r=Runtime(sys.argv[1]); r.close(wait=True)"
        child = subprocess.run([sys.executable, "-c", script, str(self.path)], capture_output=True, text=True, timeout=5)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn("Journal is locked", child.stderr)
        other = Path(self.temp.name) / "crash.sqlite"
        crash = "from automotive_catia.runtime import _JournalLock; from pathlib import Path; import os,sys; lock=_JournalLock(Path(sys.argv[1])); os._exit(0)"
        child = subprocess.run([sys.executable, "-c", crash, str(other)], capture_output=True, text=True, timeout=5)
        self.assertEqual(child.returncode, 0, child.stderr)
        reopened = Runtime(other)
        reopened.close(wait=True)

    def test_one_worker_thread(self):
        ids = [self.runtime.call("read", {}, threading.get_ident, mutating=False)["data"] for _ in range(3)]
        self.assertEqual(len(set(ids)), 1)
        self.assertNotEqual(ids[0], threading.get_ident())

    def test_coordinator_envelopes_preserved(self):
        result = self.runtime.call("bind", {}, lambda: {"ok": True, "next_document_token": "doc", "mock": True}, request_id="bind")
        self.assertEqual(result["next_document_token"], "doc")
        self.assertTrue(result["mock"])
        rejected = self.runtime.call("pad", {}, lambda: {"ok": False, "code": "DOCUMENT_CHANGED", "effects": {"outcome": "not_executed"}}, request_id="rejected")
        self.assertEqual(rejected["code"], "DOCUMENT_CHANGED")
        self.assertFalse(self.runtime.state()["blocked"])

    def test_timeout_not_cancellation(self):
        release = threading.Event()
        finished = threading.Event()
        def slow():
            release.wait(3)
            finished.set()
            return "late"
        result = self.runtime.call("slow", {}, slow, request_id="slow", timeout=0.01)
        try:
            self.assertEqual(result["error"]["code"], "OUTCOME_UNKNOWN")
            self.assertFalse(finished.is_set())
            self.assertEqual(self.runtime.acknowledge_unknown(True)["error"]["code"], "BUSY")
            self.assertEqual(self.runtime.call("next", {}, lambda: None, request_id="next")["error"]["code"], "BUSY")
        finally:
            release.set()
        for _ in range(100):
            if self.runtime.state()["idle"]:
                break
            time.sleep(0.01)
        self.assertTrue(finished.is_set())
        self.assertTrue(self.runtime.state()["blocked"])
        self.assertEqual(self.runtime.call("next", {}, lambda: None, request_id="next")["error"]["code"], "MUTATIONS_BLOCKED")
        self.assertFalse(self.runtime.acknowledge_unknown()["ok"])
        self.assertTrue(self.runtime.acknowledge_unknown(True)["ok"])
        self.assertEqual(self.runtime.call("slow", {}, lambda: None, request_id="slow")["error"]["code"], "OUTCOME_UNKNOWN")

    def test_restart_keeps_unknown_and_completed(self):
        self.runtime.call("read", {}, lambda: 42, request_id="read", mutating=False)
        self.runtime.call("broken", {}, lambda: (_ for _ in ()).throw(ValueError("partial mutation")), request_id="broken")
        self.runtime.close(wait=True)
        self.runtime = Runtime(self.path)
        self.assertTrue(self.runtime.state()["blocked"])
        self.assertTrue(self.runtime.call("read", {}, lambda: 0, request_id="read", mutating=False)["replayed"])
        self.assertEqual(self.runtime.call("broken", {}, lambda: None, request_id="broken")["error"]["code"], "OUTCOME_UNKNOWN")

    def test_journal_write_failure_releases_worker_and_blocks_mutations(self):
        original = self.runtime._db
        class FaultyDB:
            def execute(self, sql, parameters=()):
                if sql.startswith("UPDATE requests SET status="):
                    raise sqlite3.OperationalError("simulated disk full")
                return original.execute(sql, parameters)
            def __getattr__(self, key):
                return getattr(original, key)
        self.runtime._db = FaultyDB()
        result = self.runtime.call("pad", {}, lambda: {"name": "Pad.1"}, request_id="disk-error")
        self.assertEqual(result["error"]["code"], "JOURNAL_UNAVAILABLE")
        self.assertTrue(self.runtime.state()["idle"])
        self.assertTrue(self.runtime.state()["blocked"])
        self.assertEqual(self.runtime.call("pad", {}, lambda: None, request_id="disk-error")["error"]["code"], "OUTCOME_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
