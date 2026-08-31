"""Identity resolution. Name ≠ PrizePicks player_id. HAR ids freeze when present."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash

CFB_NAMES_PATH = Path(__file__).resolve().parents[2] / "configs" / "cfb_player_reboot_eligible.json"


@lru_cache(maxsize=1)
def _cfb_names() -> frozenset[str]:
    if not CFB_NAMES_PATH.is_file():
        return frozenset()
    data = json.loads(CFB_NAMES_PATH.read_text(encoding="utf-8"))
    names = data.get("official_listed_names_2026-08-27") or data.get("players") or data.get("names") or []
    if isinstance(names, dict):
        names = names.get("eligible") or names.get("list") or []
    return frozenset(str(n).strip().lower() for n in names)


def looks_like_platform_id(player_id: str, player_name: str) -> bool:
    if not player_id:
        return False
    if player_id.strip().lower() == player_name.strip().lower():
        return False
    compact = player_id.replace("-", "")
    if compact.isdigit() and len(compact) >= 4:
        return True
    if len(player_id) >= 8 and any(ch.isdigit() for ch in player_id):
        return True
    return False


def resolve_row(row: dict[str, Any], *, official_map: dict[str, str] | None = None) -> dict[str, Any]:
    official_map = official_map or {}
    name = str(row.get("playerName") or "")
    pid = str(row.get("playerId") or "")
    league = str(row.get("league") or "")
    listed = name.lower() in _cfb_names() if league == "CFB" else False
    mapped = official_map.get(name) or official_map.get(name.lower())
    platform_id = None
    if mapped:
        platform_id = mapped
    elif looks_like_platform_id(pid, name):
        platform_id = pid
    out = dict(row)
    out["cfbOfficialNameListed"] = listed
    out["cfbOfficialPlayerId"] = platform_id if (league == "CFB" and platform_id) else None
    out["identityResolved"] = bool(platform_id) or league != "CFB"
    out["identityBlocker"] = None if out["identityResolved"] or not listed else "CFB_OFFICIAL_PLAYER_ID_ABSENT"
    return out


def freeze_map(rows: list[dict]) -> dict[str, Any]:
    pairs = []
    for r in rows:
        if r.get("cfbOfficialPlayerId"):
            pairs.append({"name": r.get("playerName"), "playerId": r.get("cfbOfficialPlayerId")})
    payload = {"pairs": pairs, "count": len(pairs)}
    payload["contentHash"] = content_hash(payload)
    return payload


def build_player_index(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group every HAR player by playerId. Name ≠ platform id."""
    by_player: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("playerId") or "")
        if not pid:
            continue
        rec = by_player.get(pid)
        if rec is None:
            rec = {
                "playerId": pid,
                "playerName": row.get("playerName"),
                "sportFamily": row.get("sportFamily"),
                "league": row.get("league"),
                "identityResolved": bool(row.get("identityResolved")),
                "identityBlocker": row.get("identityBlocker"),
                "cfbOfficialPlayerId": row.get("cfbOfficialPlayerId"),
                "events": [],
                "teams": [],
                "offers": [],
            }
            by_player[pid] = rec
        event_id = str(row.get("eventId") or "")
        if event_id and event_id not in rec["events"]:
            rec["events"].append(event_id)
        team = str(row.get("team") or row.get("teamId") or "")
        if team and team not in rec["teams"]:
            rec["teams"].append(team)
        rec["offers"].append(
            {
                "projectionId": row.get("projectionId"),
                "market": row.get("market"),
                "line": row.get("line"),
                "eventId": event_id,
                "team": team,
                "opponent": row.get("opponent"),
                "modifier": row.get("modifier"),
            }
        )
    players = [by_player[k] for k in sorted(by_player)]
    for rec in players:
        rec["offerCount"] = len(rec["offers"])
        rec["eventCount"] = len(rec["events"])
    body = {
        "schema": "pillars_dcm.player_index.v1",
        "playerCount": len(players),
        "offerCount": sum(p["offerCount"] for p in players),
        "nameIsNotId": True,
        "players": players,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body

