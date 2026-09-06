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
    """Content-addressed local catalog of objects that *would* live on Drive.

    Semantic lookup is (scope, scope_id, claim_type) → ordered content hashes
    → exact identify/fetch. Drive itself is never scanned as a query engine.
    """

    def __init__(self, dest: Path | None = None) -> None:
        self.dest = Path(dest) if dest is not None else None
        self.by_hash: dict[str, dict[str, Any]] = {}
        self.semantic: dict[tuple[str, str, str], list[str]] = {}
        self.bloom = BloomFilter(m_bits=4096, k=4)
        self.drive_configured = False
        if self.dest is not None:
            self._load()

    def _semantic_key(self, scope: str, scope_id: str, claim_type: str = "") -> tuple[str, str, str]:
        return (str(scope or ""), str(scope_id or ""), str(claim_type or ""))

    def _index_semantic(self, digest: str, meta: Mapping[str, Any]) -> None:
        scope = str(meta.get("scope") or "")
        sid = str(meta.get("scopeId") or meta.get("scope_id") or "")
        ctype = str(meta.get("claimType") or meta.get("claim_type") or "")
        if not scope or not sid:
            return
        key = self._semantic_key(scope, sid, ctype)
        lst = self.semantic.setdefault(key, [])
        if digest not in lst:
            lst.append(str(digest))
        if ctype:
            k2 = self._semantic_key(scope, sid, "")
            lst2 = self.semantic.setdefault(k2, [])
            if digest not in lst2:
                lst2.append(str(digest))

    def put(self, digest: str, meta: Mapping[str, Any]) -> str:
        rec = {"digest": str(digest), **dict(meta)}
        self.by_hash[str(digest)] = rec
        self.bloom.add(str(digest))
        self._index_semantic(str(digest), rec)
        return str(digest)

    def lookup_semantic(self, scope: str, scope_id: str, claim_type: str = "") -> list[str]:
        """Ordered content hashes for a semantic key. Empty if unknown."""
        return list(self.semantic.get(self._semantic_key(scope, scope_id, claim_type)) or [])

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
            "semanticKeys": len(self.semantic),
            "driveConfigured": self.drive_configured,
            "queryEngine": "LOCAL_INDEX",
            "driveIsObjectStorage": True,
            "blockedExternal": None if self.drive_configured else BLOCKED_EXTERNAL,
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body

    def persist(self, dest: Path | None = None) -> dict[str, Any]:
        root = Path(dest or self.dest or ".")
        root.mkdir(parents=True, exist_ok=True)
        body = self.snapshot()
        (root / "drive_object_catalog.json").write_text(
            json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        entries = []
        for key, hashes in sorted(self.semantic.items()):
            payloads = {}
            for h in hashes:
                rec = self.by_hash.get(h) or {}
                if rec.get("payload") is not None:
                    payloads[h] = rec.get("payload")
                else:
                    payloads[h] = rec
            entries.append({
                "scope": key[0],
                "scopeId": key[1],
                "claimType": key[2],
                "hashes": hashes,
                "payloads": payloads,
            })
        (root / "drive_semantic_index.json").write_text(
            json.dumps({"schema": "pillars_dcm.drive_semantic_index.v1", "entries": entries}, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        return body

    def _load(self) -> None:
        if self.dest is None:
            return
        path = self.dest / "drive_semantic_index.json"
        if not path.is_file():
            return
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for rec in body.get("entries") or []:
            if not isinstance(rec, Mapping):
                continue
            scope = str(rec.get("scope") or "")
            sid = str(rec.get("scopeId") or "")
            ctype = str(rec.get("claimType") or "")
            hashes = [str(h) for h in (rec.get("hashes") or [])]
            self.semantic[self._semantic_key(scope, sid, ctype)] = hashes
            payloads = rec.get("payloads") or {}
            if isinstance(payloads, Mapping):
                for h, payload in payloads.items():
                    digest = str(h)
                    meta = payload if isinstance(payload, Mapping) else {"payload": payload}
                    stored = {"digest": digest, "scope": scope, "scopeId": sid, "claimType": ctype, "payload": meta.get("payload", meta), **{k: v for k, v in meta.items() if k != "payload"}}
                    self.by_hash[digest] = stored
                    self.bloom.add(digest)

