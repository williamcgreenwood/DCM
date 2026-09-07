"""NFL must use the shared gridiron contract without inheriting CFB routing."""
from __future__ import annotations

from dcm.research.acquisition import build_acquisition_actions
from dcm.research.os_graphs import build_market_demand_graph
from dcm.research.requests import plan_research
from dcm.research.source_health import default_gridiron_source_health
from dcm.sports.football.research_requirements import assess_football_support, market_requirements


def _nfl_row() -> dict:
    return {
        "projectionId": "NFL-OFFER-1", "sportFamily": "gridiron", "league": "NFL",
        "market": "pass_yds", "eventId": "NFL-EVENT-1", "teamId": "NFL-HOME",
        "opponentId": "NFL-AWAY", "playerId": "NFL-QB-1", "playerName": "NFL QB",
        "line": 245.5, "offeredHigher": True, "offeredLower": True, "status": "pre_game",
    }


def test_nfl_market_requirements_and_support_are_league_keyed():
    assert "pass_yds" in market_requirements("NFL")
    logs = [{"pass_att": 31, "pass_yds": 250} for _ in range(3)]
    assessed = assess_football_support(
        league="NFL", market="pass_yds", role="QB", status="ACTIVE", logs=logs,
        definition_verified=True, team_event={"playsObserved": 62, "pass_defense": 1.0},
    )
    assert assessed["modelable"] is True
    assert assessed["playableSupport"] is True


def test_nfl_demand_and_actions_use_nfl_sources_not_cfb_sources():
    rows = [_nfl_row()]
    demand = build_market_demand_graph(rows)
    assert demand["nodes"][0]["guardedLaunchSupported"] is True
    planned = plan_research(rows, "2026-09-07T00:00:00Z")
    actions = build_acquisition_actions(rows, planned["requests"])
    assert actions["actionCount"] > 0
    assert all(action["league"] == "NFL" for action in actions["actions"])
    assert any("NFL_OFFICIAL" in action["sourceCandidates"] for action in actions["actions"] if action["scope"] == "EVENT")
    health = default_gridiron_source_health("NFL")
    assert "NFL_OFFICIAL" in health.route(claim_type="EVENT", sport="NFL")
    assert "CFB_OFFICIAL_GAMEBOOK" not in health.route(claim_type="EVENT", sport="NFL")
