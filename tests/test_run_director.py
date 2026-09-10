"""Contract tests for the one-arrow research RunDirector."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.research.batch_store import make_batch_envelope, seal_batch
from dcm.runtime.run_director import DirectorStateError, RunDirector


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


def test_committed_pointer_selects_next_packet_instead_of_replaying(monkeypatch, tmp_path: Path):
    FakeSession.next_calls = 0
    run = _run(tmp_path)
    completed = make_batch_envelope(
        run_id=run.name,
        actions=[{"actionId": "AA_DONE"}],
        manifest_sha="manifest",
        har_sha256="har",
        forecast_cutoff="2026-09-08T00:00:00Z",
        code_sha="code",
    )
    completed_path = run / "research_batches" / f"{completed['batchId']}.json"
    seal_batch(completed_path, completed)
    (run / "research_checkpoint.json").write_text(json.dumps({
        "schema": "pillars_dcm.research_checkpoint.v2",
        "runId": run.name,
        "generation": 1,
        "parentCheckpointSha": None,
        "activeBatchId": completed["batchId"],
        "artifacts": {},
        "completedActionIds": ["AA_DONE"],
        "pendingActionIds": [],
        "failedActionIds": [],
        "coverageSha": None,
        "fence": None,
        "checkpointHash": "checkpoint-done",
    }), encoding="utf-8")
    (run / "active_research_batch.json").write_text(json.dumps({
        "schema": "pillars_dcm.active_research_batch.v1",
        "runId": run.name,
        "batchId": completed["batchId"],
        "batchContentSha": completed["batchContentSha"],
        "envelopePath": str(completed_path),
    }), encoding="utf-8")
    monkeypatch.setattr("dcm.runtime.run_director.HostSession.open", lambda *a, **k: FakeSession(a[0]))

    result = RunDirector(run).run_until_awaiting()

    assert result["phase"] == "AWAITING_RESPONSE"
    assert result["batchId"] == "BATCH_ONE"
    assert FakeSession.next_calls == 1


def test_dependent_offer_cap_is_recomputed_for_legacy_envelope(monkeypatch, tmp_path: Path):
    class OverBudgetSession(FakeSession):
        def next_research_batch(self, **kwargs):
            return {
                "batchId": "BATCH_OVER",
                "batchContentSha": "sha-over",
                "selectedCount": 1,
                "actions": [{"dependentPropCount": 251}],
            }

    monkeypatch.setattr("dcm.runtime.run_director.HostSession.open", lambda *a, **k: OverBudgetSession(a[0]))
    with pytest.raises(DirectorStateError, match="BATCH_CAP_EXCEEDED"):
        RunDirector(_run(tmp_path)).run_until_awaiting()
