"""Outlier Bet payload adapter.

Outlier is a catalogue/evidence surface, not a settlement source.  The
adapter keeps the Outlier capture as the source of truth while retaining an
explicit, configurable target-book offer.  A row can be accounted even when
the configured target book is absent, but it can never become selectable in
that state.  Side metadata is exact and conflict-aware: a missing or
contradictory Higher/Lower signal is ``UNKNOWN`` rather than an invented
inverse side.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from dcm.ingest.markets import map_league, map_stat, market_label

TARGET_BOOK = "PRIZEPICKS"
OUTLIER_SOURCE = "OUTLIER_BET"


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


def _alias_side(value: Any) -> str:
    """Read Outlier's compact ``o-``/``u-`` outcome alias when present."""
    token = str(value or "").strip().lower()
    if token.startswith("o-") or token.startswith("over-"):
        return "MORE"
    if token.startswith("u-") or token.startswith("under-"):
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


def _looks_like_outlier_item(item: Mapping[str, Any]) -> bool:
    """Accept current nested rows and the legacy flattened Outlier export.

    The flattened fallback is intentionally narrow: a plain ``props`` list is
    not enough to claim Outlier provenance, and JSON:API ``data`` objects are
    never inspected by this adapter.
    """
    if isinstance(item.get("outcome"), Mapping):
        return True
    if any(key in item for key in ("orf", "orfScore", "bookOdds", "outcomeId", "outcomeAlias")):
        return True
    return bool(item.get("player") or item.get("athlete") or item.get("name")) and bool(
        item.get("stat") or item.get("prop") or item.get("statType")
    ) and any(item.get(key) is not None for key in ("line", "value", "number", "points"))


def _target_book(obj: Mapping[str, Any], *, explicit: str | None) -> str:
    if explicit:
        return str(explicit).strip().upper() or TARGET_BOOK
    for key in ("targetBook", "target_book", "settlementBook", "settlement_book"):
        value = obj.get(key)
        if value:
            return str(value).strip().upper()
    dcm = obj.get("_dcm")
    if isinstance(dcm, Mapping):
        value = dcm.get("targetBook") or dcm.get("target_book")
        if value:
            return str(value).strip().upper()
    return TARGET_BOOK


def _book_offer(outcome: dict[str, Any], target_book: str) -> dict[str, Any] | None:
    offers = outcome.get("bookOdds")
    if not isinstance(offers, dict):
        return None
    direct = offers.get(target_book)
    if isinstance(direct, dict):
        return direct
    wanted = target_book.upper()
    for key, value in offers.items():
        if str(key).upper() == wanted and isinstance(value, dict):
            return value
    return None


def _book_modifier(offer: dict[str, Any] | None) -> str:
    if not offer or not isinstance(offer.get("identifier"), dict):
        return "OTHER"
    props = offer["identifier"].get("bookProps")
    if not isinstance(props, dict):
        return "OTHER"
    raw = props.get("odds_type") or props.get("oddsType")
    return _modifier(raw) if raw is not None else "OTHER"


def _status(outcome: Mapping[str, Any]) -> str:
    raw = str(outcome.get("status") or "").strip().lower().replace("-", "_")
    if raw in {"pre_game", "pregame"}:
        return "pre_game"
    if raw in {"in_progress", "live"}:
        return "in_progress"
    if raw in {"suspended", "halted"}:
        return "suspended"
    if raw:
        return "unknown"
    # Outlier's active flag describes an offer that is still on the board; it
    # does not prove a player is available or that the event has started.
    return "pre_game" if outcome.get("active") is True else "unknown"


def _resolve_side(outcome: Mapping[str, Any], offer: Mapping[str, Any] | None) -> tuple[str, bool, str]:
    raw = outcome.get("side") or outcome.get("selectedSide") or outcome.get("position")
    position_side = _side(raw)
    props = offer.get("identifier", {}).get("bookProps", {}) if isinstance(offer, Mapping) else {}
    props = props if isinstance(props, Mapping) else {}
    alias_side = _alias_side(props.get("outcomeAlias"))
    if position_side != "UNKNOWN" and alias_side != "UNKNOWN" and position_side != alias_side:
        return "UNKNOWN", True, "OUTLIER_SIDE_CONFLICT"
    resolved = position_side if position_side != "UNKNOWN" else alias_side
    return resolved, False, "" if resolved != "UNKNOWN" else "OUTLIER_SIDE_UNRESOLVED"


def _wager_types(outcome: Mapping[str, Any], side: str) -> list[str] | str:
    explicit = outcome.get("allowedWagerTypes") or outcome.get("allowed_wager_types")
    if explicit not in (None, "", []):
        return explicit
    # This is not an inverse-side inference.  Each Outlier outcome is a
    # concrete MORE or LESS outcome, so the captured outcome itself is the
    # only offered side for this row.
    return [side] if side in {"MORE", "LESS"} else ""


