"""Single-writer fencing for a DCM run.

The advisory file lock prevents two local processes from entering together;
the SQLite lease and monotonically increasing fence token make ownership
verifiable by every mutating operation.  A stale lease is never silently
repaired: an operator or an explicitly invoked recovery command must request
that action.
"""
from __future__ import annotations

import fcntl
import json
import os
import socket
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunBusyError(RuntimeError):
    code = "RUN_BUSY"

    def __init__(self, message: str = "run already has an active writer") -> None:
        super().__init__(f"{self.code}:{message}")


class RunFenceError(RuntimeError):
    code = "RUN_FENCE_INVALID"


def _now_epoch() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RunLock:
    """Context manager for one run's mutating critical section."""

    def __init__(self, run_dir: Path, *, command: str = "unknown", lease_seconds: int = 900, owner_token: str | None = None) -> None:
        self.run_dir = Path(run_dir)
        self.command = str(command)
        self.lease_seconds = max(30, int(lease_seconds))
        self.owner_token = owner_token or f"pid-{os.getpid()}-{time.time_ns()}"
        self.lock_path = self.run_dir / ".run.lock"
        self.db_path = self.run_dir / "run_lock.sqlite3"
        self._lock_fd: int | None = None
        self._db: sqlite3.Connection | None = None
        self.fence: int | None = None

    def _connect(self) -> sqlite3.Connection:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path, timeout=2.0, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=2000")
        db.execute(
            "CREATE TABLE IF NOT EXISTS writer_lease ("
            "run_id TEXT PRIMARY KEY, owner_token TEXT NOT NULL, fence INTEGER NOT NULL, "
            "lease_until REAL NOT NULL, metadata_json TEXT NOT NULL)"
        )
        return db

    def acquire(self, *, repair_stale: bool = False) -> "RunLock":
        if self._lock_fd is not None:
            return self
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._lock_fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self._lock_fd)
            self._lock_fd = None
            raise RunBusyError() from exc
        try:
            self._db = self._connect()
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute(
                "SELECT owner_token, fence, lease_until, metadata_json FROM writer_lease WHERE run_id=?",
                (self.run_dir.name,),
            ).fetchone()
            now = _now_epoch()
            if row is not None and float(row[2]) > now and str(row[0]) != self.owner_token:
                try:
                    active_metadata = json.loads(str(row[3] or "{}"))
                    active_metadata = active_metadata if isinstance(active_metadata, dict) else {}
                except json.JSONDecodeError:
                    active_metadata = {}
                holder = str(active_metadata.get("command") or "unknown")[:80]
                raise RunBusyError(
                    "active lease; "
                    f"fence={int(row[1])}; leaseUntil={float(row[2]):.3f}; command={holder}; "
                    "recovery=wait-for-owner-or-use-explicit-lock-repair-after-confirming-process-exit"
                )
            prior_metadata: dict[str, Any] = {}
            if row is not None:
                try:
                    decoded = json.loads(str(row[3] or "{}"))
                    prior_metadata = decoded if isinstance(decoded, dict) else {}
                except json.JSONDecodeError:
                    prior_metadata = {}
                if (
                    float(row[2]) <= now
                    and not repair_stale
                    and not prior_metadata.get("released")
                    and not prior_metadata.get("staleRepaired")
                ):
                    holder = str(prior_metadata.get("command") or "unknown")[:80]
                    raise RunBusyError(
                        "stale lease requires explicit repair; "
                        f"fence={int(row[1])}; leaseUntil={float(row[2]):.3f}; command={holder}; "
                        "recovery=python -m dcm.chat research-lock-repair --run <RUN_DIR>"
                    )
            fence = int(row[1]) + 1 if row is not None else 1
            metadata = {
                "runId": self.run_dir.name,
                "ownerToken": self.owner_token,
                "fence": fence,
                "command": self.command,
                "pid": os.getpid(),
                "hostnameDigest": __import__("hashlib").sha256(socket.gethostname().encode()).hexdigest()[:16],
                "acquiredAt": _now_iso(),
                "leaseUntil": now + self.lease_seconds,
                "repairStale": bool(repair_stale and row is not None),
            }
            self._db.execute(
                "INSERT INTO writer_lease(run_id,owner_token,fence,lease_until,metadata_json) VALUES(?,?,?,?,?) "
                "ON CONFLICT(run_id) DO UPDATE SET owner_token=excluded.owner_token, fence=excluded.fence, "
                "lease_until=excluded.lease_until, metadata_json=excluded.metadata_json",
                (self.run_dir.name, self.owner_token, fence, now + self.lease_seconds, json.dumps(metadata, sort_keys=True)),
            )
            self._db.execute("COMMIT")
            self.fence = fence
            return self
        except Exception:
            if self._db is not None:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                self._db.close()
                self._db = None
            if self._lock_fd is not None:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                self._lock_fd = None
            raise

    def renew(self) -> None:
        if self._db is None or self.fence is None:
            raise RunFenceError("lock is not acquired")
        until = _now_epoch() + self.lease_seconds
        cur = self._db.execute(
            "UPDATE writer_lease SET lease_until=? WHERE run_id=? AND owner_token=? AND fence=?",
            (until, self.run_dir.name, self.owner_token, self.fence),
        )
        if cur.rowcount != 1:
            raise RunFenceError("lease no longer owned")

    def assert_fence(self, fence: int | None = None) -> None:
        if self._db is None or self.fence is None:
            raise RunFenceError("lock is not acquired")
        wanted = self.fence if fence is None else int(fence)
        row = self._db.execute(
            "SELECT owner_token, fence, lease_until FROM writer_lease WHERE run_id=?",
            (self.run_dir.name,),
        ).fetchone()
        if row is None or str(row[0]) != self.owner_token or int(row[1]) != wanted or float(row[2]) < _now_epoch():
            raise RunFenceError("fencing token is not current")

    def metadata(self) -> dict[str, Any]:
        self.assert_fence()
        return {
            "schema": "pillars_dcm.run_lock.v1",
            "runId": self.run_dir.name,
            "ownerToken": self.owner_token,
            "fence": self.fence,
            "command": self.command,
        }

    def release(self) -> None:
        if self._db is not None and self.fence is not None:
            self._db.execute(
                "UPDATE writer_lease SET owner_token=?, lease_until=?, metadata_json=? "
                "WHERE run_id=? AND owner_token=? AND fence=?",
                (
                    "__released__",
                    0.0,
                    json.dumps({"runId": self.run_dir.name, "fence": self.fence, "released": True, "releasedAt": _now_iso()}, sort_keys=True),
                    self.run_dir.name,
                    self.owner_token,
                    self.fence,
                ),
            )
            self._db.close()
            self._db = None
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None

    def __enter__(self) -> "RunLock":
        return self.acquire()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()


