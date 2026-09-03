"""ChatGPT-native searching and retrieval primitives (stdlib only)."""
from __future__ import annotations

import hashlib
import math
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict, deque
from typing import Any, Callable, Hashable, Iterable, Mapping, Sequence


def exact_hash_lookup(table: Mapping[Hashable, Any], key: Hashable) -> Any:
    return table[key]


def composite_key(*parts: Any) -> tuple[Any, ...]:
    return tuple(parts)


def binary_search(sorted_values: Sequence[Any], value: Any) -> int:
    idx = bisect_left(sorted_values, value)
    if idx != len(sorted_values) and sorted_values[idx] == value:
        return idx
    return -1


def range_search(sorted_values: Sequence[Any], lo: Any, hi: Any) -> Sequence[Any]:
    return sorted_values[bisect_left(sorted_values, lo): bisect_right(sorted_values, hi)]


class InvertedIndex:
    def __init__(self) -> None:
        self.postings: dict[str, list[int]] = {}
        self.doc_lengths: dict[int, int] = {}
        self.doc_count = 0

    def add(self, doc_id: int, terms: Iterable[str]) -> None:
        terms_list = list(terms)
        self.doc_lengths[doc_id] = len(terms_list)
        self.doc_count = max(self.doc_count, doc_id + 1)
        seen: set[str] = set()
        for term in terms_list:
            if term in seen:
                self.postings.setdefault(term, [])
                continue
            seen.add(term)
            bucket = self.postings.setdefault(term, [])
            bucket.append(doc_id)

    def postings_for(self, term: str) -> list[int]:
        return list(self.postings.get(term, ()))

    def boolean_and(self, terms: Sequence[str]) -> list[int]:
        if not terms:
            return []
        sets = [set(self.postings.get(t, ())) for t in terms]
        out = sets[0]
        for s in sets[1:]:
            out &= s
        return sorted(out)

    def boolean_or(self, terms: Sequence[str]) -> list[int]:
        out: set[int] = set()
        for t in terms:
            out.update(self.postings.get(t, ()))
        return sorted(out)


