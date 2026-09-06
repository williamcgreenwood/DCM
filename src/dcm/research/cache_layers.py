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
import sqlite3
import os
from pathlib import Path
from typing import Any, Mapping

from dcm.algorithms.cache import LRUCache
from dcm.algorithms.indexing import BloomFilter, open_memory_index
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
    # Keep the key human-auditable while making delimiters unambiguous.  This
    # is the exact key used by L0/L1/L2; semantic/fuzzy lookup is never allowed
    # to masquerade as an exact hit.
    return json.dumps(
        [str(scope), str(scope_id), str(claim_type)],
        ensure_ascii=True,
        separators=(",", ":"),
    )


_CACHE_SCHEMA_VERSION = 1


def _decode_cached_row(row: tuple[Any, ...], *, label: str) -> dict[str, Any]:
    """Decode and verify a durable cache row before it becomes a reuse hit."""
    if not row:
        raise ValueError(f"{label}_EMPTY")
    try:
        rec = json.loads(row[0])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}_JSON_INVALID") from exc
    if not isinstance(rec, dict):
        raise ValueError(f"{label}_OBJECT_REQUIRED")
    expected = str(row[1] or "") if len(row) > 1 else ""
    actual = content_hash(rec)
    if not expected or expected != actual:
        raise ValueError(f"{label}_HASH_MISMATCH")
    return rec


