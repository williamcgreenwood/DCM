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
from dcm.ingest.insight_context import enrich_insight_claims
from dcm.research.insight_bridge import plan_insight_host_research
from dcm.research.insight_bridge import build_insight_research_graph
from dcm.research.emit import emit_packets_and_graph
from dcm.research.batch import _host_task
from dcm.research.batch import build_next_research_batch
from dcm.research.acquisition import build_acquisition_action_graph, build_acquisition_actions, schedule_acquisition_actions
from dcm.chat.research_bridge import _researcher_view
from dcm.research.readiness import evaluate_research_os_readiness


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


def test_same_har_context_join_emits_director_jobs_without_offer_promotion() -> None:
    claims, _ = parse_insights_payload(
        {"insights": [_row()], "nextPageToken": None},
        source_har_sha256="har-hash", source_body_hash="body-hash",
        source_snapshot_time="2026-09-14T00:00:00Z",
    )
    joined, accounting = enrich_insight_claims(claims, [
        {"league": "NFL", "kind": "entities", "httpStatus": 200, "payload": {
            "content": {"teams": [{"team": {"teamId": "t-1"}, "players": [
                {"playerId": "p-1", "fullName": "Player One", "status": "ACTIVE"},
            ]}]},
        }},
        {"league": "NFL", "kind": "schedule", "httpStatus": 200, "payload": {
            "events": [{"eventId": "e-1", "scheduledTime": "2026-09-15T20:00:00Z",
                        "home": {"teamId": "t-1", "alias": "HOM"},
                        "away": {"teamId": "t-2", "alias": "AWY"}}],
        }},
    ])
    assert accounting["states"]["VERIFIED_HAR_LOCAL"] == 1
    claim = joined[0]
    assert claim["harIdentityState"] == "VERIFIED_HAR_LOCAL"
    assert claim["observedBookOffers"][0]["state"] == "OBSERVED_INSIGHT_NOT_CURRENT_BOARD"
    bridge = plan_insight_host_research(joined, "2026-09-14T12:00:00Z")
    assert bridge["accounting"]["researchProjectionCount"] == 1
    assert bridge["accounting"]["productionSelectionPermitted"] is False
    assert {request["scope"] for request in bridge["requests"]} == {
        "EVENT", "AFFILIATION", "COUNTERPARTY", "SUBJECT"
    }
    requests = {request["scope"]: request for request in bridge["requests"]}
    assert requests["EVENT"]["eventLabel"] == "AWY @ HOM"
    assert requests["AFFILIATION"]["affiliation"] == "HOM"
    assert requests["COUNTERPARTY"]["opponent"] == "AWY"
    assert requests["SUBJECT"]["affiliation"] == "HOM"
    assert requests["SUBJECT"]["opponent"] == "AWY"


def test_verified_har_context_emits_bounded_event_packet_and_sealed_view(tmp_path: Path) -> None:
    claims, _ = parse_insights_payload(
        {"insights": [_row()], "nextPageToken": None},
        source_har_sha256="har-hash", source_body_hash="body-hash",
        source_snapshot_time="2026-09-14T00:00:00Z",
    )
    joined, _ = enrich_insight_claims(claims, [
        {"league": "NFL", "kind": "entities", "httpStatus": 200, "payload": {
            "content": {"teams": [{"team": {"teamId": "t-1"}, "players": [
                {"playerId": "p-1", "fullName": "Player One", "status": "ACTIVE"},
            ]}]},
        }},
        {"league": "NFL", "kind": "schedule", "httpStatus": 200, "payload": {
            "events": [{"eventId": "e-1", "scheduledTime": "2026-09-15T20:00:00Z",
                        "home": {"teamId": "t-1", "alias": "HOM"},
                        "away": {"teamId": "t-2", "alias": "AWY"}}],
        }},
    ])
    bridge = plan_insight_host_research(joined, "2026-09-14T12:00:00Z")
    emitted = emit_packets_and_graph(
        tmp_path,
        offer_sets=[],
        claims=[],
        cutoff="2026-09-14T12:00:00Z",
        verified_insight_event_packets=bridge["eventPackets"],
    )
    event = emitted["eventPackets"][0]
    assert event["label"] == "AWY @ HOM"
    assert event["homeTeam"] == "HOM"
    assert event["awayTeam"] == "AWY"
    assert event["contextSource"] == "SAME_HAR_ENTITIES_SCHEDULE"
    assert event["rawHarPersisted"] is False
    assert event["freeFormInsightTextPersisted"] is False
    assert "this must not be persisted" not in json.dumps(event)
    universal = emitted["universalPackets"]
    assert universal["events"][0]["eventLabel"] == "AWY @ HOM"
    request = next(row for row in bridge["requests"] if row["scope"] == "EVENT")
    action = _host_task(request, action={"actionId": "AA_EVENT_e-1", "scope": "EVENT"})
    view = _researcher_view([action], [request], universal)
    assert view[0]["displayLabel"] == "AWY @ HOM"
    assert view[0]["eventLabel"] == "AWY @ HOM"
    assert "this must not be persisted" not in json.dumps(view)


