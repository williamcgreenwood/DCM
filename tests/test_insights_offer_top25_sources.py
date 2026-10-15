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


def test_research_funnel_keeps_all_candidates_and_emits_progressive_stages() -> None:
    claims = []
    for i in range(1005):
        claims.append({
            "claimId": f"claim-{i:04d}",
            "disposition": "PLAYER_PROP_CANDIDATE",
            "paginationComplete": True,
            "marketActive": True,
            "leagueId": "NFL",
            "event": {"eventId": f"event-{i // 8}", "scheduledTime": "2026-10-16T20:00:00Z"},
            "subjectId": f"subject-{i:04d}",
            "line": float(i % 30) + 0.5,
            "direction": "HIGHER" if i % 2 else "LOWER",
            "directionClass": "HIGHER_LOWER",
            "lastNCount": 10,
            "lastNHitCount": i % 11,
            "reportedHitRate": (i % 11) / 10,
            "bookCount": 3,
            "modifierCounts": {"STANDARD": 1},
        })
    queue = build_research_queue(claims)
    funnel = queue["researchFunnel"]
    stages = {stage["stage"]: stage for stage in funnel["stages"]}
    assert queue["accounting"]["top100Count"] == 100
    assert funnel["populationCount"] == 1005
    assert stages["TOP2000"]["count"] == 1005
    assert stages["TOP1000"]["count"] == 1000
    assert stages["TOP500"]["count"] == 500
    assert stages["TOP250"]["count"] == 250
    assert stages["TOP100"]["count"] == 100
    assert stages["TOP50"]["count"] == 50
    assert stages["TOP25"]["count"] == 25
    assert stages["TOP12"]["count"] == 12
    assert stages["TOP6"]["count"] == 6
    assert funnel["byLeague"]["NFL"]["populationCount"] == 1005
    assert funnel["byLeague"]["NFL"]["stages"][-1]["count"] == 6
    assert funnel["probabilityStatus"] == "NONE"
    assert funnel["productionSelectionPermitted"] is False
    assert all(row["attentionScoreType"] == "RESEARCH_PRIORITY_NOT_PROBABILITY" for row in funnel["rows"])


def test_research_funnel_retains_unresolved_line_side_claims_after_captured_rows() -> None:
    claims = []
    for i in range(127):
        claims.append({
            "claimId": f"claim-{i:03d}",
            "disposition": "PLAYER_PROP_CANDIDATE",
            "paginationComplete": True,
            "marketActive": True,
            "leagueId": "NHL",
            "event": {"eventId": f"event-{i}", "scheduledTime": "2026-10-16T20:00:00Z"},
            "subjectId": f"subject-{i:03d}",
            "line": 2.5 if i < 2 else None,
            "direction": "HIGHER" if i == 0 else "LOWER" if i == 1 else "UNKNOWN",
            "directionClass": "HIGHER_LOWER" if i < 2 else "UNKNOWN",
            "lastNCount": 8,
            "lastNHitCount": 4,
            "bookCount": 1,
        })
    claims.append({"claimId": "accounted-gameline", "disposition": "GAMELINE", "leagueId": "NFL"})
    queue = build_research_queue(claims)
    assert queue["accounting"]["top100Count"] == 100
    assert queue["researchFunnel"]["populationCount"] == 127
    assert queue["researchFunnel"]["accountedClaimCount"] == 128
    assert queue["researchFunnel"]["excludedFromRankingCount"] == 1
    assert queue["researchFunnel"]["excludedRows"][0]["claimId"] == "accounted-gameline"
    assert [row["offerBacking"] for row in queue["top100"][:2]] == [
        "INSIGHTS_OFFER_BACKED", "INSIGHTS_OFFER_BACKED"
    ]
    assert any(row["offerBacking"] == "CURRENT_OFFER_MISSING" for row in queue["top100"])
    assert all(row["probability"] is None for row in queue["researchFunnel"]["rows"])


def test_research_funnel_partitions_daily_stages_in_user_timezone() -> None:
    claims = []
    for i, scheduled in enumerate(("2026-10-15T23:30:00Z", "2026-10-16T02:00:00Z")):
        claims.append({
            "claimId": f"daily-{i}",
            "disposition": "PLAYER_PROP_CANDIDATE",
            "paginationComplete": True,
            "marketActive": True,
            "leagueId": "NFL",
            "event": {"eventId": f"event-{i}", "scheduledTime": scheduled},
            "subjectId": f"subject-{i}",
            "line": 2.5,
            "direction": "HIGHER",
            "directionClass": "HIGHER_LOWER",
            "lastNCount": 8,
            "lastNHitCount": 4,
            "bookCount": 1,
        })
    funnel = build_research_queue(claims, event_timezone="America/Los_Angeles")["researchFunnel"]
    assert funnel["eventTimezone"] == "America/Los_Angeles"
    assert funnel["eventTimezoneValid"] is True
    assert funnel["byEventDate"]["2026-10-15"]["populationCount"] == 2
    assert funnel["byEventDate"]["2026-10-15"]["stages"][-1]["count"] == 2


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
