"""Queryable StatePack over the content-addressed research store."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from dcm.research.claims import claim_record
from dcm.research.research_store import ResearchStore
from dcm.research.statepack import STATEPACK_SCHEMA, StatePack


CUTOFF = "2026-08-30T12:00:00Z"


def _claim(scope_id: str = "PAIGE", logs: list | None = None):
    return claim_record(
        source_id="TEST_FROZEN_OFFICIAL",
        url="https://www.wnba.com/x",
        published_at="2026-08-29T00:00:00Z",
        observed_at="2026-08-29T12:00:00Z",
        forecast_cutoff=CUTOFF,
        semantic_scope="SUBJECT",
        scope_id=scope_id,
        claim_type="HISTORICAL_PERFORMANCE",
        claim_value={"game_logs": logs or [{"date": "2026-08-22", "minutes": 31}]},
        reliability=0.8,
        freshness=0.7,
    )


def test_statepack_indexes_store_and_queries_entity_source_asof(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    store.put_claim(_claim(), sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    pack = StatePack(tmp_path / "DCM_StatePack")
    ingested = pack.ingest_store(store)
    assert ingested["ingestedBlobs"] == 1
    rows = pack.query_entity("SUBJECT", "PAIGE")
    assert len(rows) == 1
    assert rows[0]["claim"]["scope_id"] == "PAIGE"
    latest = pack.query_entity("PLAYER", "PAIGE", latest_only=True)
    assert len(latest) == 1
    assert len(pack.query_source("TEST_FROZEN_OFFICIAL")) == 1
    assert len(pack.query_asof("2026-08-30")) == 1
    assert pack.counts()["blobs"] == 1


def test_snapshot_round_trip_preserves_semantic_hash(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    store.put_claim(_claim("A"), sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    store.put_claim(_claim("B"), sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    pack = StatePack(tmp_path / "DCM_StatePack")
    pack.ingest_store(store)
    snap1 = pack.snapshot()
    assert snap1["schema"] == STATEPACK_SCHEMA
    assert (tmp_path / "DCM_StatePack" / "deterministic_export.json.gz").is_file()
    assert pack.integrity_ok()["ok"] is True
    snap2 = pack.snapshot()
    assert snap1["exportHash"] == snap2["exportHash"]
    assert snap1["stateManifestHash"] == snap2["stateManifestHash"]
    other = StatePack(tmp_path / "DCM_StatePack_restore")
    restored = other.restore_from_export(tmp_path / "DCM_StatePack" / "deterministic_export.json.gz")
    assert restored["restored"] == 2
    assert other.snapshot()["exportHash"] == snap1["exportHash"]


def test_corrupt_export_fails_closed(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    store.put_claim(_claim(), sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    pack = StatePack(tmp_path / "DCM_StatePack")
    pack.ingest_store(store)
    pack.snapshot()
    with gzip.open(pack.export_path, "wb") as fh:
        fh.write(b'{"schema":"tampered","records":[]}')
    result = pack.integrity_ok()
    assert result["ok"] is False
    assert result["reason"] == "EXPORT_HASH_MISMATCH"


def test_outcomes_are_indexed_and_do_not_decide_reuse(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    store.put_claim(_claim(), sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    store.put_outcome({"projectionId": "pp-pts", "settlement": "LOSS", "frozenForecastHash": "x"})
    pack = StatePack(tmp_path / "DCM_StatePack")
    ingested = pack.ingest_store(store)
    assert ingested["ingestedOutcomes"] == 1
    assert pack.counts()["outcomes"] == 1
    rows = pack.query_entity("SUBJECT", "PAIGE")
    assert "LOSS" not in json.dumps(rows)