def repair_stale_lease(run_dir: Path) -> dict[str, Any]:
    """Explicitly record and remove an abandoned lease while holding the file lock.

    This is intentionally a separate operation.  The normal acquire path will
    not take over a live-looking lease, while this function is the operator's
    explicit acknowledgement that the previous process is gone.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = run_dir / ".run.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise RunBusyError("cannot repair while another writer holds the file lock") from exc
    db = sqlite3.connect(run_dir / "run_lock.sqlite3", timeout=2.0, isolation_level=None)
    db.execute("PRAGMA busy_timeout=2000")
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT owner_token, fence, lease_until, metadata_json FROM writer_lease WHERE run_id=?", (run_dir.name,)).fetchone()
        if row is None:
            db.execute("COMMIT")
            result = {"schema": "pillars_dcm.run_lock_repair.v1", "runId": run_dir.name, "action": "NO_LEASE", "repairedAt": _now_iso()}
        else:
            try:
                metadata = json.loads(str(row[3] or "{}"))
                metadata = metadata if isinstance(metadata, dict) else {}
            except json.JSONDecodeError:
                metadata = {}
            if metadata.get("released") or metadata.get("staleRepaired"):
                action = "NO_ACTIVE_LEASE"
            else:
                action = "STALE_LEASE_REPAIRED"
                tombstone = {
                    "runId": run_dir.name,
                    "fence": int(row[1]),
                    "staleRepaired": True,
                    "repairedAt": _now_iso(),
                }
                db.execute(
                    "UPDATE writer_lease SET owner_token=?, lease_until=?, metadata_json=? WHERE run_id=?",
                    ("__repaired__", 0.0, json.dumps(tombstone, sort_keys=True), run_dir.name),
                )
            result = {"schema": "pillars_dcm.run_lock_repair.v1", "runId": run_dir.name, "previousOwnerTokenDigest": __import__("hashlib").sha256(str(row[0]).encode()).hexdigest()[:16], "previousFence": int(row[1]), "previousLeaseUntil": float(row[2]), "action": action, "repairedAt": _now_iso()}
            db.execute("COMMIT")
        repair_path = run_dir / "run_lock_repair.json"
        tmp = repair_path.with_name(f".{repair_path.name}.{os.getpid()}.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, repair_path)
        try:
            directory = os.open(str(run_dir), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            pass
        return result
    finally:
        try:
            db.close()
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


__all__ = ["RunBusyError", "RunFenceError", "RunLock", "repair_stale_lease"]
