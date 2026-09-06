"""Cheapest-exact-first indexes for CFB identity and reusable-evidence lookup.

Order of use: in-memory hash → composite key → content-hash → SQLite B-tree
→ inverted/FTS → alias (Aho-Corasick) → fuzzy → semantic (never for known IDs).

BoardIndexes is backed by the canonical single-copy BoardStore (Phase 7–8):
audit dicts stay one copy; compute indexes use int32 row IDs / bitmaps / lean SQLite.
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
from dcm.board_store import BoardStore
from dcm.contracts.hashes import content_hash


from dcm.cfb.markets import ACTIVE_CFB_MARKETS, GUARDED_LAUNCH_MARKETS

SUPPORTED_CFB_MARKETS = ACTIVE_CFB_MARKETS
GUARDED_CFB_MARKETS = GUARDED_LAUNCH_MARKETS


class BoardIndexes:
    """Exact indexes over a frozen board. No repeated full-board linear scans.

    Backed by BoardStore: one audit copy of each row; SoA / int32 posting lists
    for compute; SQLite stores keys+row_id only (no per-row json.dumps payload).
    """

    def __init__(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        telemetry: AlgorithmTelemetry | None = None,
        store: BoardStore | None = None,
    ) -> None:
        self.telemetry = telemetry or AlgorithmTelemetry()
        self.store = store if store is not None else BoardStore(rows, telemetry=self.telemetry)
        # Legacy string views (behavior-preserving API for CFB launch / OS graphs).
        legacy = self.store.legacy_string_indexes()
        self.offer_by_id: dict[str, dict[str, Any]] = hash_table(self.store.offer_by_id_map().items())
        self.composite: dict[tuple[str, str, str, str, str, str], list[str]] = {
            k: self.store.offer_ids_for(v) for k, v in self.store.composite.items()
        }
        self.by_event: dict[str, list[str]] = legacy["by_event"]
        self.by_affiliation: dict[str, list[str]] = legacy["by_affiliation"]
        self.by_subject: dict[str, list[str]] = legacy["by_subject"]
        self.by_market: dict[str, list[str]] = legacy["by_market"]
        self.by_league: dict[str, list[str]] = legacy["by_league"]
        self.content = dict(self.store.content)
        self.eligibility = self.store.eligibility
        self.cfb_supported = self.store.cfb_supported
        self.bloom = self.store.bloom
        self.sqlite = self.store.sqlite
        self.offer_ids = self.store.offer_ids
        self.alias = AhoCorasick()
        self.inverted = InvertedIndex()
        names: list[str] = []
        for i, oid in enumerate(self.offer_ids):
            row = self.offer_by_id[oid]
            name = str(row.get("playerName") or "")
            if name:
                names.append(name)
                self.alias.add(name.lower())
                self.inverted.add(i, name.lower().split())
        if names:
            self.alias.build()
        self.telemetry.record("ALG-INDEX-001", problem_class="HOT_HASH_INDEX", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch", count=len(self.offer_by_id), phase="BUILT", note="BoardStore-backed index constructed, not queried")
        self.telemetry.record("ALG-SEARCH-002", problem_class="COMPOSITE_KEY", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch", count=len(self.composite), phase="BUILT", note="index constructed, not queried")
        self.telemetry.record("ALG-INDEX-002", problem_class="SQLITE_INDEX", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch", phase="BUILT", note="keys+row_id only")
        self.telemetry.record("ALG-INDEX-009", problem_class="BLOOM_REJECT", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch", phase="BUILT")
        self.telemetry.record("ALG-SEARCH-008", problem_class="MULTI_ALIAS_SCAN", producer="dcm.identity.resolve", consumer="dcm.research.indexes.BoardIndexes", count=len(names), phase="BUILT")
        self.telemetry.record("ALG-INDEX-016", problem_class="CONTENT_ADDRESS", producer="dcm.research.indexes.BoardIndexes", consumer="dcm.cfb.launch", count=len(self.content), phase="BUILT")

    def exact_offer(self, offer_id: str, *, downstream_used: bool = False) -> dict[str, Any] | None:
        self.telemetry.record(
            "ALG-INDEX-001",
            problem_class="HOT_HASH_INDEX",
            producer="dcm.research.indexes.BoardIndexes.exact_offer",
            consumer="dcm.cfb.launch",
            phase="QUERIED",
            downstream_used=downstream_used,
        )
        # Same single-copy dict as BoardStore (offer_by_id shares store rows).
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
        self.telemetry.record("ALG-SEARCH-002", problem_class="COMPOSITE_KEY", producer="dcm.research.indexes.BoardIndexes.lookup_composite", consumer="dcm.research.os_graphs", phase="QUERIED", downstream_used=True)
        return list(self.composite.get((sport, str(league).upper(), event, team, subject, str(market).lower()), ()))

    def sqlite_event_offers(self, event_id: str) -> list[str]:
        self.telemetry.record("ALG-INDEX-002", problem_class="SQLITE_INDEX", producer="dcm.research.indexes.BoardIndexes.sqlite_event_offers", consumer="dcm.research.os_graphs", phase="QUERIED", downstream_used=True)
        cur = self.sqlite.execute("SELECT offer_id FROM offers WHERE event_id = ?", (event_id,))
        return [str(r[0]) for r in cur.fetchall()]

    def might_have_offer(self, offer_id: str) -> bool:
        self.telemetry.record("ALG-INDEX-009", problem_class="BLOOM_REJECT", producer="dcm.research.indexes.BoardIndexes.might_have_offer", consumer="dcm.cfb.launch", phase="QUERIED", downstream_used=True)
        return self.bloom.might_contain(offer_id)

    def alias_hits(self, text: str) -> list[str]:
        self.telemetry.record("ALG-SEARCH-008", problem_class="MULTI_ALIAS_SCAN", producer="dcm.research.indexes.BoardIndexes.alias_hits", consumer="dcm.identity.resolve", phase="QUERIED", downstream_used=True)
        return [pat for _i, pat in self.alias.find(text.lower())]

    def fts_rank(self, query: str) -> list[tuple[str, float]]:
        """BM25 over player names. Never used to rediscover known offer IDs."""
        from dcm.algorithms.searching import bm25

        self.telemetry.record("ALG-SEARCH-005", problem_class="LEXICAL_RETRIEVAL", producer="dcm.algorithms.searching.bm25", consumer="dcm.research.indexes.BoardIndexes.fts_rank", phase="QUERIED", downstream_used=True)
        docs: list[list[str]] = []
        oids: list[str] = []
        for oid in self.offer_ids:
            row = self.offer_by_id.get(oid) or {}
            name = str(row.get("playerName") or "")
            if not name:
                continue
            docs.append(name.lower().split())
            oids.append(oid)
            if len(docs) >= 256:
                break
        if not docs:
            return []
        scores = bm25(query.lower().split(), docs[:256] if len(docs) > 256 else docs)
        ranked = sorted(zip(oids[: len(scores)], scores), key=lambda kv: kv[1], reverse=True)
        return [(oid, float(score) ) for oid, score in ranked if float(score) > 0][:25]

    def fuzzy_player(self, name: str, *, max_dist: int = 2) -> list[str]:
        from dcm.algorithms.searching import fuzzy_retrieve

        self.telemetry.record("ALG-SEARCH-010", problem_class="FUZZY_MATCH", producer="dcm.algorithms.searching.fuzzy_retrieve", consumer="dcm.research.indexes.BoardIndexes.fuzzy_player", phase="QUERIED", downstream_used=True)
        needle = str(name or "").lower().strip()
        if not needle:
            return []
        candidates: list[str] = []
        by_name: dict[str, str] = {}
        scanned = 0
        for oid in self.offer_ids:
            row = self.offer_by_id.get(oid) or {}
            cand = str(row.get("playerName") or "").lower()
            scanned += 1
            if cand:
                candidates.append(cand)
                by_name.setdefault(cand, oid)
            if scanned >= 256:
                break
        return [by_name[c] for c, _d in fuzzy_retrieve(needle, candidates, max_distance=max_dist) if c in by_name]

    def near_duplicate_names(self) -> list[tuple[str, str, float]]:
        from dcm.algorithms.searching import minhash_jaccard, minhash_signature, simhash

        self.telemetry.record("ALG-SEARCH-011", problem_class="NEAR_DUPLICATE", producer="dcm.algorithms.searching.minhash_signature", consumer="dcm.research.indexes.BoardIndexes.near_duplicate_names", phase="QUERIED", downstream_used=True)
        self.telemetry.record("ALG-SEARCH-012", problem_class="NEAR_DUPLICATE", producer="dcm.algorithms.searching.simhash", consumer="dcm.research.indexes.BoardIndexes.near_duplicate_names", phase="QUERIED", downstream_used=True)
        sigs: list[tuple[str, tuple[int, ...], int]] = []
        seen_names: set[str] = set()
        for oid in self.offer_ids:
            row = self.offer_by_id.get(oid) or {}
            name = str(row.get("playerName") or "").lower().strip()
            tokens = name.split()
            if len(tokens) < 1 or name in seen_names:
                continue
            seen_names.add(name)
            sigs.append((oid, minhash_signature(tokens), simhash(tokens)))
            if len(sigs) >= 64:
                break
        pairs: list[tuple[str, str, float]] = []
        for i, (a, sa, ha) in enumerate(sigs):
            for b, sb, hb in sigs[i + 1 :]:
                j = minhash_jaccard(sa, sb)
                if j >= 0.8 or (ha ^ hb).bit_count() <= 8:
                    pairs.append((a, b, j))
        return pairs

    def requirement_bitmaps(self, requests: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        _bits, ids = requirement_offer_bitmaps(requests, self.offer_ids)
        self.telemetry.record(
            "ALG-INDEX-008",
            problem_class="BITMAP_ELIGIBILITY",
            producer="dcm.research.indexes.requirement_offer_bitmaps",
            consumer="dcm.research.indexes.BoardIndexes.requirement_bitmaps",
            count=len(ids),
            phase="QUERIED",
            downstream_used=True,
        )
        return {rid: len(oids) for rid, oids in ids.items()}

    def query_retrieval_cascade(self, name: str) -> dict[str, Any]:
        """Exact-first then lexical/fuzzy/near-dup fusion. Never embeddings for known IDs."""
        from dcm.algorithms.indexing import MinHashLSHIndex, SimHashIndex
        from dcm.algorithms.searching import (
            Trie,
            bm25f,
            maximal_marginal_relevance,
            minhash_signature,
            reciprocal_rank_fusion,
            simhash,
        )

        needle = str(name or "").lower().strip()
        trie = Trie()
        names: list[str] = []
        field_docs: list[dict[str, list[str]]] = []
        oids: list[str] = []
        lsh = MinHashLSHIndex()
        sim_idx = SimHashIndex()
        for oid in self.offer_ids[:64]:
            row = self.offer_by_id.get(oid) or {}
            pname = str(row.get("playerName") or "").lower()
            if pname:
                trie.insert(pname, oid)
                names.append(pname)
            field_docs.append({
                "name": pname.split(),
                "team": str(row.get("team") or "").lower().split(),
                "market": str(row.get("market") or "").lower().split(),
            })
            oids.append(oid)
            tokens = pname.split() or [oid]
            lsh.add(oid, minhash_signature(tokens))
            sim_idx.add(oid, simhash(tokens))
        prefix = trie.prefix(needle[: max(1, min(3, len(needle)))]) if needle else []
        self.telemetry.record("ALG-SEARCH-009", problem_class="TRIE_PREFIX", producer="dcm.algorithms.searching.Trie", consumer="dcm.research.indexes.BoardIndexes.query_retrieval_cascade", phase="QUERIED", downstream_used=True)
        terms = needle.split() or ["x"]
        and_hits = self.inverted.boolean_and(terms)
        self.telemetry.record("ALG-SEARCH-007", problem_class="BOOLEAN_AND", producer="dcm.algorithms.searching.InvertedIndex.boolean_and", consumer="dcm.research.indexes.BoardIndexes.query_retrieval_cascade", phase="QUERIED", downstream_used=True)
        bm25f_scores = bm25f(terms, field_docs, field_weights={"name": 3.0, "team": 1.0, "market": 1.0}) if field_docs else []
        self.telemetry.record("ALG-SEARCH-006", problem_class="BM25F", producer="dcm.algorithms.searching.bm25f", consumer="dcm.research.indexes.BoardIndexes.query_retrieval_cascade", phase="QUERIED", downstream_used=True)
        self.telemetry.record("ALG-INDEX-010", problem_class="MINHASH_LSH", producer="dcm.algorithms.indexing.MinHashLSHIndex", consumer="dcm.research.indexes.BoardIndexes.query_retrieval_cascade", phase="QUERIED", downstream_used=True)
        self.telemetry.record("ALG-INDEX-011", problem_class="SIMHASH_INDEX", producer="dcm.algorithms.indexing.SimHashIndex", consumer="dcm.research.indexes.BoardIndexes.query_retrieval_cascade", phase="QUERIED", downstream_used=True)
        lsh_hits = lsh.query(minhash_signature(terms)) if needle else []
        self.telemetry.record("ALG-SEARCH-013", problem_class="LSH", producer="dcm.algorithms.searching.LSHIndex", consumer="dcm.research.indexes.BoardIndexes.query_retrieval_cascade", count=len(lsh_hits), phase="QUERIED", downstream_used=True)
        sim_hits = sim_idx.nearest(simhash(terms), max_distance=12) if needle else []
        fts = [oid for oid, _s in self.fts_rank(needle)]
        fuzz = self.fuzzy_player(needle)
        fused = reciprocal_rank_fusion(fts, fuzz, lsh_hits)
        self.telemetry.record("ALG-SEARCH-014", problem_class="RRF", producer="dcm.algorithms.searching.reciprocal_rank_fusion", consumer="dcm.research.indexes.BoardIndexes.query_retrieval_cascade", phase="QUERIED", downstream_used=True)
        rel = {item: score for item, score in fused}
        mmr = maximal_marginal_relevance(
            [item for item, _s in fused[:12]],
            rel,
            lambda a, b: 1.0 if a == b else 0.0,
            k=5,
        )
        self.telemetry.record("ALG-SEARCH-015", problem_class="MMR", producer="dcm.algorithms.searching.maximal_marginal_relevance", consumer="dcm.research.indexes.BoardIndexes.query_retrieval_cascade", phase="QUERIED", downstream_used=True)
        return {
            "triePrefix": prefix[:8],
            "booleanAnd": and_hits[:8],
            "bm25fTop": sorted(zip(oids, bm25f_scores), key=lambda kv: kv[1], reverse=True)[:5] if bm25f_scores else [],
            "lshHits": lsh_hits[:8],
            "simHits": sim_hits[:8],
            "rrf": fused[:8],
            "mmr": mmr,
        }

    def resolve_identities(self) -> dict[str, Any]:
        """Exact-first identity. Known projectionId → hash lookup → done.

        Bloom/composite/SQLite are not queried for IDs already in the hash table.
        Fuzzy/FTS/cascade run only when the canonical projectionId is missing.
        """
        resolved: list[dict[str, Any]] = []
        exact_n = 0
        skipped_fuzzy = 0
        fuzzy_n = 0
        cascade_n = 0
        by_name: dict[str, list[str]] = {}
        last_cascade: dict[str, Any] = {}
        for oid, row in self.offer_by_id.items():
            hit = self.exact_offer(oid, downstream_used=True)
            subject = str(row.get("playerId") or row.get("subjectId") or "")
            name = str(row.get("playerName") or "").strip()
            if name:
                by_name.setdefault(name.lower(), []).append(oid)
            if hit is not None:
                exact_n += 1
                skipped_fuzzy += 1
                resolved.append({"offerId": oid, "method": "EXACT_ID", "playerId": subject})
                continue
            method = "UNRESOLVED"
            if name:
                aliases = self.alias_hits(name)
                if aliases:
                    method = "ALIAS"
                else:
                    fuzzy = self.fuzzy_player(name)
                    if fuzzy:
                        method = "FUZZY"
                        fuzzy_n += 1
                    else:
                        fts = self.fts_rank(name)
                        if fts:
                            method = "FTS"
                        else:
                            last_cascade = self.query_retrieval_cascade(name)
                            method = "CASCADE"
                            cascade_n += 1
            resolved.append({"offerId": oid, "method": method, "playerId": subject})
        if skipped_fuzzy:
            for alg, cls, producer in (
                ("ALG-SEARCH-010", "FUZZY_MATCH", "dcm.algorithms.searching.fuzzy_retrieve"),
                ("ALG-SEARCH-005", "LEXICAL_RETRIEVAL", "dcm.algorithms.searching.bm25"),
                ("ALG-SEARCH-014", "RRF", "dcm.algorithms.searching.reciprocal_rank_fusion"),
            ):
                self.telemetry.record(
                    alg,
                    problem_class=cls,
                    producer=producer,
                    consumer="dcm.research.indexes.BoardIndexes.resolve_identities",
                    phase="SKIPPED_NOT_APPLICABLE",
                    activated=False,
                    count=skipped_fuzzy,
                    lifecycle_state="SKIPPED_NOT_APPLICABLE",
                    note="exact projectionId resolved; fuzzy/lexical/semantic not applicable",
                )
        collisions = {n: ids for n, ids in by_name.items() if len(ids) > 1}
        if collisions:
            near_dups = self.near_duplicate_names()
        else:
            near_dups = []
            self.telemetry.record(
                "ALG-SEARCH-011",
                problem_class="NEAR_DUPLICATE",
                producer="dcm.algorithms.searching.minhash_signature",
                consumer="dcm.research.indexes.BoardIndexes.resolve_identities",
                phase="SKIPPED_NOT_APPLICABLE",
                activated=False,
                lifecycle_state="SKIPPED_NOT_APPLICABLE",
                note="no display-name collisions; MinHash/SimHash not applicable",
            )
        return {
            "resolved": resolved,
            "exactCount": exact_n,
            "skippedFuzzy": skipped_fuzzy,
            "fuzzyCount": fuzzy_n,
            "cascadeCount": cascade_n,
            "nameCollisions": len(collisions),
            "nearDuplicatePairs": len(near_dups),
            "queriedEvents": 0,
            "retrievalCascade": {k: v for k, v in last_cascade.items() if k != "booleanAnd"} if last_cascade else {},
        }

    def close(self) -> None:
        try:
            self.store.close()
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
        self.telemetry.record("ALG-SEARCH-001", problem_class="EXACT_IDENTITY", producer="dcm.research.indexes.EvidenceIndexes", consumer="dcm.research.acquisition", count=max(1, len(self.by_hash)), phase="BUILT")

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
        self.telemetry.record("ALG-SEARCH-001", problem_class="EXACT_IDENTITY", producer="dcm.research.indexes.EvidenceIndexes.lookup_scope", consumer="dcm.research.acquisition", phase="QUERIED", downstream_used=True)
        hashes = self.by_scope.get((str(scope), str(scope_id))) or []
        return [self.by_hash[h] for h in hashes if h in self.by_hash]

    def has_hash(self, digest: str) -> bool:
        self.telemetry.record("ALG-INDEX-009", problem_class="BLOOM_REJECT", producer="dcm.research.indexes.EvidenceIndexes.has_hash", consumer="dcm.research.acquisition", phase="QUERIED", downstream_used=True)
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
