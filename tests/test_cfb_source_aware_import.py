"""Source-aware host observation → import → coverage → ParameterSnapshot loop."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.chat.evidence_import import import_observations, observation_to_claim
from dcm.chat.state import write_json
from dcm.ingest.har import ingest_har
from dcm.model.parameters import build_parameter_snapshot
from dcm.research.acquisition import build_acquisition_actions
from dcm.research.batch import build_next_research_batch
from dcm.research.coverage import evaluate_request
from dcm.research.observation_execute import (
    assemble_claim_value,
    execute_source_aware_observations,
    has_valid_field_coverage,
)
from dcm.research.provider import BundleProvider
from dcm.research.requests import plan_research

FIXTURE = Path(__file__).resolve().parents[1] / "artifacts" / "dcm_v6_workstream_ab" / "fixtures" / "cfb_guarded_launch_har.json"
CUTOFF = "2026-09-02T18:00:00Z"


def _board_context(tmp_path: Path) -> tuple[Path, list[dict], dict, dict]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = ingest_har(raw)["rows"]
    planned = plan_research(rows, CUTOFF)
    for req in planned["requests"]:
        req.setdefault("league", "CFB")
        req.setdefault("sportFamily", "gridiron")
    actions = build_acquisition_actions(rows, planned["requests"])
    dest = tmp_path / "run"
    dest.mkdir()
    write_json(dest / "research_requests.json", planned["requests"])
    write_json(dest / "freeze.json", {"forecastCutoff": CUTOFF})
    write_json(dest / "board.json", {"forecastCutoff": CUTOFF, "rows": rows})
    write_json(dest / "acquisition_actions.json", actions)
    write_json(dest / "host_state.json", {"forecastCutoff": CUTOFF})
    return dest, rows, planned, actions


def _event_observation(action: dict, *, empty: bool = False, typed: bool = False) -> dict:
    base = {
        "schema": "pillars_dcm.host_observation.v1",
        "actionId": action["actionId"],
        "sourceId": action.get("sourceId") or "CFB_OFFICIAL_GAMEBOOK",
        "sourceFamily": action.get("sourceFamily"),
        "sourceUrl": "https://example.com/cfb/event/CFB_TEST_1",
        "retrievedAt": "2026-09-01T12:00:00Z",
        "publishedAt": "2026-09-01T00:00:00Z",
        "entityRef": {"kind": "EVENT", "id": "CFB_TEST_1"},
        "parserVersion": "host-obs-v1-synthetic",
        "evidenceType": "EVENT_CONTEXT",
    }
    if empty:
        base["data"] = {}
        return base
    if typed:
        base["claims"] = [
            {"field": "event_context", "value": True, "unit": "boolean", "provenance": "schedule_header"},
            {"field": "scheduled_start", "value": "2026-09-05T23:00:00Z", "unit": "iso8601", "provenance": "schedule_header"},
            {"field": "venue", "value": "Fixture Stadium", "unit": "name", "provenance": "venue_block"},
            {"field": "surface", "value": "grass", "unit": "surface_type", "provenance": "venue_block"},
            {
                "field": "weather",
                "value": {"wind_mph": 7, "precipitation": 0},
                "unit": "weather_object",
                "provenance": "forecast_block",
            },
        ]
        return base
    base["data"] = {
        "event_context": True,
        "scheduled_start": "2026-09-05T23:00:00Z",
        "venue": "Fixture Stadium",
        "surface": "grass",
        "weather": {"wind_mph": 7, "precipitation": 0},
        "spread": -17.5,
        "game_total": 55.5,
    }
    return base


def test_empty_field_coverage_rejected_and_does_not_close_contract(tmp_path: Path):
    dest, rows, planned, actions = _board_context(tmp_path)
    event_action = next(a for a in actions["actions"] if a["scope"] == "EVENT")
    obs_path = tmp_path / "empty.jsonl"
    obs_path.write_text(json.dumps(_event_observation(event_action, empty=True)) + "\n", encoding="utf-8")
    result = execute_source_aware_observations(dest, obs_path)
    assert result["imported"] == 0
    assert result["rejected"] == 1
    assert result["errors"][0]["error"] == "EMPTY_FIELD_COVERAGE"
    assert result["emptyFieldCoverageCountsAsSuccess"] is False
    assert result["contractsClosed"] == 0
    assert result["parameterConsumerChanged"] is False
    event_req = next(r for r in planned["requests"] if r["scope"] == "EVENT")
    verdict = evaluate_request(event_req, BundleProvider(dest / "evidence_bundle.jsonl").all_claims())
    assert verdict["complete"] is False
    assert "EVIDENCE_CLAIM" in verdict["missing"] or verdict["claimCount"] == 0


def test_one_event_observation_fans_out_and_changes_parameter_consumers(tmp_path: Path):
    dest, rows, planned, actions = _board_context(tmp_path)
    event_action = next(a for a in actions["actions"] if a["scope"] == "EVENT")
    assert int(event_action.get("dependentOfferCount") or 0) > 1

    batch = build_next_research_batch(planned["requests"], rows=rows, max_entities=25)
    task = next(t for t in batch["tasks"] if t.get("scope") == "EVENT")
    assert task["actionId"] == event_action["actionId"]
    assert task["sourceFamily"]
    assert task["sourceCandidates"]
    assert "Acquire one permitted public-source observation" in task["acquisitionInstruction"]

    obs = _event_observation(event_action, typed=True)
    assert has_valid_field_coverage(assemble_claim_value(obs))
    obs_path = tmp_path / "event_obs.jsonl"
    obs_path.write_text(json.dumps(obs) + "\n", encoding="utf-8")

    # Before: no EVENT scope in snapshots.
    before = build_parameter_snapshot(rows[0], [])
    assert "EVENT" not in (before.get("scopes_used") or [])

    result = import_observations(dest, obs_path)
    assert result["imported"] == 1
    assert result["rejected"] == 0
    assert result["oneSourceMultipleOffers"] is True
    assert result["maxFanout"] >= 8
    assert result["contractsClosed"] >= 1
    assert result["parameterConsumerChanged"] is True
    assert result["changedOfferCount"] >= 2
    assert (dest / "parameters" / "source_aware_import_ablation.json").is_file()
    assert (dest / "parameters" / "source_aware_import_snapshots.json").is_file()
    assert (dest / "source_aware_import_result.json").is_file()

    event_req = next(r for r in planned["requests"] if r["scope"] == "EVENT")
    claims = BundleProvider(dest / "evidence_bundle.jsonl").all_claims()
    assert evaluate_request(event_req, claims)["complete"] is True
    claim = claims[0]
    assert claim["claim_hash"]
    assert claim["parser_version"] == "host-obs-v1-synthetic"
    assert claim.get("actionId") == event_action["actionId"]
    assert claim["claim_value"]["_fieldUnits"]["scheduled_start"] == "iso8601"
    assert claim["claim_value"]["_fieldProvenance"]["venue"] == "venue_block"

    after = build_parameter_snapshot(rows[0], claims)
    assert "EVENT" in (after.get("scopes_used") or [])
    assert after["parameter_snapshot_hash"] != before["parameter_snapshot_hash"]
    # Fanout: same event claim serves every offer on the board.
    changed_ids = set(result["ablation"]["changedOfferIds"])
    assert len(changed_ids) >= 2
    for row in rows[:3]:
        snap = build_parameter_snapshot(row, claims)
        assert "EVENT" in (snap.get("scopes_used") or [])


def test_idempotent_reimport_does_not_duplicate_claims(tmp_path: Path):
    dest, rows, planned, actions = _board_context(tmp_path)
    event_action = next(a for a in actions["actions"] if a["scope"] == "EVENT")
    obs_path = tmp_path / "event_obs.jsonl"
    obs_path.write_text(json.dumps(_event_observation(event_action)) + "\n", encoding="utf-8")
    first = execute_source_aware_observations(dest, obs_path)
    second = execute_source_aware_observations(dest, obs_path)
    assert first["imported"] == 1
    # Second pass dedupes against the bundle; claimCount stays stable.
    claims = BundleProvider(dest / "evidence_bundle.jsonl").all_claims()
    assert len(claims) == 1
    assert second["claimCount"] == 1


def test_observation_to_claim_rejects_empty_data():
    with pytest.raises(ValueError, match="EMPTY_FIELD_COVERAGE"):
        observation_to_claim(
            {
                "sourceUrl": "https://example.com/x",
                "retrievedAt": "2026-09-01T12:00:00Z",
                "entityRef": {"kind": "EVENT", "id": "E1"},
                "data": {},
            },
            cutoff=CUTOFF,
        )


def test_research_store_sport_is_not_semantic_scope(tmp_path: Path):
    """put_claim must store sport separately from entityKind (scope kind)."""
    dest, rows, planned, actions = _board_context(tmp_path)
    event_action = next(a for a in actions["actions"] if a["scope"] == "EVENT")
    obs_path = tmp_path / "event_obs.jsonl"
    obs_path.write_text(json.dumps(_event_observation(event_action, typed=True)) + "\n", encoding="utf-8")
    result = execute_source_aware_observations(dest, obs_path)
    assert result["imported"] == 1
    assert result["stored"], "expected ResearchStore pointers"
    pointer = result["stored"][0]
    scope_kinds = {"EVENT", "SUBJECT", "AFFILIATION", "COUNTERPARTY", "PLAYER", "TEAM", "ENVIRONMENT"}
    assert pointer["sport"] not in scope_kinds
    assert str(pointer["sport"]).upper() not in scope_kinds
    assert pointer["entityKind"] == "EVENT"
    assert result.get("sport") not in scope_kinds
    # CFB fixture boards resolve sport from row league / family.
    assert str(result["sport"]).upper() in {"CFB", "GRIDIRON"} or result["sport"] == "gridiron"


def test_invalidate_descendants_spares_unrelated_offer_parameters():
    from dcm.runtime.dag import Dag

    dag = Dag(
        cutoff=CUTOFF,
        config_hash="source-aware-import",
        schema_version="v1",
        source_versions={"parser": "test"},
    )
    claim = dag.add("EVIDENCE_CLAIM", "c1")
    dag.complete(claim.key, "c1")
    p_touch = dag.add("PARAMETER", "offer-touch", parents=[claim.key])
    dag.complete(p_touch.key, "pt")
    w_touch = dag.add("EVENT_WORLDS", "event-touch", parents=[p_touch.key])
    dag.complete(w_touch.key, "wt")
    g_touch = dag.add("GRADE", "offer-touch", parents=[p_touch.key, w_touch.key])
    dag.complete(g_touch.key, "gt")

    p_other = dag.add("PARAMETER", "offer-other", parents=[claim.key])
    dag.complete(p_other.key, "po")
    w_other = dag.add("EVENT_WORLDS", "event-other", parents=[p_other.key])
    dag.complete(w_other.key, "wo")
    g_other = dag.add("GRADE", "offer-other", parents=[p_other.key, w_other.key])
    dag.complete(g_other.key, "go")

    hit = dag.invalidate([p_touch.key], include_roots=True)
    assert p_touch.key in hit
    assert w_touch.key in hit
    assert g_touch.key in hit
    assert dag.nodes[p_other.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[w_other.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[g_other.key].state == "COMPLETE_VERIFIED"
    assert p_other.key not in hit
    assert g_other.key not in hit
    # Legacy alias still works and stays ID-scoped
    dag2 = Dag.from_snapshot(dag.snapshot())
    # restore other lineage to COMPLETE for alias check on a fresh touch
    claim2 = dag2.add("EVIDENCE_CLAIM", "c2")
    dag2.complete(claim2.key, "c2")
    p2 = dag2.add("PARAMETER", "offer-touch-2", parents=[claim2.key])
    dag2.complete(p2.key, "p2")
    g2o = [n for n in dag2.nodes.values() if n.identity == "offer-other" and n.node_type == "GRADE"][0]
    assert g2o.state == "COMPLETE_VERIFIED"
    hit2 = dag2.invalidate_descendants([p2.key], include_roots=True)
    assert p2.key in hit2
    assert g2o.key not in hit2


def test_source_aware_import_uses_indexes_and_consumer_beyond_snapshot(tmp_path: Path):
    dest, rows, planned, actions = _board_context(tmp_path)
    # Seed an unrelated PARAMETER lineage in a prior DAG artifact so execute
    # loads it and must not blanket-invalidate by type.
    from dcm.runtime.dag import Dag

    prior = Dag(
        cutoff=CUTOFF,
        config_hash="source-aware-import",
        schema_version="v1",
        source_versions={"parser": "host-observation-v1"},
    )
    other = prior.add("PARAMETER", "UNRELATED_OFFER_XYZ")
    prior.complete(other.key, "other-param")
    other_w = prior.add("EVENT_WORLDS", "UNRELATED_EVENT", parents=[other.key])
    prior.complete(other_w.key, "other-world")
    other_g = prior.add("GRADE", "UNRELATED_OFFER_XYZ", parents=[other.key, other_w.key])
    prior.complete(other_g.key, "other-grade")
    write_json(dest / "source_aware_import_dag.json", prior.snapshot())

    event_action = next(a for a in actions["actions"] if a["scope"] == "EVENT")
    obs_path = tmp_path / "event_obs.jsonl"
    obs_path.write_text(json.dumps(_event_observation(event_action, typed=True)) + "\n", encoding="utf-8")
    result = execute_source_aware_observations(dest, obs_path)
    assert result["imported"] == 1
    assert result["parameterConsumerChanged"] is True
    assert result["materialOrFeatureConsumerChanged"] is True
    consumer = result["consumer"]
    assert consumer["materialOrFeatureChanged"] is True
    assert "ParameterSnapshot.hash" in consumer["proven"]
    assert "facts_to_features" in " ".join(consumer["proven"])
    assert (dest / "parameters" / "source_aware_import_consumer.json").is_file()

    # Unrelated prior PARAMETER lineage must survive scoped invalidation.
    dag_snap = json.loads((dest / "source_aware_import_dag.json").read_text(encoding="utf-8"))
    by_key = {n["key"]: n for n in dag_snap["nodes"]}
    assert by_key[other.key]["state"] == "COMPLETE_VERIFIED"
    assert by_key[other_g.key]["state"] == "COMPLETE_VERIFIED"
    assert (dest / "runtime_dag.json").is_file()
    runtime_snap = json.loads((dest / "runtime_dag.json").read_text(encoding="utf-8"))
    assert runtime_snap.get("children") is not None
    runtime_by_key = {n["key"]: n for n in runtime_snap["nodes"]}
    assert runtime_by_key[other.key]["state"] == "COMPLETE_VERIFIED"
    assert runtime_by_key[other_g.key]["state"] == "COMPLETE_VERIFIED"
    # Touched offers install claim→fact→feature→parameter lineage
    assert any(n.get("nodeType") == "FACT" for n in runtime_snap["nodes"])
    assert any(n.get("nodeType") == "FEATURE" for n in runtime_snap["nodes"])
    # Touched grade/world nodes should be invalidated.
    invalidated = set(result["invalidatedDescendants"])
    assert invalidated
    assert other.key not in invalidated

    # BoardIndexes queried with downstream_used (HOT_HASH_INDEX QUERIED).
    telem = result.get("indexTelemetry") or {}
    executions = telem.get("executions") or telem.get("algorithms") or []
    if isinstance(telem, dict) and not executions:
        # snapshot shape: executions list under "executions"
        executions = telem.get("executions") or []
    queried_downstream = [
        row
        for row in executions
        if str(row.get("phase") or "") == "QUERIED" and row.get("downstream_used")
    ]
    assert queried_downstream, f"expected BoardIndexes QUERIED+downstream_used telemetry, got {telem}"


def test_closed_loop_observation_reschedules_and_shrinks_next_batch(tmp_path: Path):
    """incomplete → acquisition → observation → coverage → CELF next batch shrinks."""
    dest, rows, planned, actions = _board_context(tmp_path)
    event_action = next(a for a in actions["actions"] if a["scope"] == "EVENT")
    before_batch = build_next_research_batch(
        planned["requests"],
        rows=rows,
        max_entities=25,
    )
    assert before_batch["liveSelector"] == "ALG-SCHED-001"
    assert before_batch["unresolvedCount"] >= 1
    assert any(t.get("actionId") == event_action["actionId"] for t in before_batch["tasks"])
    action_count_before = int(actions["actionCount"] or 0)
    assert action_count_before >= 1

    obs_path = tmp_path / "event_obs.jsonl"
    obs_path.write_text(json.dumps(_event_observation(event_action, typed=True)) + "\n", encoding="utf-8")
    result = execute_source_aware_observations(dest, obs_path)

    assert result["imported"] == 1
    assert result["contractsClosed"] >= 1
    assert result["liveSelector"] == "ALG-SCHED-001"
    assert result["celfDownstreamUsed"] is True
    assert "ALG-SCHED-001" in (result.get("closedLoopTelemetry") or {}).get("algorithmIds", [])
    assert result["actionCountAfter"] < result["actionCountBefore"]
    assert result["unresolvedAfter"] < result["unresolvedBefore"]
    assert result["nextBatchShrunk"] is True
    assert (dest / "acquisition_action_graph.json").is_file()
    assert (dest / "acquisition_schedule.json").is_file()
    assert (dest / "material_facts.json").is_file()
    assert (dest / "host_research_batch.json").is_file()
    assert (dest / "closed_loop_algorithm_telemetry.json").is_file()

    graph = json.loads((dest / "acquisition_action_graph.json").read_text(encoding="utf-8"))
    assert graph["schema"] == "pillars_dcm.acquisition_action_graph.v1"
    assert graph["liveSelector"] == "ALG-SCHED-001"
    assert graph["actionCount"] == result["actionCountAfter"]
    assert any(e["type"] == "covers" for e in graph["edges"])

    schedule = json.loads((dest / "acquisition_schedule.json").read_text(encoding="utf-8"))
    assert schedule["liveSelector"] == "ALG-SCHED-001"
    assert schedule.get("celfActionIds") is not None

    telem = json.loads((dest / "closed_loop_algorithm_telemetry.json").read_text(encoding="utf-8"))
    celf = [
        row
        for row in (telem.get("executions") or [])
        if str(row.get("algorithm_id") or row.get("algorithmId") or "") == "ALG-SCHED-001" and row.get("downstream_used")
    ]
    assert celf, f"expected CELF downstream_used telemetry, got {telem}"

    after_batch = json.loads((dest / "host_research_batch.json").read_text(encoding="utf-8"))
    assert after_batch["liveSelector"] == "ALG-SCHED-001"
    assert after_batch["unresolvedCount"] < before_batch["unresolvedCount"]
    assert after_batch["unresolvedCount"] == result["nextBatchUnresolvedCount"]
    # Closed EVENT requirement must not reappear as an acquire task.
    assert not any(
        t.get("actionId") == event_action["actionId"] and t.get("scope") == "EVENT"
        for t in after_batch.get("tasks") or []
    )
