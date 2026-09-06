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


def test_merge_preserves_prior_game_logs_when_latest_status_omits_them(tmp_path: Path) -> None:
    """Pinnick regression: PLAYER_STATUS latest must not hide HISTORICAL game_logs."""
    store = ResearchStore(tmp_path / "store")
    logs = [
        {
            "date": f"2025-09-{i:02d}",
            "fg_att": 2,
            "fg_made": 1,
            "xp_att": 3,
            "xp_made": 3,
            "kicking_pts": 6,
        }
        for i in range(1, 13)
    ]
    historical = {
        "semantic_scope": "SUBJECT",
        "scope_id": "338765",
        "claim_type": "HISTORICAL_PERFORMANCE",
        "claim_value": {
            "game_logs": logs,
            "priorSeason_2025": {"starts": 10, "fg_att": 20},
            "opportunity": {"support_n": 12},
            "efficiency": {"support_n": 12},
        },
        "claim_hash": content_hash({"scope": "338765", "logs": 12}),
        "source_hash": "hist1",
        "reliability": 0.9,
        "freshness": 0.9,
        "observed_at": "2026-09-05T12:00:00Z",
    }
    store.put_claim(historical, sport="CFB", entity_kind="SUBJECT", as_of="2026-09-05T12:00:00Z")

    status = {
        "semantic_scope": "SUBJECT",
        "scope_id": "338765",
        "claim_type": "PLAYER_STATUS",
        "claim_value": {"status": "ACTIVE", "team": "Oklahoma"},
        "claim_hash": content_hash({"scope": "338765", "status": "ACTIVE"}),
        "source_hash": "status1",
        "reliability": 0.95,
        "freshness": 0.95,
        "observed_at": "2026-09-06T18:00:00Z",
    }
    store.put_claim(status, sport="CFB", entity_kind="SUBJECT", as_of="2026-09-06T18:00:00Z")

    merged = merge_latest_store_claims([], store, scopes=[("SUBJECT", "338765")])
    assert len(merged) == 1
    value = merged[0].get("claim_value") or {}
    preserved = value.get("game_logs") or []
    assert len(preserved) == 12
    assert value.get("status") == "ACTIVE"
    assert (value.get("priorSeason_2025") or {}).get("starts") == 10
    assert (value.get("opportunity") or {}).get("support_n") == 12
    assert (value.get("efficiency") or {}).get("support_n") == 12

    # latest_blob itself should also retain observed logs after status put
    latest = store.latest_blob("SUBJECT", "338765")
    latest_value = ((latest or {}).get("claim") or {}).get("claim_value") or {}
    assert len(latest_value.get("game_logs") or []) == 12


def test_merge_restores_logs_from_prior_records_when_latest_blob_omits_them(tmp_path: Path) -> None:
    """Already-stored PLAYER_STATUS without logs (pre-fix) still merges history."""
    import json
    from dcm.contracts.hashes import content_hash as ch

    store = ResearchStore(tmp_path / "store")
    logs = [{"date": f"2025-09-{i:02d}", "rush_att": 12, "rush_yds": 55} for i in range(1, 9)]
    historical = {
        "semantic_scope": "SUBJECT",
        "scope_id": "PINNICK",
        "claim_type": "HISTORICAL_PERFORMANCE",
        "claim_value": {"game_logs": logs, "opportunity": {"support_n": 8}},
        "claim_hash": "hist-pinnick",
        "source_hash": "h",
        "reliability": 0.9,
        "freshness": 0.9,
        "observed_at": "2026-09-05T12:00:00Z",
    }
    store.put_claim(historical, sport="CFB", entity_kind="SUBJECT", as_of="2026-09-05T12:00:00Z")

    # Plant a status-only latest blob that omits logs (bypass put_claim preserve).
    status_claim = {
        "semantic_scope": "SUBJECT",
        "scope_id": "PINNICK",
        "claim_type": "PLAYER_STATUS",
        "claim_value": {"status": "ACTIVE"},
        "claim_hash": "status-pinnick",
        "source_hash": "s",
        "reliability": 0.95,
        "freshness": 0.95,
        "observed_at": "2026-09-06T18:00:00Z",
    }
    payload = {
        "schema": "pillars_dcm.research_store.v1",
        "sport": "CFB",
        "entityKind": "SUBJECT",
        "entityId": "PINNICK",
        "asOf": "2026-09-06T18:00:00Z",
        "claim": status_claim,
    }
    digest = ch(payload)
    blob_path = store.blobs / f"{digest}.json"
    blob_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pointer = {
        "contentHash": digest,
        "sport": "CFB",
        "entityKind": "SUBJECT",
        "entityId": "PINNICK",
        "asOf": "2026-09-06T18:00:00Z",
        "asOfDate": "2026-09-06",
        "claimType": "PLAYER_STATUS",
        "claimHash": "status-pinnick",
        "historyCount": 0,
        "path": str(blob_path.relative_to(store.root)),
    }
    store._append_index(pointer)
    store._set_latest("SUBJECT:PINNICK", pointer)
    store._index_push(store._by_entity_path, "SUBJECT:PINNICK", digest)

    latest_value = ((store.latest_blob("SUBJECT", "PINNICK") or {}).get("claim") or {}).get("claim_value") or {}
    assert not (latest_value.get("game_logs") or [])

    merged = merge_latest_store_claims([], store, scopes=[("SUBJECT", "PINNICK")])
    value = merged[0].get("claim_value") or {}
    assert len(value.get("game_logs") or []) == 8
    assert value.get("status") == "ACTIVE"
    assert (value.get("opportunity") or {}).get("support_n") == 8

