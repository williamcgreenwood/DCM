"""Official WNBA/NBA schedule+status adapters. Fixture JSON first; live opt-in.

These adapters own official-league page/API parsing. Model code consumes
normalized fields (game status, start, venue, home/away). No cookies.
"""
from __future__ import annotations

import json
from typing import Any

from dcm.research.adapters.base import adapter_record, live_fetch_enabled
from dcm.research.adapters.basketball_reference import _fetch_http
from dcm.research.adapters.espn_status import canonicalize_status


def _as_text(document: dict[str, Any]) -> str:
    for key in ("json", "html", "text", "body", "content"):
        value = document.get(key)
        if isinstance(value, (str, bytes)):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
        if isinstance(value, (dict, list)):
            return json.dumps(value)
    return ""


def _games(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("games", "schedule", "events", "items"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
    return []


def _normalize_game(raw: dict[str, Any], *, league: str, adapter_id: str, adapter_version: str,
                    url: str, retrieved: str | None, published: str | None, source_class: str) -> dict[str, Any]:
    status_raw = raw.get("status") or raw.get("gameStatus") or raw.get("state")
    status = str(status_raw or "scheduled").strip().lower()
    if status in {"final", "closed", "complete"}:
        game_status = "FINAL"
    elif status in {"live", "in_progress", "inprogress", "1st", "2nd", "3rd", "4th", "ot", "halftime"}:
        game_status = "IN_PROGRESS"
    elif status in {"postponed", "suspended", "cancelled", "canceled"}:
        game_status = "SUSPENDED"
    else:
        game_status = "SCHEDULED"
    fields = {
        "league": league,
        "eventId": raw.get("gameId") or raw.get("eventId") or raw.get("id"),
        "start": raw.get("start") or raw.get("startTime") or raw.get("gameTime") or raw.get("tipoff"),
        "venue": raw.get("venue") or raw.get("arena") or raw.get("location"),
        "home": raw.get("home") or raw.get("homeTeam") or raw.get("homeAbbr"),
        "away": raw.get("away") or raw.get("awayTeam") or raw.get("visitor") or raw.get("awayAbbr"),
        "gameStatus": game_status,
        "rawStatus": status_raw,
        "environment": raw.get("environment") or ("indoor" if league in {"WNBA", "NBA"} else None),
        "playerStatus": canonicalize_status(raw.get("playerStatus")) if raw.get("playerStatus") else None,
    }
    return adapter_record(
        url=url,
        raw=raw,
        fields={k: v for k, v in fields.items() if v is not None},
        retrieved_at=retrieved,
        published_at=published,
        source_class=source_class,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        extra={"kind": "EVENT_SCHEDULE"},
    )


class _OfficialScheduleAdapter:
    source_class = "OFFICIAL_LEAGUE"

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        payload = spec.get("json") or spec.get("html") or spec.get("text") or spec.get("body")
        url = str(spec.get("url") or spec.get("source_url") or "")
        if payload is not None:
            text = json.dumps(payload) if isinstance(payload, (dict, list)) else (
                payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload)
            )
            return {
                "url": url or f"fixture://official/{self.adapter_id}",
                "json": text,
                "retrievedAt": spec.get("retrieved_at") or spec.get("retrievedAt") or self.retrieved_at,
                "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
                "fixture": True,
                "league": spec.get("league") or getattr(self, "league", None),
            }
        if not live_fetch_enabled(self.live):
            raise RuntimeError(f"{self.adapter_id}_LIVE_FETCH_DISABLED")
        if not url:
            raise ValueError(f"{self.adapter_id}_URL_REQUIRED")
        return {
            "url": url,
            "html": _fetch_http(url),
            "retrievedAt": self.retrieved_at,
            "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
            "fixture": False,
            "league": spec.get("league") or getattr(self, "league", None),
        }

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        league = str(document.get("league") or getattr(self, "league", "") or "")
        return [
            _normalize_game(
                raw,
                league=league,
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                url=url,
                retrieved=retrieved,
                published=published,
                source_class=self.source_class,
            )
            for raw in _games(_as_text(document))
        ]


class OfficialWNBAAdapter(_OfficialScheduleAdapter):
    adapter_id = "OfficialWNBAAdapter"
    adapter_version = "official-wnba-1"
    league = "WNBA"


class OfficialNBAAdapter(_OfficialScheduleAdapter):
    adapter_id = "OfficialNBAAdapter"
    adapter_version = "official-nba-1"
    league = "NBA"