def _open_persistent_index(path: Path) -> tuple[Any, str, list[str]]:
    """Open a durable L2 index, falling back without deleting corrupt bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    blockers: list[str] = []
    try:
        conn = sqlite3.connect(str(path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        version = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
        if version not in (0, _CACHE_SCHEMA_VERSION):
            raise RuntimeError(f"RESEARCH_CACHE_SCHEMA_VERSION_UNSUPPORTED:{version}")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS research ("
            "k TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_id TEXT NOT NULL, "
            "claim_type TEXT NOT NULL, payload TEXT NOT NULL, asof TEXT NOT NULL, "
            "payload_hash TEXT NOT NULL)"
        )
        # A pre-patch database may have the old six-column table.  Add the
        # payload hash in place; rows are still verified on read.
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(research)").fetchall()}
        if "payload_hash" not in columns:
            conn.execute("ALTER TABLE research ADD COLUMN payload_hash TEXT NOT NULL DEFAULT ''")
            rows = conn.execute("SELECT k, payload FROM research").fetchall()
            for key, payload in rows:
                try:
                    digest = content_hash(json.loads(payload))
                except (TypeError, ValueError, json.JSONDecodeError):
                    digest = ""
                conn.execute("UPDATE research SET payload_hash = ? WHERE k = ?", (digest, key))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_scope_asof ON research(scope, scope_id, asof DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_scope_type_asof ON research(scope, scope_id, claim_type, asof DESC)")
        conn.execute(f"PRAGMA user_version = {_CACHE_SCHEMA_VERSION}")
        conn.commit()
        check = str(conn.execute("PRAGMA integrity_check").fetchone()[0] or "")
        if check.lower() != "ok":
            raise RuntimeError(f"RESEARCH_CACHE_INTEGRITY_CHECK_FAILED:{check}")
        return conn, "PERSISTENT_SQLITE", blockers
    except (OSError, sqlite3.DatabaseError, RuntimeError, ValueError) as exc:
        try:
            conn.close()  # type: ignore[union-attr]
        except Exception:
            pass
        # Preserve the bytes for later forensic repair.  The in-memory index is
        # a safe execution fallback, but it is explicitly not a durable hit.
        blockers.append(type(exc).__name__)
        return open_memory_index(), "MEMORY_FALLBACK_CORRUPT_OR_UNSUPPORTED", blockers


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
        self.l2_path = (self.run_root / "research_cache.sqlite3") if self.run_root else None
        if self.l2_path is not None:
            self.l2, self.persistence_state, self.persistence_blockers = _open_persistent_index(self.l2_path)
        else:
            self.l2 = open_memory_index()
            self.l2.execute(
                "CREATE TABLE IF NOT EXISTS research ("
                "k TEXT PRIMARY KEY, scope TEXT, scope_id TEXT, claim_type TEXT, payload TEXT, asof TEXT, payload_hash TEXT)"
            )
            self.persistence_state = "PROCESS_MEMORY_ONLY"
            self.persistence_blockers = []
        self._bloom = BloomFilter(m_bits=1 << 18, k=5)
        try:
            for (key,) in self.l2.execute("SELECT k FROM research").fetchall():
                self._bloom.add(str(key))
        except Exception:
            self.persistence_blockers.append("INDEX_REBUILD_FAILED")
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
        payload_hash = content_hash(rec)
        asof = str(rec.get("observed_at") or rec.get("valid_at") or rec.get("published_at") or "")
        self.l2.execute(
            "INSERT OR REPLACE INTO research (k, scope, scope_id, claim_type, payload, asof, payload_hash) VALUES (?,?,?,?,?,?,?)",
            (k, str(scope), str(scope_id), ctype, payload, asof, payload_hash),
        )
        if self.persistence_state == "PERSISTENT_SQLITE":
            self.l2.commit()
        self._bloom.add(k)
        if self.drive is not None and hasattr(self.drive, "put"):
            digest = str(rec.get("claim_hash") or content_hash(rec))
            self.drive.put(digest, {
                "kind": "EVIDENCE_CLAIM",
                "scope": scope,
                "scopeId": scope_id,
                "claimType": ctype,
                "payload": rec,
            })
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
        if not self._bloom.might_contain(k) and claim_type:
            row = None
        elif claim_type:
            cur = self.l2.execute("SELECT payload, payload_hash FROM research WHERE k = ?", (k,))
            row = cur.fetchone()
        else:
            cur = self.l2.execute(
                "SELECT payload, payload_hash FROM research WHERE scope = ? AND scope_id = ? ORDER BY asof DESC LIMIT 1",
                (scope, scope_id),
            )
            row = cur.fetchone()
        if row:
            try:
                rec = _decode_cached_row(row, label="CACHE_PAYLOAD")
                self.hits["L2"] += 1
                self.l0[k] = rec
                return rec, "L2"
            except ValueError as exc:
                self.persistence_blockers.append(str(exc))
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
        if self.drive is not None:
            hashes: list[str] = []
            if hasattr(self.drive, "lookup_semantic"):
                try:
                    hashes = list(self.drive.lookup_semantic(scope, scope_id, claim_type) or [])
                except Exception:
                    hashes = []
            for digest in reversed(hashes):
                try:
                    ident = self.drive.identify(digest) if hasattr(self.drive, "identify") else None
                except Exception:
                    ident = None
                if not isinstance(ident, Mapping) or not ident.get("present"):
                    continue
                meta = ident.get("meta") if isinstance(ident.get("meta"), Mapping) else {}
                payload = meta.get("payload") if isinstance(meta, Mapping) else None
                rec = dict(payload) if isinstance(payload, Mapping) else dict(meta or {"digest": digest})
                self.hits["L5"] += 1
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
            "SELECT payload, payload_hash, asof FROM research WHERE scope = ? AND scope_id = ? AND asof <= ? "
            "AND (? = '' OR claim_type = ?) ORDER BY asof DESC LIMIT 1",
            (scope, scope_id, str(as_of), claim_type, claim_type),
        )
        row = cur.fetchone()
        if row:
            try:
                rec = _decode_cached_row((row[0], row[1]), label="ASOF_CACHE_PAYLOAD")
                self.hits["L4"] += 1
                k = _key(scope, scope_id, claim_type)
                self.l0[k] = rec
                return rec, "L4"
            except ValueError as exc:
                self.persistence_blockers.append(str(exc))
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
            "persistence": {
                "state": self.persistence_state,
                "path": self.l2_path.name if self.l2_path else None,
                "schemaVersion": _CACHE_SCHEMA_VERSION,
                "blockers": sorted(set(self.persistence_blockers)),
            },
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

    def clear_ephemeral(self, *, clear_persistent: bool = True) -> None:
        """Drop current-run/process/L2 rows; durable L5 remains unchanged.

        ``clear_persistent=True`` preserves the historical test and operator
        contract.  Restart durability is verified by close/reopen without this
        method; callers that only want to evict L0/L1 pass False.
        """
        self.l0.clear()
        self.l1 = LRUCache(capacity=4096)
        if clear_persistent:
            try:
                self.l2.execute("DELETE FROM research")
                if self.persistence_state == "PERSISTENT_SQLITE":
                    self.l2.commit()
                self._bloom = BloomFilter(m_bits=1 << 18, k=5)
            except Exception:
                self.persistence_blockers.append("CLEAR_FAILED")

    def close(self) -> None:
        try:
            if self.persistence_state == "PERSISTENT_SQLITE":
                self.l2.commit()
            self.l2.close()
        except Exception:
            return


def content_address_bytes(payload: Mapping[str, Any] | bytes) -> str:
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(payload).hexdigest()
    return content_hash(payload)
