from __future__ import annotations

import json
from pathlib import Path

from dcm.chat.slate import run_slate
from dcm.contracts.hashes import content_hash
from dcm.ingest.har import ingest_har
from dcm.ingest.insights import (
    PAGINATION_INCOMPLETE,
    PAGINATION_MALFORMED,
    parse_insights_payload,
)


def _insight(insight_id: str) -> dict:
    return {
        "insightId": insight_id,
        "subjectType": "PLAYER",
        "playerId": f"player-{insight_id}",
        "teamId": "team-1",
        "leagueId": "NFL",
        "eventId": f"event-{insight_id}",
        "event": {"eventId": f"event-{insight_id}", "scheduledTime": "2026-09-20T17:00:00Z"},
        "marketType": "PLAYER_PROP",
        "marketId": f"market-{insight_id}",
        "marketOutcomeId": f"outcome-{insight_id}",
        "marketActive": True,
        "proposition": "RECEPTIONS",
        "line": 4.5,
        "position": "OVER",
        "outcomeLabel": "Over",
        "lastN": [True, True, False],
        "hitRate": 0.66,
        "books": ["PRIZEPICKS"],
    }


def _har(path: Path, insight_id: str) -> None:
    body = json.dumps({"insights": [_insight(insight_id)], "nextPageToken": None})
    payload = {
        "log": {
            "version": "1.2",
            "creator": {"name": "test", "version": "1"},
            "entries": [
                {
                    "startedDateTime": "2026-09-16T08:20:00Z",
                    "request": {
                        "method": "GET",
                        "url": "https://api.prizepicks.com/sportsdata/NFL/insights",
                        "headers": [],
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {"mimeType": "application/json", "text": body},
                    },
                }
            ],
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_malformed_and_incomplete_pagination_are_not_complete() -> None:
    _, malformed = parse_insights_payload(
        {"insights": [], "nextPageToken": 7},
        source_har_sha256="har",
        source_body_hash="body",
    )
    _, incomplete = parse_insights_payload(
        {"insights": [], "pagination": {"complete": False}},
        source_har_sha256="har",
        source_body_hash="body",
    )
    assert malformed["paginationState"] == PAGINATION_MALFORMED
    assert malformed["paginationComplete"] is False
    assert incomplete["paginationState"] == PAGINATION_INCOMPLETE
    assert incomplete["paginationComplete"] is False


def test_har_malformed_insights_is_accounted_as_evidence() -> None:
    raw = json.dumps(
        {
            "log": {
                "version": "1.2",
                "entries": [
                    {
                        "startedDateTime": "2026-09-16T08:20:00Z",
                        "request": {"method": "GET", "url": "https://api.prizepicks.com/sportsdata/NFL/insights"},
                        "response": {
                            "status": 200,
                            "content": {"text": json.dumps({"insights": {"bad": True}, "nextPageToken": "more"})},
                        },
                    }
                ],
            }
        }
    ).encode()
    result = ingest_har(raw, raw_bytes=raw)
    assert result["insightClaims"] == []
    assert result["evidencePayloads"][0]["nextPageTokenState"] == PAGINATION_MALFORMED
    assert result["indexStats"]["insights_pagination_incomplete"] == 1


def test_explicit_prompt_slate_runs_each_capture_and_union(tmp_path: Path) -> None:
    prompt = tmp_path / "deep-research-report.md"
    prompt.write_text("# Prompt\n\nPHASE ZERO — AUDIT\nPHASE ONE — ACCOUNT\n", encoding="utf-8")
    first = tmp_path / "CFB_capture.har"
    second = tmp_path / "NFL_capture.har"
    _har(first, "i-cfb")
    _har(second, "i-nfl")

    result = run_slate(
        inputs=[second, first],
        run_root=tmp_path / "slate",
        prompt=prompt,
        cutoff_from_capture=True,
        workspace=tmp_path / "runtime",
    )

    assert result["sourceCount"] == 2
    assert [row["sportHint"] for row in result["sources"]] == ["CFB", "NFL"]
    assert result["canonicalClaimCount"] == 2
    assert result["boardOfferCount"] == 0
    assert result["productionSelectionPermitted"] is False
    assert result["probabilityStatus"] == "NONE"
    assert result["nextAction"]["boardHarRequired"] is False

    root = tmp_path / "slate"
    census = json.loads((root / "har_census.json").read_text(encoding="utf-8"))
    assert census["executionId"] == result["executionId"]
    assert census["union"]["canonicalClaimCount"] == 2
    assert census["union"]["reconciliationState"] == "RECONCILED"
    assert json.loads((root / "research_queue_top100.json").read_text())["accounting"]["top100Count"] == 2
    receipt = json.loads((root / "execution_receipt.json").read_text(encoding="utf-8"))
    assert receipt["platform"]["github"] == "PENDING_REMOTE_READBACK"
    assert receipt["status"]["predictive"] == "PREDICTIVE_NOT_EARNED"
    assert receipt["contentHash"] == content_hash({k: v for k, v in receipt.items() if k != "contentHash"})
    assert receipt["boardHarRequired"] is False
    assert receipt["requiredOperatorAsks"] == []
    assert receipt["nextRequiredOperatorInput"] == "NONE"
    assert [row["name"] for row in receipt["autonomousPhases"]] == ["RESEARCH", "SETTLE", "TRAIN", "PLAYABLES"]
    top25 = json.loads((root / "top25.json").read_text(encoding="utf-8"))
    assert top25["boardOfferCount"] == 0
    assert len(top25["rows"]) > 0
    audit = (root / "audit_report.md").read_text(encoding="utf-8")
    assert "optional board HAR is not a required next" in audit

    composite_dirs = list((root / "composite_run").glob("RUN_*/"))
    assert len(composite_dirs) == 1
    index_receipt = json.loads((composite_dirs[0] / "search_index_receipt.json").read_text(encoding="utf-8"))
    assert index_receipt["documentKinds"]["insights"] == 2
