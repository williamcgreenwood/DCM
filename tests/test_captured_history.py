"""Full-board, cutoff-safe captured-history directional modeling."""
from __future__ import annotations

import json
import sqlite3

from dcm.model.captured_history import build_captured_history_decisions
from dcm.model.captured_history_database import build_captured_prop_database


def _claim(**overrides):
    claim = {
        "claimId": "claim-1",
        "disposition": "PLAYER_PROP_CANDIDATE",
        "leagueId": "NFL",
        "playerId": "player-1",
        "proposition": "RECEPTIONS",
        "line": 2.5,
        "direction": "HIGHER",
        "directionClass": "HIGHER_LOWER",
        "reportedHitRate": 0.01,
        "modifierCounts": {"STANDARD": 1},
        "history": {"items": [
            {"date": "2026-10-01T00:00:00Z", "eventId": "e1", "value": 4},
            {"date": "2026-10-02T00:00:00Z", "eventId": "e2", "value": 3},
            {"date": "2026-10-03T00:00:00Z", "eventId": "e3", "value": 5},
            {"date": "2026-10-04T00:00:00Z", "eventId": "e4", "value": 1},
            {"date": "2026-10-16T00:00:00Z", "eventId": "future", "value": 0},
        ]},
    }
    claim.update(overrides)
    return claim


def test_cutoff_empirical_distribution_keeps_discrete_masses_and_ignores_reported_rate():
    first = build_captured_history_decisions(
        [_claim()], forecast_cutoff="2026-10-15T10:59:00Z"
    )["rows"][0]
    second = build_captured_history_decisions(
        [_claim(reportedHitRate=0.99)], forecast_cutoff="2026-10-15T10:59:00Z"
    )["rows"][0]

    assert first["reportedHitRateUsedAsForecast"] is False
    assert first["historyObservationCount"] == 4
    assert first["excludedAfterCutoffCount"] == 1
    assert first["empiricalPointMasses"] == {"1": 1, "3": 1, "4": 1, "5": 1}
    assert first["pHigher"] == 0.75
    assert first["terminalStatus"] == "PASS"  # sparse history fails the 95% lower-bound rule
    assert first["claimId"] in build_captured_history_decisions(
        [_claim()], forecast_cutoff="2026-10-15T10:59:00Z"
    )["rankStages"]["top2000"]
    assert build_captured_history_decisions(
        [_claim()], forecast_cutoff="2026-10-15T10:59:00Z"
    )["recommendationRankStages"]["top6"] == []
    assert first["outcomeCounts"] == second["outcomeCounts"]
    assert first["pHigher"] == second["pHigher"]


def test_no_unobserved_side_is_invented_and_policy_exclusions_are_terminal():
    no_side = _claim(direction="PUSH", directionClass="OTHER")
    goblin = _claim(claimId="goblin", modifierCounts={"GOBLIN": 1})
    half_line = _claim(claimId="half", line=0.5, proposition="RECEPTIONS")
    int_exception = _claim(claimId="int", line=0.5, proposition="INTERCEPTIONS")

    rows = build_captured_history_decisions(
        [no_side, goblin, half_line, int_exception],
        forecast_cutoff="2026-10-15T10:59:00Z",
    )["rows"]
    by_id = {row["claimId"]: row for row in rows}

    assert by_id[no_side["claimId"]]["offeredSides"] == []
    assert by_id[no_side["claimId"]]["reason"] == "MISSING_OR_UNRESOLVED_OFFERED_SIDE"
    assert by_id[goblin["claimId"]]["terminalStatus"] == "EXCLUDED_BY_POLICY"
    assert by_id[half_line["claimId"]]["reason"] == "POLICY_LINE_0_5_EXCLUDED"
    assert by_id[int_exception["claimId"]]["historyObservationCount"] == 4


def test_all_supplied_claims_get_terminal_rows_when_cutoff_missing():
    result = build_captured_history_decisions([_claim(), _claim(claimId="claim-2")], forecast_cutoff=None)

    assert result["inputClaimCount"] == 2
    assert len(result["rows"]) == 2
    assert {row["reason"] for row in result["rows"]} == {"FORECAST_CUTOFF_MISSING_OR_INVALID"}


def test_target_local_event_date_limits_ranking_but_keeps_out_of_scope_accounting():
    in_scope = _claim()
    in_scope["event"] = {"scheduledTime": "2026-10-16T06:30:00Z"}
    out_scope = _claim(claimId="other-date")
    out_scope["event"] = {"scheduledTime": "2026-10-16T08:00:00Z"}

    result = build_captured_history_decisions(
        [in_scope, out_scope],
        forecast_cutoff="2026-10-15T10:59:00Z",
        event_date="2026-10-15",
        event_timezone="America/Los_Angeles",
    )
    rows = {row["claimId"]: row for row in result["rows"]}

    assert rows["claim-1"]["eventLocalDate"] == "2026-10-15"
    assert rows["other-date"]["terminalStatus"] == "OUT_OF_RUN_SCOPE"
    assert result["directionallyRankedCount"] <= 1


def test_sqlite_audit_database_joins_decision_source_and_indexed_history(tmp_path):
    claim = _claim(sourceHarSha256="har-sha", sourceBodyHash="body-sha")
    decisions = build_captured_history_decisions(
        [claim], forecast_cutoff="2026-10-15T10:59:00Z"
    )
    manifest = build_captured_prop_database(tmp_path, [claim], decisions)
    db = tmp_path / manifest["path"]

    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT terminal_status, reported_hit_rate, history_observation_count FROM source_claims"
        ).fetchone()
        observations = connection.execute(
            "SELECT count(*), sum(cutoff_safe) FROM history_observations"
        ).fetchone()
        indexes = {
            value[0] for value in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        raw = connection.execute("SELECT source_claim_json FROM source_claims").fetchone()[0]

    assert manifest["sourceClaimCount"] == 1
    assert len(manifest["sha256"]) == 64
    assert row[0] == "PASS"
    assert row[1] == 0.01
    assert row[2] == 4
    assert observations == (5, 4)
    assert "idx_claim_target_sport_market" in indexes
    assert "idx_history_date_value" in indexes
    assert json.loads(raw)["claimId"] == "claim-1"
