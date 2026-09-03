"""Research cache: long-lived history vs short-lived status, as-of keyed.

Cache identity includes source, adapter version, as-of, entity, and kind.
Deterministic: expiry is as-of vs published, never wall-clock.
No cookies, tokens, or raw HAR bodies are stored.
"""
from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash


LONG_LIVED = frozenset({
    "PLAYER_GAME_LOG",
    "TEAM_GAME_LOG",
    "TEAM_SEASON",
    "PLAYER_SEASON",
    "MARKET_DEFINITION",
    "VENUE",
})
SHORT_LIVED = frozenset({
    "INJURY",
    "STATUS",
    "LINEUP",
    "ON_OFF",
    "ROLE",
    "WEATHER",
    "LINE",
    "EVENT_STATUS",
})


def cache_identity(
    *,
    source_id: str,
    adapter_version: str,
    as_of: str,
    entity: str,
    kind: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = {
        "sourceId": str(source_id or ""),
        "adapterVersion": str(adapter_version or ""),
        "asOf": str(as_of or ""),
        "entity": str(entity or ""),
        "kind": str(kind or ""),
        "longevity": "SHORT_LIVED" if str(kind or "") in SHORT_LIVED else "LONG_LIVED",
    }
    if extra:
        body["extra"] = dict(extra)
    body["cacheKey"] = content_hash(body)
    return body


class ResearchCache:
    """In-process as-of keyed store. Caller persists if needed."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def put(self, identity: dict[str, Any], value: Any, *, published_at: str = "") -> dict[str, Any]:
        key = str(identity.get("cacheKey") or cache_identity(**{
            "source_id": identity.get("sourceId") or "",
            "adapter_version": identity.get("adapterVersion") or "",
            "as_of": identity.get("asOf") or "",
            "entity": identity.get("entity") or "",
            "kind": identity.get("kind") or "",
        }).get("cacheKey"))
        rec = {
            "identity": identity,
            "publishedAt": published_at or identity.get("asOf") or "",
            "value": value,
            "kind": identity.get("kind"),
            "longevity": identity.get("longevity"),
        }
        self._store[key] = rec
        return rec

    def get(self, identity: dict[str, Any], *, as_of: str | None = None) -> Any | None:
        key = str(identity.get("cacheKey") or "")
        rec = self._store.get(key)
        if rec is None:
            return None
        cutoff = str(as_of or identity.get("asOf") or "")
        published = str(rec.get("publishedAt") or "")
        if cutoff and published and published > cutoff:
            return None
        return rec.get("value")

    def hits(self) -> int:
        return len(self._store)
