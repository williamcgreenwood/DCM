"""ResearchPopulationManifest: canonical universal entities + legacy compatibility."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.research.population import (
    UNIVERSAL_IMPORTANCE,
    UNIVERSAL_FRESHNESS,
    build_research_population_manifest,
)
from dcm.research.requests import plan_research
from dcm.runner import run_dcm


def _row(**kwargs):
    rec = {
        "projectionId": "p0",
        "playerId": "PAIGE",
        "playerName": "Paige Bueckers",
        "sportFamily": "basketball",
        "league": "WNBA",
        "team": "DAL",
        "teamId": "DAL",
        "opponent": "CON",
        "eventId": "E1",
        "eventLabel": "DAL vs CON",
        "market": "pts",
        "line": 21.5,
        "modifier": "STANDARD",
        "offeredHigher": True,
        "offeredLower": True,
        "boardId": "FULL_GAME",
        "status": "pre_game",
        "isLive": False,
        "side": "MORE",
        "role": "G",
    }
    rec.update(kwargs)
    return rec


def test_manifest_counts_universal_entities_and_fanout_priority():
    rows = [
        _row(projectionId=f"pp{i}", market=m)
        for i, m in enumerate(["pts", "reb", "ast", "pra", "pr", "pa", "ra", "3pm"])
    ]
    rows.append(
        _row(
            projectionId="nfl1",
            playerId="QB1",
            playerName="QB One",
            sportFamily="gridiron",
            league="NFL",
            team="KC",
            teamId="KC",
            opponent="BUF",
            eventId="NFL-E",
            market="pass_yds",
            line=275.5,
            role="QB",
        )
    )
    cutoff = "2026-08-30T12:00:00Z"
    planned = plan_research(rows, cutoff)
    man = build_research_population_manifest(rows, planned=planned, cutoff=cutoff)
    assert man["schema"] == "pillars_dcm.research_population_manifest.v2"
    assert man["canonical"] is True
    assert man["eligibleOfferCount"] == 9
    assert man["subjectOfferSetCount"] == 2

    subjects = man["entities"]["subjects"]
    paige = next(p for p in subjects if p["entityId"] == "PAIGE")
    assert paige["dependentOfferCount"] == 8
    expected = (
        8
        * UNIVERSAL_IMPORTANCE["SUBJECT"]
        * UNIVERSAL_FRESHNESS["SUBJECT"]
    )
    assert abs(paige["fanOutPriority"] - expected) < 1e-9

    assert man["uniqueCounts"]["subjects"] >= 2
    assert man["entities"]["offers"]
    assert man["entities"]["events"]
    assert man["entities"]["affiliations"]
    assert man["entities"]["counterparties"]
    assert man["entities"]["competitions"]
    assert man["entities"]["marketDefinitions"]
    assert "players" not in man["entities"]
    assert "teams" not in man["entities"]
    assert "contentHash" in man

    nfl_subject = next(p for p in subjects if p["entityId"] == "QB1")
    assert nfl_subject["dependentOfferCount"] == 1


def test_account_only_emits_canonical_and_legacy_research_artifacts(tmp_path: Path):
    result = run_dcm(
        input_path=None,
        forecast_cutoff="2026-08-29T00:00:00Z",
        output_root=tmp_path,
        synthetic=True,
        research="fixture",
        account_only=True,
    )
    dest = Path(result["dest"])
    man_path = dest / "research_population_manifest.json"
    legacy_path = dest / "research_population_manifest_legacy.json"
    subject_sets_path = dest / "subject_offer_sets.json"
    player_sets_path = dest / "player_offer_sets.json"
    dependency_path = dest / "research_dependency_graph.json"
    universal_plan_path = dest / "universal_host_research_plan.json"
    sport_contract_path = dest / "sport_plugin_contract_registry.json"
    for path in (man_path, legacy_path, subject_sets_path, player_sets_path, dependency_path, universal_plan_path, sport_contract_path):
        assert path.is_file()

    man = json.loads(man_path.read_text())
    assert man["schema"] == "pillars_dcm.research_population_manifest.v2"
    assert man["eligibleOfferCount"] >= 1
    assert "subjects" in man["entities"]

    subject_sets = json.loads(subject_sets_path.read_text())
    assert subject_sets["setCount"] >= 1
    assert subject_sets["schema"] == "pillars_dcm.subject_offer_sets.v1"

    player_sets = json.loads(player_sets_path.read_text())
    assert player_sets["compatibilityOnly"] is True

    legacy = json.loads(legacy_path.read_text())
    assert legacy["schema"] == "pillars_dcm.research_population_manifest.v1"
    assert legacy["compatibilityOnly"] is True

    graph = json.loads(dependency_path.read_text())
    assert graph["schema"] == "pillars_dcm.research_dependency_graph.v1"

    universal_plan = json.loads(universal_plan_path.read_text())
    assert universal_plan["schema"] == "pillars_dcm.universal_host_research_plan.v1"
    assert universal_plan["researchHierarchy"][4] == "SUBJECT"
    assert "PLAYER" not in universal_plan["researchHierarchy"]
    assert "TEAM" not in universal_plan["researchHierarchy"]

    sport_contracts = json.loads(sport_contract_path.read_text())
    assert sport_contracts["schema"] == "pillars_dcm.sport_plugin_contract_registry.v1"
    assert sport_contracts["genericFallbackAllowed"] is False
    assert sport_contracts["productionCompleteSports"] == []
