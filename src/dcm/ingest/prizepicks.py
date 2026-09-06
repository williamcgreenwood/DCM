"""PrizePicks payload adapters. JSON:API, flattened projections, and already-normalized rows."""

from __future__ import annotations

from typing import Any

from dcm.ingest.markets import map_league, map_stat, market_label


def _rel(item: dict, included: dict, *names: str) -> dict | None:
    rels = item.get("relationships") or {}
    for name in names:
        ref = (rels.get(name) or {}).get("data")
        if isinstance(ref, list):
            ref = ref[0] if ref else None
        if not isinstance(ref, dict):
            continue
        found = included.get((str(ref.get("type")), str(ref.get("id"))))
        if isinstance(found, dict):
            return found
    return None


def _attrs(node: dict | None) -> dict:
    if not isinstance(node, dict):
        return {}
    a = node.get("attributes")
    return a if isinstance(a, dict) else {}


def _modifier(attrs: dict) -> str:
    odds = str(attrs.get("odds_type") or attrs.get("oddsType") or attrs.get("odds") or "standard").lower()
    blob = " ".join(str(attrs.get(k, "")) for k in ("odds_type", "oddsType", "projection_type", "custom_image", "flash_sale_line_score")).lower()
    if "goblin" in odds or "goblin" in blob:
        return "GOBLIN"
    if "demon" in odds or "demon" in blob:
        return "DEMON"
    if "standard" in odds or odds in ("", "standard", "none"):
        return "STANDARD"
    return "OTHER"


def _normalize_side(value: Any) -> str | None:
    u = str(value or "").strip().upper()
    if u in {"MORE", "OVER", "HIGHER"}:
        return "MORE"
    if u in {"LESS", "UNDER", "LOWER"}:
        return "LESS"
    return None


def _side_list(value: Any) -> tuple[bool, bool]:
    seq = value if isinstance(value, list) else [value] if value is not None else []
    more = less = False
    for item in seq:
        key = str(item or "").strip().lower()
        if key in {"more", "over", "higher"}:
            more = True
        elif key in {"less", "under", "lower"}:
            less = True
        elif key in {"both", "over_under", "under_or_over", "higher_lower", "more_less"}:
            more = less = True
    return more, less


def _side(attrs: dict) -> tuple[str, bool, bool]:
    """Verify offered sides. Missing side metadata fails closed."""
    explicit_more = attrs.get("offered_higher")
    explicit_less = attrs.get("offered_lower")
    more = bool(explicit_more) if explicit_more is not None else False
    less = bool(explicit_less) if explicit_less is not None else False
    for key in ("allowed_wager_types", "allowed_pick_types", "offered_sides", "wager_types"):
        if key in attrs:
            m, l = _side_list(attrs.get(key))
            more, less = more or m, less or l
    if attrs.get("over_odds") is not None or attrs.get("over") is not None:
        more = True
    if attrs.get("under_odds") is not None or attrs.get("under") is not None:
        less = True
    selected = _normalize_side(attrs.get("selected_side") or attrs.get("side") or attrs.get("pick_side"))
    if selected == "MORE":
        more = True
    elif selected == "LESS":
        less = True
    if _modifier(attrs) == "GOBLIN":
        return "MORE", True, False
    if selected is not None:
        return selected, more, less
    if more and not less:
        return "MORE", True, False
    if less and not more:
        return "LESS", False, True
    return "UNKNOWN", more, less


def _board_id(duration: dict | None, attrs: dict) -> str:
    d = _attrs(duration)
    name = str(d.get("name") or d.get("display_name") or attrs.get("board_time") or attrs.get("projection_type") or "FULL_GAME")
    u = name.upper()
    if "QTRS" in u or "QUARTERS WITH" in u or "QTRS W" in u:
        return "QTRS"
    if "1ST Q" in u or u in {"Q1", "1Q"} or "FIRST QUARTER" in u:
        return "Q1"
    if "2ND Q" in u or u in {"Q2", "2Q"} or "SECOND QUARTER" in u:
        return "Q2"
    if "3RD Q" in u or u in {"Q3", "3Q"} or "THIRD QUARTER" in u:
        return "Q3"
    if "4TH Q" in u or u in {"Q4", "4Q"} or "FOURTH QUARTER" in u:
        return "Q4"
    if "1H" in u or "FIRST HALF" in u or "1ST HALF" in u:
        return "1H"
    if "2H" in u or "SECOND HALF" in u:
        return "2H"
    return "FULL_GAME"