def bm25(
    query_terms: Sequence[str],
    documents: Sequence[Sequence[str]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    n = len(documents)
    if n == 0:
        return []
    avgdl = sum(len(doc) for doc in documents) / n
    df: Counter[str] = Counter()
    tfs: list[Counter[str]] = []
    for doc in documents:
        tf = Counter(doc)
        tfs.append(tf)
        df.update(tf.keys())
    scores: list[float] = []
    for i, doc in enumerate(documents):
        score = 0.0
        dl = max(1, len(doc))
        for term in query_terms:
            freq = tfs[i][term]
            if freq == 0 or df[term] == 0:
                continue
            idf = math.log((n - df[term] + 0.5) / (df[term] + 0.5) + 1.0)
            denom = freq + k1 * (1.0 - b + b * dl / max(avgdl, 1e-9))
            score += idf * (freq * (k1 + 1.0)) / denom
        scores.append(score)
    return scores


def bm25f(
    query_terms: Sequence[str],
    field_docs: Sequence[Mapping[str, Sequence[str]]],
    *,
    field_weights: Mapping[str, float] | None = None,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    weights = dict(field_weights or {})
    fused: list[list[str]] = []
    for doc in field_docs:
        terms: list[str] = []
        for field, tokens in doc.items():
            w = max(1, int(round(float(weights.get(field, 1.0)))))
            for _ in range(w):
                terms.extend(tokens)
        fused.append(terms)
    return bm25(query_terms, fused, k1=k1, b=b)


def wand_topk(
    query_terms: Sequence[str],
    documents: Sequence[Sequence[str]],
    *,
    k: int = 10,
) -> list[tuple[int, float]]:
    """Block-Max WAND-style Top-K over in-memory BM25 scores.

    For ChatGPT-native board sizes this evaluates BM25 then uses a bounded
    heap. The selection engine only activates it when document count is large.
    """
    from dcm.algorithms.sorting import heap_topk

    scores = bm25(query_terms, documents)
    ranked = heap_topk(list(enumerate(scores)), k=k, key=lambda item: item[1])
    return [(int(i), float(s)) for i, s in ranked]


class Trie:
    def __init__(self) -> None:
        self.root: dict[str, Any] = {}

    def insert(self, word: str, value: Any = True) -> None:
        node = self.root
        for ch in word:
            node = node.setdefault(ch, {})
        node["$"] = value

    def prefix(self, word: str) -> list[str]:
        node: dict[str, Any] | None = self.root
        for ch in word:
            if node is None or ch not in node:
                return []
            node = node[ch]
        out: list[str] = []

        def walk(cur: dict[str, Any], prefix: str) -> None:
            if "$" in cur:
                out.append(prefix)
            for ch, nxt in cur.items():
                if ch == "$":
                    continue
                walk(nxt, prefix + ch)

        if node is not None:
            walk(node, word)
        return out

    def get(self, word: str) -> Any:
        node: dict[str, Any] | None = self.root
        for ch in word:
            if node is None or ch not in node:
                return None
            node = node[ch]
        if node is None:
            return None
        return node.get("$")


class AhoCorasick:
    def __init__(self) -> None:
        self.goto: list[dict[str, int]] = [{}]
        self.fail: list[int] = [0]
        self.output: list[tuple[str, ...]] = [()]

    def add(self, pattern: str) -> None:
        node = 0
        for ch in pattern:
            nxt = self.goto[node].get(ch)
            if nxt is None:
                nxt = len(self.goto)
                self.goto[node][ch] = nxt
                self.goto.append({})
                self.fail.append(0)
                self.output.append(())
            node = nxt
        self.output[node] = self.output[node] + (pattern,)

    def build(self) -> None:
        q: deque[int] = deque()
        for nxt in self.goto[0].values():
            q.append(nxt)
            self.fail[nxt] = 0
        while q:
            r = q.popleft()
            for ch, nxt in self.goto[r].items():
                q.append(nxt)
                f = self.fail[r]
                while f and ch not in self.goto[f]:
                    f = self.fail[f]
                self.fail[nxt] = self.goto[f].get(ch, 0)
                self.output[nxt] = self.output[nxt] + self.output[self.fail[nxt]]

    def find(self, text: str) -> list[tuple[int, str]]:
        node = 0
        hits: list[tuple[int, str]] = []
        for i, ch in enumerate(text):
            while node and ch not in self.goto[node]:
                node = self.fail[node]
            node = self.goto[node].get(ch, 0)
            for pat in self.output[node]:
                hits.append((i, pat))
        return hits


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def fuzzy_retrieve(query: str, candidates: Sequence[str], *, max_distance: int = 2) -> list[tuple[str, int]]:
    hits: list[tuple[str, int]] = []
    for cand in candidates:
        d = levenshtein(query, cand)
        if d <= max_distance:
            hits.append((cand, d))
    hits.sort(key=lambda item: (item[1], item[0]))
    return hits


def _stable_hash64(text: str, salt: str = "") -> int:
    digest = hashlib.sha256(f"{salt}:{text}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def minhash_signature(tokens: Iterable[str], *, num_perm: int = 32, seed: str = "DCM") -> tuple[int, ...]:
    uniq = list(dict.fromkeys(str(t) for t in tokens))
    if not uniq:
        return tuple(0 for _ in range(num_perm))
    sig: list[int] = []
    for i in range(num_perm):
        best = min(_stable_hash64(tok, f"{seed}:{i}") for tok in uniq)
        sig.append(best)
    return tuple(sig)


def minhash_jaccard(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    same = sum(1 for x, y in zip(a, b) if x == y)
    return same / len(a)


def simhash(tokens: Iterable[str], *, bits: int = 64) -> int:
    acc = [0] * bits
    for tok in tokens:
        h = _stable_hash64(str(tok), "sim")
        for i in range(bits):
            acc[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i, v in enumerate(acc):
        if v > 0:
            out |= 1 << i
    return out


def hamming64(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class LSHIndex:
    def __init__(self, *, bands: int = 8, rows: int = 4) -> None:
        self.bands = bands
        self.rows = rows
        self.buckets: dict[tuple[int, tuple[int, ...]], list[str]] = defaultdict(list)

    def add(self, key: str, signature: Sequence[int]) -> None:
        width = self.bands * self.rows
        sig = list(signature[:width])
        if len(sig) < width:
            sig.extend([0] * (width - len(sig)))
        for band in range(self.bands):
            chunk = tuple(sig[band * self.rows:(band + 1) * self.rows])
            self.buckets[(band, chunk)].append(key)

    def query(self, signature: Sequence[int]) -> list[str]:
        width = self.bands * self.rows
        sig = list(signature[:width])
        if len(sig) < width:
            sig.extend([0] * (width - len(sig)))
        found: dict[str, None] = {}
        for band in range(self.bands):
            chunk = tuple(sig[band * self.rows:(band + 1) * self.rows])
            for key in self.buckets.get((band, chunk), ()):
                found[key] = None
        return list(found)


def reciprocal_rank_fusion(*ranked_lists: Sequence[str], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, 1):
            scores[item] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def maximal_marginal_relevance(
    candidates: Sequence[str],
    relevance: Mapping[str, float],
    similarity: Callable[[str, str], float],
    *,
    k: int = 5,
    lambda_mult: float = 0.7,
) -> list[str]:
    remaining = list(candidates)
    selected: list[str] = []
    while remaining and len(selected) < k:
        best = None
        best_score = None
        for cand in remaining:
            rel = float(relevance.get(cand, 0.0))
            sim = max((similarity(cand, s) for s in selected), default=0.0)
            score = lambda_mult * rel - (1.0 - lambda_mult) * sim
            if best_score is None or score > best_score or (score == best_score and cand < str(best)):
                best = cand
                best_score = score
        selected.append(str(best))
        remaining.remove(best)
    return selected


def bfs(adj: Mapping[str, Sequence[str]], start: str) -> list[str]:
    seen = {start}
    order = [start]
    q = deque([start])
    while q:
        node = q.popleft()
        for nxt in adj.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                order.append(nxt)
                q.append(nxt)
    return order


def dfs(adj: Mapping[str, Sequence[str]], start: str) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []

    def walk(node: str) -> None:
        if node in seen:
            return
        seen.add(node)
        order.append(node)
        for nxt in adj.get(node, ()):
            walk(nxt)

    walk(start)
    return order


def bidirectional_search(adj: Mapping[str, Sequence[str]], start: str, goal: str) -> list[str] | None:
    if start == goal:
        return [start]
    fwd_parent = {start: None}
    back_parent = {goal: None}
    fq, bq = deque([start]), deque([goal])
    meet = None
    while fq and bq:
        meet = _expand_frontier(adj, fq, fwd_parent, back_parent)
        if meet is not None:
            break
        meet = _expand_frontier(adj, bq, back_parent, fwd_parent)
        if meet is not None:
            break
    if meet is None:
        return None
    left: list[str] = []
    cur: str | None = meet
    while cur is not None:
        left.append(cur)
        cur = fwd_parent[cur]
    left.reverse()
    right: list[str] = []
    cur = back_parent[meet]
    while cur is not None:
        right.append(cur)
        cur = back_parent[cur]
    return left + right


def _expand_frontier(
    adj: Mapping[str, Sequence[str]],
    q: deque[str],
    parent: dict[str, str | None],
    other: dict[str, str | None],
) -> str | None:
    if not q:
        return None
    node = q.popleft()
    for nxt in adj.get(node, ()):
        if nxt in parent:
            continue
        parent[nxt] = node
        if nxt in other:
            return nxt
        q.append(nxt)
    return None


def weighted_set_cover(
    universe: Iterable[Hashable],
    sets: Mapping[str, Iterable[Hashable]],
    weights: Mapping[str, float] | None = None,
) -> tuple[list[str], set[Hashable]]:
    uncovered = set(universe)
    chosen: list[str] = []
    w = dict(weights or {})
    remaining = {sid: set(cover) for sid, cover in sets.items()}
    while uncovered:
        best_id = None
        best_score = -1.0
        for sid, cover in remaining.items():
            if sid in chosen:
                continue
            gain = len(cover & uncovered)
            if gain <= 0:
                continue
            score = gain / max(float(w.get(sid, 1.0)), 1e-12)
            if score > best_score or (score == best_score and (best_id is None or sid < best_id)):
                best_id = sid
                best_score = score
        if best_id is None:
            break
        chosen.append(best_id)
        uncovered -= remaining[best_id]
    return chosen, uncovered


def submodular_lazy_greedy(
    items: Sequence[str],
    marginal_gain: Callable[[str, frozenset[str]], float],
    cost: Callable[[str], float],
    *,
    budget: float | None = None,
    k: int | None = None,
) -> list[str]:
    import heapq

    selected: list[str] = []
    selected_set: set[str] = set()
    spent = 0.0
    stamp = {item: 0 for item in items}
    heap: list[tuple[float, str, int]] = []
    empty = frozenset()
    for item in items:
        gain = marginal_gain(item, empty)
        u = gain / max(cost(item), 1e-12)
        heapq.heappush(heap, (-u, item, 0))
    while heap:
        if k is not None and len(selected) >= k:
            break
        _neg, item, seen = heapq.heappop(heap)
        if item in selected_set or seen != stamp[item]:
            continue
        current_gain = marginal_gain(item, frozenset(selected_set))
        current_u = current_gain / max(cost(item), 1e-12)
        stamp[item] += 1
        if heap and current_u + 1e-15 < -heap[0][0]:
            heapq.heappush(heap, (-current_u, item, stamp[item]))
            continue
        item_cost = cost(item)
        if budget is not None and spent + item_cost > budget:
            continue
        if current_gain <= 0:
            continue
        selected.append(item)
        selected_set.add(item)
        spent += item_cost
    return selected


def brute_force_cosine(
    query: Sequence[float],
    corpus: Mapping[str, Sequence[float]],
    *,
    k: int = 5,
) -> list[tuple[str, float]]:
    def _norm(vec: Sequence[float]) -> float:
        return math.sqrt(sum(x * x for x in vec)) or 1e-12

    qn = _norm(query)
    scored: list[tuple[str, float]] = []
    for key, vec in corpus.items():
        n = min(len(query), len(vec))
        dot = sum(float(query[i]) * float(vec[i]) for i in range(n))
        scored.append((key, dot / (qn * _norm(vec))))
    scored.sort(key=lambda kv: (-kv[1], kv[0]))
    return scored[:k]


def not_active_challenger(*_args: Any, **_kwargs: Any) -> None:
    from dcm.algorithms.contracts import AlgorithmNotProductionActive

    raise AlgorithmNotProductionActive("PERMANENT_CHALLENGER_NOT_PRODUCTION_ACTIVE")
