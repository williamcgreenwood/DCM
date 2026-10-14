from __future__ import annotations

import pytest

from dcm.research.research_store import ResearchStore
from dcm.research.statepack import StatePack


def _candidate(**changes):
    body = {
        "candidateId": "DISCOVERY:TEST:001",
        "title": "Synthetic method lead",
        "hypothesis": "A tested candidate may reduce redundant feature work.",
        "sourceId": "TEST_SOURCE",
        "sourceAuthority": "UNVERIFIED_TEST_FIXTURE",
        "sourceUrl": "https://example.org/paper",
        "sourceContentSha256": "a" * 64,
        "rightsState": "DISCOVERY_ONLY",
        "license": "UNREVIEWED",
        "rightsEvidence": {},
        "requiredData": ["cutoff-safe fixture matrix"],
        "expectedBenefit": "Lower duplicate computation",
        "possibleHarm": "Leakage or unjustified model complexity",
        "experimentEvidence": [],
        "metricEvidence": [],
        "testReferences": [],
        "downstreamConsumer": "",
        "lifecycle": "CANDIDATE",
    }
    body.update(changes)
    return body


def test_discovery_records_are_rights_gated_idempotent_and_append_only(tmp_path):
    store = ResearchStore(tmp_path / "research")
    first = store.append_discovery_event(_candidate())
    retry = store.append_discovery_event(_candidate())
    assert first == retry
    assert len(store.discovery_events(candidate_id="DISCOVERY:TEST:001")) == 1

    with pytest.raises(ValueError, match="ADOPTION_RIGHTS_NOT_AUTHORIZED"):
        store.append_discovery_event(_candidate(lifecycle="ADOPTED"), event_type="LIFECYCLE_DECISION")

    adopted = _candidate(
        lifecycle="ADOPTED",
        rightsState="AUTHORIZED_RESEARCH",
        rightsEvidence={"reviewer": "test", "reviewedAt": "2026-10-14T00:00:00Z",
                        "evidenceUrl": "https://example.org/license", "permittedUses": ["research"]},
        experimentEvidence=[{"runId": "SYNTHETIC-1", "inputHash": "b" * 64}],
        metricEvidence=[{"name": "runtime_ms", "value": 1.0, "fixtureOnly": True}],
        testReferences=["tests/test_research_discovery.py"],
        downstreamConsumer="dcm.research.example_consumer",
    )
    second = store.append_discovery_event(adopted, event_type="LIFECYCLE_DECISION")
    events = store.discovery_events(candidate_id="DISCOVERY:TEST:001")
    assert len(events) == 2
    assert events[-1]["contentHash"] == second["contentHash"]
    assert events[0]["lifecycle"] == "CANDIDATE"


def test_discovery_log_detects_tampering_and_rejects_untrusted_url(tmp_path):
    store = ResearchStore(tmp_path / "research")
    with pytest.raises(ValueError, match="URL_MUST_USE_HTTPS"):
        store.append_discovery_event(_candidate(sourceUrl="http://example.org/paper"))
    store.append_discovery_event(_candidate())
    path = store.indexes / "discovery_events.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace("Synthetic method lead", "tampered"), encoding="utf-8")
    with pytest.raises(ValueError, match="EVENT_HASH_MISMATCH"):
        store.discovery_events()
    with pytest.raises(ValueError, match="EVENT_HASH_MISMATCH"):
        store.append_discovery_event(_candidate())


def test_discovery_history_survives_statepack_snapshot_restore(tmp_path):
    store = ResearchStore(tmp_path / "research")
    event = store.append_discovery_event(_candidate())
    pack = StatePack(tmp_path / "statepack")
    assert pack.ingest_store(store)["ingestedDiscoveryEvents"] == 1
    pack.snapshot()

    restored = StatePack(tmp_path / "restored")
    result = restored.restore_from_export(tmp_path / "statepack" / "deterministic_export.json.gz")
    assert result["restoredDiscoveryEvents"] == 1
    assert restored.query_discovery(candidate_id="DISCOVERY:TEST:001")[0]["contentHash"] == event["contentHash"]
    assert restored.snapshot()["discoveryEvents"] == 1