def _row(item: dict[str, Any], idx: int, *, target_book: str) -> dict[str, Any] | None:
    nested = item.get("outcome") if isinstance(item.get("outcome"), dict) else None
    outcome = nested or item
    line = _num(next((outcome.get(key) for key in ("line", "value", "number", "points") if outcome.get(key) is not None), None))
    player_id = str(
        outcome.get("playerId") or item.get("playerId") or item.get("player")
        or item.get("athlete") or item.get("name") or ""
    )
    outcome_id = str(
        outcome.get("outcomeId") or item.get("outcomeId") or item.get("id")
        or item.get("projectionId") or f"OUTLIER_ROW_{idx}"
    )
    if line is None or not player_id or not outcome_id:
        return None
    raw_market = str(
        outcome.get("proposition") or outcome.get("market") or outcome.get("marketLabel")
        or item.get("stat") or item.get("prop") or item.get("statType") or ""
    )
    market, label = map_stat(raw_market)
    league, sport = map_league(outcome.get("leagueId") or item.get("league") or item.get("sport"), None)
    offer = _book_offer(outcome, target_book)
    props = offer.get("identifier", {}).get("bookProps", {}) if offer else {}
    props = props if isinstance(props, dict) else {}
    side, side_conflict, side_reason = _resolve_side(outcome, offer)
    if side == "UNKNOWN" and not nested:
        # Legacy flattened exports put side under the row rather than the
        # nested outcome.  This is still an observed side, never an inverse.
        legacy_side = _side(item.get("side") or item.get("direction") or item.get("position"))
        if legacy_side != "UNKNOWN":
            side = legacy_side
            side_reason = "EXACT_CAPTURED_SIDE"
    offered_higher = side == "MORE"
    offered_lower = side == "LESS"
    wager_types = _wager_types(outcome, side)
    period = str(outcome.get("period") or outcome.get("boardId") or "").strip().upper()
    if not period:
        # Do not turn an absent period into an asserted regulation board.  The
        # downstream market plugin must see UNKNOWN and fail closed until the
        # capture supplies an exact period/overtime definition.
        include_overtime = outcome.get("includeOvertime")
        if include_overtime is True:
            period = "FULL_GAME"
        elif include_overtime is False:
            period = "REGULATION"
        else:
            period = "UNKNOWN"
    market_definition = str(
        outcome.get("marketDefinition")
        or outcome.get("marketDefinitionId")
        or outcome.get("marketId")
        or ""
    )
    target_odds = offer.get("odds") if offer else None
    status = _status(outcome)
    return {
        "projectionId": f"OUTLIER:{outcome_id}:{target_book}", "sourceProjectionId": outcome_id,
        "sportFamily": sport, "league": league,
        "eventId": str(outcome.get("eventId") or item.get("eventId") or item.get("gameId") or ""),
        "eventLabel": str(outcome.get("eventLabel") or item.get("event") or ""), "playerId": player_id,
        "playerName": str(item.get("playerName") or item.get("player") or item.get("athlete") or item.get("name") or ""),
        "teamId": str(outcome.get("teamId") or item.get("teamId") or item.get("team") or ""),
        "team": str(outcome.get("team") or item.get("team") or ""),
        "opponentId": str(outcome.get("oppTeamId") or item.get("opponentId") or item.get("opponent") or ""),
        "opponent": str(outcome.get("opponent") or item.get("opponent") or ""), "market": market,
        "marketLabel": label if label != "UNKNOWN" else market_label(market, raw_market), "line": line,
        "side": side, "offeredHigher": offered_higher, "offeredLower": offered_lower,
        "allowedWagerTypes": wager_types, "sideConflict": side_conflict, "sideResolution": side_reason or "EXACT_CAPTURED_SIDE",
        "modifier": _book_modifier(offer), "boardId": period, "period": period,
        "includeOvertime": outcome.get("includeOvertime"), "marketDefinition": market_definition,
        "marketDefinitionId": str(outcome.get("marketId") or ""),
        "productType": "PLAYER_PICKS", "role": str(item.get("position") or ""), "sourceBook": "OUTLIER_BET",
        "sourceFormat": "OUTLIER", "targetBook": target_book, "targetBookOfferPresent": offer is not None,
        "targetBookOutcomeAlias": str(props.get("outcomeAlias") or ""),
        "targetBookOdds": target_odds, "targetBookDecimalOdds": offer.get("decimal") if offer else None,
        "targetBookOfferBooks": sorted(str(k).upper() for k in (outcome.get("bookOdds") or {}).keys()) if isinstance(outcome.get("bookOdds"), dict) else [],
        "outlierOrf": item.get("orf"),
        "outlierOrfScore": item.get("orfScore"), "outlierHitRates": item.get("stats") if isinstance(item.get("stats"), dict) else {},
        "sourceUpdatedAt": str(item.get("updatedAt") or outcome.get("updatedAt") or ""),
        "eventStartTime": str(outcome.get("eventStartTime") or outcome.get("startTime") or ""),
        "status": status, "isLive": status in {"in_progress", "suspended"},
        "identityResolved": bool(player_id), "captureOrdinal": idx,
    }


def parse_outlier_payload(obj: Any, *, target_book: str | None = None) -> tuple[str, list[dict]] | None:
    if not isinstance(obj, dict):
        return None
    items = list(_items(obj))
    if not items:
        return None
    selected_book = _target_book(obj, explicit=target_book)
    rows = [
        row for index, item in enumerate(items)
        if _looks_like_outlier_item(item)
        and (row := _row(item, index, target_book=selected_book))
    ]
    return (OUTLIER_SOURCE, rows) if rows else None
