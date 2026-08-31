"""PlayerResearchPacket: full-season logs, derived windows, adapter-owned HTML."""
from __future__ import annotations

from pathlib import Path

from dcm.research.adapters.basketball_reference import (
    BasketballReferenceGameLogAdapter,
    BasketballReferencePlayerAdapter,
)
from dcm.research.player_offer_set import build_player_offer_sets
from dcm.research.player_packet import build_packets_for_offer_sets, build_player_research_packet
from dcm.research.gamelog import normalize_basketball_log


FIXTURES = Path(__file__).resolve().parent / "research_fixtures"
ASOF = "2026-08-30T12:00:00Z"


def _season_logs(n=37):
    logs = []
    for i in range(n):
        logs.append({
            "date_game": f"2026-05-{(i % 28) + 1:02d}",
            "mp": f"{28 + (i % 8)}:{(i * 3) % 60:02d}",
            "pts": 14 + (i % 12),
            "fga": 12 + (i % 7),
            "fg": 6 + (i % 5),
            "fg3": 1 + (i % 3),
            "fg3a": 4 + (i % 4),
            "ft": 2,
            "fta": 2 + (i % 2),
            "trb": 3 + (i % 4),
            "ast": 4 + (i % 5),
            "stl": i % 3,
            "blk": i % 2,
            "tov": 1 + (i % 3),
            "gs": 1,
        })
    return logs


def _paige_rows(n=12):
    markets = ["pts", "pra", "reb", "ast", "pr", "pa", "ra", "3pm", "stl", "blk", "tov", "fgm"]
    rows = []
    for i, mkt in enumerate(markets[:n]):
        rows.append({
            "projectionId": f"pp{i}",
            "playerId": "PAIGE",
            "playerName": "Paige Bueckers",
            "sportFamily": "basketball",
            "league": "WNBA",
            "team": "DAL",
            "teamId": "DAL",
            "opponent": "CON",
            "eventId": "E1",
            "eventLabel": "DAL vs CON",
            "eventStartTime": "2026-08-30T21:30:00Z",
            "market": mkt,
            "line": 10.5 + i,
            "modifier": "STANDARD",
            "offeredHigher": True,
            "offeredLower": True,
            "boardId": "FULL_GAME",
            "status": "pre_game",
        })
    return rows


def test_full_season_37_logs_l5_derived_full_log_retained():
    logs = _season_logs(37)
    packet = build_player_research_packet(
        identity={"playerId": "PAIGE", "playerName": "Paige Bueckers", "league": "WNBA", "sportFamily": "basketball"},
        status="ACTIVE",
        role_hints={"role": "starter"},
        structured_logs=logs,
        as_of=ASOF,
        league="WNBA",
    )
    assert packet["gameLogCount"] == 37
    assert packet["fullSeasonRetained"] is True
    assert len(packet["gameLogs"]) == 37
    assert packet["windows"]["L5"]["nAvailable"] == 5
    assert packet["windows"]["L5"]["derivedFromFullLog"] is True
    assert packet["windows"]["L5"]["doesNotReplaceFullLog"] is True
    assert packet["opportunity"]["support_n"] >= 3
    assert packet["efficiency"]["support_n"] >= 3
    assert packet["opportunity"]["from"] == "FULL_USABLE_LOGS"
    assert packet["evidenceUsed"] is True
    assert packet["priorUsedAsResearch"] is False
    assert packet["windows"]["L3"]["nRequested"] == 3
    assert packet["windows"]["L10"]["nAvailable"] == 10
    assert packet["windows"]["L20"]["nAvailable"] == 20


