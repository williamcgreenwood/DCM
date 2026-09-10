"""Contract tests for the one-arrow research RunDirector."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.runtime.run_director import RunDirector


class FakeSession:
    next_calls = 0
    imports: list[bool] = []

    def __init__(self, run: Path, *, workspace: Path | None = None):
        self.run = run

    def checkpoint_verify(self):
        return {"valid": True}

    def next_research_batch(self, **kwargs):
        type(self).next_calls += 1
        assert kwargs["max_entities"] == 8
        assert kwargs["max_dependent_offers"] == 250
        return {"batchId": "BATCH_ONE", "batchContentSha": "sha-one", "selectedCount": 1, "actions": [{}]}

    def research_validate(self, path):
        return {"validCount": 1, "failureCount": 0}

    def import_evidence(self, path, *, select_next=True):
        type(self).imports.append(select_next)
        return {"imported": 1, "responseFailureCount": 0}

    def coverage(self, **kwargs):
        assert kwargs["select_next"] is False
        return {"completeRequests": ["REQ_ONE"], "incompleteRequests": []}

    def _persist_research_checkpoint(self, **kwargs):
        return {"checkpointHash": "checkpoint-two"}


def _run(tmp_path: Path) -> Path:
    run = tmp_path / "RUN_TEST"
    run.mkdir()
    (run / "run_manifest.json").write_text(json.dumps({"runId": run.name}), encoding="utf-8")
    (run / "research_checkpoint.json").write_text(json.dumps({
        "schema": "pillars_dcm.research_checkpoint.v2", "runId": run.name,
        "generation": 0, "parentCheckpointSha": None, "activeBatchId": None,
        "artifacts": {}, "completedActionIds": [], "pendingActionIds": [],
        "failedActionIds": [], "coverageSha": None, "fence": None,
        "checkpointHash": "",
    }), encoding="utf-8")
    # The fake session supplies checkpoint verification; the director only
    # needs the file to establish that this is an existing run directory.
    return run


def test_run_until_awaiting_selects_one_packet_and_never_selects_batch_two(monkeypatch, tmp_path: Path):
    FakeSession.next_calls = 0
    monkeypatch.setattr("dcm.runtime.run_director.HostSession.open", lambda *a, **k: FakeSession(a[0]))
    director = RunDirector(_run(tmp_path))

    result = director.run_until_awaiting()
    assert result["phase"] == "AWAITING_RESPONSE"
    assert result["batchId"] == "BATCH_ONE"
    assert FakeSession.next_calls == 1
    assert result["lock"]["held"] is False

    waiting = director.step()
    assert waiting["phase"] == "AWAITING_RESPONSE"
    assert waiting["waiting"] is True
    assert FakeSession.next_calls == 1


def test_import_and_coverage_never_select_next_batch(monkeypatch, tmp_path: Path):
    FakeSession.next_calls = 0
    FakeSession.imports = []
    monkeypatch.setattr("dcm.runtime.run_director.HostSession.open", lambda *a, **k: FakeSession(a[0]))
    director = RunDirector(_run(tmp_path))
    assert director.run_until_awaiting()["phase"] == "AWAITING_RESPONSE"
    response = director.run / "responses" / "BATCH_ONE.response.json"
    response.parent.mkdir()
    response.write_text(json.dumps({"observations": [{"ok": True}]}), encoding="utf-8")

    assert director.step()["phase"] == "VALIDATE"
    assert director.step()["phase"] == "IMPORT"
    assert director.step()["phase"] == "COVERAGE"
    assert director.step()["phase"] == "CHECKPOINT_CAS"
    assert director.step()["phase"] == "SELECT_OR_RESUME_BATCH"
    assert FakeSession.imports == [False]
    assert FakeSession.next_calls == 1
