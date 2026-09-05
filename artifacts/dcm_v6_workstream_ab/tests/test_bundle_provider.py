from pathlib import Path

from dcm.research.claims import claim_record
from dcm.research.provider import BundleProvider, collect, write_bundle
from dcm.research.requests import build_requests


def test_bundle_provider_roundtrip_hashes(tmp_path: Path):
    cutoff = "2026-08-28T12:00:00Z"
    claim = claim_record(
        source_id="OFFICIAL_TEST",
        url="https://www.wnba.com/example",
        published_at="2026-08-27T00:00:00Z",
        observed_at="2026-08-27T12:00:00Z",
        forecast_cutoff=cutoff,
        semantic_scope="SPORT",
        scope_id="basketball:WNBA",
        claim_type="rules_calendar_distribution",
        claim_value={"distribution_family": "count", "overtime": "INCLUDE_FULL_GAME"},
        reliability=0.9,
        freshness=0.8,
    )
    path = tmp_path / "evidence_bundle.jsonl"
    provider = write_bundle(path, [claim])
    again = BundleProvider(path)
    req = {
        "request_id": "x",
        "scope": "SPORT",
        "scope_id": "basketball:WNBA",
        "need": "rules_calendar_distribution",
        "forecast_cutoff": cutoff,
    }
    got = again.resolve(req)
    assert len(got) == 1
    assert got[0]["claim_hash"] == claim["claim_hash"]
    assert got[0]["source_hash"] == claim["source_hash"]
    m1 = provider.manifest()
    m2 = again.manifest()
    assert m1["bundle_hash"] == m2["bundle_hash"]
    assert m1["contentHash"] == m2["contentHash"]


def test_market_definition_split_reuses_across_offers():
    rows = [
        {
            "projectionId": "a", "sportFamily": "basketball", "league": "WNBA",
            "eventId": "E1", "teamId": "T", "playerId": "P1", "playerName": "A",
            "market": "pts", "line": 20.5, "boardId": "FULL_GAME", "modifier": "STANDARD",
            "eventLabel": "x", "status": "pre_game", "offeredHigher": True, "offeredLower": True,
            "side": "MORE",
        },
        {
            "projectionId": "b", "sportFamily": "basketball", "league": "WNBA",
            "eventId": "E1", "teamId": "T", "playerId": "P2", "playerName": "B",
            "market": "pts", "line": 18.5, "boardId": "FULL_GAME", "modifier": "STANDARD",
            "eventLabel": "x", "status": "pre_game", "offeredHigher": True, "offeredLower": True,
            "side": "MORE",
        },
    ]
    reqs = build_requests(rows, "2026-08-28T00:00:00Z")
    defs = [r for r in reqs if r["scope"] == "MARKET_DEFINITION"]
    offers = [r for r in reqs if r["scope"] == "OFFER"]
    assert len(defs) == 1
    assert len(offers) == 2
    assert not any(r["scope"] == "MARKET" for r in reqs)