def _game_teams(ga: dict) -> tuple[str, str]:
    home = str(ga.get("home_team_name") or ga.get("home_name") or ga.get("home") or "")
    away = str(ga.get("away_team_name") or ga.get("away_name") or ga.get("away") or "")
    meta = ga.get("metadata")
    if isinstance(meta, dict):
        info = meta.get("game_info") if isinstance(meta.get("game_info"), dict) else {}
        teams = info.get("teams") if isinstance(info.get("teams"), dict) else {}
        home_n = teams.get("home") if isinstance(teams.get("home"), dict) else {}
        away_n = teams.get("away") if isinstance(teams.get("away"), dict) else {}
        home = home or str(home_n.get("abbreviation") or home_n.get("name") or "")
        away = away or str(away_n.get("abbreviation") or away_n.get("name") or "")
    return home, away


def _event_label(ga: dict, away: str, home: str, team: str, opponent: str) -> str:
    if away and home:
        return f"{away} @ {home}"
    return f"{team} vs {opponent}" if team or opponent else ""


def _status(attrs: dict) -> str:
    raw = str(attrs.get("status") or "").strip().lower()
    if raw in {"pre_game", "in_progress", "suspended"}:
        return raw
    if raw in {"pre-game", "pregame"}:
        return "pre_game"
    if raw in {"in-progress", "live"}:
        return "in_progress"
    if raw:
        return "unknown"
    return "unknown"


def _row_from_jsonapi(item: dict, included: dict) -> dict | None:
    attrs = _attrs(item)
    line = attrs.get("line_score", attrs.get("lineScore", attrs.get("line")))
    try:
        line_f = float(line)
    except (TypeError, ValueError):
        return None
    player = _rel(item, included, "new_player", "player")
    league_n = _rel(item, included, "league")
    game = _rel(item, included, "new_game", "game")
    duration = _rel(item, included, "duration")
    pa, la, ga = _attrs(player), _attrs(league_n), _attrs(game)
    player_name = str(pa.get("display_name") or pa.get("name") or attrs.get("description") or "UNKNOWN")
    # HAR player/game IDs only. Never infer player_id from name.
    player_rel_id = (player or {}).get("id")
    player_id = str(player_rel_id) if player_rel_id not in (None, "") else ""
    league_name = la.get("name") or la.get("league") or attrs.get("league_ppid")
    league, sport_family = map_league(league_name, la.get("sport") or la.get("sport_name") or la.get("icon"))
    stat_label = str(
        attrs.get("stat_type")
        or attrs.get("statType")
        or _attrs(_rel(item, included, "stat_type", "new_stat_type")).get("name")
        or "unknown"
    )
    market, market_label_s = map_stat(stat_label)
    home, away = _game_teams(ga)
    team = str(pa.get("team") or pa.get("team_name") or home or "UNK")
    opponent = away if team and home and str(team).upper() == str(home).upper() else (home if team and away and str(team).upper() == str(away).upper() else (home or away or "UNK"))
    event_id = str((game or {}).get("id") or ga.get("id") or attrs.get("game_id") or f"{league}_{team}_{opponent}")
    event_label = _event_label(ga, away, home, team, opponent)
    side, oh, ol = _side(attrs)
    modifier = _modifier(attrs)
    status = _status(attrs)
    return {
        "projectionId": str(item.get("id") or attrs.get("id") or f"{player_id}_{market}_{line_f}"),
        "sportFamily": sport_family,
        "league": league,
        "eventId": event_id,
        "eventLabel": event_label,
        "playerId": player_id,
        "playerName": player_name,
        "teamId": team,
        "team": team,
        "opponent": opponent,
        "market": market,
        "marketLabel": market_label_s,
        "line": line_f,
        "side": side,
        "offeredHigher": oh,
        "offeredLower": ol,
        "modifier": modifier,
        "boardId": _board_id(duration, attrs),
        "productType": "PLAYER_PICKS",
        "role": str(pa.get("position") or pa.get("position_abbreviation") or ""),
        "sourceUpdatedAt": str(attrs.get("updated_at") or ""),
        "eventStartTime": str(attrs.get("start_time") or ga.get("start_time") or ""),
        "status": status,
        "isLive": bool(attrs.get("is_live") or attrs.get("isLive")),
        "isLiveScored": bool(attrs.get("is_live_scored") or attrs.get("isLiveScored")),
        "inGame": bool(attrs.get("in_game") or attrs.get("inGame")),
        "eventType": str(attrs.get("event_type") or ""),
        "combo": bool(pa.get("combo")) or str(attrs.get("event_type") or "").lower() == "combo",
        "identityResolved": bool(player_id),
        "allowedWagerTypes": attrs.get("allowed_wager_types"),
        "statTypeRaw": stat_label,
        "leagueId": str((league_n or {}).get("id") or ""),
    }


