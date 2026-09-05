from __future__ import annotations

from dcm.research.authority import SourceAuthorityRegistry, derive_quality
from dcm.research.coverage import coverage_report
from dcm.research.role_epoch import RoleEpochBuilder, partition_logs


def test_source_authority_derives_reliability_freshness():
    q = derive_quality(
        source_id="NBA_OFFICIAL",
        url="https://www.nba.com/stats",
        published_at="2026-08-28T00:00:00Z",
        observed_at="2026-08-28T01:00:00Z",
        forecast_cutoff="2026-08-29T00:00:00Z",
    )
    assert q["source_class"] == "OFFICIAL_LEAGUE"
    assert 0.9 <= q["reliability"] <= 1.0
    assert 0.0 < q["freshness"] <= 1.0
    assert "source_id" in q["host_supplies"]
    assert "reliability" in q["dcm_derives"]
    reg = SourceAuthorityRegistry()
    again = reg.derive(
        source_id="TEST_FROZEN_OFFICIAL",
        url="https://www.wnba.com/x",
        published_at="2026-08-27T00:00:00Z",
        observed_at="2026-08-27T00:00:00Z",
        forecast_cutoff="2026-08-29T00:00:00Z",
    )
    assert again["source_class"] == "TEST_FROZEN"


def test_sport_specific_event_team_fail_closed():
    requests = [
        {"request_id": "E", "scope": "EVENT", "scope_id": "E1", "need": "x", "league": "WNBA", "sportFamily": "basketball"},
        {"request_id": "T", "scope": "TEAM", "scope_id": "T1", "need": "x", "league": "NFL", "sportFamily": "gridiron"},
    ]
    empty = coverage_report(requests, [])
    assert empty["complete"] is False
    basketball_ok = coverage_report(
        [requests[0]],
        [{"semantic_scope": "EVENT", "scope_id": "E1", "claim_value": {
            "event_context": True, "scheduled_start": "2026-08-28T00:00:00Z", "venue": "arena", "environment": "indoor",
        }}],
    )
    assert basketball_ok["complete"] is True
    football_bad = coverage_report(
        [requests[1]],
        [{"semantic_scope": "TEAM", "scope_id": "T1", "claim_value": {"note": "non-empty but missing required fields"}}],
    )
    assert football_bad["complete"] is False
    assert "FOOTBALL_TEAM_INJURY_OR_DEPTH" in football_bad["requests"][0]["missing"]


def test_role_epoch_builder_partitions_when_claims_exist():
    logs = [
        {"minutes": 32, "role": "starter"},
        {"minutes": 12, "role": "bench"},
        {"minutes": 28, "role": "starter", "teammate_out": True},
    ]
    parts = partition_logs(logs)
    assert len(parts["starter"]) == 1
    assert len(parts["bench"]) == 1
    assert len(parts["teammate_out"]) == 1
    built = RoleEpochBuilder().build({"role_epoch_logs": logs, "role": "starter"})
    assert built["invented"] is False
    assert built["log_count"] == 3
    assert built["partitions"]["starter"]
    assert "stub" not in str(built.get("builder") or "").lower()
    assert "epochs" in built
    assert "shrinkage" in built
    assert built["comparable_logs"] is not None
