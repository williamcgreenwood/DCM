from __future__ import annotations

import random

from dcm.ingest.board import rows_as_of
from dcm.ingest.prizepicks import _side
from dcm.model.line_surface import surface
from dcm.model.parameters import build_parameter_snapshot
from dcm.model.uncertainty import evidence_safe_probability
from dcm.model.worlds import simulate_player_worlds
from dcm.research.provider import FixtureProvider, collect
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