def test_unresolved_har_identity_never_emits_a_director_job() -> None:
    claims, _ = parse_insights_payload(
        {"insights": [_row()], "nextPageToken": None},
        source_har_sha256="har-hash", source_body_hash="body-hash",
    )
    joined, _ = enrich_insight_claims(claims, [])
    bridge = plan_insight_host_research(joined, "2026-09-14T12:00:00Z")
    assert bridge["requests"] == []
    assert bridge["accounting"]["blocked"]["HAR_IDENTITY_UNRESOLVED"] == 1


def test_insights_research_graph_and_actions_never_create_board_offers() -> None:
    claims, _ = parse_insights_payload(
        {"insights": [_row()], "nextPageToken": None},
        source_har_sha256="har-hash", source_body_hash="body-hash",
        source_snapshot_time="2026-09-14T00:00:00Z",
    )
    joined, _ = enrich_insight_claims(claims, [
        {"league": "NFL", "kind": "entities", "httpStatus": 200, "payload": {
            "content": {"teams": [{"team": {"teamId": "t-1"}, "players": [
                {"playerId": "p-1", "fullName": "Player One", "status": "ACTIVE"},
            ]}]},
        }},
        {"league": "NFL", "kind": "schedule", "httpStatus": 200, "payload": {
            "events": [{"eventId": "e-1", "scheduledTime": "2026-09-15T20:00:00Z",
                        "home": {"teamId": "t-1", "alias": "HOM"},
                        "away": {"teamId": "t-2", "alias": "AWY"}}],
        }},
    ])
    bridge = plan_insight_host_research(joined, "2026-09-14T12:00:00Z")
    signal_graph = build_insight_research_graph(bridge)
    actions = build_acquisition_actions([], bridge["requests"])
    schedule = schedule_acquisition_actions(actions)
    action_graph = build_acquisition_action_graph(actions, schedule=schedule)

    assert signal_graph["researchOnly"] is True
    assert signal_graph["platformOfferCount"] == 0
    assert signal_graph["claimCount"] == 1
    assert actions["actionCount"] == 4
    assert all(action["offerIds"] == [] for action in actions["actions"])
    assert all(action["claimIds"] == [claims[0]["claimId"]] for action in actions["actions"])
    assert all(action["researchOnly"] is True for action in actions["actions"])
    assert action_graph["offerCount"] == 0
    assert action_graph["claimCount"] == 1
    assert any(edge["type"] == "covers_claim" for edge in action_graph["edges"])
    assert schedule["dependentOfferBudgetUsed"] == 0
    assert schedule["dependentClaimCountUsed"] > 0

    batch = build_next_research_batch(bridge["requests"], rows=[], max_entities=25)
    assert batch["selectedCount"] == 4
    assert batch["dependentOfferBudgetUsed"] == 0
    assert batch["dependentClaimCountUsed"] > 0
    assert all(task["researchOnly"] is True for task in batch["tasks"])
    assert all(task["dependentOfferCount"] == 0 for task in batch["tasks"])

    readiness = evaluate_research_os_readiness(
        board_graph={"contentHash": "empty-board", "nodeCount": 0},
        market_demand_graph={"contentHash": "empty-demand", "definitionCount": 0},
        requirement_graph={"contentHash": "signal-req", "nodeCount": 4, "topoOk": True},
        indexes_meta={"contentHash": "empty-index", "offerCount": 0},
        reused_evidence_scopes=0,
        acquisition_actions=actions,
        source_routing={"valid": True},
        research_signal_graph=signal_graph,
        research_only=True,
    )
    assert readiness["researchMayBegin"] is True
    assert readiness["researchMode"] == "INSIGHTS_RESEARCH_ONLY"
    assert readiness["prerequisites"]["boardGraphValid"] is False
    assert "BOARD_GRAPH_INVALID" not in readiness["blockers"]
