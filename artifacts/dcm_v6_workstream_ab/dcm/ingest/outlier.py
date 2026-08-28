"""Outlier Bet payload adapter. Distinct from PrizePicks. Unknown shapes fail closed."""

from __future__ import annotations

from typing import Any

from dcm.ingest.markets import map_league, map_stat, market_label


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _row(item: dict, idx: int) -> dict | None:
    line = _num(item.get("line") or item.get("value") or item.get("number") or item.get("points"))
    if line is None:
        return None
    player_name = str(item.get("player") or item.get("playerName") or item.get("athlete") or item.get("name") or "")
    if not player_name:
        return None
    stat = str(item.get("stat") or item.get("market") or item.get("prop") or item.get("statType") or "")
    market, label = map_stat(stat)
    league, sport = map_league(item.get("league") or item.get("sport"), item.get("sport"))
    side_raw = str(item.get("side") or item.get("direction") or "").upper()
    side = "MORE" if side_raw in ("MORE", "OVER", "HIGHER") else "LESS" if side_raw in ("LESS", "UNDER", "LOWER") else "UNKNOWN"
    book = str(item.get("book") or item.get("sportsbook") or item.get("source") or "OUTLIER")
    pid = str(item.get("id") or item.get("projectionId") or f"out_{idx}_{player_name}_{market}_{line}")
    team = str(item.get("team") or "UNK")
    opp = str(item.get("opponent") or "UNK")
    return {
        "projectionId": pid,
        "sportFamily": sport,
        "league": league,
        "eventId": str(item.get("eventId") or item.get("gameId") or f"{league}_{team}_{opp}"),
        "eventLabel": str(item.get("event") or f"{team} vs {opp}"),
        "playerId": str(item.get("playerId") or player_name),
        "playerName": player_name,
        "teamId": team,
        "team": team,
        "opponent": opp,
        "market": market,
        "marketLabel": label if label != "UNKNOWN" else market_label(market, stat),
        "line": line,
        "side": side,
        "offeredHigher": side == "MORE" or side == "UNKNOWN",
        "offeredLower": side == "LESS" or side == "UNKNOWN",
        "modifier": "STANDARD",
        "boardId": "FULL_GAME",
        "productType": "PLAYER_PICKS",
        "role": str(item.get("position") or ""),
        "sourceBook": book,
        "sourceUpdatedAt": str(item.get("updatedAt") or ""),
    }


def parse_outlier_payload(obj: Any) -> tuple[str, list[dict]] | None:
    if not isinstance(obj, dict):
        return None
    for key in ("markets", "props", "offers", "lines", "projections"):
        seq = obj.get(key)
        if isinstance(seq, list) and seq and isinstance(seq[0], dict):
            if seq[0].get("projectionId") and key == "projections":
                continue
            rows = [r for i, x in enumerate(seq) if isinstance(x, dict) for r in [_row(x, i)] if r]
            if rows:
                return ("OUTLIER_BET", rows)
    return None
