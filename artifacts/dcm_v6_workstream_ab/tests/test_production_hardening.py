from __future__ import annotations

import random

from dcm.ingest.board import rows_as_of
from dcm.ingest.prizepicks import _side
from dcm.model.line_surface import surface
from dcm.model.parameters import build_parameter_snapshot
from dcm.model.uncertainty import evidence_safe_probability
from dcm.model.worlds import generate_event_contexts, simulate_player_worlds
from dcm.research.provider import FixtureProvider, collect
from dcm.runtime.governor import Governor
from dcm.selection.portfolio import build_card


def test_missing_offered_side_fails_closed():
    side, more, less = _side({"line_score": 20.5, "stat_type": "Points", "odds_type": "standard"})
    assert side == "UNKNOWN"
    assert more is False and less is False
    side, more, less = _side({"odds_type": "goblin"})
    assert (side, more, less) == ("MORE", True, False)


def test_asof_board_excludes_post_cutoff_snapshot():
    ingest = {
        "rowHistory": {
            "p1": [
                {"projectionId": "p1", "line": 10.5, "sourceSnapshotTime": "2026-08-28T10:00:00Z", "sourceUpdatedAt": "2026-08-28T10:00:00Z"},
                {"projectionId": "p1", "line": 12.5, "sourceSnapshotTime": "2026-08-28T12:00:00Z", "sourceUpdatedAt": "2026-08-28T12:00:00Z"},
            ]
        }
    }
    rows, stats = rows_as_of(ingest, "2026-08-28T11:00:00Z")
    assert rows[0]["line"] == 10.5
    assert stats["post_cutoff_snapshots_excluded"] == 1


def test_fixture_research_is_never_production_ready():
    reqs = [{"request_id": "x", "scope": "PLAYER", "scope_id": "p", "need": "status_role_logs_opportunity_efficiency", "forecast_cutoff": "2026-08-28T10:00:00Z"}]
    bundle = collect(reqs, FixtureProvider("2026-08-28T10:00:00Z"))
    assert bundle["complete"] is True
    assert bundle["production_ready"] is False
    assert bundle["fixture_claims"] == 1


def _claim(scope, scope_id, value, h):
    return {
        "semantic_scope": scope, "scope_id": scope_id, "claim_value": value,
        "source_id": "OFFICIAL", "reliability": 0.95, "freshness": 0.95, "claim_hash": h,
        "observed_at": "2026-08-28T10:00:00Z",
    }


def test_real_evidence_parameterizes_worlds_and_separates_opportunity_efficiency():
    row = {
        "sportFamily": "basketball", "league": "NBA", "eventId": "E", "playerId": "P",
        "teamId": "T", "projectionId": "X", "market": "pts", "role": "F",
    }
    logs = [{"minutes": 36, "fga": 20, "tpa": 8, "fta": 5, "reb": 9, "ast": 6} for _ in range(8)]
    claims = [
        _claim("PLAYER", "P", {"status": "ACTIVE", "game_logs": logs, "opportunity": {"support_n": 8}, "efficiency": {"support_n": 8}}, "a"),
        _claim("TEAM", "T", {"pace_multiplier": 1.03, "matchup_efficiency_multiplier": 1.01}, "b"),
        _claim("EVENT", "E", {}, "c"),
        _claim("MARKET", "X", {"definition_verified": True}, "d"),
    ]
    snap = build_parameter_snapshot(row, claims)
    assert snap["production_eligible"] is True
    assert snap["opportunity"]["support_n"] >= 8
    assert snap["efficiency"]["support_n"] >= 8
    worlds = simulate_player_worlds(row, n=64, seed="x", parameter_snapshot=snap)
    assert all(abs(w["pra"] - (w["pts"] + w["reb"] + w["ast"])) < 1e-9 for w in worlds)


def test_synthetic_probability_is_heavily_shrunk():
    assert evidence_safe_probability(0.70, support_n=0, data_quality=0.2, ood_risk=0.8, synthetic=True) < 0.55


def test_directional_line_surface_and_shared_dependency_constraint():
    values = list(range(101))
    more = surface(values, 40.0, side="MORE")
    less = surface(values, 60.0, side="LESS")
    assert more["side"] == "MORE" and less["side"] == "LESS"
    assert more["true_unclamped_line_tolerance"] >= 0
    assert less["true_unclamped_line_tolerance"] >= 0

    def p(pid, event, team, tags):
        return {"grade": "PLAYABLE", "dependencyTags": tags, "row": {"playerId": pid, "eventId": event, "teamId": team, "market": "pts", "modifier": "STANDARD"}}
    card = build_card([
        p("A", "E1", "T1", ["QBUNIT:T1:Q"]),
        p("B", "E2", "T1", ["QBUNIT:T1:Q"]),
        p("C", "E3", "T2", []),
    ])
    assert [x["row"]["playerId"] for x in card] == ["A", "C"]


