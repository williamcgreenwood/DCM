"""Drive is object storage, not the query engine.

Local indexes/catalogs/Bloom identify the exact object first. A Drive fetch
is last and is BLOCKED_EXTERNAL when Drive is not configured. Never scan
Drive to rediscover known offer/event/player IDs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dcm.algorithms.indexing import BloomFilter
from dcm.contracts.hashes import content_hash


DRIVE_NOT_CONFIGURED = "NOT_CONFIGURED"
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"


class DriveObjectCatalog:
    """Content-addressed local catalog of objects that *would* live on Drive."""

    def __init__(self, dest: Path | None = None) -> None:
        self.dest = Path(dest) if dest is not None else None
        self.by_hash: dict[str, dict[str, Any]] = {}
        self.bloom = BloomFilter(m_bits=4096, k=4)
        self.drive_configured = False

    def put(self, digest: str, meta: Mapping[str, Any]) -> str:
        rec = {"digest": str(digest), **dict(meta)}
        self.by_hash[str(digest)] = rec
        self.bloom.add(str(digest))
        return str(digest)

    def identify(self, digest: str) -> dict[str, Any]:
        """Exact local identification. Does not fetch Drive."""
        key = str(digest)
        if key not in self.bloom:
            return {"digest": key, "present": False, "lookup": "BLOOM_NEGATIVE"}
        rec = self.by_hash.get(key)
        if rec is None:
            return {"digest": key, "present": False, "lookup": "BLOOM_FALSE_POSITIVE"}
        return {"digest": key, "present": True, "lookup": "LOCAL_EXACT", "meta": rec}

    def fetch(self, digest: str) -> dict[str, Any]:
        identified = self.identify(digest)
        if not identified.get("present"):
            return {**identified, "fetched": False, "status": "NOT_FOUND"}
        if not self.drive_configured:
            return {
                **identified,
                "fetched": False,
                "status": DRIVE_NOT_CONFIGURED,
                "blocked": BLOCKED_EXTERNAL,
                "note": "Drive credentials/mount are not present. Local fallback remains legal.",
            }
        return {**identified, "fetched": False, "status": BLOCKED_EXTERNAL, "note": "Drive fetch is host-side."}

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": "pillars_dcm.drive_object_catalog.v1",
            "objectCount": len(self.by_hash),
            "driveConfigured": self.drive_configured,
            "queryEngine": "LOCAL_INDEX",
            "driveIsObjectStorage": True,
            "blockedExternal": None if self.drive_configured else BLOCKED_EXTERNAL,
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body

    def persist(self, dest: Path | None = None) -> dict[str, Any]:
        path = Path(dest or self.dest or ".") / "drive_object_catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = self.snapshot()
        path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return body
