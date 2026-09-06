"""Forecast must re-merge ResearchStore latest claims into the bundle."""

from __future__ import annotations

from pathlib import Path

from dcm.contracts.hashes import content_hash
from dcm.research.research_store import ResearchStore, merge_latest_store_claims


def test_merge_latest_store_claims_adds_missing_store_claim(tmp_path: Path) -> None:
    store = ResearchStore(tmp_path / "store")
    claim = {
        "semantic_scope": "AFFILIATION",
        "scope_id": "WIS",
        "claim_type": "HISTORICAL_PERFORMANCE",
        "claim_value": {"plays": 60.0, "pace": 0.9, "team": "Wisconsin"},
        "claim_hash": content_hash({"scope": "WIS", "plays": 60.0}),
        "source_hash": "s1",
        "reliability": 0.9,
        "freshness": 0.9,
        "observed_at": "2026-09-06T15:26:00Z",
    }
    store.put_claim(claim, sport="CFB", entity_kind="AFFILIATION", as_of="2026-09-06T15:30:00Z")
    stale = {
        "semantic_scope": "AFFILIATION",
        "scope_id": "WIS",
        "claim_type": "HISTORICAL_PERFORMANCE",
        "claim_value": {"team": "Wisconsin", "paceMatchupNote": "slow"},
        "claim_hash": "stalehash",
        "source_hash": "s0",
        "reliability": 0.5,
        "freshness": 0.5,
        "observed_at": "2026-09-06T15:10:00Z",
    }
    merged = merge_latest_store_claims([stale], store, scopes=[("AFFILIATION", "WIS")])
    assert len(merged) == 2
    assert any((c.get("claim_value") or {}).get("plays") == 60.0 for c in merged)


def test_merge_is_idempotent_on_claim_hash(tmp_path: Path) -> None:
    store = ResearchStore(tmp_path / "store")
    claim = {
        "semantic_scope": "AFFILIATION",
        "scope_id": "ND",
        "claim_type": "HISTORICAL_PERFORMANCE",
        "claim_value": {"plays": 62.0, "pace": 0.92},
        "claim_hash": "samehash",
        "source_hash": "s1",
        "reliability": 0.9,
        "freshness": 0.9,
        "observed_at": "2026-09-06T15:26:00Z",
    }
    store.put_claim(claim, sport="CFB", entity_kind="AFFILIATION", as_of="2026-09-06T15:30:00Z")
    merged = merge_latest_store_claims([claim], store, scopes=[("AFFILIATION", "ND")])
    assert len(merged) == 1
