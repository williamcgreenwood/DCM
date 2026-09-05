"""Canonical planner emits SUBJECT/AFFILIATION/COUNTERPARTY, not PLAYER/TEAM."""
from __future__ import annotations

from dcm.model.parameters import build_parameter_snapshot
from dcm.research.claims import claim_record
from dcm.research.classify import market_definition_id
from dcm.research.requests import plan_research
from dcm.research.scopes import claims_for, canonical_scope
from dcm.research.universal_packets import build_universal_packets
from dcm.research.player_offer_set import build_player_offer_sets

CUTOFF = "2026-08-30T12:00:00Z"


def _row():
    return {
        "projectionId": "p1",
        "playerId": "PAIGE",
        "playerName": "Paige",
        "sportFamily": "basketball",
        "league": "WNBA",
        "team": "DAL",
        "teamId": "DAL",
        "opponent": "CON",
        "eventId": "E1",
        "market": "pts",
        "line": 18.5,
        "modifier": "STANDARD",
        "offeredHigher": True,
        "offeredLower": True,
        "boardId": "FULL_GAME",
        "status": "pre_game",
    }


def _claim(scope, scope_id, value):
    return claim_record(
        source_id="TEST_FROZEN_OFFICIAL",
        url="https://www.wnba.com/test",
        published_at="2026-08-29T00:00:00Z",
        observed_at="2026-08-29T12:00:00Z",
        forecast_cutoff=CUTOFF,
        semantic_scope=scope,
        scope_id=scope_id,
        claim_type="x",
        claim_value=value,
        reliability=0.8,
        freshness=0.7,
    )


def test_plan_research_emits_universal_scopes_only():
    planned = plan_research([_row()], CUTOFF)
    scopes = {r["scope"] for r in planned["requests"]}
    assert "SUBJECT" in scopes
    assert "AFFILIATION" in scopes
    assert "COUNTERPARTY" in scopes
    assert "ENVIRONMENT" in scopes
    assert "COMPETITION" in scopes
    assert "PLAYER" not in scopes
    assert "TEAM" not in scopes
    assert planned["adapterScopesEmitted"] is False
    aff = next(r for r in planned["requests"] if r["scope"] == "AFFILIATION")
    opp = next(r for r in planned["requests"] if r["scope"] == "COUNTERPARTY")
    assert aff["scope_id"] == "DAL"
    assert opp["scope_id"] == "CON"


def test_subject_claims_alias_player_lookup():
    claims = [_claim("SUBJECT", "PAIGE", {"status": "ACTIVE", "role": "starter"})]
    found = claims_for(claims, "PLAYER", "PAIGE")
    assert len(found) == 1
    assert canonical_scope("PLAYER") == "SUBJECT"


def test_parameter_snapshot_accepts_subject_affiliation_claims():
    row = _row()
    def_id = market_definition_id(row)
    claims = [
        _claim("SPORT", "basketball:WNBA", {"distribution_family": "count"}),
        _claim("COMPETITION", "basketball:WNBA", {"competition_context": True}),
        _claim("EVENT", "E1", {"starters_known": True, "environment": "indoor", "scheduled_start": "2026-08-30T00:00:00Z"}),
        _claim("ENVIRONMENT", "env:E1", {"environment_context": True, "venue": "arena"}),
        _claim("AFFILIATION", "DAL", {"pace_multiplier": 1.02, "matchup_efficiency_multiplier": 1.0}),
        _claim("COUNTERPARTY", "CON", {"pace_multiplier": 1.01}),
        _claim(
            "SUBJECT",
            "PAIGE",
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
        _claim("OFFER", "p1", {"offer_recorded": True, "line": 18.5}),
    ]
    snap = build_parameter_snapshot(row, claims)
    assert "SUBJECT" in snap["scopes_used"]
    assert "AFFILIATION" in snap["scopes_used"]
    assert "layers" in snap
    assert snap["layers"]["subject"]["subjectId"] == "PAIGE"
    assert snap["layers"]["availability"]
    assert snap["parameter_snapshot_hash"]


def test_universal_packets_wrap_player_team_compat():
    sets = build_player_offer_sets([_row()])
    claims = [
        _claim("AFFILIATION", "DAL", {"team_logs": [{"date_game": "2026-06-01", "pts": 80, "opp_pts": 70, "fga": 60, "fta": 20, "tov": 12, "oreb": 8}]}),
        _claim("EVENT", "E1", {"scheduled_start": "2026-08-30T21:30:00Z", "venue": "CPC", "environment": "indoor"}),
    ]
    docs = build_universal_packets(sets, claims=claims, as_of=CUTOFF)
    assert docs["subjectPacketCount"] >= 1
    assert docs["affiliationPacketCount"] >= 1
    assert docs["eventPacketCount"] >= 1
    assert docs["environmentPacketCount"] >= 1
    assert docs["subjects"][0]["subjectId"] == "PAIGE"
    assert docs["canonical"] is True
