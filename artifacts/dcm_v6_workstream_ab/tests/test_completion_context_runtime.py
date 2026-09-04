"""Acceptance checks for the completion-context runtime bindings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3

from dcm.cfb.rules import build_cfb_rules_snapshot
from dcm.research.cache_layers import ResearchCacheCascade
from dcm.research.claims import claim_record
from dcm.research.material_facts import resolve_material_facts
from dcm.research.source_health import SourceHealthRegistry
from dcm.runtime.checkpoint import write_checkpoint
from dcm.runtime.checkpoint_outbox import load_outbox
from dcm.runtime.checkpoint_reconciliation import reconcile_checkpoint_outbox
from dcm.runtime.github_archive import scan_for_secrets
from dcm.runtime.input_boundary import (
    build_input_boundary_manifest,
    inspect_input_boundary,
)
from dcm.selection.decision_integrity import (
    SurvivorState,
    inverse_consistency_audit,
    probability_sanity_diagnostic,
)
from dcm.signals.cfb_runtime import build_cfb_signal_registry, execute_cfb_signals


def test_research_cache_reopens_from_durable_sqlite(tmp_path):
    first = ResearchCacheCascade(tmp_path)
    first.put(
        "PLAYER", "p1", {"claim_type": "STATUS", "value": "ACTIVE"}, claim_type="STATUS"
    )
    first.close()
    second = ResearchCacheCascade(tmp_path)
    value, layer = second.get("PLAYER", "p1", claim_type="STATUS")
    assert layer == "L2"
    assert value == {"claim_type": "STATUS", "value": "ACTIVE"}
    assert second.snapshot()["persistence"]["state"] == "PERSISTENT_SQLITE"
    second.close()


def test_research_cache_rejects_tampered_payload_hash(tmp_path):
    first = ResearchCacheCascade(tmp_path)
    first.put("PLAYER", "p1", {"value": "ACTIVE"}, claim_type="STATUS")
    first.close()
    with sqlite3.connect(tmp_path / "research_cache.sqlite3") as conn:
        conn.execute("UPDATE research SET payload_hash = ?", ("0" * 64,))
        conn.commit()
    second = ResearchCacheCascade(tmp_path)
    value, layer = second.get("PLAYER", "p1", claim_type="STATUS")
    assert value is None
    assert layer == "L6"
    assert "CACHE_PAYLOAD_HASH_MISMATCH" in second.snapshot()["persistence"]["blockers"]
    second.close()


def test_input_boundary_only_emits_safe_hashes_and_marker_classes(tmp_path):
    source = tmp_path / "capture.har"
    raw = {
        "log": {
            "version": "1.2",
            "entries": [{
                "request": {"headers": [
                    {"name": "Cookie", "value": "DO_NOT_EMIT"},
                    {"name": "Authorization", "value": "Bearer DO_NOT_EMIT"},
                ]},
                "response": {"headers": []},
            }],
        }
    }
    source.write_text(json.dumps(raw), encoding="utf-8")
    record = inspect_input_boundary(source)
    assert record["quarantine"]["rawBytesNeverEmitted"] is True
    assert record["redaction"]["sensitiveHeaderClasses"] == ["AUTHORIZATION", "COOKIE"]
    assert "DO_NOT_EMIT" not in json.dumps(record)
    manifest = build_input_boundary_manifest([record], run_id="r1", har_sha256=record["sha256"])
    assert manifest["safeSummaryOnly"] is True
    assert manifest["rawArtifactsUploaded"] is False
    boundary_path = tmp_path / "input_security_boundary.json"
    boundary_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert scan_for_secrets(boundary_path) == []


def test_capability_boundary_summary_is_archive_safe(tmp_path):
    path = tmp_path / "capability_manifest.json"
    path.write_text(json.dumps({
        "schema": "pillars_dcm.capability_authority_manifest.v1",
        "inputBoundary": {
            "rawBytesNeverEmitted": True,
            "rawArtifactsCommitted": False,
            "rawArtifactsUploaded": False,
            "files": [{"name": "capture.har", "rawSensitive": True}],
        },
    }), encoding="utf-8")
    assert scan_for_secrets(path) == []


def test_source_health_clock_is_deterministic():
    now = [datetime(2026, 9, 4, tzinfo=timezone.utc)]
    health = SourceHealthRegistry({"sources": [{"sourceId": "A", "sports": ["CFB"]}]}, clock=lambda: now[0])
    health.record_failure("A", now=now[0])
    health.record_failure("A", now=now[0])
    health.record_failure("A", now=now[0])
    assert health.snapshot()["circuits"]["A"] == "OPEN"
    now[0] = now[0] + timedelta(seconds=301)
    assert health.route(claim_type="EVENT") == ["A"]
    assert health.snapshot()["circuits"]["A"] == "HALF_OPEN"


def test_temporal_correction_replaces_without_false_conflict():
    cutoff = "2026-09-04T00:00:00Z"
    old = claim_record(
        source_id="SRC", url="https://source.example/status", published_at="2026-09-01T00:00:00Z",
        observed_at="2026-09-01T00:00:00Z", forecast_cutoff=cutoff, semantic_scope="PLAYER",
        scope_id="p1", claim_type="STATUS", claim_value={"status": "ACTIVE"}, reliability=.9, freshness=1.0,
    )
    correction = claim_record(
        source_id="SRC", url="https://source.example/status", published_at="2026-09-02T00:00:00Z",
        observed_at="2026-09-02T00:00:00Z", forecast_cutoff=cutoff, semantic_scope="PLAYER",
        scope_id="p1", claim_type="STATUS", claim_value={"status": "OUT"}, reliability=.9, freshness=1.0,
        correction_of=old["claim_hash"],
    )
    resolved = resolve_material_facts([old, correction], cutoff=cutoff)
    fact = resolved["facts"][0]
    assert fact["value"] == {"status": "OUT"}
    assert fact["conflict"] is False
    assert fact["temporalState"] == "SUCCESSION"
    assert old["claim_hash"] in fact["correctionOf"]


def test_cfb_signal_runtime_has_real_consumers_and_no_probability_override():
    registry = build_cfb_signal_registry()
    _, evaluations, features = execute_cfb_signals(
        {"playerId": "p1", "eventId": "e1"},
        {"opportunity": {"support_n": 5}, "efficiency": {"support_n": 4}, "minimum_model_support": True, "data_quality": .8, "ood_risk": .1},
        {"contentHash": "a" * 64}, cutoff="2026-09-04T00:00:00Z", registry=registry,
    )
    assert registry.execution_order
    assert evaluations and features
    assert all(item.to_dict()["canChangeProbabilityDirectly"] is False for item in evaluations)
    assert all(item.get("signalEvaluationHash") for item in features)


def test_decision_integrity_is_reject_only_and_rules_are_separate():
    assert probability_sanity_diagnostic(p_higher=.4, p_lower=.5, p_push=.1)["valid"]
    audit = inverse_consistency_audit(
        {"projectionId": "p", "offeredHigher": True, "offeredLower": False},
        {"MORE": {"rawP": .7, "evidenceSafeP": .6}}, "MORE",
    )
    assert audit["valid"]
    survivor = SurvivorState()
    survivor.reject("p", "TEST_REJECTION")
    assert survivor.accept("p") is False
    rules = build_cfb_rules_snapshot(as_of="2026-09-04T00:00:00Z")
    assert rules["statisticalAuthority"]["authorityId"] != rules["platformSettlementAuthority"]["authorityId"]
    assert rules["allActiveMarketsMapped"] is True
    assert rules["productionEligible"] is False
    assert {"pass_att", "dropbacks", "sacks_taken", "scramble_att", "targets", "receptions"} <= set(rules["globalFieldSemantics"])
    assert rules["identityRules"]["player"]
    assert all(item["settlementOutcomes"]["CORRECTED"] for item in rules["marketMappings"])


def test_checkpoint_outbox_is_idempotent(tmp_path):
    payload = {"runId": "r1", "forecastCutoff": "2026-09-04T00:00:00Z", "artifactRoot": str(tmp_path)}
    write_checkpoint(tmp_path / "checkpoint.json", payload)
    write_checkpoint(tmp_path / "checkpoint.json", payload)
    assert len(load_outbox(tmp_path / "checkpoint_outbox.jsonl")) == 1
    reconciliation = json.loads((tmp_path / "checkpoint_reconciliation.json").read_text())
    assert reconciliation["failClosed"] is True
    assert reconciliation["resumePointer"] == "LOCAL_ONLY_EXTERNAL_UNVERIFIED"
    assert reconcile_checkpoint_outbox(
        {**payload, "checkpointHash": reconciliation["checkpointHash"]},
        tmp_path / "checkpoint_outbox.jsonl",
        github={"checkpointHash": reconciliation["checkpointHash"]},
        drive={"checkpointHash": reconciliation["checkpointHash"]},
    )["resumePointer"] == "REMOTE_VERIFIED"
