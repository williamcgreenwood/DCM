"""Tests for the Insights research-to-production consumer boundary."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.chat.insight_closure import build_top100_artifact, evaluate_insight_selection
from dcm.ingest.insights import parse_insights_payload
from dcm.research.insight_bridge import insights_offer_snapshots, plan_insight_host_research
from dcm.research.insight_queue import build_research_queue
from dcm.research.offer_revalidation import import_offer_revalidations


def _claim(*, insight_id: str = "i-1", scheduled: str = "2099-09-20T17:00:00Z") -> dict:
    return {
        "insightId": insight_id,
        "subjectType": "PLAYER",
        "playerId": "player-1",
        "teamId": "team-1",
        "leagueId": "NFL",
        "eventId": "event-1",
        "event": {
            "eventId": "event-1",
            "scheduledTime": scheduled,
            "home": {"id": "team-1", "teamId": "team-1", "alias": "HOM"},
            "away": {"id": "team-2", "teamId": "team-2", "alias": "AWY"},
        },
        "marketType": "PLAYER_PROP",
        "marketId": "market-1",
        "marketOutcomeId": "outcome-1",
        "marketActive": True,
        "proposition": "RECEPTIONS",
        "line": 4.5,
        "position": "OVER",
        "outcomeLabel": "Over",
        "lastN": [True, True, False, True],
        "hitRate": 0.75,
        "books": ["PRIZEPICKS"],
    }


def _parsed_claim() -> dict:
    rows, _ = parse_insights_payload(
        {"insights": [_claim()], "nextPageToken": None},
        source_har_sha256="har-sha",
        source_body_hash="body-sha",
    )
    assert rows
    # The production HAR join supplies this exact same-HAR identity.  The
    # parser-only fixture adds the equivalent verified join explicitly so the
    # consumer test exercises the production path rather than an unresolved
    # identity branch.
    rows[0]["harIdentity"] = {
        "state": "VERIFIED_HAR_LOCAL",
        "player": {"id": "player-1", "name": "Player One", "teamId": "team-1", "status": "ACTIVE"},
        "event": {
            "id": "event-1",
            "scheduledTime": "2099-09-20T17:00:00Z",
            "status": "PRE_GAME",
            "home": {"id": "team-1", "alias": "HOM"},
            "away": {"id": "team-2", "alias": "AWY"},
        },
        "source": "SAME_HAR_ENTITIES_SCHEDULE",
    }
    rows[0]["harIdentityState"] = "VERIFIED_HAR_LOCAL"
    return rows[0]


def test_top100_is_research_priority_and_never_a_probability() -> None:
    claim = _parsed_claim()
    queue = build_research_queue([claim])
    artifact = build_top100_artifact(queue, requests=[], coverage={"complete": False})

    assert artifact["candidateCount"] == 1
    assert artifact["productionTop100"] == []
    assert artifact["rows"][0]["probability"] is None
    assert artifact["rows"][0]["researchPriorityScoreType"] == "NOT_A_PROBABILITY"


def test_offer_revalidation_unavailable_is_durable_and_not_a_har_request(tmp_path: Path) -> None:
    claim = _parsed_claim()
    snapshots = insights_offer_snapshots([claim])["snapshots"]
    unavailable = import_offer_revalidations(
        tmp_path,
        [],
        snapshots=snapshots,
        cutoff="2026-09-17T21:51:00Z",
    )

    assert unavailable["status"] == "UNAVAILABLE"
    assert unavailable["blocker"] == "OFFER_REVALIDATION_UNAVAILABLE"
    assert unavailable["boardHarRequired"] is False

    observed = snapshots[0]
    available = import_offer_revalidations(
        tmp_path,
        [{
            "claimId": observed["claimId"],
            "eventId": observed["eventId"],
            "subjectId": observed["subjectId"],
            "proposition": observed["proposition"],
            "periodLabel": observed.get("periodLabel") or "",
            "line": observed["line"],
            "direction": observed["direction"],
            "eventStatus": "PRE_GAME",
            "marketDefinitionId": "NFL_RECEPTIONS_FULL_GAME_V1",
            "settlementRuleHash": "rule-sha",
            "sourceId": "approved_offer_source",
            "sourceUrl": "https://example.com/current-offer",
            "sourceHash": "current-offer-sha",
            "authority": "APPROVED_PLATFORM_SOURCE",
            "retrievedAt": "2026-09-17T21:50:00Z",
        }],
        snapshots=snapshots,
        cutoff="2026-09-17T21:51:00Z",
    )
    assert available["status"] == "AVAILABLE"
    assert available["snapshotCount"] == 1


def test_current_offer_model_gates_produce_top100_top25_and_freeze(tmp_path: Path) -> None:
    claim = _parsed_claim()
    queue = build_research_queue([claim])
    bridge = plan_insight_host_research([claim], "2026-09-17T21:51:00Z")
    (tmp_path / "research_requests.json").write_text(json.dumps(bridge["requests"]), encoding="utf-8")
    snapshots = insights_offer_snapshots([claim])["snapshots"]
    import_offer_revalidations(
        tmp_path,
        [{
            "claimId": snapshots[0]["claimId"],
            "eventId": snapshots[0]["eventId"],
            "subjectId": snapshots[0]["subjectId"],
            "proposition": snapshots[0]["proposition"],
            "periodLabel": snapshots[0].get("periodLabel") or "",
            "line": snapshots[0]["line"],
            "direction": snapshots[0]["direction"],
            "eventStatus": "PRE_GAME",
            "scheduledTime": "2099-09-20T17:00:00Z",
            "marketDefinitionId": "NFL_RECEPTIONS_FULL_GAME_V1",
            "settlementRuleHash": "rule-sha",
            "sourceId": "approved_offer_source",
            "sourceUrl": "https://example.com/current-offer",
            "sourceHash": "current-offer-sha",
            "authority": "APPROVED_PLATFORM_SOURCE",
            "retrievedAt": "2026-09-17T21:50:00Z",
        }],
        snapshots=snapshots,
        cutoff="2026-09-17T21:51:00Z",
    )
    coverage = {
        "complete": True,
        "requested": len(bridge["requests"]),
        "requests": [
            {"requestId": request["request_id"], "complete": True}
            for request in bridge["requests"]
        ],
    }
    model = {
        "status": "CERTIFIED",
        "registryState": "PROMOTED",
        "predictiveCertified": True,
        "productionRootCertified": True,
        "predictiveClaim": "PREDICTIVE",
        "predictions": [{
            "claimId": claim["claimId"],
            "evidenceSafeP": 0.72,
            "calibratedP": 0.70,
            "lowerBound": 0.61,
            "reliability": 0.9,
            "dataQuality": 0.9,
            "fragility": 0.1,
            "oodRisk": 0.1,
            "falseSignRisk": 0.05,
            "epistemicUncertainty": 0.1,
            "volatility": 0.2,
            "forecastCutoff": "2026-09-17T21:51:00Z",
            "parameterSnapshot": {"status": "ACTIVE"},
        }],
    }

    state = evaluate_insight_selection(
        dest=tmp_path,
        claims=[claim],
        queue=queue,
        coverage=coverage,
        model_result=model,
        board_offer_count=0,
    )

    selection = state["selection"]
    assert selection["productionTop100Count"] == 1
    assert selection["productionTop25Count"] == 1
    assert selection["playableCount"] == 1
    assert selection["freeze"]["status"] == "FROZEN"
    assert state["top100"]["productionTop100Count"] == 1
    assert state["top100"]["productionTop100"]
    assert selection["noBoardHarAsk"] is True
