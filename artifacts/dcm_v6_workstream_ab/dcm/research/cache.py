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
    """Compatibility cache with optional durable SQLite backing.

    Existing providers use the small identity/get/put interface in this
    module.  When ``run_root`` is supplied, those same calls are backed by the
    exact-first ``ResearchCacheCascade`` so a restart can reuse validated
    claims.  The no-argument form remains process-local for small unit tests.
    """

    def __init__(self, run_root: Any | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._cascade = None
        if run_root is not None:
            from dcm.research.cache_layers import ResearchCacheCascade
            self._cascade = ResearchCacheCascade(run_root)

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
        if self._cascade is not None:
            self._cascade.put(
                "IDENTITY",
                key,
                {
                    "cacheIdentity": dict(identity),
                    "value": value,
                    "published_at": rec["publishedAt"],
                },
                claim_type="COLLECT",
            )
        return rec

    def get(self, identity: dict[str, Any], *, as_of: str | None = None) -> Any | None:
        key = str(identity.get("cacheKey") or "")
        rec = self._store.get(key)
        if rec is None and self._cascade is not None:
            persisted, _layer = self._cascade.get("IDENTITY", key, claim_type="COLLECT")
            if isinstance(persisted, dict):
                cached_identity = persisted.get("cacheIdentity")
                if isinstance(cached_identity, dict):
                    rec = {
                        "identity": cached_identity,
                        "publishedAt": persisted.get("published_at") or "",
                        "value": persisted.get("value"),
                        "kind": cached_identity.get("kind"),
                        "longevity": cached_identity.get("longevity"),
                    }
                    self._store[key] = rec
        if rec is None:
            return None
        cutoff = str(as_of or identity.get("asOf") or "")
        published = str(rec.get("publishedAt") or "")
        if cutoff and published and published > cutoff:
            return None
        return rec.get("value")

    def hits(self) -> int:
        return len(self._store)

    def snapshot(self) -> dict[str, Any]:
        if self._cascade is not None:
            return self._cascade.snapshot()
        return {
            "schema": "pillars_dcm.research_cache.v1",
            "persistence": {"state": "PROCESS_MEMORY_ONLY"},
            "entries": len(self._store),
        }

    def close(self) -> None:
        if self._cascade is not None:
            self._cascade.close()
