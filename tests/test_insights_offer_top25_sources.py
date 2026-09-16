"""Insights offer-equivalent Top25, sport-correct sources, pipeline constitution."""
from __future__ import annotations

from dcm.algorithms.pipeline_constitution import (
    PIPELINE_CONSTITUTION_ID,
    PipelineConstitutionGate,
    evaluate_insights_har_pipeline,
)
from dcm.ingest.insights import parse_insights_payload
from dcm.research.acquisition import build_acquisition_actions
from dcm.research.insight_bridge import insights_offer_snapshots
from dcm.research.insight_queue import build_research_queue
from dcm.research.source_catalog import (
    candidate_sources_for_sport,
    load_source_catalog,
    normalize_competition_id,
    sport_family_for_league,
)
from dcm.research.source_health import (
    default_sport_source_health,
    default_universal_source_health,
)


def _insight_row(*, position: str = "OVER", line: float | None = 4.5, league: str = "NFL") -> dict:
    row = {
        "insightId": "i-1",
        "subjectType": "PLAYER",
        "playerId": "p-1",
        "teamId": "t-1",
        "leagueId": league,
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
        "line": line,
        "position": position,
        "outcomeLabel": "Over" if position == "OVER" else ("Under" if position == "UNDER" else position),
        "lastN": [True, True, False, True, True],
        "hitRate": 0.8,
        "books": ["PRIZEPICKS"],
        "bookOdds": {"PRIZEPICKS": {"odds": "-137", "decimal": 1.73, "identifier": {"bookProps": {"odds_type": "standard"}}}},
        "splits": [],
        "playerData": {"items": [{"date": "2026-09-10T00:00:00Z", "eventId": "old-1", "value": 5.0, "stat": 5.0}]},
    }
    return row


def test_insights_only_fixture_fills_top100_and_insights_top25() -> None:
    claims = []
    for i in range(30):
        row = _insight_row()
        row["insightId"] = f"i-{i}"
        row["playerId"] = f"p-{i}"
        row["eventId"] = f"e-{i // 3}"
        row["event"] = {
            "eventId": f"e-{i // 3}",
            "scheduledTime": "2026-09-15T20:00:00Z",
            "home": {"teamId": "t-1", "alias": "HOM"},
            "away": {"teamId": "t-2", "alias": "AWY"},
        }
        row["line"] = 3.5 + (i % 5)
        parsed, _ = parse_insights_payload(
            {"insights": [row], "nextPageToken": None},
            source_har_sha256="har",
            source_body_hash="body",
        )
        claims.extend(parsed)
    queue = build_research_queue(claims)
    offers = insights_offer_snapshots(claims)
    assert queue["accounting"]["top100Count"] > 0
    assert queue["accounting"]["top25Count"] > 0
    assert len(queue["insightsTop25"]) > 0
    assert all(row.get("offerBacking") == "INSIGHTS_OFFER_BACKED" for row in queue["top25"])
    assert all(row.get("candidateClass") == "RESEARCH_CANDIDATE" for row in queue["top25"])
    assert all(row.get("predictiveClaim") == "NONE" for row in queue["top25"])
    assert offers["insightsOfferCount"] == len(claims)
    assert offers["boardOfferCount"] == 0
    assert offers["accounting"]["productionSelectionPermitted"] is False


def test_missing_side_fail_closes_insights_offer() -> None:
    row = _insight_row(position="HOME")
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
    assert offers["insightsOfferCount"] == 0
    assert offers["accounting"]["blocked"].get("MISSING_SIDE") or offers["accounting"]["blocked"].get("NOT_PLAYER_PROP_CANDIDATE")

    # Explicit player prop with unknown side also fail-closes.
    bad = _insight_row(position="UNKNOWN")
    bad["position"] = "UNKNOWN"
    bad["outcomeLabel"] = "UNKNOWN"
    claims2, _ = parse_insights_payload(
        {"insights": [bad], "nextPageToken": None},
        source_har_sha256="har",
        source_body_hash="body",
    )
    # Force missing side even if adapter marks differently
    for claim in claims2:
        claim["direction"] = "UNKNOWN"
        claim["directionClass"] = "UNKNOWN"
        claim["disposition"] = "PLAYER_PROP_CANDIDATE"
    offers2 = insights_offer_snapshots(claims2)
    assert offers2["insightsOfferCount"] == 0
    assert offers2["accounting"]["blocked"]["MISSING_SIDE"] >= 1


