"""Host claim log aliases must feed football opportunity support."""

from __future__ import annotations

from dcm.model.parameters import _collect_player_game_logs, build_parameter_snapshot


def test_collect_game_logs_sample_2025_alias() -> None:
    player = {
        "status": "ACTIVE",
        "role": "QB",
        "game_logs": [],
        "game_logs_sample_2025": [
            {"date": "2025-09-01", "pass_att": 30, "pass_yds": 250, "pass_td": 2},
            {"date": "2025-09-08", "pass_att": 28, "pass_yds": 210, "pass_td": 1},
            {"date": "2025-09-15", "pass_att": 32, "pass_yds": 275, "pass_td": 3},
        ],
    }
    logs = _collect_player_game_logs(player)
    assert len(logs) == 3
    assert logs[0]["pass_att"] == 30


def test_parameter_snapshot_uses_sample_logs_for_support() -> None:
    row = {
        "projectionId": "p1",
        "playerId": "pl1",
        "eventId": "e1",
        "teamId": "T",
        "market": "pass_yds",
        "sportFamily": "gridiron",
        "league": "CFB",
        "boardId": "FULL_GAME",
        "line": 220.5,
    }
    claims = [{
        "semantic_scope": "SUBJECT",
        "scope_id": "pl1",
        "claim_type": "HISTORICAL_PERFORMANCE",
        "claim_value": {
            "status": "ACTIVE",
            "role": "QB",
            "game_logs": [],
            "game_logs_sample_2025": [
                {"date": "2025-09-01", "pass_att": 30, "pass_yds": 250},
                {"date": "2025-09-08", "pass_att": 28, "pass_yds": 210},
                {"date": "2025-09-15", "pass_att": 32, "pass_yds": 275},
            ],
        },
        "source_hash": "s1",
        "claim_hash": "c1",
        "reliability": 0.9,
        "freshness": 0.9,
    }]
    rules = {
        "productionEligible": True,
        "contentHash": "rules1",
        "marketMappings": [{"market": "pass_yds", "verified": True}],
    }
    out = build_parameter_snapshot(row, claims, rules_snapshot=rules)
    assert out["definition_verified"] is True
    assert out["status"] == "ACTIVE"
    support = out.get("model_support") or {}
    assert int(support.get("opportunitySupportN") or 0) >= 3
    assert out.get("blocker") != "MINIMUM_OPPORTUNITY_SUPPORT_MISSING"
