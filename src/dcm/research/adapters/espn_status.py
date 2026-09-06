"""ESPNStatusAdapter: injury/availability from fixture JSON/HTML. Live opt-in.

Does not invent status. Unknown labels stay UNKNOWN and fail closed at the
PLAYABLE gate. Cookies/tokens never enter adapter records.
"""
from __future__ import annotations

import json
import re
from typing import Any

from dcm.research.adapters.base import adapter_record, live_fetch_enabled
from dcm.research.adapters.basketball_reference import _fetch_http


ADAPTER_ID = "ESPNStatusAdapter"
ADAPTER_VERSION = "espn-status-1"
SOURCE_CLASS = "INJURY_STATUS"

_STATUS_MAP = {
    "active": "ACTIVE",
    "available": "ACTIVE",
    "probable": "PROBABLE",
    "questionable": "QUESTIONABLE",
    "doubtful": "DOUBTFUL",
    "out": "OUT",
    "inactive": "INACTIVE",
    "suspended": "SUSPENDED",
    "gtd": "QUESTIONABLE",
    "game time decision": "QUESTIONABLE",
    "rest": "OUT",
    "injured reserve": "OUT",
    "ir": "OUT",
}


def canonicalize_status(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return "UNKNOWN"
    if text in _STATUS_MAP:
        return _STATUS_MAP[text]
    for key, mapped in _STATUS_MAP.items():
        if key in text:
            return mapped
    return "UNKNOWN"


def _as_text(document: dict[str, Any]) -> str:
    for key in ("json", "html", "text", "body", "content"):
        value = document.get(key)
        if isinstance(value, (str, bytes)):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
        if isinstance(value, (dict, list)):
            return json.dumps(value)
    return ""


def _parse_payload(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []
    if text[0] in "[{":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            rows = data.get("injuries") or data.get("athletes") or data.get("items") or data.get("entries") or []
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
    rows: list[dict[str, Any]] = []
    for match in re.finditer(
        r'data-player="([^"]+)"[^>]*data-status="([^"]+)"(?:[^>]*data-team="([^"]+)")?',
        text,
        re.IGNORECASE,
    ):
        rows.append({"player": match.group(1), "status": match.group(2), "team": match.group(3)})
    return rows


class ESPNStatusAdapter:
    adapter_id = ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, live: bool | None = None, retrieved_at: str | None = None):
        self.live = live
        self.retrieved_at = retrieved_at

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        payload = spec.get("json") or spec.get("html") or spec.get("text") or spec.get("body")
        url = str(spec.get("url") or spec.get("source_url") or "")
        if payload is not None:
            if isinstance(payload, (dict, list)):
                text = json.dumps(payload)
            elif isinstance(payload, bytes):
                text = payload.decode("utf-8", errors="replace")
            else:
                text = str(payload)
            return {
                "url": url or "fixture://espn/status",
                "json": text,
                "retrievedAt": spec.get("retrieved_at") or spec.get("retrievedAt") or self.retrieved_at,
                "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
                "fixture": True,
            }
        if not live_fetch_enabled(self.live):
            raise RuntimeError("ESPN_STATUS_LIVE_FETCH_DISABLED")
        if not url:
            raise ValueError("ESPN_STATUS_URL_REQUIRED")
        return {
            "url": url,
            "html": _fetch_http(url),
            "retrievedAt": self.retrieved_at,
            "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
            "fixture": False,
        }

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or "")
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        rows = _parse_payload(_as_text(document))
        records: list[dict[str, Any]] = []
        for raw in rows:
            name = raw.get("player") or raw.get("athlete") or raw.get("name") or raw.get("displayName")
            team = raw.get("team") or raw.get("teamAbbr") or raw.get("team_id")
            status = canonicalize_status(raw.get("status") or raw.get("injuryStatus") or raw.get("type"))
            comment = raw.get("comment") or raw.get("details") or raw.get("description")
            fields = {
                "playerName": name,
                "playerId": raw.get("playerId") or raw.get("id"),
                "team": team,
                "status": status,
                "rawStatus": raw.get("status"),
                "comment": comment,
            }
            records.append(
                adapter_record(
                    url=url,
                    raw=raw,
                    fields={k: v for k, v in fields.items() if v is not None},
                    retrieved_at=retrieved,
                    published_at=published,
                    source_class=self.source_class,
                    adapter_id=self.adapter_id,
                    adapter_version=self.adapter_version,
                    extra={"kind": "INJURY_STATUS"},
                )
            )
        return records
