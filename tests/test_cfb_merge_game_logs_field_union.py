"""SUBJECT claim game_logs must field-union by date, not replace.

Cooper Flanagan (250389) regression: earlier claim had rush_att=0 + targets;
later claim had targets only. Plain dict.update replaced the list and dropped
rush_att, so rush_rec_td opportunitySupportN collapsed to 0.
"""

from __future__ import annotations

from dcm.model.parameters import (
    _collect_player_game_logs,
    _merge,
    _union_game_log_lists,
    build_parameter_snapshot,
)
from dcm.sports.football.research_requirements import assess_football_support, support_count


def _rich_logs() -> list[dict]:
    return [
        {"date": "2025-09-06", "rush_att": 0, "targets": 4, "receptions": 3, "rec_yds": 28},
        {"date": "2025-09-13", "rush_att": 0, "targets": 5, "receptions": 4, "rec_yds": 41},
        {"date": "2025-09-20", "rush_att": 0, "targets": 3, "receptions": 2, "rec_yds": 19},
    ]


def _thin_logs() -> list[dict]:
    return [
        {"date": "2025-09-06", "targets": 4, "receptions": 3},
        {"date": "2025-09-13", "targets": 5, "receptions": 4},
        {"date": "2025-09-20", "targets": 3, "receptions": 2},
    ]


def test_union_game_log_lists_retains_rush_att_zero() -> None:
    merged = _union_game_log_lists(_rich_logs(), _thin_logs())
    assert len(merged) == 3
    for row in merged:
        assert row.get("rush_att") == 0
        assert row.get("targets") is not None
    assert support_count(merged, ("rush_att", "targets")) == 3


def test_merge_subject_claims_field_unions_game_logs() -> None:
    pairs = [
        (
            {"observed_at": "2026-09-06T15:27:40Z"},
            {"status": "ACTIVE", "role": "WR", "game_logs": _rich_logs()},
        ),
        (
            {"observed_at": "2026-09-06T15:28:09Z"},
            {"status": "ACTIVE", "role": "WR", "game_logs": _thin_logs()},
        ),
    ]
    merged = _merge(pairs)
    logs = merged["game_logs"]
    assert len(logs) == 3
    assert all(row.get("rush_att") == 0 for row in logs)
    assert all(row.get("targets") is not None for row in logs)
    assert support_count(logs, ("rush_att", "targets")) >= 1


def test_collect_unions_duplicate_dates_across_aliases() -> None:
    player = {
        "game_logs": _thin_logs(),
        "game_logs_sample_2025": _rich_logs(),
    }
    # Collection order prefers game_logs first, then sample — field union must
    # still pick up rush_att=0 from the sample rows with the same dates.
    logs = _collect_player_game_logs(player)
    assert len(logs) == 3
    assert all(row.get("rush_att") == 0 for row in logs)
    assert support_count(logs, ("rush_att", "targets")) == 3


def test_flanagan_rush_rec_td_opportunity_support_retained() -> None:
    row = {
        "projectionId": "pp-250389-td",
        "playerId": "250389",
        "eventId": "evt1",
        "teamId": "TEAM",
        "market": "rush_rec_td",
        "sportFamily": "gridiron",
        "league": "CFB",
        "boardId": "FULL_GAME",
        "line": 0.5,
        "role": "WR",
    }
    claims = [
        {
            "semantic_scope": "SUBJECT",
            "scope_id": "250389",
            "claim_type": "HISTORICAL_PERFORMANCE",
            "claim_value": {
                "status": "ACTIVE",
                "role": "WR",
                "game_logs": _rich_logs(),
            },
            "source_hash": "s-rich",
            "claim_hash": "c-rich",
            "reliability": 0.9,
            "freshness": 0.9,
            "observed_at": "2026-09-06T15:27:40Z",
        },
        {
            "semantic_scope": "SUBJECT",
            "scope_id": "250389",
            "claim_type": "HISTORICAL_PERFORMANCE",
            "claim_value": {
                "status": "ACTIVE",
                "role": "WR",
                "game_logs": _thin_logs(),
            },
            "source_hash": "s-thin",
            "claim_hash": "c-thin",
            "reliability": 0.9,
            "freshness": 0.9,
            "observed_at": "2026-09-06T15:28:09Z",
        },
    ]
    rules = {
        "productionEligible": True,
        "contentHash": "rules-td",
        "marketMappings": [{"market": "rush_rec_td", "verified": True}],
    }
    snap = build_parameter_snapshot(row, claims, rules_snapshot=rules)
    support = snap.get("model_support") or {}
    assert int(support.get("opportunitySupportN") or 0) >= 1

    # Direct assess path with merged player logs (same consumer gap).
    from dcm.model.parameters import _pairs

    merged_player = _merge(_pairs(claims, "SUBJECT", "250389"))
    logs = merged_player["game_logs"]
    assessed = assess_football_support(
        market="rush_rec_td",
        role="WR",
        status="ACTIVE",
        logs=logs,
        definition_verified=True,
        team_event={"playsObserved": True, "pass_defense": 0.5, "rush_defense": 0.5},
    )
    assert assessed["opportunitySupportN"] >= 1
    assert "MINIMUM_OPPORTUNITY_SUPPORT_MISSING" not in assessed["modelBlockers"]
    assert support_count(logs, ("rush_att", "targets")) >= 1
