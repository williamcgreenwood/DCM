from __future__ import annotations

from dcm.ingest.outlier import parse_outlier_payload
from dcm.model.parameters import build_parameter_snapshot
import pytest

from dcm.research.claims import claim_record, conflict_ledger, dedupe
from dcm.research.provider import _validate_claim
from dcm.research.temporal import TemporalLeakError
from dcm.contracts.hashes import content_hash


def _base_row() -> dict:
    return {
        "sportFamily": "basketball",
        "league": "NBA",
        "eventId": "E",
        "playerId": "P",
        "teamId": "T",
        "projectionId": "X",
        "market": "pts",
        "role": "G",
    }


def _claim(scope: str, scope_id: str, value: dict, h: str) -> dict:
    return {
        "semantic_scope": scope,
        "scope_id": scope_id,
        "claim_value": value,
        "source_id": "OFFICIAL",
        "reliability": 0.95,
        "freshness": 0.95,
        "claim_hash": h,
        "observed_at": "2026-08-28T10:00:00Z",
    }


def test_outlier_unknown_side_fails_closed_and_zero_line_is_preserved():
    parsed = parse_outlier_payload({
        "props": [{
            "id": "o1",
            "player": "Player One",
            "stat": "Points",
            "league": "NBA",
            "team": "AAA",
            "opponent": "BBB",
            "line": 0,
        }]
    })
    assert parsed is not None
    _, rows = parsed
    assert rows[0]["line"] == 0.0
    assert rows[0]["side"] == "UNKNOWN"
    assert rows[0]["offeredHigher"] is False
    assert rows[0]["offeredLower"] is False


def test_unknown_or_uncertain_status_is_not_production_selectable():
    row = _base_row()
    logs = [{"minutes": 32, "fga": 15, "reb": 5, "ast": 4} for _ in range(5)]
    base = [
        _claim("TEAM", "T", {"pace_multiplier": 1.0}, "t"),
        _claim("EVENT", "E", {"venue": "X"}, "e"),
        _claim("MARKET", "X", {"definition_verified": True}, "m"),
    ]
    for status, blocker in (("UNKNOWN", "PLAYER_STATUS_UNKNOWN"), ("QUESTIONABLE", "PLAYER_STATUS_UNCERTAIN")):
        claims = base + [
            _claim("PLAYER", "P", {
                "status": status,
                "role": "starter",
                "game_logs": logs,
                "opportunity": {"support_n": 5},
                "efficiency": {"support_n": 5},
            }, status)
        ]
        snap = build_parameter_snapshot(row, claims)
        assert snap["production_eligible"] is False
        assert snap["blocker"] == blocker


def test_dedupe_never_mutates_hashed_claim_content_and_conflicts_are_sidecar():
    a = claim_record(
        source_id="A",
        url="https://example.com/a",
        published_at="2026-08-28T09:00:00Z",
        observed_at="2026-08-28T10:00:00Z",
        forecast_cutoff="2026-08-28T11:00:00Z",
        semantic_scope="PLAYER",
        scope_id="P",
        claim_type="status",
        claim_value={"status": "ACTIVE"},
        reliability=0.9,
        freshness=0.9,
    )
    b = claim_record(
        source_id="B",
        url="https://example.com/b",
        published_at="2026-08-28T09:00:00Z",
        observed_at="2026-08-28T10:00:00Z",
        forecast_cutoff="2026-08-28T11:00:00Z",
        semantic_scope="PLAYER",
        scope_id="P",
        claim_type="status",
        claim_value={"status": "OUT"},
        reliability=0.9,
        freshness=0.9,
    )
    original = {x["claim_hash"]: content_hash({k: v for k, v in x.items() if k != "claim_hash"}) for x in (a, b)}
    got = dedupe([a, b, a])
    assert len(got) == 2
    for x in got:
        assert x["claim_hash"] == original[x["claim_hash"]]
    conflicts = conflict_ledger(got)
    states = {row["state"] for row in conflicts}
    assert "UNRESOLVED_CONTEMPORANEOUS_CONFLICT" in states
    assert "UNRESOLVED_CONTEMPORANEOUS_FIELD_CONFLICT" in states


def test_published_after_cutoff_is_temporal_leak_even_if_observed_time_is_safe():
    with pytest.raises(TemporalLeakError) as exc:
        claim_record(
            source_id="A",
            url="https://example.com/a",
            published_at="2026-08-28T12:00:00Z",
            observed_at="2026-08-28T10:00:00Z",
            forecast_cutoff="2026-08-28T11:00:00Z",
            semantic_scope="PLAYER",
            scope_id="P",
            claim_type="status",
            claim_value={"status": "ACTIVE"},
            reliability=0.9,
            freshness=0.9,
        )
    assert exc.value.field == "published_at"


def test_production_evidence_rejects_secret_bearing_source_url():
    claim = claim_record(
        source_id="A",
        url="https://example.com/player?token=secret-value",
        published_at="2026-08-28T09:00:00Z",
        observed_at="2026-08-28T10:00:00Z",
        forecast_cutoff="2026-08-28T11:00:00Z",
        semantic_scope="PLAYER",
        scope_id="P",
        claim_type="status",
        claim_value={"status": "ACTIVE"},
        reliability=0.9,
        freshness=0.9,
    )
    request = {
        "scope": "PLAYER",
        "scope_id": "P",
        "forecast_cutoff": "2026-08-28T11:00:00Z",
    }
    with pytest.raises(ValueError, match="SECRET_QUERY"):
        _validate_claim(claim, request)


def test_cross_claim_type_field_conflict_is_blocking():
    base = dict(
        source_id="A",
        published_at="2026-08-28T09:00:00Z",
        observed_at="2026-08-28T10:00:00Z",
        forecast_cutoff="2026-08-28T11:00:00Z",
        semantic_scope="PLAYER",
        scope_id="P",
        reliability=0.9,
        freshness=0.9,
    )
    a = claim_record(
        **base,
        url="https://example.com/status",
        claim_type="status_report",
        claim_value={"status": "ACTIVE"},
    )
    b = claim_record(
        **{**base, "source_id": "B"},
        url="https://example.com/role",
        claim_type="role_update",
        claim_value={"status": "OUT", "role": "starter"},
    )
    conflicts = conflict_ledger([a, b])
    assert any(
        row.get("state") == "UNRESOLVED_CONTEMPORANEOUS_FIELD_CONFLICT"
        and row.get("field") == "status"
        for row in conflicts
    )