def test_sport_source_mapping_unit() -> None:
    assert normalize_competition_id("NCAAFB") == "CFB"
    assert sport_family_for_league("MLB") == "baseball"
    assert sport_family_for_league("NFL") == "gridiron"
    assert sport_family_for_league("WNBA") == "basketball"
    assert sport_family_for_league("SOCCER") == "soccer"
    assert sport_family_for_league("CFB") == "gridiron"

    cat = load_source_catalog()
    assert any(s["sourceId"] == "official_mlb" for s in cat["sources"])
    mlb = candidate_sources_for_sport(league="MLB", entity_kind="SUBJECT")
    mlb_ids = [s["sourceId"] for s in mlb]
    assert "official_mlb" in mlb_ids or "baseball_reference" in mlb_ids
    assert "cfb_official_athletics" not in mlb_ids
    assert "open_meteo_weather" not in mlb_ids

    health = default_sport_source_health(league="MLB")
    route = health.route(claim_type="SUBJECT", sport="MLB")
    assert route
    assert route[0] != "CFB_WEATHER"
    assert "CFB_WEATHER" not in route

    cfb = default_sport_source_health(league="CFB")
    env = cfb.route(claim_type="ENVIRONMENT", sport="CFB")
    assert env[0] == "CFB_WEATHER"

    uni = default_universal_source_health()
    mlb_subj = uni.route(claim_type="SUBJECT", sport="MLB")
    assert mlb_subj[0] != "CFB_WEATHER"


def test_acquisition_never_picks_cfb_weather_for_mlb() -> None:
    rows = [{
        "projectionId": "p1",
        "playerId": "bat1",
        "eventId": "g1",
        "league": "MLB",
        "sportFamily": "baseball",
        "market": "h",
        "line": 1.5,
        "offeredHigher": True,
        "offeredLower": False,
        "modifier": "STANDARD",
        "status": "pre_game",
    }]
    requests = [{
        "request_id": "REQ_MLB_1",
        "scope": "SUBJECT",
        "scope_id": "bat1",
        "need": "availability_role_opportunity_recent_performance",
        "forecast_cutoff": "2026-09-16T00:00:00Z",
        "dependent_prop_count": 1,
        "dependent_offer_ids": ["p1"],
        "league": "MLB",
        "sportFamily": "baseball",
        "eventId": "g1",
        "priority_score": 1.0,
        "hierarchy_rank": 1,
    }]
    doc = build_acquisition_actions(rows, requests)
    assert doc["actionCount"] >= 1
    for act in doc["actions"]:
        assert act.get("sourceId") != "CFB_WEATHER"
        assert "CFB_WEATHER" not in (act.get("sourceCandidates") or [])


def test_pipeline_constitution_gate_records_consumers() -> None:
    gate = evaluate_insights_har_pipeline(context={"claimCount": 30, "top100Count": 30, "top25Count": 25})
    assert gate["constitutionId"] == PIPELINE_CONSTITUTION_ID
    assert gate["valid"] is True
    assert gate["blockers"] == []
    assert gate["activatedAlgorithmIds"]
    assert len(gate["stages"]) == 7
    assert all(stage["status"] == "ACTIVE" for stage in gate["stages"])
    assert all(stage.get("consumer") for stage in gate["stages"])
    assert gate["telemetry"]["ceremonialViolations"] == []
    assert gate["predictiveClaim"] == "NONE"
    assert gate["learningRevision"] == "LR000000"

    # Ceremonial ACTIVE without downstream consumer is blocked by telemetry helpers.
    bad = PipelineConstitutionGate()
    bad.telemetry.record(
        "ALG-SORT-001",
        problem_class="FINAL_RANK",
        producer="test",
        consumer="nowhere",
        activated=True,
        phase="EXECUTED",
        downstream_used=False,
    )
    snap = bad.telemetry.snapshot()
    assert snap["ceremonialViolations"]
