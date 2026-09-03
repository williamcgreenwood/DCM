"""Persistent research store and delta classification."""
from __future__ import annotations

from pathlib import Path

from dcm.research.claims import claim_record
from dcm.research.research_store import ResearchStore, classify_delta, classify_requests
from dcm.research.batch import build_next_research_batch, scheduler_score


CUTOFF = "2026-08-30T12:00:00Z"


def _claim():
    return claim_record(
        source_id="TEST_FROZEN_OFFICIAL",
        url="https://www.wnba.com/x",
        published_at="2026-08-29T00:00:00Z",
        observed_at="2026-08-29T12:00:00Z",
        forecast_cutoff=CUTOFF,
        semantic_scope="SUBJECT",
        scope_id="PAIGE",
        claim_type="HISTORICAL_PERFORMANCE",
        claim_value={"game_logs": [
            {"date": "2026-08-18", "minutes": 28},
            {"date": "2026-08-20", "minutes": 30},
            {"date": "2026-08-22", "minutes": 31},
        ]},
        reliability=0.8,
        freshness=0.7,
    )


def test_store_is_content_addressed_and_latest_pointer(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    claim = _claim()
    p1 = store.put_claim(claim, sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    p2 = store.put_claim(claim, sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    assert p1["contentHash"] == p2["contentHash"]
    assert len(list((tmp_path / "research_store" / "blobs").glob("*.json"))) == 1
    latest = store.latest_for("SUBJECT", "PAIGE")
    assert latest["contentHash"] == p1["contentHash"]
    loaded = store.get(p1["contentHash"])
    assert loaded["claim"]["claim_hash"] == claim["claim_hash"]


def test_delta_new_entity_then_reuse():
    req = {"scope": "SUBJECT", "scope_id": "PAIGE", "need": "status_role_logs_opportunity_efficiency", "dependent_prop_count": 8}
    first = classify_delta(request=req, prior=None)
    assert first["deltaClass"] in {"NEW_ENTITY_FULL_RESEARCH", "RESEARCH_NEW"}
    assert first["acquire"] is True
    reused = classify_delta(request=req, prior={"freshness": 0.9, "affiliationId": "DAL"})
    assert reused["deltaClass"] == "REUSE_VALID"
    assert reused["acquire"] is False
    changed = classify_delta(
        request=req,
        prior={"freshness": 0.9, "affiliationId": "DAL"},
        current_affiliation="LAS",
    )
    assert changed["deltaClass"] == "TEAM_CHANGED"
    gap = classify_delta(request=req, prior={"freshness": 0.9}, known_history_count=2, required_history_count=3)
    assert gap["deltaClass"] == "APPEND_MISSING_HISTORY"


def test_batch_skips_reuse_valid_and_groups_by_event():
    requests = [
        {
            "request_id": "R1",
            "scope": "EVENT",
            "scope_id": "E1",
            "need": "start",
            "forecast_cutoff": CUTOFF,
            "dependent_prop_count": 10,
            "eventId": "E1",
            "priority_score": 9.0,
        },
        {
            "request_id": "R2",
            "scope": "SUBJECT",
            "scope_id": "P1",
            "need": "status_role_logs_opportunity_efficiency",
            "forecast_cutoff": CUTOFF,
            "dependent_prop_count": 8,
            "eventId": "E1",
            "priority_score": 6.0,
        },
        {
            "request_id": "R3",
            "scope": "OFFER",
            "scope_id": "o1",
            "need": "line",
            "forecast_cutoff": CUTOFF,
            "dependent_prop_count": 1,
            "eventId": "E1",
            "priority_score": 0.4,
        },
    ]
    batch = build_next_research_batch(requests, max_entities=25)
    assert batch["eventBatchCount"] >= 1
    assert batch["selectedCount"] >= 1
    score = scheduler_score(requests[1], uncertainty_reduction=1.0, cost=1.0)
    assert score > 0
    classified = classify_requests(requests, store=None)
    assert all(r["deltaClass"] == "NEW_ENTITY_FULL_RESEARCH" or r["acquire"] for r in classified if r["scope"] == "SUBJECT")


def test_classify_requests_hydrates_blob_not_pointer(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    claim = _claim()
    store.put_claim(claim, sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    req = {
        "scope": "SUBJECT",
        "scope_id": "PAIGE",
        "need": "status_role_logs_opportunity_efficiency",
        "dependent_prop_count": 8,
        "affiliationId": "DAL",
    }
    classified = classify_requests([req], store)
    assert classified[0]["deltaClass"] == "REUSE_VALID"
    assert classified[0]["acquire"] is False
    assert classified[0]["priorContentHash"]


def test_append_missing_history_from_stored_logs(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    short = _claim()
    short["claim_value"] = {"game_logs": [{"date": "2026-08-20", "minutes": 30}]}
    store.put_claim(short, sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    classified = classify_requests(
        [{"scope": "SUBJECT", "scope_id": "PAIGE", "need": "game_logs", "requiredHistoryCount": 3}],
        store,
    )
    assert classified[0]["deltaClass"] == "APPEND_MISSING_HISTORY"
    assert classified[0]["acquire"] is True
    assert classified[0]["lastVerified"]["date"] == "2026-08-20"


def test_game_log_append_is_deduped_and_does_not_replace_history(tmp_path: Path):
    from dcm.research.research_store import merge_game_logs, game_identity
    existing = [{"date": "2026-08-20", "eventId": "G42", "minutes": 30}]
    incoming = [
        {"date": "2026-08-20", "eventId": "G42", "minutes": 99},
        {"date": "2026-08-22", "eventId": "G43", "minutes": 28},
    ]
    merged, appended = merge_game_logs(existing, incoming)
    assert len(merged) == 2
    assert game_identity(merged[0]) == "event:G42"
    assert merged[0]["minutes"] == 30
    assert len(appended) == 1
    assert appended[0]["eventId"] == "G43"


def test_outcome_memory_does_not_change_research_delta(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    claim = _claim()
    store.put_claim(claim, sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    store.put_outcome({"projectionId": "pp-pts", "settlement": "LOSS", "frozenForecastHash": "x"})
    classified = classify_requests(
        [{"scope": "SUBJECT", "scope_id": "PAIGE", "need": "game_logs"}],
        store,
    )
    assert classified[0]["deltaClass"] == "REUSE_VALID"
    tel = store.telemetry(reused=1, acquired=0)
    assert tel["webRequestsAvoided"] == 1
    assert tel["hostPerformanceCertified"] is False
    assert tel["cacheHitRate"] == 1.0


def test_source_and_time_indexes_exist(tmp_path: Path):
    store = ResearchStore(tmp_path / "research_store")
    store.put_claim(_claim(), sport="basketball", entity_kind="SUBJECT", as_of=CUTOFF)
    assert (tmp_path / "research_store" / "indexes" / "by_entity.json").is_file()
    assert (tmp_path / "research_store" / "indexes" / "by_source.json").is_file()
    assert (tmp_path / "research_store" / "indexes" / "by_asof.json").is_file()

