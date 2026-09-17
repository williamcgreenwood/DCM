"""HAR-only autonomous closure: Insights captures are the platform capture."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.chat.session import HostSession
from dcm.chat.slate import run_slate
from dcm.chat.slate_autonomous import (
    AUTONOMOUS_PHASE_ORDER,
    MIN_TRAINING_LABELS,
    advance_autonomous_closure,
    classify_claim_event_timing,
    operator_contract,
    receipt_requires_board_har,
)
from dcm.ingest.insights import parse_insights_payload
from dcm.research.insight_bridge import insights_offer_snapshots
from dcm.research.insight_queue import build_research_queue


def _insight(*, insight_id: str = "i-1", position: str = "OVER", scheduled: str = "2026-09-20T17:00:00Z", status: str | None = None) -> dict:
    event = {"eventId": f"event-{insight_id}", "scheduledTime": scheduled}
    if status:
        event["status"] = status
    return {
        "insightId": insight_id,
        "subjectType": "PLAYER",
        "playerId": f"player-{insight_id}",
        "teamId": "team-1",
        "leagueId": "NFL",
        "eventId": f"event-{insight_id}",
        "event": event,
        "marketType": "PLAYER_PROP",
        "marketId": f"market-{insight_id}",
        "marketOutcomeId": f"outcome-{insight_id}",
        "marketActive": True,
        "proposition": "RECEPTIONS",
        "line": 4.5,
        "position": position,
        "outcomeLabel": "Over" if position == "OVER" else ("Under" if position == "UNDER" else position),
        "lastN": [True, True, False],
        "hitRate": 0.66,
        "books": ["PRIZEPICKS"],
    }


def _har(path: Path, insight_id: str, *, position: str = "OVER") -> None:
    body = json.dumps({"insights": [_insight(insight_id=insight_id, position=position)], "nextPageToken": None})
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


def test_receipt_requires_board_har_detects_forbidden_asks() -> None:
    assert receipt_requires_board_har({"boardHarRequired": True}) is True
    assert receipt_requires_board_har({
        "requiredOperatorAsks": ["Provide a current platform board/HAR for Insights-only"],
    }) is True
    assert receipt_requires_board_har({
        "operatorContract": {"boardHarRequired": False, "requiredOperatorAsks": [], "nextRequiredOperatorInput": "NONE"},
        "note": "Insights HARs with line+side are the platform capture",
    }) is False


def test_operator_contract_never_requires_board_har() -> None:
    with_offers = operator_contract(board_offer_count=0, insights_offer_count=12, claim_count=12)
    assert with_offers["boardHarRequired"] is False
    assert with_offers["requiredOperatorAsks"] == []
    assert with_offers["optionalBoardHar"]["blocksResearchTop100"] is False
    assert with_offers["informational"]["CURRENT_OFFER_MISSING"] is False
    assert receipt_requires_board_har(with_offers) is False

    missing = operator_contract(board_offer_count=0, insights_offer_count=0, claim_count=3)
    assert missing["informational"]["CURRENT_OFFER_MISSING"] is True
    assert missing["boardHarRequired"] is False
    assert missing["requiredOperatorAsks"] == []
    assert receipt_requires_board_har(missing) is False


def test_classify_event_timing_does_not_invent_final() -> None:
    future = {"event": {"scheduledTime": "2026-09-20T17:00:00Z"}}
    assert classify_claim_event_timing(future, cutoff="2026-09-16T08:20:00Z") == "FUTURE"
    final = {"event": {"scheduledTime": "2026-09-10T17:00:00Z", "status": "FINAL"}}
    assert classify_claim_event_timing(final, cutoff="2026-09-16T08:20:00Z") == "FINAL"
    unknown = {"event": {"scheduledTime": "2026-09-10T17:00:00Z"}}
    assert classify_claim_event_timing(unknown, cutoff="2026-09-16T08:20:00Z") == "UNKNOWN"


def test_insights_only_slate_receipt_has_no_board_har_required_blocker(tmp_path: Path) -> None:
    prompt = tmp_path / "deep-research-report.md"
    prompt.write_text("# Prompt\n\nPHASE ZERO — AUDIT\nPHASE ONE — ACCOUNT\n", encoding="utf-8")
    har = tmp_path / "NFL_insights.har"
    _har(har, "i-nfl")

    result = run_slate(
        inputs=[har],
        run_root=tmp_path / "slate",
        prompt=prompt,
        workspace=tmp_path / "runtime",
    )

    assert result["boardOfferCount"] == 0
    assert result["boardHarRequired"] is False
    assert result["nextRequiredOperatorInput"] == "NONE"
    assert result["queueTop25Count"] > 0
    assert result["insightsOfferCount"] > 0

    root = tmp_path / "slate"
    receipt = json.loads((root / "execution_receipt.json").read_text(encoding="utf-8"))
    top25 = json.loads((root / "top25.json").read_text(encoding="utf-8"))
    playables = json.loads((root / "playables.json").read_text(encoding="utf-8"))
    feature = json.loads((root / "feature_snapshot.json").read_text(encoding="utf-8"))

    assert receipt["boardHarRequired"] is False
    assert receipt["requiredOperatorAsks"] == []
    assert receipt["nextRequiredOperatorInput"] == "NONE"
    assert receipt["operatorContract"]["boardHarRequired"] is False
    assert receipt["operatorContract"]["optionalBoardHar"]["blocksAutonomousLoop"] is False
    assert receipt_requires_board_har(receipt) is False
    assert [row["name"] for row in receipt["autonomousPhases"]] == list(AUTONOMOUS_PHASE_ORDER)
    assert all("status" in row for row in receipt["autonomousPhases"])
    assert {row["name"] for row in receipt["autonomousPhases"]} == set(AUTONOMOUS_PHASE_ORDER)
    settle = next(row for row in receipt["autonomousPhases"] if row["name"] == "SETTLE")
    assert settle["status"] in {"DEFERRED_FUTURE", "AWAITING_AUTHORITATIVE_OUTCOMES", "SETTLED"}
    train = next(row for row in receipt["autonomousPhases"] if row["name"] == "TRAIN")
    assert train["status"] in {
        "SKIPPED_NO_SETTLEMENT",
        "SKIPPED_INSUFFICIENT_LABELS",
        "SKIPPED_CALIBRATION_NOT_EARNED",
    }
    playable_phase = next(row for row in receipt["autonomousPhases"] if row["name"] == "PLAYABLES")
    assert playable_phase["status"] == "ABSTAINED_GATES_NOT_MET"
    assert playable_phase["count"] == 0

    assert top25["boardOfferCount"] == 0
    assert len(top25["rows"]) > 0
    assert all(row.get("offerBacking") == "INSIGHTS_OFFER_BACKED" for row in top25["rows"])
    assert top25["boardHarRequired"] is False
    assert playables["count"] == 0
    assert "CURRENT_OFFER_MISSING" not in str(playables.get("reason") or "")
    assert feature["boardHarRequired"] is False
    assert "NO_VERIFIED_CURRENT_BOARD_OFFERS" not in feature["reasonCodes"]
    assert "Provide a current platform board" not in (root / "audit_report.md").read_text(encoding="utf-8")
    dumped = json.dumps(receipt)
    assert "Provide a current platform board" not in dumped
    assert "current board HAR" not in dumped.lower() or "do not" in dumped.lower()

    # Exercise the real ChatGPT host boundary with a supplemental current
    # offer response.  It must import without a batch and refresh the same
    # run's selection artifacts; no replacement HAR is part of this path.
    composite_id = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))["compositeRunId"]
    inner = root / "composite_run" / composite_id
    snapshot = json.loads((inner / "insights_offer_snapshots.json").read_text(encoding="utf-8"))["snapshots"][0]
    offer_response = tmp_path / "current_offer_response.json"
    offer_response.write_text(json.dumps({
        "schema": "pillars_dcm.research_response.v1",
        "offerRevalidations": [{
            "claimId": snapshot["claimId"],
            "projectionId": snapshot.get("projectionId"),
            "eventId": snapshot["eventId"],
            "subjectId": snapshot["subjectId"],
            "proposition": snapshot["proposition"],
            "periodLabel": snapshot.get("periodLabel") or "",
            "line": snapshot["line"],
            "direction": snapshot["direction"],
            "eventStatus": "PRE_GAME",
            "scheduledTime": snapshot.get("scheduledTime"),
            "marketDefinitionId": "NFL_RECEPTIONS_FULL_GAME_V1",
            "settlementRuleHash": "test-rule-hash",
            "sourceId": "approved-current-offer",
            "sourceUrl": "https://example.com/current-offer",
            "sourceHash": "current-offer-hash",
            "authority": "APPROVED_PLATFORM_SOURCE",
            "retrievedAt": "2026-09-17T21:50:00Z",
        }],
    }), encoding="utf-8")
    resumed = HostSession.open(root, workspace=tmp_path / "runtime").autonomous_resume(offer_response)
    assert resumed["processedResponses"][0]["offerRevalidation"]["status"] == "AVAILABLE"
    assert resumed["boardHarRequired"] is False


def test_missing_side_still_fail_closes_and_does_not_fill_insights_offers() -> None:
    row = _insight(position="HOME")
    row["position"] = "HOME"
    row["outcomeLabel"] = "HOM"
    row["subjectType"] = "TEAM"
    row["playerId"] = None
    row["marketType"] = "GAMELINE"
    row["proposition"] = "MONEYLINE"
    claims, _ = parse_insights_payload(
        {"insights": [row], "nextPageToken": None},
        source_har_sha256="har",
        source_body_hash="body",
    )
    offers = insights_offer_snapshots(claims)
    queue = build_research_queue(claims)
    assert offers["insightsOfferCount"] == 0
    assert offers["accounting"]["blocked"]
    assert all(item.get("offerBacking") != "INSIGHTS_OFFER_BACKED" or item.get("candidateClass") != "RESEARCH_CANDIDATE" for item in queue["top25"])
    closure = advance_autonomous_closure(
        session=None,
        claims=claims,
        board_offer_count=0,
        insights_offer_count=0,
        insights_top25_count=0,
        cutoff="2026-09-16T08:20:00Z",
        observations_imported=False,
        research_queue_selected=0,
    )
    assert closure["operatorContract"]["informational"]["CURRENT_OFFER_MISSING"] is True
    assert closure["boardHarRequired"] is False
    assert receipt_requires_board_har(closure) is False


def test_final_events_settle_whole_population_without_inventing(tmp_path: Path) -> None:
    parsed, _ = parse_insights_payload(
        {
            "insights": [
                _insight(insight_id="i-final", scheduled="2026-09-10T17:00:00Z", status="FINAL"),
            ],
            "nextPageToken": None,
        },
        source_har_sha256="har",
        source_body_hash="body",
    )
    claim = parsed[0]
    outcomes = [
        {
            "eventId": claim["event"]["eventId"],
            "subjectId": claim["subjectId"],
            "proposition": claim["proposition"],
            "periodLabel": claim.get("periodLabel") or "",
            "line": claim["line"],
            "direction": claim["direction"],
            "observedValue": 6.0,
            "sourceHash": "outcome-hash",
            "authority": "OFFICIAL_TEST",
            "metric": "RECEPTIONS",
        }
    ]
    dest = tmp_path / "run"
    dest.mkdir()
    outcomes_path = tmp_path / "outcomes.json"
    outcomes_path.write_text(json.dumps({"outcomes": outcomes}), encoding="utf-8")

    class _Session:
        def __init__(self, path: Path) -> None:
            self.dest = path
            self.workspace = path

    closure = advance_autonomous_closure(
        session=_Session(dest),
        claims=parsed,
        board_offer_count=0,
        insights_offer_count=1,
        insights_top25_count=1,
        cutoff="2026-09-16T08:20:00Z",
        observations_imported=False,
        research_queue_selected=1,
        outcomes=outcomes_path,
    )
    settle = next(row for row in closure["phases"] if row["name"] == "SETTLE")
    assert settle["status"] == "SETTLED"
    assert settle["outcomesInvented"] is False
    assert closure["settlement"]["settledCount"] >= 1
    train = next(row for row in closure["phases"] if row["name"] == "TRAIN")
    assert train["trainingEligibleCount"] >= 0
    if train["trainingEligibleCount"] < MIN_TRAINING_LABELS:
        assert train["status"] in {"SKIPPED_INSUFFICIENT_LABELS", "SKIPPED_NO_SETTLEMENT"}
    assert closure["learningRevision"] == "LR000000"
    assert receipt_requires_board_har(closure) is False
