"""Cheapest-exact-first indexes for CFB identity and reusable-evidence lookup.

Order of use: in-memory hash → composite key → content-hash → SQLite B-tree
→ inverted/FTS → alias (Aho-Corasick) → fuzzy → semantic (never for known IDs).
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from dcm.algorithms.indexing import (
    Bitset,
    BloomFilter,
    hash_table,
    open_memory_index,
    sqlite_composite_index,
)
from dcm.algorithms.searching import AhoCorasick, InvertedIndex
from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.contracts.hashes import content_hash


SUPPORTED_CFB_MARKETS = (
    "pass_yds",
    "pass_att",
    "pass_cmp",
    "rush_yds",
    "rush_att",
    "rec_yds",
    "receptions",
    "pass_rush_yds",
    "rush_rec_yds",
)


class BoardIndexes:
    """Exact indexes over a frozen board. No repeated full-board linear scans."""

    def __init__(self, rows: Iterable[Mapping[str, Any]], *, telemetry: AlgorithmTelemetry | None = None) -> None:
        self.telemetry = telemetry or AlgorithmTelemetry()
        self.offer_by_id: dict[str, dict[str, Any]] = hash_table()
        self.composite: dict[tuple[str, str, str, str, str, str], list[str]] = {}
        self.by_event: dict[str, list[str]] = {}
        self.by_affiliation: dict[str, list[str]] = {}
        self.by_subject: dict[str, list[str]] = {}
        self.by_market: dict[str, list[str]] = {}
        self.by_league: dict[str, list[str]] = {}
        self.content: dict[str, str] = {}
        self.eligibility = Bitset()
        self.cfb_supported = Bitset()
        self.bloom = BloomFilter(m_bits=4096, k=4)
        self.alias = AhoCorasick()
        self.inverted = InvertedIndex()
        self.sqlite = open_memory_index()
        self.sqlite.execute(
            "CREATE TABLE IF NOT EXISTS offers ("
            "offer_id TEXT PRIMARY KEY, sport TEXT, league TEXT, event_id TEXT, "
            "team_id TEXT, subject_id TEXT, market TEXT, player_name TEXT, payload TEXT)"
        )
        sqlite_composite_index(self.sqlite, "offers", ("sport", "league", "event_id", "team_id", "subject_id", "market"))
        sqlite_composite_index(self.sqlite, "offers", ("league", "market"), name="idx_offers_league_market")
        sqlite_composite_index(self.sqlite, "offers", ("event_id", "subject_id"), name="idx_offers_event_subject")
        names: list[str] = []
        offer_ids: list[str] = []
        for i, raw in enumerate(rows):
            row = dict(raw)
            oid = str(row.get("projectionId") or "")
            if not oid:
                continue
            self.offer_by_id[oid] = row
            offer_ids.append(oid)
            sport = str(row.get("sportFamily") or "")
            league = str(row.get("league") or "").upper()
            event = str(row.get("eventId") or "")
            team = str(row.get("teamId") or row.get("team") or "")
            subject = str(row.get("playerId") or row.get("subjectId") or "")
            market = str(row.get("market") or "").lower()
            key = (sport, league, event, team, subject, market)
            self.composite.setdefault(key, []).append(oid)
            self.by_event.setdefault(event, []).append(oid)
            self.by_affiliation.setdefault(team, []).append(oid)
            self.by_subject.setdefault(subject, []).append(oid)
            self.by_market.setdefault(market, []).append(oid)
            self.by_league.setdefault(league, []).append(oid)
            digest = content_hash({"offer": oid, "line": row.get("line"), "market": market})
            self.content[digest] = oid
            self.eligibility.add(i)
            if league == "CFB" and market in SUPPORTED_CFB_MARKETS and row.get("modifier") != "GOBLIN":
                self.cfb_supported.add(i)
            self.bloom.add(oid)
            name = str(row.get("playerName") or "")
            if name:
                names.append(name)
                self.alias.add(name.lower())
                self.inverted.add(i, name.lower().split())
            self.sqlite.execute(
                "INSERT OR REPLACE INTO offers VALUES (?,?,?,?,?,?,?,?,?)",
                (oid, sport, league, event, team, subject, market, name, json.dumps(row, sort_keys=True, default=str)),
            )
        if names:
            self.alias.build()
        self.offer_ids = tuple(offer_ids)
        self.telemetry.record("ALG-INDEX-001", problem_class="HOT_HASH_INDEX", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch", count=len(self.offer_by_id))
        self.telemetry.record("ALG-SEARCH-002", problem_class="COMPOSITE_KEY", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch", count=len(self.composite))
        self.telemetry.record("ALG-INDEX-002", problem_class="SQLITE_INDEX", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch")
        self.telemetry.record("ALG-INDEX-009", problem_class="BLOOM_REJECT", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch")
        self.telemetry.record("ALG-SEARCH-008", problem_class="MULTI_ALIAS_SCAN", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.identity.resolve", count=len(names))
        self.telemetry.record("ALG-INDEX-016", problem_class="CONTENT_ADDRESS", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch", count=len(self.content))

    def exact_offer(self, offer_id: str) -> dict[str, Any] | None:
        return self.offer_by_id.get(str(offer_id))

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
        return list(self.composite.get((sport, str(league).upper(), event, team, subject, str(market).lower()), ()))

    def sqlite_event_offers(self, event_id: str) -> list[str]:
        cur = self.sqlite.execute("SELECT offer_id FROM offers WHERE event_id = ?", (event_id,))
        return [str(r[0]) for r in cur.fetchall()]

    def might_have_offer(self, offer_id: str) -> bool:
        return self.bloom.might_contain(offer_id)

    def alias_hits(self, text: str) -> list[str]:
        return [pat for _i, pat in self.alias.find(text.lower())]

    def close(self) -> None:
        try:
            self.sqlite.close()
        except sqlite3.Error:
            return


class EvidenceIndexes:
    """Exact reusable-evidence lookup. Web acquisition is last."""

    def __init__(self, claims: Iterable[Mapping[str, Any]] | None = None, *, telemetry: AlgorithmTelemetry | None = None) -> None:
        self.telemetry = telemetry or AlgorithmTelemetry()
        self.by_hash: dict[str, dict[str, Any]] = hash_table()
        self.by_scope: dict[tuple[str, str], list[str]] = {}
        self.bloom = BloomFilter(m_bits=4096, k=4)
        self.sqlite = open_memory_index()
        for claim in claims or ():
            self.add(dict(claim))
        self.telemetry.record("ALG-SEARCH-001", problem_class="EXACT_IDENTITY", producer="dcm.research.indexes.EvidenceIndexes", consumer="dcm.research.acquisition", count=max(1, len(self.by_hash)))

    def add(self, claim: Mapping[str, Any]) -> str:
        rec = dict(claim)
        digest = str(rec.get("claim_hash") or content_hash(rec))
        rec["claim_hash"] = digest
        self.by_hash[digest] = rec
        scope = str(rec.get("semantic_scope") or "")
        scope_id = str(rec.get("scope_id") or "")
        self.by_scope.setdefault((scope, scope_id), []).append(digest)
        self.bloom.add(digest)
        payload = json.dumps(rec, sort_keys=True, default=str)
        self.sqlite.execute(
            "INSERT INTO records (entity_id, claim_type, valid_at, observed_at, cutoff, payload) VALUES (?,?,?,?,?,?)",
            (scope_id, scope, str(rec.get("published_at") or ""), str(rec.get("observed_at") or ""), str(rec.get("forecast_cutoff") or ""), payload),
        )
        return digest

    def lookup_scope(self, scope: str, scope_id: str) -> list[dict[str, Any]]:
        hashes = self.by_scope.get((str(scope), str(scope_id))) or []
        return [self.by_hash[h] for h in hashes if h in self.by_hash]

    def has_hash(self, digest: str) -> bool:
        if digest not in self.bloom:
            return False
        return digest in self.by_hash

    def close(self) -> None:
        try:
            self.sqlite.close()
        except sqlite3.Error:
            return


def requirement_offer_bitmaps(
    requests: Iterable[Mapping[str, Any]],
    offer_ids: Sequence[str],
) -> tuple[dict[str, Bitset], dict[str, list[str]]]:
    """Reverse index Requirement → Offers as Python bitsets plus id lists."""
    index = {oid: i for i, oid in enumerate(offer_ids)}
    bits: dict[str, Bitset] = {}
    ids: dict[str, list[str]] = {}
    n = len(index)
    for req in requests:
        rid = str(req.get("request_id") or req.get("requestId") or "")
        if not rid:
            continue
        dependents = req.get("dependent_offer_ids") or req.get("dependentOfferIds") or []
        bs = Bitset(n)
        present: list[str] = []
        for oid in dependents:
            pos = index.get(str(oid))
            if pos is None:
                continue
            bs.add(pos)
            present.append(str(oid))
        bits[rid] = bs
        ids[rid] = present
    return bits, ids
