"""Research reuse cascade L0–L6. Cheapest exact layer first.

L0 current-run exact cache
L1 process-local LRU
L2 SQLite structured research index
L3 content-addressed ResearchStore
L4 bitemporal evidence/material-fact catalog
L5 durable object lookup (local promoted + Drive catalog when configured)
L6 web acquisition (last)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from dcm.algorithms.cache import LRUCache
from dcm.algorithms.indexing import open_memory_index
from dcm.contracts.hashes import content_hash

REUSE_VALID = "REUSE_VALID"
REFRESH_STALE = "REFRESH_STALE"
APPEND_MISSING_HISTORY = "APPEND_MISSING_HISTORY"
REFRESH_CURRENT_CONTEXT = "REFRESH_CURRENT_CONTEXT"
NEW_OPPONENT_REQUIRED = "NEW_OPPONENT_REQUIRED"
ROLE_EPOCH_CHANGED = "ROLE_EPOCH_CHANGED"
TEAM_CHANGED = "TEAM_CHANGED"
DEFINITION_CHANGED = "DEFINITION_CHANGED"
CONTRADICTED_REVERIFY = "CONTRADICTED_REVERIFY"
REPLACE_INVALIDATED = "REPLACE_INVALIDATED"
NEW_ENTITY_FULL_RESEARCH = "NEW_ENTITY_FULL_RESEARCH"

DISPOSITIONS = (
    REUSE_VALID, REFRESH_STALE, APPEND_MISSING_HISTORY, REFRESH_CURRENT_CONTEXT,
    NEW_OPPONENT_REQUIRED, ROLE_EPOCH_CHANGED, TEAM_CHANGED, DEFINITION_CHANGED,
    CONTRADICTED_REVERIFY, REPLACE_INVALIDATED, NEW_ENTITY_FULL_RESEARCH,
)


def _key(scope: str, scope_id: str, claim_type: str = "") -> str:
    return f"{scope}|{scope_id}|{claim_type}"


class ResearchCacheCascade:
    """Exact-first reuse. Web acquisition is L6 and never the first lookup."""

    def __init__(
        self,
        run_root: Path | None = None,
        *,
        store: Any | None = None,
        drive: Any | None = None,
    ) -> None:
        self.run_root = Path(run_root) if run_root else None
        self.l0: dict[str, dict[str, Any]] = {}
        self.l1 = LRUCache(capacity=4096)
        self.l2 = open_memory_index()
        self.l2.execute(
            "CREATE TABLE IF NOT EXISTS research ("
            "k TEXT PRIMARY KEY, scope TEXT, scope_id TEXT, claim_type TEXT, payload TEXT, asof TEXT)"
        )
        self.store = store
        self.drive = drive
        self.hits = {f"L{i}": 0 for i in range(7)}
        self.misses = 0
        self.lookups = 0

    def put(self, scope: str, scope_id: str, claim: Mapping[str, Any], *, claim_type: str = "") -> str:
        rec = dict(claim)
        ctype = claim_type or str(rec.get("claim_type") or "")
        k = _key(scope, scope_id, ctype)
        self.l0[k] = rec
        self.l1.put(k, rec)
        if ctype:
            k_scope = _key(scope, scope_id, "")
            self.l0.setdefault(k_scope, rec)
            self.l1.put(k_scope, rec)
        payload = json.dumps(rec, sort_keys=True, default=str)
        asof = str(rec.get("observed_at") or rec.get("valid_at") or rec.get("published_at") or "")
        self.l2.execute(
            "INSERT OR REPLACE INTO research VALUES (?,?,?,?,?,?)",
            (k, scope, scope_id, ctype, payload, asof),
        )
        if self.drive is not None and hasattr(self.drive, "put"):
            digest = str(rec.get("claim_hash") or content_hash(rec))
            self.drive.put(digest, {"kind": "EVIDENCE_CLAIM", "scope": scope, "scopeId": scope_id, "key": k})
        return k

    def get(self, scope: str, scope_id: str, *, claim_type: str = "") -> tuple[dict[str, Any] | None, str]:
        self.lookups += 1
        k = _key(scope, scope_id, claim_type)
        if k in self.l0:
            self.hits["L0"] += 1
            return self.l0[k], "L0"
        hit = self.l1.get(k)
        if hit is not None:
            self.hits["L1"] += 1
            self.l0[k] = hit
            return hit, "L1"
        if claim_type:
            cur = self.l2.execute("SELECT payload FROM research WHERE k = ?", (k,))
        else:
            cur = self.l2.execute(
                "SELECT payload FROM research WHERE scope = ? AND scope_id = ? ORDER BY asof DESC LIMIT 1",
                (scope, scope_id),
            )
        row = cur.fetchone()
        if row:
            rec = json.loads(row[0])
            self.hits["L2"] += 1
            self.l0[k] = rec
            return rec, "L2"
        if self.store is not None:
            try:
                found = self.store.lookup_latest(scope, scope_id) if hasattr(self.store, "lookup_latest") else None
            except Exception:
                found = None
            if found:
                self.hits["L3"] += 1
                rec = dict(found) if isinstance(found, Mapping) else {"claim_value": found}
                self.l0[k] = rec
                return rec, "L3"
        if self.drive is not None and hasattr(self.drive, "identify"):
            digest = content_hash({"scope": scope, "scope_id": scope_id, "claim_type": claim_type})
            try:
                ident = self.drive.identify(digest)
            except Exception:
                ident = None
            if isinstance(ident, Mapping) and ident.get("present"):
                self.hits["L5"] += 1
                rec = dict(ident.get("meta") or {"digest": digest})
                self.l0[k] = rec
                return rec, "L5"
        self.misses += 1
        self.hits["L6"] += 0
        return None, "L6"

    def get_asof(
        self,
        scope: str,
        scope_id: str,
        as_of: str,
        *,
        claim_type: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        """L4 bitemporal catalog: latest payload with asof <= as_of."""
        self.lookups += 1
        cur = self.l2.execute(
            "SELECT payload, asof FROM research WHERE scope = ? AND scope_id = ? AND asof <= ? "
            "AND (? = '' OR claim_type = ?) ORDER BY asof DESC LIMIT 1",
            (scope, scope_id, str(as_of), claim_type, claim_type),
        )
        row = cur.fetchone()
        if row:
            rec = json.loads(row[0])
            self.hits["L4"] += 1
            k = _key(scope, scope_id, claim_type)
            self.l0[k] = rec
            return rec, "L4"
        self.misses += 1
        return None, "L6"

    def disposition(
        self,
        *,
        existing: Mapping[str, Any] | None,
        role_epoch_changed: bool = False,
        team_changed: bool = False,
        opponent_changed: bool = False,
        definition_changed: bool = False,
        contradicted: bool = False,
        stale: bool = False,
        missing_history: bool = False,
        new_entity: bool = False,
        line_only: bool = False,
    ) -> str:
        if new_entity or existing is None:
            return NEW_ENTITY_FULL_RESEARCH
        if contradicted:
            return CONTRADICTED_REVERIFY
        if definition_changed:
            return DEFINITION_CHANGED
        if role_epoch_changed:
            return ROLE_EPOCH_CHANGED
        if team_changed:
            return TEAM_CHANGED
        if opponent_changed:
            return NEW_OPPONENT_REQUIRED
        if missing_history:
            return APPEND_MISSING_HISTORY
        if stale and not line_only:
            return REFRESH_STALE
        if line_only:
            return REFRESH_CURRENT_CONTEXT
        return REUSE_VALID

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": "pillars_dcm.research_cache_cascade.v1",
            "hits": dict(self.hits),
            "misses": self.misses,
            "lookups": self.lookups,
            "l0Size": len(self.l0),
            "reuseRatio": (sum(self.hits[k] for k in ("L0", "L1", "L2", "L3", "L4", "L5")) / self.lookups) if self.lookups else 0.0,
            "dispositions": list(DISPOSITIONS),
            "layers": {
                "L0": "current-run exact",
                "L1": "process-local LRU",
                "L2": "sqlite structured",
                "L3": "content-addressed ResearchStore",
                "L4": "bitemporal as-of catalog",
                "L5": "durable object / Drive catalog",
                "L6": "external acquisition",
            },
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body

    def close(self) -> None:
        try:
            self.l2.close()
        except Exception:
            return


def content_address_bytes(payload: Mapping[str, Any] | bytes) -> str:
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(payload).hexdigest()
    return content_hash(payload)
