"""Universal SubjectOfferSet and dependency graph contracts."""
from __future__ import annotations

from dcm.research.dependency_graph import build_research_dependency_graph
from dcm.research.player_offer_set import build_player_offer_sets
from dcm.research.subject_offer_set import build_subject_offer_sets


def _player_row(pid: str, market: str, line: float):
    return {
        "projectionId": pid,
        "playerId": "PAIGE",
        "playerName": "Paige Bueckers",
        "sportFamily": "basketball",
        "league": "WNBA",
        "teamId": "DAL",
        "opponent": "CON",
        "eventId": "E1",
        "eventLabel": "DAL vs CON",
        "eventStartTime": "2026-08-31T20:00:00Z",
        "market": market,
        "line": line,
        "modifier": "STANDARD",
        "offeredHigher": True,
        "offeredLower": True,
        "boardId": "FULL_GAME",
        "status": "pre_game",
        "isLive": False,
    }


def test_player_aliases_normalize_into_one_subject_offer_set():
    rows = [_player_row("a", "pts", 20.5), _player_row("b", "ast", 6.5)]
    sets = build_subject_offer_sets(rows)
    assert len(sets) == 1
    item = sets[0]
    assert item["setId"] == "SOS|PAIGE|E1"
    assert item["subjectId"] == "PAIGE"
    assert item["subjectType"] == "PLAYER"
    assert item["subjectName"] == "Paige Bueckers"
    assert item["sportId"] == "basketball"
    assert item["competitionId"] == "WNBA"
    assert item["affiliationId"] == "DAL"
    assert item["counterpartyIds"] == ["CON"]
    assert item["offerCount"] == 2
    assert item["markets"] == ["ast", "pts"]


def test_non_player_subject_is_first_class_not_forced_into_player_shape():
    rows = [
        {
            "projectionId": "fight-1",
            "subjectId": "FIGHTER_A",
            "subjectType": "FIGHTER",
            "subjectName": "Fighter A",
            "sportId": "combat",
            "competitionId": "UFC",
            "affiliationId": "GYM_A",
            "counterpartyIds": ["FIGHTER_B"],
            "eventId": "UFC-X",
            "eventLabel": "Fighter A vs Fighter B",
            "eventStart": "2026-09-01T02:00:00Z",
            "marketCanonicalName": "sig_strikes",
            "market": "sig_strikes",
            "line": 72.5,
            "modifier": "STANDARD",
            "offeredMore": True,
            "offeredLess": True,
            "period": "FULL_FIGHT",
            "status": "pre_event",
        }
    ]
    sets = build_subject_offer_sets(rows)
    assert len(sets) == 1
    item = sets[0]
    assert item["subjectType"] == "FIGHTER"
    assert item["subjectId"] == "FIGHTER_A"
    assert item["counterpartyIds"] == ["FIGHTER_B"]
    assert item["markets"] == ["sig_strikes"]
    # Legacy player compatibility intentionally does not fabricate a player.
    assert build_player_offer_sets(rows) == []


def test_research_dependency_graph_contains_only_universal_entity_types():
    rows = [_player_row("a", "pts", 20.5), _player_row("b", "reb", 4.5)]
    sets = build_subject_offer_sets(rows)
    graph = build_research_dependency_graph(sets)
    node_types = {node["type"] for node in graph["nodes"]}
    assert "Subject" in node_types
    assert "Affiliation" in node_types
    assert "Counterparty" in node_types
    assert "Competition" in node_types
    assert "SubjectOfferSet" in node_types
    assert "Player" not in node_types
    assert "Team" not in node_types
    assert graph["edgeCount"] > 0
    assert "contentHash" in graph


def test_same_subject_different_events_remain_separate():
    row_a = _player_row("a", "pts", 20.5)
    row_b = _player_row("b", "pts", 21.5)
    row_b["eventId"] = "E2"
    sets = build_subject_offer_sets([row_a, row_b])
    assert {item["eventId"] for item in sets} == {"E1", "E2"}
    assert len(sets) == 2
