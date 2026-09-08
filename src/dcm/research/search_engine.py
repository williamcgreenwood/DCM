"""Deterministic local search/ranking engine used by the DCM batch planner.

The engine ranks already-acquired records and research documents.  It is not
an HTTP crawler and therefore does not pretend that a local index replaces the
ChatGPT Work web-search surface.  The host supplies public-source observations;
this module creates bounded, reproducible retrieval and deduplication over
them before the canonical importer sees them.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from dcm.algorithms.searching import (
    AhoCorasick,
    InvertedIndex,
    LSHIndex,
    Trie,
    bm25f,
    fuzzy_retrieve,
    hamming64,
    maximal_marginal_relevance,
    minhash_jaccard,
    minhash_signature,
    reciprocal_rank_fusion,
    simhash,
    wand_topk,
)
from dcm.contracts.hashes import content_hash


ENGINE_SCHEMA = "pillars_dcm.search_engine.v1"
_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def _tokens(value: Any) -> list[str]:
    return [x.lower() for x in _TOKEN.findall(str(value or "")) if len(x) > 1]


def _time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class SearchEngine:
    def __init__(self, documents: Iterable[Mapping[str, Any]] = ()) -> None:
        self.documents: list[dict[str, Any]] = [dict(doc) for doc in documents if isinstance(doc, Mapping)]
        self.inverted = InvertedIndex()
        self.trie = Trie()
        self.aho = AhoCorasick()
        self.lsh = LSHIndex()
        self.exact: dict[str, list[int]] = defaultdict(list)
        self.composite: dict[tuple[str, str], list[int]] = defaultdict(list)
        self.doc_tokens: list[list[str]] = []
        self.doc_fields: list[dict[str, list[str]]] = []
        self.signatures: dict[int, tuple[int, ...]] = {}
        self.simhashes: dict[int, int] = {}
        self._build()

    def _build(self) -> None:
        seen: set[str] = set()
        for index, doc in enumerate(self.documents):
            fields: dict[str, list[str]] = {}
            all_tokens: list[str] = []
            for key, value in sorted(doc.items(), key=lambda item: str(item[0])):
                if key in {"publishedAt", "published_at", "validAt", "valid_at", "retrievedAt", "retrieved_at"}:
                    continue
                field_tokens = _tokens(value)
                fields[str(key)] = field_tokens
                all_tokens.extend(field_tokens)
            self.doc_tokens.append(all_tokens)
            self.doc_fields.append(fields)
            self.inverted.add(index, all_tokens)
            doc_id = str(doc.get("id") or doc.get("documentId") or doc.get("claim_hash") or index)
            self.exact[doc_id].append(index)
            scope = str(doc.get("semantic_scope") or doc.get("scope") or "").upper()
            scope_id = str(doc.get("scope_id") or doc.get("scopeId") or "")
            if scope and scope_id:
                self.composite[(scope, scope_id)].append(index)
            for token in sorted(set(all_tokens)):
                self.trie.insert(token, True)
                if token not in seen:
                    self.aho.add(token)
                    seen.add(token)
            signature = minhash_signature(all_tokens)
            self.signatures[index] = signature
            self.simhashes[index] = simhash(all_tokens)
            self.lsh.add(str(index), signature)
        self.aho.build()

    @property
    def index_receipt(self) -> dict[str, Any]:
        body = {
            "schema": ENGINE_SCHEMA,
            "documentCount": len(self.documents),
            "termCount": len(self.inverted.postings),
            "exactKeyCount": len(self.exact),
            "compositeKeyCount": len(self.composite),
            "algorithms": ["EXACT", "COMPOSITE", "BOOLEAN", "BM25F", "WAND_TOPK", "TRIE", "AHO_CORASICK", "MINHASH", "SIMHASH", "LSH", "RRF", "MMR"],
        }
        body["indexHash"] = content_hash(body)
        return body

    def _eligible(self, *, cutoff: str | None = None, valid_at: str | None = None) -> set[int]:
        cutoff_time = _time(cutoff)
        valid_time = _time(valid_at)
        eligible: set[int] = set()
        for i, doc in enumerate(self.documents):
            published = _time(doc.get("publishedAt") or doc.get("published_at") or doc.get("retrievedAt") or doc.get("retrieved_at"))
            if cutoff_time and published and published > cutoff_time:
                continue
            valid_from = _time(doc.get("validFrom") or doc.get("valid_from") or doc.get("validAt") or doc.get("valid_at"))
            valid_to = _time(doc.get("validTo") or doc.get("valid_to"))
            if valid_time and valid_from and valid_time < valid_from:
                continue
            if valid_time and valid_to and valid_time > valid_to:
                continue
            eligible.add(i)
        return eligible

    def duplicate_candidates(self, *, threshold: float = 0.9) -> list[list[int]]:
        buckets: dict[str, list[int]] = defaultdict(list)
        for index, doc in enumerate(self.documents):
            exact = str(doc.get("claim_hash") or doc.get("recordDigest") or "")
            buckets[exact or f"approx:{self.simhashes[index]}"] .append(index)
        groups: list[list[int]] = []
        for values in buckets.values():
            values = sorted(set(values))
            if len(values) < 2:
                continue
            groups.append(values)
        # LSH candidates are approximate only; exact token similarity is the
        # merge gate, so false positives never become merged claims.
        for index in range(len(self.documents)):
            candidates = [int(x) for x in self.lsh.query(self.signatures[index]) if int(x) != index]
            for other in candidates:
                if minhash_jaccard(self.signatures[index], self.signatures[other]) >= float(threshold):
                    groups.append(sorted({index, other}))
        unique = {tuple(group) for group in groups if len(group) > 1}
        return [list(group) for group in sorted(unique)]

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        cutoff: str | None = None,
        valid_at: str | None = None,
        exact_id: str | None = None,
        scope: str | None = None,
        scope_id: str | None = None,
        required_terms: Iterable[str] = (),
    ) -> dict[str, Any]:
        eligible = self._eligible(cutoff=cutoff, valid_at=valid_at)
        if exact_id:
            candidate_ids = set(self.exact.get(str(exact_id), [])) & eligible
        elif scope and scope_id:
            candidate_ids = set(self.composite.get((str(scope).upper(), str(scope_id)), [])) & eligible
        else:
            terms = _tokens(query)
            boolean = set(self.inverted.boolean_or(terms)) & eligible if terms else set(eligible)
            required = [str(term).lower() for term in required_terms if str(term)]
            if required:
                boolean &= set(self.inverted.boolean_and(required))
            candidate_ids = boolean or set(eligible)
        query_terms = _tokens(query)
        field_docs = [self.doc_fields[i] for i in range(len(self.documents))]
        scores = bm25f(query_terms, field_docs, field_weights={"name": 3.0, "title": 3.0, "entity": 2.0, "text": 1.0, "content": 1.0})
        scored = sorted(((i, scores[i]) for i in candidate_ids), key=lambda item: (-item[1], str(self.documents[item[0]].get("id") or item[0])))
        if len(candidate_ids) > 1000:
            scored = [(i, score) for i, score in wand_topk(query_terms, [self.doc_tokens[i] for i in sorted(candidate_ids)], k=min(max(k * 5, k), len(candidate_ids)))]
            ordered = sorted(candidate_ids)
            scored = [(ordered[i], score) for i, score in scored]
        bm25_ids = [str(self.documents[i].get("id") or i) for i, _ in scored]
        bool_ids = [str(self.documents[i].get("id") or i) for i in sorted(candidate_ids)]
        fused_ids = [item for item, _ in reciprocal_rank_fusion(bm25_ids, bool_ids)]
        relevance = {str(self.documents[i].get("id") or i): float(scores[i]) for i in candidate_ids}
        token_by_id = {str(self.documents[i].get("id") or i): set(self.doc_tokens[i]) for i in candidate_ids}
        def similarity(left: str, right: str) -> float:
            a, b = token_by_id.get(left, set()), token_by_id.get(right, set())
            return len(a & b) / max(1, len(a | b))
        selected_ids = maximal_marginal_relevance(fused_ids, relevance, similarity, k=max(0, int(k)))
        results = []
        for doc_id in selected_ids:
            indices = self.exact.get(doc_id, [])
            index = next((i for i in indices if i in candidate_ids), None)
            if index is None:
                continue
            result = dict(self.documents[index])
            result["_score"] = round(float(relevance.get(doc_id, 0.0)), 8)
            result["_documentId"] = doc_id
            results.append(result)
        return {
            "schema": ENGINE_SCHEMA,
            "query": str(query),
            "cutoff": cutoff,
            "validAt": valid_at,
            "candidateCount": len(candidate_ids),
            "results": results,
            "algorithmIds": ["ALG-SEARCH-001", "ALG-SEARCH-003", "ALG-SEARCH-004", "ALG-SEARCH-006", "ALG-SEARCH-008", "ALG-SEARCH-009", "ALG-SEARCH-013", "ALG-SEARCH-014", "ALG-SEARCH-015", "ALG-SEARCH-017", "ALG-SEARCH-018"],
            "indexHash": self.index_receipt["indexHash"],
        }


__all__ = ["ENGINE_SCHEMA", "SearchEngine"]
