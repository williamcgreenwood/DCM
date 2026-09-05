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

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cfb_guarded_launch_har.json"
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
