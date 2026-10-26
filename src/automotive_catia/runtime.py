"""Single-STA dispatcher with durable replay protection, not exactly-once COM.

An interrupted COM call cannot be cancelled safely. Unknown outcomes remain in
the journal even after an operator acknowledges inspection of the CAD session.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Callable

from .safety import SafetyError, failure, normalize_result, validate_finite


class _JournalLock:
    """OS-held advisory lock; the file may persist, but the lock cannot go stale."""
    def __init__(self, path: Path):
        self._file = open(str(path) + ".lock", "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self._file.seek(0, 2)
                if self._file.tell() == 0:
                    self._file.write(b"0")
                    self._file.flush()
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            self._file.close()
            raise RuntimeError("Journal is locked by another runtime, or locking is unavailable") from exc

    def close(self):
        if not self._file.closed:
            # Closing the descriptor releases the kernel lock, including on crash.
            self._file.close()


class Runtime:
    def __init__(self, journal_path: str | Path, timeout: float = 60):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        validate_finite(timeout)
        self.timeout = timeout
        path = Path(journal_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._journal_lock = _JournalLock(path)
        self._db = None
        try:
            self._db = sqlite3.connect(str(path), check_same_thread=False)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, digest TEXT NOT NULL, operation TEXT NOT NULL, document TEXT NOT NULL, status TEXT NOT NULL, result TEXT, acknowledged INTEGER NOT NULL DEFAULT 0)")
            self._db.execute("UPDATE requests SET status='unknown' WHERE status='pending'")
            self._db.commit()
            self._blocked = bool(self._db.execute("SELECT 1 FROM requests WHERE status='unknown' AND acknowledged=0 LIMIT 1").fetchone())
        except BaseException:
            if self._db is not None:
                self._db.close()
            self._journal_lock.close()
            raise
        self._lock = threading.RLock()
        self._queue = queue.Queue()
        self._active = None
        self._closed = False
        self._worker = threading.Thread(target=self._run, name="catia-single-sta", daemon=True)
        self._worker.start()

    def state(self) -> dict:
        with self._lock:
            return {"idle": self._active is None, "blocked": self._blocked,
                    "closed": self._closed,
                    "reason": "unknown_outcome_requires_inspection" if self._blocked else None}

    def acknowledge_unknown(self, acknowledge: bool = False) -> dict:
        with self._lock:
            if self._closed:
                return failure("CLOSED", "Runtime is closed")
            if acknowledge is not True:
                return failure("ACK_REQUIRED", "Inspect the actual CAD state before explicit acknowledgement")
            if self._active is not None:
                return failure("BUSY", "The COM call is still running; acknowledgement cannot cancel it")
            try:
                self._db.execute("UPDATE requests SET acknowledged=1 WHERE status='unknown'")
                self._db.commit()
            except sqlite3.Error as exc:
                self._blocked = True
                return failure("JOURNAL_UNAVAILABLE", str(exc))
            self._blocked = False
            return {"ok": True, "message": "Block cleared; previous unknown request IDs remain non-retryable"}

    def call(self, operation: str, arguments: dict, function: Callable, *,
             request_id: str | None = None, document_token: str = "",
             mutating: bool = True, timeout: float | None = None) -> dict:
        """Run a trusted coordinator callable, returning an envelope or raw data.

        Dicts with a boolean ``ok`` are already-normalized coordinator envelopes.
        The coordinator must normalize untrusted upstream responses itself and
        explicitly mark preflight failures as effects.outcome=not_executed.
        """
        try:
            validate_finite(arguments)
            duration = self.timeout if timeout is None else timeout
            validate_finite(duration)
            if duration <= 0:
                raise SafetyError("INVALID_ARGUMENT", "timeout must be positive")
            if mutating and (not isinstance(request_id, str) or not request_id.strip()):
                raise SafetyError("REQUEST_ID_REQUIRED", "Mutations require a nonempty request_id")
            if request_id is not None and (not isinstance(request_id, str) or len(request_id) > 256):
                raise SafetyError("INVALID_ARGUMENT", "request_id must be a string of at most 256 characters")
            key = request_id or "read-" + uuid.uuid4().hex
            payload = json.dumps([operation, arguments, document_token, mutating], sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        except (ValueError, TypeError) as exc:
            return failure(getattr(exc, "code", "INVALID_ARGUMENT"), str(exc))
        with self._lock:
            if self._closed:
                return failure("CLOSED", "Runtime is closed")
            try:
                existing = self._db.execute("SELECT digest,status,result FROM requests WHERE id=?", (key,)).fetchone()
            except sqlite3.Error as exc:
                self._blocked = True
                return failure("JOURNAL_UNAVAILABLE", str(exc))
            if existing:
                if existing[0] != digest:
                    return failure("REQUEST_ID_CONFLICT", "This request_id was used with different operation, arguments, document or effects")
                if existing[1] == "completed":
                    result = json.loads(existing[2])
                    result["replayed"] = True
                    return result
                return failure("OUTCOME_UNKNOWN", "Request may already have executed; inspect CAD and do not blindly retry", outcome="unknown")
            if self._active is not None:
                return failure("BUSY", "Another COM call is running; requests are not queued")
            if mutating and self._blocked:
                return failure("MUTATIONS_BLOCKED", "Unknown prior outcome requires operator inspection and acknowledgement")
            job = {"id": key, "function": function, "event": threading.Event(), "timed_out": False, "result": None}
            try:
                self._db.execute("INSERT INTO requests(id,digest,operation,document,status) VALUES(?,?,?,?,?)", (key, digest, operation, document_token, "pending"))
                self._db.commit()
            except sqlite3.Error as exc:
                self._blocked = True
                try:
                    self._db.rollback()
                except sqlite3.Error:
                    pass
                return failure("JOURNAL_UNAVAILABLE", str(exc))
            self._active = job
            self._queue.put(job)
        if not job["event"].wait(duration):
            with self._lock:
                if not job["event"].is_set():
                    job["timed_out"] = True
                    self._blocked = True
                    try:
                        self._db.execute("UPDATE requests SET status='unknown' WHERE id=?", (key,))
                        self._db.commit()
                    except sqlite3.Error:
                        # The durable pending row also blocks replay after restart.
                        pass
                    return failure("OUTCOME_UNKNOWN", "Deadline exceeded; COM continues running and is NOT cancelled", outcome="unknown")
        return job["result"]

    def _run(self):
        pythoncom = None
        startup_error = None
        if os.name == "nt":
            try:
                import pythoncom as com
                com.CoInitializeEx(com.COINIT_APARTMENTTHREADED)
                pythoncom = com
            except Exception as exc:
                startup_error = exc
        try:
            while True:
                try:
                    job = self._queue.get(timeout=0.05)
                except queue.Empty:
                    if pythoncom is not None:
                        try:
                            pythoncom.PumpWaitingMessages()
                        except Exception:
                            with self._lock:
                                self._blocked = True
                    continue
                if job is None:
                    return
                try:
                    if startup_error:
                        raise RuntimeError("STA initialization failed: " + str(startup_error))
                    raw = job["function"]()
                    if isinstance(raw, dict) and isinstance(raw.get("ok"), bool):
                        # Preserve next_document_token, mock, steps and error code.
                        result = dict(raw)
                        effects = dict(result.get("effects") or {})
                        effects.setdefault("outcome", "call_returned" if raw["ok"] else "unknown")
                        effects["rollback"] = False
                        result["effects"] = effects
                    else:
                        result = normalize_result(raw)
                    # Ensure journal serialization succeeds before declaring completion.
                    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
                except BaseException as exc:
                    result = failure(getattr(exc, "code", "EXECUTION_FAILED"), str(exc), outcome="unknown")
                    encoded = json.dumps(result, ensure_ascii=False)
                with self._lock:
                    uncertain = job["timed_out"] or result.get("effects", {}).get("outcome") in {"unknown", "possibly_modified"}
                    if uncertain:
                        self._blocked = True
                    try:
                        self._db.execute("UPDATE requests SET status=?,result=? WHERE id=?", ("unknown" if uncertain else "completed", encoded, job["id"]))
                        self._db.commit()
                    except sqlite3.Error as exc:
                        self._blocked = True
                        result = failure("JOURNAL_UNAVAILABLE", "COM may have completed but outcome could not be recorded: " + str(exc), outcome="unknown")
                        try:
                            self._db.rollback()
                        except sqlite3.Error:
                            pass
                    finally:
                        job["result"] = result
                        self._active = None
                        job["event"].set()
                if pythoncom is not None:
                    try:
                        pythoncom.PumpWaitingMessages()
                    except Exception:
                        with self._lock:
                            self._blocked = True
        finally:
            try:
                if pythoncom is not None:
                    pythoncom.CoUninitialize()
            finally:
                with self._lock:
                    try:
                        self._db.close()
                    finally:
                        self._journal_lock.close()

    def close(self, wait: bool = False):
        # Never call Queue.join or wait for a stuck COM call by default.
        with self._lock:
            if not self._closed:
                self._closed = True
                self._queue.put(None)
        if wait:
            self._worker.join()