def _row_from_normalized(item: dict) -> dict | None:
    if not item.get("projectionId"):
        return None
    line = item.get("line")
    try:
        line_f = float(line)
    except (TypeError, ValueError):
        return None
    market = str(item.get("market") or "")
    return {
        "projectionId": str(item["projectionId"]),
        "sportFamily": str(item.get("sportFamily") or "unknown"),
        "league": str(item.get("league") or "UNKNOWN"),
        "eventId": str(item.get("eventId") or ""),
        "eventLabel": str(item.get("eventLabel") or ""),
        "playerId": str(item.get("playerId") or ""),
        "playerName": str(item.get("playerName") or ""),
        "teamId": str(item.get("teamId") or item.get("team") or ""),
        "team": str(item.get("team") or ""),
        "opponent": str(item.get("opponent") or ""),
        "market": market,
        "marketLabel": str(item.get("marketLabel") or market_label(market)),
        "line": line_f,
        "side": str(item.get("side") or "UNKNOWN"),
        "offeredHigher": bool(item.get("offeredHigher", str(item.get("side")) == "MORE")),
        "offeredLower": bool(item.get("offeredLower", str(item.get("side")) == "LESS")),
        "modifier": str(item.get("modifier") or "OTHER"),
        "boardId": str(item.get("boardId") or "FULL_GAME"),
        "productType": str(item.get("productType") or "PLAYER_PICKS"),
        "role": str(item.get("role") or ""),
        "sourceUpdatedAt": str(item.get("sourceUpdatedAt") or ""),
        "eventStartTime": str(item.get("eventStartTime") or item.get("startTime") or ""),
    }


def parse_prizepicks_payload(obj: Any) -> tuple[str, list[dict]] | None:
    if not isinstance(obj, dict):
        return None
    data = obj.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("projectionId"):
        rows = [r for r in (_row_from_normalized(x) for x in data) if r]
        return ("PRIZEPICKS_NORMALIZED", rows) if rows else None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        first = data[0]
        attrs = first.get("attributes") if isinstance(first.get("attributes"), dict) else {}
        looks = first.get("type") in ("projection", "new_projection") or "line_score" in attrs or "lineScore" in attrs
        if looks:
            included: dict[tuple[str, str], dict] = {}
            for node in obj.get("included") or []:
                if isinstance(node, dict) and node.get("id") is not None:
                    included[(str(node.get("type")), str(node.get("id")))] = node
            rows = [r for r in (_row_from_jsonapi(x, included) for x in data if isinstance(x, dict)) if r]
            return ("PRIZEPICKS_JSONAPI", rows) if rows else None
    projections = obj.get("projections")
    if isinstance(projections, list) and projections:
        rows = []
        for p in projections:
            if isinstance(p, dict) and p.get("projectionId"):
                row = _row_from_normalized(p)
                if row:
                    rows.append(row)
        return ("PRIZEPICKS_FLAT", rows) if rows else None
    return None
