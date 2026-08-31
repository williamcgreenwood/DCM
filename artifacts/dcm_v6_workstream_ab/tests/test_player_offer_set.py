"""PlayerOfferSet: N markets for one player+event collapse to one research subject."""
from __future__ import annotations

from dcm.research.player_offer_set import PlayerOfferSet, build_player_offer_sets


PAIGE_MARKETS = [
    ("pts", 21.5),
    ("pra", 32),
    ("reb", 4),
    ("fantasy", 38),
    ("ast", 6.5),
    ("ra", 10.5),
    ("tpa", 4.5),
    ("fgm", 8.5),
    ("pr", 25.5),
    ("fga", 16.5),
    ("fg2m", 7),
    ("pa", 28.5),
]


def _row(pid, market, line, **extra):
    rec = {
        "projectionId": pid,
        "playerId": extra.get("playerId", "PAIGE"),
        "playerName": extra.get("playerName", "Paige Bueckers"),
        "sportFamily": extra.get("sportFamily", "basketball"),
        "league": extra.get("league", "WNBA"),
        "team": extra.get("team", "DAL"),
        "teamId": extra.get("teamId", "DAL"),
        "opponent": extra.get("opponent", "CON"),
        "eventId": extra.get("eventId", "DAL-CON-20260830"),
        "eventLabel": extra.get("eventLabel", "DAL-G vs CON Sun"),
        "eventStartTime": extra.get("eventStartTime", "2026-08-30T21:30:00Z"),
        "market": market,
        "line": line,
        "modifier": extra.get("modifier", "STANDARD"),
        "offeredHigher": True,
        "offeredLower": True,
        "boardId": extra.get("boardId", "FULL_GAME"),
        "status": "pre_game",
        "isLive": False,
        "side": "MORE",
    }
    rec.update({k: v for k, v in extra.items() if k not in rec})
    return rec


def test_twelve_paige_offers_collapse_to_one_set():
    rows = [
        _row(f"pp{i}", market, line)
        for i, (market, line) in enumerate(PAIGE_MARKETS)
    ]
    assert len(rows) == 12
    sets = build_player_offer_sets(rows)
    assert len(sets) == 1
    pos = sets[0]
    assert pos["playerId"] == "PAIGE"
    assert pos["eventId"] == "DAL-CON-20260830"
    assert pos["offerCount"] == 12
    assert len(pos["offers"]) == 12
    assert len(pos["markets"]) >= 8
    assert "pts" in pos["markets"]
    assert "pra" in pos["markets"]
    assert pos["playerName"] == "Paige Bueckers"
    assert pos["league"] == "WNBA"
    assert pos["setId"] == "POS|PAIGE|DAL-CON-20260830"
    assert PlayerOfferSet(
        playerId="PAIGE", playerName="Paige Bueckers", sportFamily="basketball",
        league="WNBA", team="DAL", opponent="CON", eventId="DAL-CON-20260830",
        eventLabel="x", eventStartTime="", offers=[],
    ).set_id == pos["setId"]


def test_same_player_two_events_stay_separate():
    rows = [
        _row("a1", "pts", 21.5, eventId="E1"),
        _row("a2", "ast", 6.5, eventId="E1"),
        _row("b1", "pts", 20.5, eventId="E2", eventLabel="DAL vs NYL"),
    ]
    sets = build_player_offer_sets(rows)
    assert len(sets) == 2
    by_event = {s["eventId"]: s for s in sets}
    assert by_event["E1"]["offerCount"] == 2
    assert by_event["E2"]["offerCount"] == 1


def test_eight_plus_markets_one_set_not_n_subjects():
    rows = [_row(f"m{i}", mkt, 10.5 + i) for i, (mkt, _) in enumerate(PAIGE_MARKETS[:8])]
    sets = build_player_offer_sets(rows)
    assert len(sets) == 1
    assert sets[0]["offerCount"] == 8
