"""Portable queryable StatePack (DCM6-ROS-EG-001 §7).

    DCM_StatePack/
      state_manifest.json
      research_state.sqlite
      deterministic_export.json.gz
      schema_manifest.json
      integrity_manifest.sha256

SQLite is the operational query surface. The filesystem ResearchStore remains
the content-addressed blob layer; this pack indexes those blobs for as-of /
entity / source queries without committing the changing DB to Git.
"""
from __future__ import annotations

import gzip
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dcm.contracts.hashes import content_hash
from dcm.research.research_store import STORE_SCHEMA, ResearchStore, extract_game_logs
from dcm.research.scopes import canonical_scope

STATEPACK_SCHEMA = "pillars_dcm.statepack.v1"
SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blobs (
    content_hash TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    stored_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claim_index (
    content_hash TEXT PRIMARY KEY,
    sport TEXT NOT NULL DEFAULT '',
    entity_kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    as_of TEXT NOT NULL DEFAULT '',
    as_of_date TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    claim_type TEXT NOT NULL DEFAULT '',
    claim_hash TEXT NOT NULL DEFAULT '',
    freshness REAL,
    reliability REAL,
    history_count INTEGER NOT NULL DEFAULT 0,
    affiliation_id TEXT NOT NULL DEFAULT '',
    opponent_id TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS latest (
    entity_key TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (
    content_hash TEXT PRIMARY KEY,
    projection_id TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '',
    frozen_forecast_hash TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    decides_research_reuse INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_claim_entity ON claim_index(entity_kind, entity_id, as_of_date);
CREATE INDEX IF NOT EXISTS idx_claim_source ON claim_index(source_id);
CREATE INDEX IF NOT EXISTS idx_claim_asof ON claim_index(as_of_date);
CREATE INDEX IF NOT EXISTS idx_claim_type ON claim_index(claim_type);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _asof_day(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return "unknown"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


class StatePack:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "research_state.sqlite"
        self.manifest_path = self.root / "state_manifest.json"
        self.schema_manifest_path = self.root / "schema_manifest.json"
        self.export_path = self.root / "deterministic_export.json.gz"
        self.integrity_path = self.root / "integrity_manifest.sha256"
        self._init_db()

    def _init_db(self) -> None:
        conn = _connect(self.db_path)
        try:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("schema", STATEPACK_SCHEMA),
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("version", str(SCHEMA_VERSION)),
            )
            conn.commit()
        finally:
            conn.close()

    def put_blob(self, payload: dict[str, Any], *, stored_at: str | None = None) -> str:
        digest = content_hash(payload)
        conn = _connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO blobs(content_hash, payload_json, stored_at) VALUES (?, ?, ?)",
                (digest, json.dumps(payload, sort_keys=True, ensure_ascii=True), stored_at or _utc_now()),
            )
            conn.commit()
        finally:
            conn.close()
        return digest

    def index_claim(self, payload: dict[str, Any], *, content_hash_value: str | None = None) -> dict[str, Any]:
        digest = content_hash_value or self.put_blob(payload)
        claim = payload.get("claim") if isinstance(payload.get("claim"), dict) else payload
        value = claim.get("claim_value") if isinstance(claim.get("claim_value"), dict) else {}
        kind = canonical_scope(str(payload.get("entityKind") or claim.get("semantic_scope") or ""))
        entity_id = str(payload.get("entityId") or claim.get("scope_id") or "")
        asof = str(payload.get("asOf") or claim.get("forecast_cutoff") or claim.get("observed_at") or "")
        row = {
            "content_hash": digest,
            "sport": str(payload.get("sport") or ""),
            "entity_kind": kind,
            "entity_id": entity_id,
            "as_of": asof,
            "as_of_date": _asof_day(asof),
            "source_id": str(claim.get("source_id") or ""),
            "claim_type": str(claim.get("claim_type") or ""),
            "claim_hash": str(claim.get("claim_hash") or ""),
            "freshness": claim.get("freshness"),
            "reliability": claim.get("reliability"),
            "history_count": len(extract_game_logs(claim)),
            "affiliation_id": str(value.get("affiliationId") or value.get("teamId") or ""),
            "opponent_id": str(value.get("opponentId") or value.get("counterpartyId") or ""),
        }
        conn = _connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO claim_index(
                    content_hash, sport, entity_kind, entity_id, as_of, as_of_date,
                    source_id, claim_type, claim_hash, freshness, reliability,
                    history_count, affiliation_id, opponent_id
                ) VALUES (
                    :content_hash, :sport, :entity_kind, :entity_id, :as_of, :as_of_date,
                    :source_id, :claim_type, :claim_hash, :freshness, :reliability,
                    :history_count, :affiliation_id, :opponent_id
                )
                """,
                row,
            )
            if kind and entity_id:
                conn.execute(
                    "INSERT OR REPLACE INTO latest(entity_key, content_hash) VALUES (?, ?)",
                    (f"{kind}:{entity_id}", digest),
                )
            conn.commit()
        finally:
            conn.close()
        return {"contentHash": digest, **{k: v for k, v in row.items() if k != "content_hash"}}

    def ingest_store(self, store: ResearchStore) -> dict[str, Any]:
        n = 0
        for blob_path in sorted(store.blobs.glob("*.json")):
            try:
                payload = json.loads(blob_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            self.put_blob(payload)
            self.index_claim(payload)
            n += 1
        o_n = 0
        if store.outcomes.is_dir():
            conn = _connect(self.db_path)
            try:
                for path in sorted(store.outcomes.glob("*.json")):
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    digest = content_hash(payload)
                    outcome = payload.get("outcome") if isinstance(payload.get("outcome"), dict) else {}
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO outcomes(
                            content_hash, projection_id, result, frozen_forecast_hash,
                            payload_json, decides_research_reuse
                        ) VALUES (?, ?, ?, ?, ?, 0)
                        """,
                        (
                            digest,
                            str(outcome.get("projectionId") or ""),
                            str(outcome.get("settlement") or outcome.get("result") or ""),
                            str(outcome.get("frozenForecastHash") or ""),
                            json.dumps(payload, sort_keys=True),
                        ),
                    )
                    o_n += 1
                conn.commit()
            finally:
                conn.close()
        return {"ingestedBlobs": n, "ingestedOutcomes": o_n}

    def _load_blob(self, conn: sqlite3.Connection, digest: str) -> dict[str, Any]:
        row = conn.execute(
            "SELECT payload_json FROM blobs WHERE content_hash = ?",
            (digest,),
        ).fetchone()
        if not row:
            return {"contentHash": digest, "missing": True}
        payload = json.loads(row["payload_json"])
        payload["_contentHash"] = digest
        return payload

    def query_entity(
        self,
        kind: str,
        entity_id: str,
        *,
        as_of: str | None = None,
        latest_only: bool = False,
    ) -> list[dict[str, Any]]:
        kind_c = canonical_scope(kind)
        conn = _connect(self.db_path)
        try:
            if latest_only:
                row = conn.execute(
                    "SELECT content_hash FROM latest WHERE entity_key = ?",
                    (f"{kind_c}:{entity_id}",),
                ).fetchone()
                hashes = [row["content_hash"]] if row else []
            else:
                sql = "SELECT content_hash FROM claim_index WHERE entity_kind = ? AND entity_id = ?"
                args: list[Any] = [kind_c, entity_id]
                if as_of:
                    sql += " AND as_of_date <= ?"
                    args.append(_asof_day(as_of))
                sql += " ORDER BY as_of_date ASC, content_hash ASC"
                hashes = [r["content_hash"] for r in conn.execute(sql, args)]
            return [self._load_blob(conn, h) for h in hashes if h]
        finally:
            conn.close()

    def query_source(self, source_id: str) -> list[dict[str, Any]]:
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT content_hash FROM claim_index WHERE source_id = ? ORDER BY content_hash",
                (str(source_id),),
            ).fetchall()
            return [self._load_blob(conn, r["content_hash"]) for r in rows]
        finally:
            conn.close()

    def query_asof(self, as_of_date: str) -> list[dict[str, Any]]:
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT content_hash FROM claim_index WHERE as_of_date = ? ORDER BY content_hash",
                (_asof_day(as_of_date),),
            ).fetchall()
            return [self._load_blob(conn, r["content_hash"]) for r in rows]
        finally:
            conn.close()

    def counts(self) -> dict[str, int]:
        conn = _connect(self.db_path)
        try:
            return {
                "blobs": int(conn.execute("SELECT COUNT(*) AS n FROM blobs").fetchone()["n"]),
                "claims": int(conn.execute("SELECT COUNT(*) AS n FROM claim_index").fetchone()["n"]),
                "latestEntities": int(conn.execute("SELECT COUNT(*) AS n FROM latest").fetchone()["n"]),
                "outcomes": int(conn.execute("SELECT COUNT(*) AS n FROM outcomes").fetchone()["n"]),
            }
        finally:
            conn.close()

    def deterministic_records(self) -> list[dict[str, Any]]:
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT content_hash, payload_json FROM blobs ORDER BY content_hash"
            ).fetchall()
            return [
                {"contentHash": row["content_hash"], "payload": json.loads(row["payload_json"])}
                for row in rows
            ]
        finally:
            conn.close()

    def snapshot(self) -> dict[str, Any]:
        records = self.deterministic_records()
        export_obj = {
            "schema": STATEPACK_SCHEMA,
            "storeSchema": STORE_SCHEMA,
            "recordCount": len(records),
            "records": records,
        }
        raw = json.dumps(export_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        export_hash = content_hash(export_obj)
        with gzip.open(self.export_path, "wb") as fh:
            fh.write(raw)
        counts = self.counts()
        schema_manifest = {
            "schema": STATEPACK_SCHEMA,
            "schemaVersion": SCHEMA_VERSION,
            "tables": ["schema_meta", "blobs", "claim_index", "latest", "outcomes"],
            "wal": True,
            "foreignKeys": True,
        }
        schema_hash = content_hash(schema_manifest)
        self.schema_manifest_path.write_text(
            json.dumps(schema_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest = {
            "schema": STATEPACK_SCHEMA,
            "createdAt": _utc_now(),
            "counts": counts,
            "files": {
                "research_state.sqlite": self.db_path.name,
                "deterministic_export.json.gz": self.export_path.name,
                "schema_manifest.json": self.schema_manifest_path.name,
                "integrity_manifest.sha256": self.integrity_path.name,
            },
            "exportHash": export_hash,
            "schemaManifestHash": schema_hash,
            "gitMustNotCommitChangingDb": True,
            "learningRevision": "LR000000",
            "predictiveClaim": "NONE",
        }
        semantic = {k: v for k, v in manifest.items() if k != "createdAt"}
        manifest["contentHash"] = content_hash(semantic)
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        integrity = {
            "schema": "pillars_dcm.statepack_integrity.v1",
            "exportHash": export_hash,
            "schemaManifestHash": schema_hash,
            "stateManifestHash": manifest["contentHash"],
            "recordCount": len(records),
        }
        integrity["integrityHash"] = content_hash(integrity)
        self.integrity_path.write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "schema": STATEPACK_SCHEMA,
            "root": str(self.root),
            "exportHash": export_hash,
            "integrityHash": integrity["integrityHash"],
            "stateManifestHash": manifest["contentHash"],
            **counts,
        }

    def restore_from_export(self, export_path: Path | None = None) -> dict[str, Any]:
        path = Path(export_path) if export_path else self.export_path
        with gzip.open(path, "rb") as fh:
            data = json.loads(fh.read().decode("utf-8"))
        records: Iterable[dict[str, Any]] = data.get("records") or []
        n = 0
        for rec in records:
            payload = rec.get("payload") if isinstance(rec, dict) else None
            if not isinstance(payload, dict):
                continue
            self.put_blob(payload)
            self.index_claim(payload)
            n += 1
        return {"restored": n, "exportSchema": data.get("schema")}

    def integrity_ok(self) -> dict[str, Any]:
        if not self.integrity_path.is_file() or not self.export_path.is_file():
            return {"ok": False, "reason": "SNAPSHOT_MISSING"}
        try:
            integrity = json.loads(self.integrity_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"ok": False, "reason": "INTEGRITY_UNREADABLE"}
        records = self.deterministic_records()
        export_obj = {
            "schema": STATEPACK_SCHEMA,
            "storeSchema": STORE_SCHEMA,
            "recordCount": len(records),
            "records": records,
        }
        current = content_hash(export_obj)
        expected = str(integrity.get("exportHash") or "")
        if current != expected:
            return {"ok": False, "reason": "EXPORT_HASH_MISMATCH", "expected": expected, "actual": current}
        return {"ok": True, "exportHash": current, "recordCount": len(records)}
