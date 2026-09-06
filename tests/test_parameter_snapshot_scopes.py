from __future__ import annotations

from dcm.model.parameters import build_parameter_snapshot
from dcm.research.claims import claim_record
from dcm.research.classify import market_definition_id

CUTOFF = "2026-08-28T12:00:00Z"


def _claim(scope: str, scope_id: str, value: dict, need: str = "x") -> dict:
    return claim_record(
        source_id="TEST_FROZEN_OFFICIAL",
        url="https://www.wnba.com/test-frozen",
        published_at="2026-08-27T00:00:00Z",
        observed_at="2026-08-27T12:00:00Z",
        forecast_cutoff=CUTOFF,
        semantic_scope=scope,
        scope_id=scope_id,
        claim_type=need,
        claim_value=value,
        reliability=0.8,
        freshness=0.7,
    )


def test_snapshot_builds_from_market_definition_and_offer_without_legacy_market():
    row = {
        "projectionId": "p1",
        "sportFamily": "basketball",
        "league": "WNBA",
        "eventId": "E1",
        "teamId": "T1",
        "playerId": "PL1",
        "market": "pts",
        "boardId": "FULL_GAME",
        "line": 20.5,
        "role": "G",
    }
    def_id = market_definition_id(row)
    claims = [
        _claim("SPORT", "basketball:WNBA", {"distribution_family": "count", "overtime": "INCLUDE_FULL_GAME"}),
        _claim("EVENT", "E1", {"starters_known": True, "environment": "indoor", "scheduled_start": "2026-08-28T00:00:00Z"}),
        _claim("TEAM", "T1", {"pace_multiplier": 1.02, "matchup_efficiency_multiplier": 1.0}),
        _claim(
            "PLAYER",
            "PL1",
            {
                "status": "ACTIVE",
                "role": "starter",
                "opportunity": {"support_n": 5, "minutes_mean": 32.0},
                "efficiency": {"support_n": 5, "fga_per_min": 0.5},
                "role_epoch_logs": [
                    {"minutes": 30, "fga": 14, "reb": 6, "ast": 4},
                    {"minutes": 32, "fga": 16, "reb": 5, "ast": 5},
                    {"minutes": 34, "fga": 15, "reb": 7, "ast": 3},
                ],
            },
        ),
        _claim("MARKET_DEFINITION", def_id, {"definition_verified": True, "stat": "points"}),
        _claim("OFFER", "p1", {"offer_recorded": True, "line": 20.5, "offeredHigher": True, "offeredLower": True}),
    ]
    assert not any(c["semantic_scope"] == "MARKET" for c in claims)
    snap = build_parameter_snapshot(row, claims)
    assert snap["definition_verified"] is True
    assert "MARKET_DEFINITION" in snap["scopes_used"]
    assert "OFFER" in snap["scopes_used"]
    assert "MARKET" not in snap["scopes_used"]
    assert snap["legacy_market_fallback"] is False
    assert snap["parameter_snapshot_hash"]
