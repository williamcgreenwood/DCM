"""ResearchPopulationManifest: unique entities + fan-out after classify/plan."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.research.population import build_research_population_manifest
from dcm.research.requests import INFO_IMPORTANCE, plan_research
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


def test_manifest_counts_entities_and_fanout_priority():
    rows = [
        _row(projectionId=f"pp{i}", market=m)
        for i, m in enumerate(["pts", "reb", "ast", "pra", "pr", "pa", "ra", "3pm"])
    ]
    # football row must not break basketball entities
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
    assert man["schema"] == "pillars_dcm.research_population_manifest.v1"
    assert man["eligiblePropCount"] == 9
    players = man["entities"]["players"]
    paige = next(p for p in players if p["scopeId"] == "PAIGE")
    assert paige["dependentOfferCount"] == 8
    assert paige["importance"] == INFO_IMPORTANCE["PLAYER"]
    assert abs(paige["fanOutPriority"] - 8 * INFO_IMPORTANCE["PLAYER"]) < 1e-9
    assert man["uniqueCounts"]["PLAYER"] >= 2
    assert man["entities"]["offers"]
    assert man["entities"]["events"]
    assert man["entities"]["teams"]
    assert man["entities"]["marketDefinitions"]
    assert "contentHash" in man
    # football entity present, basketball still first-class
    nfl_player = next(p for p in players if p["scopeId"] == "QB1")
    assert nfl_player["dependentOfferCount"] == 1


def test_account_only_emits_manifest(tmp_path: Path):
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
    sets_path = dest / "player_offer_sets.json"
    assert man_path.is_file()
    assert sets_path.is_file()
    man = json.loads(man_path.read_text())
    assert man["eligiblePropCount"] >= 1
    assert "entities" in man
    sets = json.loads(sets_path.read_text())
    assert sets["setCount"] >= 1
