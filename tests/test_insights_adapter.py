from __future__ import annotations

import json
from pathlib import Path

from dcm.ingest.har import ingest_har
from dcm.ingest.insights import (
    PAGINATION_NONEMPTY,
    PAGINATION_TERMINAL_NULL,
    parse_insights_payload,
)
from dcm.learning.insight_settlement import append_insight_settlements, settle_insight_population
from dcm.research.insight_queue import build_research_queue


def _row(*, position: str = "OVER", label: str = "Over") -> dict:
    return {
        "insightId": "i-1",
        "subjectType": "PLAYER",
        "playerId": "p-1",
        "teamId": "t-1",
        "leagueId": "NFL",
        "eventId": "e-1",
        "event": {
            "eventId": "e-1",
            "scheduledTime": "2026-09-15T20:00:00Z",
            "home": {"teamId": "t-1", "alias": "HOM"},
            "away": {"teamId": "t-2", "alias": "AWY"},
        },
        "marketId": "m-1",
        "marketOutcomeId": "mo-1",
        "marketType": "PLAYER_PROP",
        "marketActive": True,
        "proposition": "RECEPTIONS",
        "line": 4.5,
        "position": position,
        "outcomeLabel": label,
        "lastN": [True, True, False, True, True],
        "hitRate": 0.8,
        "books": ["PRIZEPICKS", "DRAFTKINGS"],
        "bookOdds": {
            "PRIZEPICKS": {
                "odds": "-137",
                "decimal": 1.73,
                "identifier": {"bookProps": {"odds_type": "standard"}},
            }
        },
        "splits": [{"splitType": "HOME"}],
        "playerData": {
            "items": [
                {"date": "2026-09-10T00:00:00Z", "eventId": "old-1", "value": 5.0, "stat": 5.0}
            ]
        },
        "text": "this must not be persisted",
    }


def test_typed_adapter_preserves_claim_semantics_without_free_text() -> None:
    claims, accounting = parse_insights_payload(
        {"insights": [_row()], "nextPageToken": None},
        source_har_sha256="har-hash",
        source_body_hash="body-hash",
        source_snapshot_time="2026-09-14T00:00:00Z",
    )
    assert accounting["paginationState"] == PAGINATION_TERMINAL_NULL
    assert accounting["paginationComplete"] is True
    assert len(claims) == 1
    claim = claims[0]
    assert claim["disposition"] == "PLAYER_PROP_CANDIDATE"
    assert claim["direction"] == "HIGHER"
    assert claim["directionClass"] == "HIGHER_LOWER"
    assert claim["historicalSignalOnly"] is True
    assert claim["productionEligible"] is False
    assert "text" not in json.dumps(claim).lower()
    assert "bookOutcomeId" not in json.dumps(claim)


def test_pagination_nonempty_is_retained_but_not_complete() -> None:
    claims, accounting = parse_insights_payload(
        {"insights": [_row()], "nextPageToken": "next-page"},
        source_har_sha256="har-hash",
        source_body_hash="body-hash",
    )
    assert accounting["paginationState"] == PAGINATION_NONEMPTY
    assert accounting["paginationComplete"] is False
    assert claims[0]["paginationComplete"] is False


def test_home_away_team_outcome_is_not_converted_to_higher_lower() -> None:
    row = _row(position="HOME", label="HOM")
    row.update({"subjectType": "TEAM", "playerId": None, "marketType": "GAMELINE", "proposition": "MONEYLINE"})
    claims, _ = parse_insights_payload(
        {"insights": [row]},
        source_har_sha256="har-hash",
        source_body_hash="body-hash",
    )
    assert claims[0]["direction"] == "HOME"
    assert claims[0]["directionClass"] == "TEAM_SIDE"
    assert claims[0]["disposition"] == "TEAM_MARKET_ACCOUNTED"


def test_queue_is_research_only_and_has_top100_top25() -> None:
    claims, _ = parse_insights_payload(
        {"insights": [_row()]},
        source_har_sha256="har-hash",
        source_body_hash="body-hash",
    )
    queue = build_research_queue(claims)
    assert queue["accounting"]["top100Count"] == 1
    assert queue["accounting"]["top25Count"] == 1
    assert queue["top25"][0]["probability"] is None
    assert queue["top25"][0]["productionEligible"] is False


def test_settlement_requires_exact_identity_and_can_build_training_label() -> None:
    claims, _ = parse_insights_payload(
        {"insights": [_row()]},
        source_har_sha256="har-hash",
        source_body_hash="body-hash",
    )
    claim = claims[0]
    outcome = {
        "eventId": "e-1",
        "subjectId": "p-1",
        "proposition": "RECEPTIONS",
        "periodLabel": "",
        "line": 4.5,
        "direction": "HIGHER",
        "observedValue": 6,
        "metric": "receptions",
        "sourceId": "official-score",
        "sourceHash": "outcome-hash",
        "authority": "OFFICIAL_LEAGUE",
    }
    settled = settle_insight_population(
        claims,
        [outcome],
        decision_cutoff="2026-09-14T00:00:00Z",
        settlement_rule_hash="rule-hash",
        recorded_at="2026-09-16T00:00:00Z",
    )
    assert settled["results"] == {"WIN": 1}
    assert settled["trainingEligibleCount"] == 1
    assert settled["ledger"][0]["binaryLabel"] == 1


def test_settlement_append_is_idempotent(tmp_path: Path) -> None:
    claims, _ = parse_insights_payload(
        {"insights": [_row()]},
        source_har_sha256="har-hash",
        source_body_hash="body-hash",
    )
    settled = settle_insight_population(
        claims,
        [],
        decision_cutoff="2026-09-14T00:00:00Z",
        settlement_rule_hash="rule-hash",
        recorded_at="2026-09-16T00:00:00Z",
    )
    first = append_insight_settlements(
        tmp_path,
        settled["ledger"],
        run_id="run-1",
        decision_cutoff="2026-09-14T00:00:00Z",
    )
    second = append_insight_settlements(
        tmp_path,
        settled["ledger"],
        run_id="run-1",
        decision_cutoff="2026-09-14T00:00:00Z",
    )
    assert first["appended"] == 1
    assert second["appended"] == 0
    assert len((tmp_path / "insight_settlement_ledger.jsonl").read_text().splitlines()) == 1
