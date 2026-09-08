"""Regression tests for the resumable DCM batch-search worker."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dcm.contracts.hashes import content_hash
from dcm.research.action_state import (
    apply_failure,
    eligible_action_ids,
    load_action_state,
    save_action_state,
)
from dcm.research.batch_store import (
    BatchEnvelopeOverwriteBlocked,
    CheckpointCasMismatch,
    make_batch_envelope,
    seal_batch,
    verify_checkpoint,
    write_checkpoint_cas,
)
from dcm.research.coverage import coverage_report
from dcm.research.coverage_incremental import incremental_coverage_report
from dcm.research.failures import append_failure, failure_record, load_failures
from dcm.research.run_lock import RunBusyError, RunLock, repair_stale_lease
from dcm.research.response import ResponseEnvelopeError, load_response, validate_response_binding
from dcm.research.acquisition import schedule_acquisition_actions
from dcm.research.search_engine import SearchEngine
from dcm.research.search_query import compile_query
from dcm.chat.research_bridge import _ensure_research_prerequisites, next_research_batch


def _action(action_id: str, request_id: str, source_id: str = "SRC_A") -> dict[str, object]:
    return {
        "actionId": action_id,
        "requestId": request_id,
        "requirementIds": [request_id],
        "scope": "EVENT",
        "scopeId": request_id,
        "sourceId": source_id,
    }


def test_permanent_request_failure_excludes_all_actions_for_request(tmp_path: Path):
    actions = [_action("AA_1", "REQ_1"), _action("AA_2", "REQ_1", "SRC_B"), _action("AA_3", "REQ_2")]
    states: dict[str, dict[str, object]] = {}
    failure_path = tmp_path / "research_failures.jsonl"
    _, failure = apply_failure(
        states,
        run_id="RUN_1",
        batch_id="BATCH_1",
        action_id="AA_1",
        request_id="REQ_1",
        code="REQUIRED_FIELD_MISSING",
        retryable=False,
        exclusion_scope="REQUEST",
        source_id="SRC_A",
        failure_path=failure_path,
        now="2026-09-08T00:00:00Z",
        safe_reason="missing required field",
    )
    assert failure["sourceId"] == "SRC_A"
    eligible = eligible_action_ids(
        actions,
        states=states,
        failures=load_failures(failure_path),
        run_id="RUN_1",
        batch_id="BATCH_1",
        now="2026-09-08T00:01:00Z",
    )
    assert eligible == {"AA_3"}


def test_retryable_failure_is_excluded_until_deterministic_backoff_expires(tmp_path: Path):
    states: dict[str, dict[str, object]] = {}
    failure_path = tmp_path / "failures.jsonl"
    row, failure = apply_failure(
        states,
        run_id="RUN_1",
        batch_id="BATCH_1",
        action_id="AA_1",
        request_id="REQ_1",
        code="SOURCE_RATE_LIMITED",
        retryable=True,
        failure_path=failure_path,
        now="2026-09-08T00:00:00Z",
    )
    assert row["state"] == "FAILED_RETRYABLE"
    assert failure["nextRetryAt"] == "2026-09-08T00:00:30Z"
    action = _action("AA_1", "REQ_1")
    assert not eligible_action_ids([action], states=states, failures=load_failures(failure_path), now="2026-09-08T00:00:29Z")
    assert eligible_action_ids([action], states=states, failures=load_failures(failure_path), now="2026-09-08T00:00:30Z") == {"AA_1"}


def test_retryable_failure_backoff_is_enforced_when_scheduler_omits_now(tmp_path: Path):
    states: dict[str, dict[str, object]] = {}
    failure_path = tmp_path / "failures.jsonl"
    row, failure = apply_failure(
        states,
        run_id="RUN_1",
        batch_id="BATCH_1",
        action_id="AA_1",
        request_id="REQ_1",
        code="SOURCE_RATE_LIMITED",
        retryable=True,
        failure_path=failure_path,
        next_retry_at="2999-01-01T00:00:00Z",
        now="2026-09-08T00:00:00Z",
    )
    assert row["state"] == "FAILED_RETRYABLE"
    assert not eligible_action_ids(
        [_action("AA_1", "REQ_1")],
        states=states,
        failures=load_failures(failure_path),
    )


def test_lock_repair_cli_is_exposed_in_the_host_contract():
    from dcm.chat.cli import build_parser
    from dcm.chat.contracts import HOST_COMMANDS

    assert "research-lock-repair" in HOST_COMMANDS
    parsed = build_parser().parse_args(["research-lock-repair", "--run", "/tmp/run"])
    assert parsed.command == "research-lock-repair"


def test_same_response_failure_key_does_not_increment_attempt_twice(tmp_path: Path):
    states: dict[str, dict[str, object]] = {}
    failure_path = tmp_path / "failures.jsonl"
    first, first_failure = apply_failure(
        states,
        run_id="RUN",
        batch_id="BATCH",
        action_id="AA",
        request_id="REQ",
        code="SOURCE_UNAVAILABLE",
        retryable=True,
        failure_path=failure_path,
        failure_key="response-failure-1",
        now="2026-09-08T00:00:00Z",
    )
    second, second_failure = apply_failure(
        states,
        run_id="RUN",
        batch_id="BATCH",
        action_id="AA",
        request_id="REQ",
        code="SOURCE_UNAVAILABLE",
        retryable=True,
        failure_path=failure_path,
        failure_key="response-failure-1",
        now="2026-09-08T00:00:01Z",
    )
    assert first_failure == second_failure
    assert first["attempt"] == second["attempt"] == 1


def test_response_envelope_is_bound_to_the_active_immutable_batch(tmp_path: Path):
    action = _action("AA_1", "REQ_1")
    envelope = make_batch_envelope(
        run_id=tmp_path.name,
        actions=[action],
        manifest_sha="manifest",
        har_sha256="har",
        forecast_cutoff="2026-09-08T00:00:00Z",
        code_sha="code",
        parent_checkpoint_sha="checkpoint",
        search_blueprint_hash="blueprint",
    )
    envelope_path = tmp_path / "research_batches" / f"{envelope['batchId']}.json"
    sealed = seal_batch(envelope_path, envelope)
    (tmp_path / "active_research_batch.json").write_text(json.dumps({
        "batchId": sealed["batchId"],
        "batchContentSha": sealed["batchContentSha"],
        "searchBlueprintHash": sealed["searchBlueprintHash"],
        "envelopePath": str(envelope_path),
    }), encoding="utf-8")
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps({
        "schema": "pillars_dcm.research_response.v1",
        "runId": tmp_path.name,
        "batchId": sealed["batchId"],
        "batchContentSha": sealed["batchContentSha"],
        "checkpointSha": "checkpoint",
        "searchBlueprintHash": sealed["searchBlueprintHash"],
        "observations": [],
        "failures": [],
    }), encoding="utf-8")
    response = validate_response_binding(load_response(response_path), tmp_path)
    assert response["bindingStatus"] == "BOUND"
    assert response["boundBatchId"] == sealed["batchId"]
    response_path.write_text(response_path.read_text(encoding="utf-8").replace(sealed["batchId"], "BATCH_WRONG"), encoding="utf-8")
    with pytest.raises(ResponseEnvelopeError, match="BATCH_MISMATCH"):
        validate_response_binding(load_response(response_path), tmp_path)


def test_response_blueprint_mismatch_is_rejected(tmp_path: Path):
    envelope = make_batch_envelope(
        run_id=tmp_path.name,
        actions=[_action("AA_1", "REQ_1")],
        manifest_sha="manifest",
        har_sha256="har",
        forecast_cutoff="2026-09-08T00:00:00Z",
        code_sha="code",
        parent_checkpoint_sha="checkpoint",
        search_blueprint_hash="blueprint-a",
    )
    envelope_path = tmp_path / "research_batches" / f"{envelope['batchId']}.json"
    sealed = seal_batch(envelope_path, envelope)
    (tmp_path / "active_research_batch.json").write_text(json.dumps({
        "batchId": sealed["batchId"],
        "batchContentSha": sealed["batchContentSha"],
        "searchBlueprintHash": sealed["searchBlueprintHash"],
        "envelopePath": str(envelope_path),
    }), encoding="utf-8")
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps({
        "schema": "pillars_dcm.research_response.v1",
        "runId": tmp_path.name,
        "batchId": sealed["batchId"],
        "batchContentSha": sealed["batchContentSha"],
        "checkpointSha": "checkpoint",
        "searchBlueprintHash": "blueprint-b",
        "observations": [],
        "failures": [],
    }), encoding="utf-8")
    with pytest.raises(ResponseEnvelopeError, match="BLUEPRINT_MISMATCH"):
        validate_response_binding(load_response(response_path), tmp_path)


def test_failure_only_response_envelope_has_no_pseudo_observation(tmp_path: Path):
    from dcm.research.observation_typed import _load_observations

    path = tmp_path / "failure-only.response.json"
    path.write_text(json.dumps({
        "schema": "pillars_dcm.research_response.v1",
        "observations": [],
        "failures": [{"actionId": "AA_1", "code": "CUTOFF_VIOLATION"}],
    }), encoding="utf-8")
    assert _load_observations(path) == []


def test_failure_append_is_idempotent_and_conflicts_fail_closed(tmp_path: Path):
    path = tmp_path / "failures.jsonl"
    record = failure_record(
        run_id="RUN",
        batch_id="BATCH",
        action_id="AA",
        code="SOURCE_UNAVAILABLE",
        retryable=False,
        recorded_at="2026-09-08T00:00:00Z",
    )
    assert append_failure(path, record) == record
    assert append_failure(path, record) == record
    assert len(load_failures(path)) == 1
    conflict = dict(record)
    conflict["safeReason"] = "different reason"
    conflict["contentHash"] = content_hash({k: v for k, v in conflict.items() if k not in {"contentHash", "failureId"}})
    with pytest.raises(RuntimeError, match="FAILURE_IDEMPOTENCY_CONFLICT"):
        append_failure(path, conflict)


def test_batch_envelope_is_immutable_and_same_identity_is_byte_stable(tmp_path: Path):
    path = tmp_path / "research_batches" / "BATCH.json"
    base = make_batch_envelope(
        run_id="RUN",
        actions=[_action("AA_1", "REQ_1")],
        manifest_sha="manifest",
        har_sha256="har",
        forecast_cutoff="2026-09-08T00:00:00Z",
        code_sha="code",
        search_blueprint_hash="blueprint",
    )
    first = seal_batch(path, base)
    before = path.read_bytes()
    second = seal_batch(path, make_batch_envelope(
        run_id="RUN",
        actions=[_action("AA_1", "REQ_1")],
        manifest_sha="manifest",
        har_sha256="har",
        forecast_cutoff="2026-09-08T00:00:00Z",
        code_sha="code",
        search_blueprint_hash="blueprint",
    ))
    assert first == second
    assert path.read_bytes() == before
    conflicting = make_batch_envelope(
        run_id="RUN",
        actions=[_action("AA_2", "REQ_2")],
        manifest_sha="manifest",
        har_sha256="har",
        forecast_cutoff="2026-09-08T00:00:00Z",
        code_sha="code",
        search_blueprint_hash="blueprint",
    )
    with pytest.raises(BatchEnvelopeOverwriteBlocked):
        seal_batch(path, conflicting)


def test_uncheckpointed_active_pointer_cannot_be_advanced(tmp_path: Path):
    batch_dir = tmp_path / "research_batches"
    envelope = make_batch_envelope(
        run_id=tmp_path.name,
        actions=[_action("AA_1", "REQ_1")],
        manifest_sha="manifest",
        har_sha256="har",
        forecast_cutoff="2026-09-08T00:00:00Z",
        code_sha="code",
        search_blueprint_hash="blueprint",
    )
    path = batch_dir / f"{envelope['batchId']}.json"
    sealed = seal_batch(path, envelope)
    (tmp_path / "active_research_batch.json").write_text(
        json.dumps({"batchId": sealed["batchId"], "batchContentSha": sealed["batchContentSha"], "searchBlueprintHash": sealed["searchBlueprintHash"], "envelopePath": str(path)}),
        encoding="utf-8",
    )
    (tmp_path / "host_research_batch.json").write_text(
        json.dumps({"schema": "pillars_dcm.host_research_batch.v1", "batchId": sealed["batchId"], "tasks": sealed["actions"]}),
        encoding="utf-8",
    )
    result = next_research_batch(tmp_path)
    assert result["batchId"] == sealed["batchId"]
    assert result["batchStatus"] == "ACTIVE_PENDING_CHECKPOINT"
    assert result["resumeRequired"] is True


def test_checkpoint_compare_and_swap_and_hash_verification(tmp_path: Path):
    path = tmp_path / "research_checkpoint.json"
    first = write_checkpoint_cas(
        path,
        expected_parent_sha=None,
        run_id="RUN",
        generation=1,
        active_batch_id="BATCH_1",
        artifacts={"a": "sha-a"},
        pending_action_ids=["AA_2"],
    )
    assert verify_checkpoint(path)["checkpointHash"] == first["checkpointHash"]
    with pytest.raises(CheckpointCasMismatch):
        write_checkpoint_cas(
            path,
            expected_parent_sha="stale",
            run_id="RUN",
            generation=2,
            active_batch_id="BATCH_2",
            artifacts={},
        )
    second = write_checkpoint_cas(
        path,
        expected_parent_sha=first["checkpointHash"],
        run_id="RUN",
        generation=2,
        active_batch_id="BATCH_2",
        artifacts={"a": "sha-a", "b": "sha-b"},
    )
    assert second["parentCheckpointSha"] == first["checkpointHash"]
    assert second["generation"] == 2


def test_single_writer_lock_and_explicit_stale_lease_repair(tmp_path: Path):
    run = tmp_path / "RUN"
    first = RunLock(run, command="first").acquire()
    try:
        with pytest.raises(RunBusyError):
            RunLock(run, command="second").acquire()
    finally:
        first.release()

    db = sqlite3.connect(run / "run_lock.sqlite3")
    db.execute(
        "INSERT OR REPLACE INTO writer_lease(run_id,owner_token,fence,lease_until,metadata_json) VALUES(?,?,?,?,?)",
        (run.name, "abandoned", 4, 0.0, "{}"),
    )
    db.commit()
    db.close()
    receipt = repair_stale_lease(run)
    assert receipt["action"] == "STALE_LEASE_REPAIRED"
    repaired = RunLock(run, command="recovered").acquire()
    assert repaired.fence == 5
    repaired.release()


def test_action_state_save_is_hashed_and_reloadable(tmp_path: Path):
    path = tmp_path / "action_state.json"
    states = {"AA": {"actionId": "AA", "state": "PENDING", "attempt": 0}}
    saved = save_action_state(path, states)
    assert saved["contentHash"]
    assert load_action_state(path)["AA"]["state"] == "PENDING"


def test_incremental_coverage_reuses_unaffected_requests_and_matches_full():
    requests = [
        {"request_id": "REQ_1", "scope": "EVENT", "scope_id": "E1"},
        {"request_id": "REQ_2", "scope": "EVENT", "scope_id": "E2"},
    ]
    claims = [
        {
            "semantic_scope": "EVENT",
            "scope_id": "E1",
            "claim_value": {"event_context": True},
            "claim_hash": "C1",
        }
    ]
    prior = coverage_report(requests, claims)
    changed = [{"semantic_scope": "EVENT", "scope_id": "E1", "claim_hash": "C1"}]
    incremental = incremental_coverage_report(requests, claims, prior=prior, changed_claims=changed, verify_full=True)
    full = coverage_report(requests, claims)
    assert incremental["requestsEvaluated"] == 1
    assert incremental["equalityVerified"] is True
    assert incremental["requests"] == full["requests"]


def test_search_engine_applies_cutoff_exact_scope_and_deduplication():
    documents = [
        {"id": "old", "scope": "EVENT", "scope_id": "E1", "title": "alpha event", "publishedAt": "2026-09-07T00:00:00Z", "claim_hash": "same"},
        {"id": "new", "scope": "EVENT", "scope_id": "E1", "title": "alpha event", "publishedAt": "2026-09-09T00:00:00Z", "claim_hash": "new"},
        {"id": "copy", "scope": "EVENT", "scope_id": "E2", "title": "alpha event", "publishedAt": "2026-09-07T00:00:00Z", "claim_hash": "same"},
    ]
    engine = SearchEngine(documents)
    result = engine.search("alpha", cutoff="2026-09-08T00:00:00Z", exact_id="old", k=5)
    assert [row["id"] for row in result["results"]] == ["old"]
    assert result["candidateCount"] == 1
    assert [0, 2] in engine.duplicate_candidates()
    assert "WAND_TOPK" in engine.index_receipt["algorithms"]


def test_query_plan_expands_research_need_into_machine_required_fields():
    plan = compile_query(
        {"actionId": "AA_EVENT", "scope": "EVENT", "scopeId": "E1", "sourceCandidates": ["OFFICIAL"]},
        request={"requestId": "REQ", "scope": "EVENT", "scope_id": "E1", "need": "start_venue_starters_environment"},
        cutoff="2026-09-08T00:00:00Z",
    )
    assert plan["requiredFields"] == ["environment", "scheduled_start", "starters_known", "venue"]
    assert plan["verificationPlan"]["requireAllFields"] == plan["requiredFields"]


def test_offer_budget_rejects_oversized_first_action_and_fills_later_feasible_work():
    def action(action_id: str, offers: list[str], requirement: str) -> dict[str, object]:
        return {
            "actionId": action_id,
            "scope": "EVENT",
            "scopeId": requirement,
            "eventId": requirement,
            "sourceFamily": "event_schedule_venue_status",
            "requirementIds": [requirement],
            "offerIds": offers,
            "dependentOfferCount": len(offers),
            "expectedGain": 1.0,
            "cost": 1.0,
            "weight": 1.0,
        }

    schedule = schedule_acquisition_actions(
        {
            "actions": [
                action("AA_TOO_LARGE", ["O1", "O2", "O3"], "REQ_LARGE"),
                action("AA_SMALL_1", ["O4"], "REQ_1"),
                action("AA_SMALL_2", ["O5"], "REQ_2"),
            ]
        },
        max_actions=2,
        max_dependent_offers=2,
    )
    assert "AA_TOO_LARGE" not in schedule["selectedActionIds"]
    assert schedule["selectedCount"] == 2
    assert schedule["dependentOfferBudgetUsed"] <= 2
    assert "AA_TOO_LARGE" in schedule["budgetSkippedActionIds"]
    assert all(int(batch["dependentOfferCount"]) <= 2 for batch in schedule["packedBatches"])


def test_stale_action_plan_is_rebuilt_when_request_identity_changes(tmp_path: Path):
    requests = [
        {"request_id": "REQ_1", "scope": "EVENT", "scope_id": "E1", "need": "event_context"},
        {"request_id": "REQ_2", "scope": "EVENT", "scope_id": "E2", "need": "event_context"},
    ]
    (tmp_path / "research_requests.json").write_text(json.dumps(requests), encoding="utf-8")
    (tmp_path / "board.json").write_text(json.dumps({"rows": [], "forecastCutoff": "2026-09-08T00:00:00Z"}), encoding="utf-8")
    (tmp_path / "acquisition_actions.json").write_text(json.dumps({
        "schema": "pillars_dcm.acquisition_actions.v1",
        "actionCount": 1,
        "requirementCount": 1,
        "actions": [{"actionId": "AA_OLD", "requirementIds": ["REQ_OLD"]}],
    }), encoding="utf-8")
    readiness = _ensure_research_prerequisites(tmp_path)
    assert readiness["schema"] == "pillars_dcm.research_os_readiness.v1"
    repaired = json.loads((tmp_path / "research_prerequisite_repair.json").read_text(encoding="utf-8"))
    assert repaired["reason"] == "REQUEST_ACTION_IDENTITY_MISMATCH"
    rebuilt = json.loads((tmp_path / "acquisition_actions.json").read_text(encoding="utf-8"))
    assert rebuilt["requirementCount"] == 2
    assert {rid for action in rebuilt["actions"] for rid in action["requirementIds"]} == {"REQ_1", "REQ_2"}
