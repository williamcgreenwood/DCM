"""Outlier Bet payload adapter.

Outlier is a catalogue/evidence surface, not a settlement source. This adapter
preserves an explicit side and target-book metadata; it never infers a Lower
from another book. Missing/unknown target modifiers fail closed as ``OTHER``.
"""
from __future__ import annotations

from typing import Any, Iterable

from dcm.ingest.markets import map_league, map_stat, market_label

TARGET_BOOK = "PRIZEPICKS"


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _side(value: Any) -> str:
    token = str(value or "").strip().upper()
    if token in {"MORE", "OVER", "HIGHER"}:
        return "MORE"
    if token in {"LESS", "UNDER", "LOWER"}:
        return "LESS"
    return "UNKNOWN"


def _modifier(value: Any) -> str:
    token = str(value or "").strip().lower()
    if "goblin" in token:
        return "GOBLIN"
    if "demon" in token:
        return "DEMON"
    if token in {"standard", "", "none"}:
        return "STANDARD"
    return "OTHER"


def _items(obj: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("props", "markets", "offers", "lines"):
        value = obj.get(key)
        if isinstance(value, list):
            yield from (item for item in value if isinstance(item, dict))


def _book_offer(outcome: dict[str, Any]) -> dict[str, Any] | None:
    offers = outcome.get("bookOdds")
    offer = offers.get(TARGET_BOOK) if isinstance(offers, dict) else None
    return offer if isinstance(offer, dict) else None


def _book_modifier(offer: dict[str, Any] | None) -> str:
    if not offer or not isinstance(offer.get("identifier"), dict):
        return "OTHER"
    props = offer["identifier"].get("bookProps")
    if not isinstance(props, dict):
        return "OTHER"
    raw = props.get("odds_type") or props.get("oddsType")
    return _modifier(raw) if raw is not None else "OTHER"


def _row(item: dict[str, Any], idx: int) -> dict[str, Any] | None:
    outcome = item.get("outcome") if isinstance(item.get("outcome"), dict) else item
    line = _num(outcome.get("line"))
    player_id = str(outcome.get("playerId") or item.get("playerId") or "")
    outcome_id = str(outcome.get("outcomeId") or item.get("outcomeId") or "")
    if line is None or not player_id or not outcome_id:
        return None
    raw_market = str(outcome.get("proposition") or outcome.get("market") or outcome.get("marketLabel") or "")
    market, label = map_stat(raw_market)
    league, sport = map_league(outcome.get("leagueId") or item.get("league"), None)
    offer = _book_offer(outcome)
    props = offer.get("identifier", {}).get("bookProps", {}) if offer else {}
    props = props if isinstance(props, dict) else {}
    side = _side(outcome.get("position") or outcome.get("side"))
    return {
        "projectionId": f"OUTLIER:{outcome_id}:{TARGET_BOOK}", "sourceProjectionId": outcome_id,
        "sportFamily": sport, "league": league, "eventId": str(outcome.get("eventId") or ""),
        "eventLabel": str(outcome.get("eventLabel") or ""), "playerId": player_id,
        "playerName": str(item.get("playerName") or ""), "teamId": str(outcome.get("teamId") or ""),
        "team": str(outcome.get("team") or ""), "opponentId": str(outcome.get("oppTeamId") or ""),
        "opponent": str(outcome.get("opponent") or ""), "market": market,
        "marketLabel": label if label != "UNKNOWN" else market_label(market, raw_market), "line": line,
        "side": side, "offeredHigher": side == "MORE", "offeredLower": side == "LESS",
        "modifier": _book_modifier(offer), "boardId": "FULL_GAME" if bool(outcome.get("includeOvertime", True)) else "REGULATION",
        "productType": "PLAYER_PICKS", "role": str(item.get("position") or ""), "sourceBook": "OUTLIER_BET",
        "targetBook": TARGET_BOOK, "targetBookOfferPresent": offer is not None,
        "targetBookOutcomeAlias": str(props.get("outcomeAlias") or ""),
        "targetBookOdds": offer.get("odds") if offer else None, "outlierOrf": item.get("orf"),
        "outlierOrfScore": item.get("orfScore"), "outlierHitRates": item.get("stats") if isinstance(item.get("stats"), dict) else {},
        "sourceUpdatedAt": str(item.get("updatedAt") or ""), "status": "pre_game" if outcome.get("active") is True else "unknown",
        "identityResolved": bool(player_id), "captureOrdinal": idx,
    }


def parse_outlier_payload(obj: Any) -> tuple[str, list[dict]] | None:
    if not isinstance(obj, dict):
        return None
    items = list(_items(obj))
    if not items:
        return None
    rows = [row for index, item in enumerate(items) if (row := _row(item, index))]
    return ("OUTLIER_BET", rows) if rows else None
