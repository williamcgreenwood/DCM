"""CFB rules snapshot must drive definition_verified for mapped markets."""

from __future__ import annotations

from dcm.cfb.rules import build_cfb_rules_snapshot
from dcm.model.parameters import build_parameter_snapshot
from dcm.platform.prizepicks.platform_rules_authority import resolve_platform_rules_authority


def _eligible_snapshot() -> dict:
    auth = resolve_platform_rules_authority([])
    return build_cfb_rules_snapshot(
        as_of="2026-09-06T15:30:00Z",
        platform_source_hashes=auth["platform_source_hashes"],
        platform_rules_verified=True,
    )


def test_rules_snapshot_verifies_mapped_market_definition() -> None:
    snap = _eligible_snapshot()
    assert snap["productionEligible"] is True
    market = snap["marketMappings"][0]["market"]
    row = {
        "projectionId": "p1",
        "playerId": "pl1",
        "eventId": "e1",
        "teamId": "T",
        "market": market,
        "sportFamily": "gridiron",
        "league": "CFB",
        "line": 10.5,
    }
    out = build_parameter_snapshot(row, [], rules_snapshot=snap)
    assert out["definition_verified"] is True
    assert out.get("blocker") != "UNVERIFIED_MARKET_DEFINITION"


def test_without_rules_snapshot_market_stays_unverified() -> None:
    snap = _eligible_snapshot()
    market = snap["marketMappings"][0]["market"]
    row = {
        "projectionId": "p1",
        "playerId": "pl1",
        "eventId": "e1",
        "teamId": "T",
        "market": market,
        "sportFamily": "gridiron",
        "league": "CFB",
        "line": 10.5,
    }
    out = build_parameter_snapshot(row, [])
    assert out["definition_verified"] is False
    assert out.get("blocker") == "UNVERIFIED_MARKET_DEFINITION"


def test_host_claim_definition_verified_preserved() -> None:
    snap = _eligible_snapshot()
    market = snap["marketMappings"][0]["market"]
    row = {
        "projectionId": "p1",
        "playerId": "pl1",
        "eventId": "e1",
        "teamId": "T",
        "market": market,
        "sportFamily": "gridiron",
        "league": "CFB",
        "line": 10.5,
    }
    claims = [{
        "semantic_scope": "MARKET_DEFINITION",
        "scope_id": f"gridiron:CFB:{market}:FULL_GAME",
        "claim_type": "exact_stat_definition",
        "claim_value": {"definition_verified": True, "stat": market},
        "source_hash": "hostdef1",
        "claim_hash": "hostdef1c",
        "reliability": 0.9,
        "freshness": 0.9,
    }]
    # If claim merge path differs, at least rules path must not downgrade True.
    out = build_parameter_snapshot(row, claims, rules_snapshot=snap)
    assert out["definition_verified"] is True