def test_mp_trb_normalize_via_adapter_html():
    html = (FIXTURES / "br_gamelog_paige.html").read_text(encoding="utf-8")
    adapter = BasketballReferenceGameLogAdapter(retrieved_at=ASOF)
    batch = adapter.fetch_normalize({
        "html": html,
        "url": "https://www.basketball-reference.com/wnba/players/b/bueckpa01w/gamelog/2026/",
        "retrieved_at": ASOF,
        "published_at": ASOF,
        "league": "WNBA",
    })
    assert batch["logs"]
    first = batch["logs"][0]
    assert first["minutes"] > 0
    assert "reb" in first
    raw_mp = normalize_basketball_log({"mp": "32:15", "trb": 5, "pts": 25, "ast": 6})
    assert raw_mp is not None
    assert abs(raw_mp["minutes"] - 32.25) < 1e-9
    assert raw_mp["reb"] == 5
    packet = build_player_research_packet(
        identity={"playerId": "PAIGE", "league": "WNBA"},
        gamelog_html=html,
        as_of=ASOF,
        league="WNBA",
        source_url="https://www.basketball-reference.com/wnba/players/b/bueckpa01w/gamelog/2026/",
        retrieved_at=ASOF,
    )
    assert packet["gameLogCount"] >= 3
    assert packet["evidenceUsed"] is True
    player_html = (FIXTURES / "br_player_paige.html").read_text(encoding="utf-8")
    summary = BasketballReferencePlayerAdapter(retrieved_at=ASOF).normalize({
        "html": player_html,
        "url": "https://www.basketball-reference.com/wnba/players/b/bueckpa01w.html",
        "retrievedAt": ASOF,
        "publishedAt": ASOF,
    })
    assert summary
    assert str(summary[0]["fields"].get("games")) == "37"


def test_one_packet_reused_for_every_offer_in_set():
    rows = _paige_rows(12)
    sets = build_player_offer_sets(rows)
    assert len(sets) == 1
    claims = [{
        "semantic_scope": "PLAYER",
        "scope_id": "PAIGE",
        "claim_value": {
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": _season_logs(37),
            "opportunity": {"support_n": 37},
            "efficiency": {"support_n": 37},
        },
        "claim_hash": "claim-paige",
        "url": "https://www.basketball-reference.com/wnba/players/b/bueckpa01w/gamelog/2026/",
        "source_id": "BASKETBALL_REFERENCE",
        "source_hash": "src-paige",
    }]
    packets = build_packets_for_offer_sets(sets, claims=claims, as_of=ASOF)
    assert len(packets) == 1
    packet = packets[0]
    assert packet["packetId"]
    offer_ids = [o["projectionId"] for o in sets[0]["offers"]]
    assert set(packet["appliesToProjectionIds"]) == set(offer_ids)
    assert len(packet["appliesToProjectionIds"]) == 12
    # same packet id drives every market
    for pid in offer_ids:
        assert pid in packet["appliesToProjectionIds"]
        assert packet["packetId"] == packets[0]["packetId"]


def test_pra_identity_fields_on_packet():
    packet = build_player_research_packet(
        identity={"playerId": "PAIGE", "league": "WNBA"},
        structured_logs=_season_logs(10),
        as_of=ASOF,
        league="WNBA",
    )
    pra = packet["praIdentity"]
    assert pra["componentsPresent"] is True
    assert pra["pts_mean"] is not None
    assert pra["reb_mean"] is not None
    assert pra["ast_mean"] is not None
    assert abs(pra["pra_mean"] - (pra["pts_mean"] + pra["reb_mean"] + pra["ast_mean"])) < 1e-9
    assert pra["identity"] == "pra = pts + reb + ast"
    assert pra["support_n"] >= 3


def test_minutes_missing_flagged_never_silent_prior_as_research():
    logs = [
        {"mp": 30, "pts": 20, "trb": 4, "ast": 5, "fga": 14},
        {"pts": 18, "trb": 3, "ast": 4},  # no minutes
        {"mp": "DNP", "pts": 0},
    ]
    packet = build_player_research_packet(
        identity={"playerId": "PAIGE", "league": "WNBA"},
        structured_logs=logs,
        as_of=ASOF,
        league="WNBA",
    )
    assert "MINUTES_MISSING" in packet["flags"]
    assert packet["gameLogCount"] == 1
    assert packet["priorUsedAsResearch"] is False
    # evidenceUsed true only because one usable log exists, not because a prior was filled
    assert packet["evidenceUsed"] is True
    empty = build_player_research_packet(
        identity={"playerId": "PAIGE", "league": "WNBA"},
        structured_logs=[{"pts": 20}, {"pts": 18}],
        as_of=ASOF,
        league="WNBA",
    )
    assert empty["evidenceUsed"] is False
    assert empty["opportunity"]["support_n"] == 0
    assert empty["priorUsedAsResearch"] is False
    assert "NO_USABLE_GAME_LOGS" in empty["flags"]
    assert empty["thin"] is True
