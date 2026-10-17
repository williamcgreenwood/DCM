from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dcm.chat import run_guard
from dcm.chat.cli import main
from dcm.contracts.hashes import content_hash


def test_guard_records_child_failure_without_logs(tmp_path: Path, monkeypatch) -> None:
    real_popen = subprocess.Popen

    def child(_args, **kwargs):
        return real_popen([sys.executable, "-c", "raise RuntimeError('private capture data')"], **kwargs)

    monkeypatch.setattr(run_guard.subprocess, "Popen", child)
    status, failure = run_guard.supervise_slate(["run-slate"], tmp_path, max_seconds=10, stall_seconds=5)
    assert status == 1
    assert failure["code"] == "RUN_CHILD_FAILED"
    assert "private capture data" not in json.dumps(failure)
    assert failure["contentHash"] == content_hash({k: v for k, v in failure.items() if k != "contentHash"})
    assert json.loads((tmp_path / "run_failure.json").read_text()) == failure


def test_guard_kills_stalled_child_and_preserves_stage(tmp_path: Path, monkeypatch) -> None:
    real_popen = subprocess.Popen

    def child(_args, **kwargs):
        return real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)

    monkeypatch.setattr(run_guard.subprocess, "Popen", child)
    run_guard.progress(tmp_path, "SOURCE_INGEST", state="STARTED")
    status, failure = run_guard.supervise_slate(["run-slate"], tmp_path, max_seconds=2, stall_seconds=1)
    assert status == 1
    assert failure["code"] == "RUN_PROGRESS_STALLED"
    assert failure["productionSelectionPermitted"] is False


def test_run_slate_cli_supervisor_receipts_invalid_input(tmp_path: Path, capsys) -> None:
    root = tmp_path / "run"
    status = main([
        "run-slate", "--har", str(tmp_path / "missing.har"),
        "--run-root", str(root), "--max-runtime-seconds", "10",
    ])
    assert status == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["code"] == "RUN_CHILD_FAILED"
    assert printed["lastStage"] == "STARTUP"
    assert (root / "run_failure.json").is_file()


def test_guard_detects_hard_kill_that_python_cannot_catch(tmp_path: Path, monkeypatch) -> None:
    real_popen = subprocess.Popen

    def child(_args, **kwargs):
        return real_popen([sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"], **kwargs)

    monkeypatch.setattr(run_guard.subprocess, "Popen", child)
    status, failure = run_guard.supervise_slate(["run-slate"], tmp_path, max_seconds=10, stall_seconds=5)
    assert status == 1
    assert failure["code"] == "RUN_CHILD_KILLED"
    assert failure["checkpointVerified"] is False


def test_guard_rejects_zero_exit_without_terminal_receipts(tmp_path: Path, monkeypatch) -> None:
    real_popen = subprocess.Popen

    def child(_args, **kwargs):
        return real_popen([sys.executable, "-c", "print('{}')"], **kwargs)

    monkeypatch.setattr(run_guard.subprocess, "Popen", child)
    status, failure = run_guard.supervise_slate(["run-slate"], tmp_path, max_seconds=10, stall_seconds=5)
    assert status == 1
    assert failure["code"] == "RUN_OUTPUT_INCOMPLETE"
