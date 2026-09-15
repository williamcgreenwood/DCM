"""Join typed Outlier Insight claims to sanitized entities and schedule pages.

The join is deliberately local to one HAR: IDs are exact, cached (304) pages
remain unverified, and no response body is emitted.  Joined identity fields are
search aliases for host research, never a current-offer assertion.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from dcm.contracts.hashes import content_hash


def _text(value: Any) -> str:
    return str(value or "").strip()


def _items(payload: dict[str, Any], *names: str) -> list[dict[str, Any]]:
    for name in names:
        value = payload.get(name)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict) and isinstance(value.get("items"), list):
            return [row for row in value["items"] if isinstance(row, dict)]
    # Outlier's same-HAR entity response is a cacheable 304 payload with the
    # usable collection nested under ``content``.  Treat these wrappers the
    # same as ``data`` so an otherwise exact entity/schedule join cannot
    # silently become an empty research plan.  This remains bounded to the
    # named collections above; it never performs fuzzy discovery.
    for wrapper in ("data", "content", "result", "response"):
        nested = payload.get(wrapper)
        if isinstance(nested, dict):
            items = _items(nested, *names)
            if items:
                return items
    return []


def _team(row: dict[str, Any]) -> dict[str, str]:
    item = row.get("team") if isinstance(row.get("team"), dict) else row
    return {
        "id": _text(item.get("teamId") or item.get("id")),
        "name": _text(item.get("name") or item.get("fullName")),
        "alias": _text(item.get("alias") or item.get("abbreviation")),
    }


def _player(row: dict[str, Any]) -> dict[str, str]:
    item = row.get("player") if isinstance(row.get("player"), dict) else row
    return {
        "id": _text(item.get("playerId") or item.get("id")),
        "name": _text(item.get("fullName") or item.get("name") or item.get("displayName")),
        "teamId": _text(item.get("teamId")),
        "status": _text(item.get("status")),
    }


def _event(row: dict[str, Any]) -> dict[str, Any]:
    item = row.get("event") if isinstance(row.get("event"), dict) else row
    home = _team(item.get("home") if isinstance(item.get("home"), dict) else {})
    away = _team(item.get("away") if isinstance(item.get("away"), dict) else {})
    return {
        "id": _text(item.get("eventId") or item.get("id")),
        "scheduledTime": _text(item.get("scheduledTime") or item.get("startTime")),
        "status": _text(item.get("status")),
        "venue": _text(item.get("venue") if isinstance(item.get("venue"), str) else (item.get("venue") or {}).get("name")),
        "home": home,
        "away": away,
    }


def enrich_insight_claims(
    claims: list[dict[str, Any]], pages: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach exact same-HAR entity/schedule context and emit only bounded fields."""
    players: dict[tuple[str, str], tuple[dict[str, str], int]] = {}
    events: dict[tuple[str, str], tuple[dict[str, Any], int]] = {}
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("payload"), dict):
            continue
        league = _text(page.get("league")).upper()
        status = int(page.get("httpStatus") or 0)
        payload = page["payload"]
        kind = _text(page.get("kind")).lower()
        if kind == "entities":
            for row in _items(payload, "players"):
                item = _player(row)
                if item["id"]:
                    players[(league, item["id"])] = (item, status)
            for team_row in _items(payload, "teams"):
                nested = team_row.get("players") if isinstance(team_row.get("players"), list) else []
                team = _team(team_row)
                for row in nested:
                    if not isinstance(row, dict):
                        continue
                    item = _player(row)
                    if not item["teamId"]:
                        item["teamId"] = team["id"]
                    if item["id"]:
                        players[(league, item["id"])] = (item, status)
        elif kind == "schedule":
            for row in _items(payload, "events", "schedule"):
                item = _event(row)
                if item["id"]:
                    events[(league, item["id"])] = (item, status)

    joined: list[dict[str, Any]] = []
    states: Counter[str] = Counter()
    for original in claims:
        claim = dict(original)
        league = _text(claim.get("leagueId")).upper()
        event_stub = claim.get("event") if isinstance(claim.get("event"), dict) else {}
        player_pair = players.get((league, _text(claim.get("playerId"))))
        event_pair = events.get((league, _text(event_stub.get("eventId"))))
        if player_pair and event_pair:
            status = min(player_pair[1], event_pair[1])
            state = "VERIFIED_HAR_LOCAL" if status // 100 == 2 else "HAR_ALIAS_CACHED_UNVERIFIED"
            player, event = player_pair[0], event_pair[0]
            claim["harIdentity"] = {
                "state": state,
                "player": {"id": player["id"], "name": player["name"], "teamId": player["teamId"], "status": player["status"]},
                "event": event,
                "source": "SAME_HAR_ENTITIES_SCHEDULE",
            }
            claim["subjectName"] = player["name"] or claim.get("subjectName") or ""
            claim["event"] = {
                **event_stub,
                "eventId": event["id"],
                "scheduledTime": event["scheduledTime"] or event_stub.get("scheduledTime") or "",
                "home": event["home"],
                "away": event["away"],
            }
        else:
            state = "UNRESOLVED_HAR_IDENTITY"
            claim["harIdentity"] = {"state": state, "source": "SAME_HAR_ENTITIES_SCHEDULE"}
        claim["harIdentityState"] = state
        claim["claimHash"] = content_hash({k: v for k, v in claim.items() if k != "claimHash"})
        states[state] += 1
        joined.append(claim)
    return joined, {
        "schema": "pillars_dcm.insight_har_identity_accounting.v1",
        "claimCount": len(joined),
        "states": dict(sorted(states.items())),
        "contentHash": content_hash(joined),
    }
