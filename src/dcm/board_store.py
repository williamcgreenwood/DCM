"""Canonical single-copy BoardStore (audit dicts + compute SoA indexes).

Two-representation architecture:
  Audit  — frozen row dicts, stable string IDs, content hashes, versioned JSON.
  Compute — int32 row_id, NumPy columns, bitmaps / int32 posting lists.

Indexes never duplicate full dict payloads. SQLite persists keys + row_id only.
Public lookup APIs still return auditable dicts (intentional boundary conversion).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from dcm.algorithms.indexing import Bitset, BloomFilter, open_memory_index, sqlite_composite_index
from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.cfb.markets import ACTIVE_CFB_MARKETS
from dcm.compact import CompactNumericBoard, DTYPE_ID
from dcm.contracts.hashes import content_hash

SCHEMA_VERSION = "dcm.board_store.v1-20260906"
SUPPORTED_CFB_MARKETS = ACTIVE_CFB_MARKETS


class BoardStore:
    """Single-copy board with SoA indexes. No repeated full-board linear scans."""

    def __init__(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        telemetry: AlgorithmTelemetry | None = None,
    ) -> None:
        self.telemetry = telemetry or AlgorithmTelemetry()
        self.schema = SCHEMA_VERSION
        material: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            oid = str(row.get("projectionId") or "")
            if not oid:
                continue
            material.append(row)

        self._rows: tuple[dict[str, Any], ...] = tuple(material)
        self.n = len(self._rows)
        self.offer_ids: tuple[str, ...] = tuple(str(r.get("projectionId") or "") for r in self._rows)
        self.row_id_by_offer: dict[str, int] = {oid: i for i, oid in enumerate(self.offer_ids)}

        # Compute representation (SoA).
        self.compact = CompactNumericBoard.from_board_rows(self._rows)
        self.content: dict[str, str] = {}
        self.composite: dict[tuple[str, str, str, str, str, str], list[np.int32]] = {}
        self.by_event_rows: dict[str, np.ndarray] = {}
        self.by_affiliation_rows: dict[str, np.ndarray] = {}
        self.by_subject_rows: dict[str, np.ndarray] = {}
        self.by_market_rows: dict[str, np.ndarray] = {}
        self.by_league_rows: dict[str, np.ndarray] = {}
        self.eligibility = Bitset(self.n)
        self.cfb_supported = Bitset(self.n)
        self.bloom = BloomFilter(m_bits=4096, k=4)

        # Lean SQLite: keys + row_id only (payload lives once in _rows).
        self.sqlite = open_memory_index()
        self.sqlite.execute(
            "CREATE TABLE IF NOT EXISTS offers ("
            "offer_id TEXT PRIMARY KEY, sport TEXT, league TEXT, event_id TEXT, "
            "team_id TEXT, subject_id TEXT, market TEXT, player_name TEXT, row_id INTEGER NOT NULL)"
        )
        sqlite_composite_index(
            self.sqlite, "offers", ("sport", "league", "event_id", "team_id", "subject_id", "market")
        )
        sqlite_composite_index(self.sqlite, "offers", ("league", "market"), name="idx_offers_league_market")
        sqlite_composite_index(self.sqlite, "offers", ("event_id", "subject_id"), name="idx_offers_event_subject")
        sqlite_composite_index(self.sqlite, "offers", ("row_id",), name="idx_offers_row_id")

        event_post: dict[str, list[int]] = {}
        aff_post: dict[str, list[int]] = {}
        sub_post: dict[str, list[int]] = {}
        mkt_post: dict[str, list[int]] = {}
        league_post: dict[str, list[int]] = {}

        for i, row in enumerate(self._rows):
            oid = self.offer_ids[i]
            sport = str(row.get("sportFamily") or "")
            league = str(row.get("league") or "").upper()
            event = str(row.get("eventId") or "")
            team = str(row.get("teamId") or row.get("team") or "")
            subject = str(row.get("playerId") or row.get("subjectId") or "")
            market = str(row.get("market") or "").lower()
            name = str(row.get("playerName") or "")
            key = (sport, league, event, team, subject, market)
            self.composite.setdefault(key, []).append(np.int32(i))
            event_post.setdefault(event, []).append(i)
            aff_post.setdefault(team, []).append(i)
            sub_post.setdefault(subject, []).append(i)
            mkt_post.setdefault(market, []).append(i)
            league_post.setdefault(league, []).append(i)
            digest = content_hash({"offer": oid, "line": row.get("line"), "market": market})
            self.content[digest] = oid
            self.eligibility.add(i)
            if league == "CFB" and market in SUPPORTED_CFB_MARKETS and row.get("modifier") != "GOBLIN":
                self.cfb_supported.add(i)
            self.bloom.add(oid)
            self.sqlite.execute(
                "INSERT OR REPLACE INTO offers VALUES (?,?,?,?,?,?,?,?,?)",
                (oid, sport, league, event, team, subject, market, name, int(i)),
            )

        self.by_event_rows = {k: np.asarray(v, dtype=DTYPE_ID) for k, v in event_post.items()}
        self.by_affiliation_rows = {k: np.asarray(v, dtype=DTYPE_ID) for k, v in aff_post.items()}
        self.by_subject_rows = {k: np.asarray(v, dtype=DTYPE_ID) for k, v in sub_post.items()}
        self.by_market_rows = {k: np.asarray(v, dtype=DTYPE_ID) for k, v in mkt_post.items()}
        self.by_league_rows = {k: np.asarray(v, dtype=DTYPE_ID) for k, v in league_post.items()}

        self.telemetry.record(
            "ALG-INDEX-001",
            problem_class="HOT_HASH_INDEX",
            producer="dcm.board_store.BoardStore",
            consumer="dcm.research.indexes.BoardIndexes",
            count=self.n,
            phase="BUILT",
            note="single-copy BoardStore constructed",
        )
        self.telemetry.record(
            "ALG-INDEX-002",
            problem_class="SQLITE_INDEX",
            producer="dcm.board_store.BoardStore",
            consumer="dcm.research.indexes.BoardIndexes",
            phase="BUILT",
            note="sqlite keys+row_id only; payload not duplicated",
        )
        self.telemetry.record(
            "ALG-INDEX-008",
            problem_class="BITMAP_ELIGIBILITY",
            producer="dcm.board_store.BoardStore",
            consumer="dcm.research.indexes.BoardIndexes",
            count=self.n,
            phase="BUILT",
        )

    # --- Audit boundary (public) -------------------------------------------------

    def row(self, row_id: int) -> dict[str, Any]:
        if row_id < 0 or row_id >= self.n:
            raise IndexError("row_id out of range")
        return self._rows[row_id]

    def exact_offer(self, offer_id: str, *, downstream_used: bool = False) -> dict[str, Any] | None:
        self.telemetry.record(
            "ALG-INDEX-001",
            problem_class="HOT_HASH_INDEX",
            producer="dcm.board_store.BoardStore.exact_offer",
            consumer="dcm.cfb.launch",
            phase="QUERIED",
            downstream_used=downstream_used,
        )
        rid = self.row_id_by_offer.get(str(offer_id))
        if rid is None:
            return None
        return self._rows[rid]

    def offer_by_id_map(self) -> dict[str, dict[str, Any]]:
        """Legacy-compatible view: offer_id → audit row (same dict objects, no copy)."""
        return {oid: self._rows[i] for i, oid in enumerate(self.offer_ids)}

    def rows_for(self, row_ids: Sequence[int] | np.ndarray) -> list[dict[str, Any]]:
        return [self._rows[int(i)] for i in row_ids]

    def offer_ids_for(self, row_ids: Sequence[int] | np.ndarray) -> list[str]:
        return [self.offer_ids[int(i)] for i in row_ids]

    # --- Compute indexes (no full-board scan) ------------------------------------

    def row_ids_for_event(self, event_id: str) -> np.ndarray:
        return self.by_event_rows.get(str(event_id), np.asarray([], dtype=DTYPE_ID))

    def row_ids_for_subject(self, subject_id: str) -> np.ndarray:
        return self.by_subject_rows.get(str(subject_id), np.asarray([], dtype=DTYPE_ID))

    def row_ids_for_affiliation(self, team_id: str) -> np.ndarray:
        return self.by_affiliation_rows.get(str(team_id), np.asarray([], dtype=DTYPE_ID))

    def row_ids_for_market(self, market: str) -> np.ndarray:
        return self.by_market_rows.get(str(market).lower(), np.asarray([], dtype=DTYPE_ID))

    def offer_ids_for_event(self, event_id: str) -> list[str]:
        return self.offer_ids_for(self.row_ids_for_event(event_id))

    def offer_ids_for_subject(self, subject_id: str) -> list[str]:
        return self.offer_ids_for(self.row_ids_for_subject(subject_id))

    def offer_ids_for_affiliation(self, team_id: str) -> list[str]:
        return self.offer_ids_for(self.row_ids_for_affiliation(team_id))

    def offer_ids_for_market(self, market: str) -> list[str]:
        return self.offer_ids_for(self.row_ids_for_market(market))

    def legacy_string_indexes(self) -> dict[str, dict[str, list[str]]]:
        """BoardIndexes-compatible posting lists (string offer IDs)."""
        return {
            "by_event": {k: self.offer_ids_for(v) for k, v in self.by_event_rows.items()},
            "by_affiliation": {k: self.offer_ids_for(v) for k, v in self.by_affiliation_rows.items()},
            "by_subject": {k: self.offer_ids_for(v) for k, v in self.by_subject_rows.items()},
            "by_market": {k: self.offer_ids_for(v) for k, v in self.by_market_rows.items()},
            "by_league": {k: self.offer_ids_for(v) for k, v in self.by_league_rows.items()},
        }

    def lookup_composite(
        self,
        *,
        sport: str,
        league: str,
        event: str,
        team: str,
        subject: str,
        market: str,
    ) -> list[str]:
        key = (sport, str(league).upper(), event, team, subject, str(market).lower())
        return self.offer_ids_for(self.composite.get(key, ()))

    def sqlite_event_offers(self, event_id: str) -> list[str]:
        self.telemetry.record(
            "ALG-INDEX-002",
            problem_class="SQLITE_INDEX",
            producer="dcm.board_store.BoardStore.sqlite_event_offers",
            consumer="dcm.research.os_graphs",
            phase="QUERIED",
            downstream_used=True,
        )
        cur = self.sqlite.execute("SELECT offer_id FROM offers WHERE event_id = ?", (event_id,))
        return [str(r[0]) for r in cur.fetchall()]

    def sqlite_has_payload_column(self) -> bool:
        cur = self.sqlite.execute("PRAGMA table_info(offers)")
        cols = {str(r[1]) for r in cur.fetchall()}
        return "payload" in cols

    def might_have_offer(self, offer_id: str) -> bool:
        return self.bloom.might_contain(offer_id)

    def mapping_audit(self) -> dict[str, Any]:
        """Stable ID mapping summary for audits / PROGRAM_STATUS."""
        return {
            "schema": SCHEMA_VERSION,
            "n": self.n,
            "offerIds": list(self.offer_ids),
            "events": sorted(k for k in self.by_event_rows if k),
            "subjects": sorted(k for k in self.by_subject_rows if k),
            "markets": sorted(k for k in self.by_market_rows if k),
            "affiliations": sorted(k for k in self.by_affiliation_rows if k),
            "sqlitePayloadDuplicated": self.sqlite_has_payload_column(),
            "compactShape": {
                "n": self.compact.n,
                "lineDtype": str(self.compact.line.dtype),
                "idDtype": str(self.compact.offer_i.dtype),
            },
        }

    def close(self) -> None:
        try:
            self.sqlite.close()
        except sqlite3.Error:
            return


def board_store_matches_index_semantics(
    store: BoardStore,
    *,
    by_event: Mapping[str, Sequence[str]],
    by_subject: Mapping[str, Sequence[str]],
    by_affiliation: Mapping[str, Sequence[str]],
    by_market: Mapping[str, Sequence[str]],
    offer_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, bool]:
    """Compare BoardStore lookups to BoardIndexes string-index semantics."""
    def _same(a: Mapping[str, Sequence[str]], b: Mapping[str, Sequence[str]]) -> bool:
        keys = set(a) | set(b)
        for k in keys:
            if list(a.get(k) or ()) != list(b.get(k) or ()):
                return False
        return True

    legacy = store.legacy_string_indexes()
    rows_match = True
    for oid, row in offer_by_id.items():
        got = store.exact_offer(oid)
        if got is None or str(got.get("projectionId") or "") != oid:
            rows_match = False
            break
        # Same object identity preferred (single copy); content equality required.
        if dict(got) != dict(row) and got is not row:
            # Content equality of critical keys
            for key in ("projectionId", "eventId", "playerId", "market", "line", "league"):
                if got.get(key) != row.get(key):
                    rows_match = False
                    break
    return {
        "offers": rows_match and set(store.offer_ids) == set(offer_by_id),
        "by_event": _same(legacy["by_event"], by_event),
        "by_subject": _same(legacy["by_subject"], by_subject),
        "by_affiliation": _same(legacy["by_affiliation"], by_affiliation),
        "by_market": _same(legacy["by_market"], by_market),
        "no_payload_column": not store.sqlite_has_payload_column(),
    }