def test_event_start_is_not_market_updated_at():
    from dcm.ingest.prizepicks import parse_prizepicks_payload
    payload = {
        "data": [{
            "id": "x1", "type": "projection",
            "attributes": {
                "line_score": 10.5, "stat_type": "Points", "odds_type": "standard",
                "updated_at": "2026-08-28T10:00:00Z", "start_time": "2026-08-29T02:00:00Z",
                "offered_higher": True, "offered_lower": True,
            },
            "relationships": {
                "new_player": {"data": {"id": "p1", "type": "new_player"}},
                "league": {"data": {"id": "l1", "type": "league"}},
                "new_game": {"data": {"id": "g1", "type": "new_game"}},
            },
        }],
        "included": [
            {"id": "p1", "type": "new_player", "attributes": {"display_name": "P", "team": "AAA"}},
            {"id": "l1", "type": "league", "attributes": {"name": "NBA", "sport": "Basketball"}},
            {"id": "g1", "type": "new_game", "attributes": {"home_name": "AAA", "away_name": "BBB"}},
        ],
    }
    _, rows = parse_prizepicks_payload(payload)
    assert rows[0]["sourceUpdatedAt"] == "2026-08-28T10:00:00Z"
    assert rows[0]["eventStartTime"] == "2026-08-29T02:00:00Z"


def test_schema_gate_rejects_reconstruction_hash(tmp_path):
    from dcm.runtime.schema_root import verify_schema
    p = tmp_path / "Phase_BC_Immutable_Contracts.json"
    p.write_text('{"reconstruction": true}', encoding="utf-8")
    import os
    old = os.environ.get("DCM_PHASE_BC_SCHEMA")
    os.environ["DCM_PHASE_BC_SCHEMA"] = str(p)
    try:
        state = verify_schema(tmp_path)
    finally:
        if old is None:
            os.environ.pop("DCM_PHASE_BC_SCHEMA", None)
        else:
            os.environ["DCM_PHASE_BC_SCHEMA"] = old
    assert state["productionEligible"] is False
    assert state["state"] == "HASH_MISMATCH_RECONSTRUCTION_NOT_CANONICAL"


def test_event_contexts_are_shared_by_event_not_player():
    a = generate_event_contexts("basketball", "E1", n=16, seed="HAR")
    b = generate_event_contexts("basketball", "E1", n=16, seed="HAR")
    c = generate_event_contexts("basketball", "E2", n=16, seed="HAR")
    assert a == b
    assert a != c
    assert len(a) == 16


def test_portfolio_rejects_highly_correlated_simulated_selection_outcomes():
    def candidate(pid, event, outcomes):
        return {
            "grade": "PLAYABLE",
            "_selectionOutcomes": bytes(outcomes),
            "dependencyTags": [f"EVENT:{event}"],
            "row": {
                "projectionId": pid,
                "playerId": pid,
                "eventId": event,
                "teamId": pid,
                "market": "pts",
                "modifier": "STANDARD",
            },
        }
    pattern = [2, 2, 0, 2, 0, 0, 2, 2] * 8
    inverse = [0 if x == 2 else 2 if x == 0 else 1 for x in pattern]
    card = build_card([
        candidate("A", "E1", pattern),
        candidate("B", "E1", pattern),
        candidate("C", "E2", inverse),
    ])
    assert [x["row"]["projectionId"] for x in card] == ["A", "C"]


def test_adaptive_governor_escalates_only_serious_production_candidates():
    gov = Governor(fast_worlds=256, serious_worlds=2048, ceiling_worlds=8192, mc_se_target=0.008)
    assert gov.next_world_count(
        current=256, selected_probability=0.59, decision_threshold=0.58,
        production_selectable=False,
    ) == 256
    assert gov.next_world_count(
        current=256, selected_probability=0.59, decision_threshold=0.58,
        production_selectable=True,
    ) == 2048
    assert gov.next_world_count(
        current=2048, selected_probability=0.59, decision_threshold=0.58,
        production_selectable=True,
    ) == 4096
    assert gov.next_world_count(
        current=4096, selected_probability=0.59, decision_threshold=0.58,
        production_selectable=True,
    ) == 4096
