"""Supervise a slate in a separate process so hard kills leave a typed receipt.

The child writes only stage names and counts to progress.json. Raw capture data
and subprocess logs remain local; the terminal receipt never contains them.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def progress(root: Path, stage: str, *, state: str, completed: int = 0, total: int = 0) -> None:
    """Record a bounded, privacy-safe stage transition for the parent watchdog."""
    _atomic_json(Path(root) / "run_progress.json", {
        "schema": "pillars_dcm.run_progress.v1",
        "stage": stage,
        "state": state,
        "completed": completed,
        "total": total,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    })


def _cgroup_limit() -> int | None:
    for path in (Path("/sys/fs/cgroup/memory.max"), Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")):
        try:
            value = int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            continue
        if 0 < value < (1 << 50):
            return value
    return None


def _rss_bytes(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def _cgroup_usage() -> int | None:
    for path in (Path("/sys/fs/cgroup/memory.current"), Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")):
        try:
            return int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            continue
    return None


def _terminate(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def _terminal_receipts_valid(root: Path, *, not_before_ns: int) -> bool:
    paths = (root / "run_manifest.json", root / "execution_receipt.json")
    try:
        if any(path.stat().st_mtime_ns < not_before_ns for path in paths):
            return False
        manifest = json.loads(paths[0].read_text(encoding="utf-8"))
        receipt = json.loads(paths[1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for value in (manifest, receipt):
        if not isinstance(value, dict) or value.get("contentHash") != content_hash(
            {key: item for key, item in value.items() if key != "contentHash"}
        ):
            return False
    phases = receipt.get("phaseStatus") or []
    required = {"ACCOUNT_EACH_HAR", "RECONCILE_UNION", "CHECKPOINT_VERIFY"}
    states = {
        str(phase.get("name")): str(phase.get("status"))
        for phase in phases if isinstance(phase, dict)
    }
    return bool(manifest.get("compositeRunId")) and all(
        states.get(name) == "COMPLETE" for name in required
    ) and not any(
        isinstance(phase, dict) and phase.get("status") == "FAILED" for phase in phases
    )


def supervise_slate(
    argv: list[str], root: Path, *,
    max_seconds: int = 7200, stall_seconds: int = 1200, max_rss_mib: int = 0,
) -> tuple[int, dict[str, Any] | None]:
    """Return the child's status; persist a terminal receipt even after SIGKILL.

    A zero RSS limit uses 80% of the cgroup limit, if one exists. The parent
    observes progress transitions, not CPU activity, to catch nonterminating
    computation. Operators may adjust positive limits for known large slates.
    """
    if max_seconds <= 0 or stall_seconds <= 0 or max_rss_mib < 0:
        raise ValueError("RUN_GUARD_LIMIT_INVALID")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cgroup_total = _cgroup_limit()
    limit = max_rss_mib * 1024 * 1024 if max_rss_mib else cgroup_total
    if not max_rss_mib and limit:
        limit = int(limit * 0.8)
    usage_limit = int(cgroup_total * 0.9) if cgroup_total and not max_rss_mib else None
    progress_path = root / "run_progress.json"
    progress_path.unlink(missing_ok=True)
    failure_path = root / "run_failure.json"
    failure_path.unlink(missing_ok=True)
    started_wall_ns = time.time_ns()
    started = time.monotonic()
    last_change = started
    last_mtime: int | None = None
    reason: str | None = None
    # Captured stdout/stderr can contain operational paths. They are local
    # only, mode 0600, and never embedded in the failure receipt.
    private = root / ".private_run_guard" / f"{started_wall_ns}-{os.getpid()}"
    private.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(private, 0o700)
    out_path = private / "child.stdout"
    err_path = private / "child.stderr"
    with out_path.open("wb") as out, err_path.open("wb") as err:
        os.chmod(out_path, 0o600)
        os.chmod(err_path, 0o600)
        proc = subprocess.Popen(
            [sys.executable, "-m", "dcm.chat", *argv, "--unsupervised-child"],
            stdout=out, stderr=err, start_new_session=True,
        )
        try:
            while proc.poll() is None:
                try:
                    mtime = progress_path.stat().st_mtime_ns
                except OSError:
                    mtime = None
                if mtime is not None and mtime != last_mtime:
                    last_mtime, last_change = mtime, time.monotonic()
                elapsed = time.monotonic() - started
                rss = _rss_bytes(proc.pid)
                usage = _cgroup_usage() if not max_rss_mib else None
                if usage_limit and usage is not None and usage > usage_limit:
                    reason = "RUN_CGROUP_MEMORY_PRESSURE"
                elif limit and rss is not None and rss > limit:
                    reason = "RUN_MEMORY_LIMIT"
                elif elapsed > max_seconds:
                    reason = "RUN_WALL_TIMEOUT"
                elif time.monotonic() - last_change > stall_seconds:
                    reason = "RUN_PROGRESS_STALLED"
                if reason:
                    _terminate(proc)
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            reason = "RUN_INTERRUPTED"
            _terminate(proc)
    if proc.returncode == 0 and _terminal_receipts_valid(root, not_before_ns=started_wall_ns):
        # The child emitted one JSON response; preserve CLI compatibility.
        sys.stdout.write(out_path.read_text(encoding="utf-8"))
        out_path.unlink(missing_ok=True)
        err_path.unlink(missing_ok=True)
        private.rmdir()
        return 0, None
    try:
        stage = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stage = {}
    code = reason or (
        "RUN_OUTPUT_INCOMPLETE" if proc.returncode == 0 else
        "RUN_CHILD_KILLED" if proc.returncode and proc.returncode < 0 else "RUN_CHILD_FAILED"
    )
    receipt = {
        "schema": "pillars_dcm.run_failure.v1",
        "state": "FAILED_WITH_PARTIAL_ARTIFACTS",
        "code": code,
        "exitCode": proc.returncode,
        "lastStage": stage.get("stage", "STARTUP"),
        "lastStageState": stage.get("state", "UNKNOWN"),
        "completed": stage.get("completed", 0),
        "total": stage.get("total", 0),
        "elapsedSeconds": round(time.monotonic() - started, 2),
        "logFilesLocalOnly": True,
        "checkpointVerified": False,
        "productionSelectionPermitted": False,
    }
    receipt["contentHash"] = content_hash(receipt)
    _atomic_json(failure_path, receipt)
    return 1, receipt
