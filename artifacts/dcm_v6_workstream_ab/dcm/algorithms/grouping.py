"""Deterministic grouping: hash groups, Union-Find, SCC, hypergraphs."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Hashable, Iterable, Mapping, Sequence

from dcm.algorithms.searching import weighted_set_cover
from dcm.algorithms.sorting import topological_kahn


def composite_group(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> dict[tuple[Any, ...], list[Mapping[str, Any]]]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(k) for k in keys)].append(row)
    return dict(groups)


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[Hashable, Hashable] = {}
        self.rank: dict[Hashable, int] = {}

    def find(self, x: Hashable) -> Hashable:
        self.parent.setdefault(x, x)
        self.rank.setdefault(x, 0)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: Hashable, b: Hashable) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True

    def components(self) -> dict[Hashable, list[Hashable]]:
        groups: dict[Hashable, list[Hashable]] = defaultdict(list)
        for node in list(self.parent):
            groups[self.find(node)].append(node)
        return {k: sorted(v, key=str) for k, v in groups.items()}


def connected_components(edges: Sequence[tuple[Hashable, Hashable]], nodes: Iterable[Hashable] | None = None) -> list[list[Hashable]]:
    uf = UnionFind()
    for n in nodes or ():
        uf.find(n)
    for a, b in edges:
        uf.union(a, b)
        uf.find(a)
        uf.find(b)
    return [members for _, members in sorted(uf.components().items(), key=lambda kv: str(kv[0]))]


def tarjan_scc(adj: Mapping[str, Sequence[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    onstack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    result: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        low[v] = index
        index += 1
        stack.append(v)
        onstack.add(v)
        for w in adj.get(v, ()):
            if w not in indices:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], indices[w])
        if low[v] == indices[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                onstack.remove(w)
                comp.append(w)
                if w == v:
                    break
            result.append(list(reversed(comp)))

    for node in sorted(adj):
        if node not in indices:
            strongconnect(node)
        for nxt in adj.get(node, ()):
            if nxt not in indices:
                strongconnect(nxt)
    return result


def kahn_layers(nodes: Sequence[str], edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    incoming: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        adj[a].append(b)
        incoming[b] += 1
    remaining = set(nodes)
    layers: list[list[str]] = []
    while remaining:
        ready = sorted(n for n in remaining if incoming[n] == 0)
        if not ready:
            raise ValueError("KAHN_CYCLE")
        layers.append(ready)
        for n in ready:
            remaining.remove(n)
            for nxt in adj[n]:
                incoming[nxt] -= 1
    return layers


def hypergraph_group(edge_members: Mapping[str, Sequence[str]]) -> dict[str, tuple[str, ...]]:
    return {eid: tuple(dict.fromkeys(members)) for eid, members in edge_members.items()}


def constraint_group(
    items: Sequence[str],
    *,
    must_link: Sequence[tuple[str, str]] = (),
    cannot_link: Sequence[tuple[str, str]] = (),
) -> list[list[str]]:
    uf = UnionFind()
    for item in items:
        uf.find(item)
    forbidden = {(min(a, b), max(a, b)) for a, b in cannot_link}
    for a, b in must_link:
        if (min(a, b), max(a, b)) in forbidden:
            raise ValueError(f"CONSTRAINT_CONFLICT:{a}:{b}")
        uf.union(a, b)
    for a, b in cannot_link:
        if uf.find(a) == uf.find(b):
            raise ValueError(f"CONSTRAINT_CONFLICT:{a}:{b}")
    return [members for _, members in sorted(uf.components().items(), key=lambda kv: str(kv[0]))]


def hierarchical_agglomerative(
    labels: Sequence[str],
    distance: Callable[[str, str], float],
    *,
    threshold: float,
) -> list[list[str]]:
    clusters = [[lab] for lab in labels]
    while len(clusters) > 1:
        best_i = best_j = -1
        best_d = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = min(distance(a, b) for a in clusters[i] for b in clusters[j])
                if best_d is None or d < best_d:
                    best_d = d
                    best_i, best_j = i, j
        if best_d is None or best_d > threshold:
            break
        merged = clusters[best_i] + clusters[best_j]
        clusters = [c for k, c in enumerate(clusters) if k not in {best_i, best_j}]
        clusters.append(merged)
    return [sorted(c) for c in clusters]


def set_cover_groups(
    universe: Iterable[Hashable],
    bundles: Mapping[str, Iterable[Hashable]],
    weights: Mapping[str, float] | None = None,
) -> list[str]:
    chosen, _uncovered = weighted_set_cover(universe, bundles, weights)
    return chosen


def topological_group_order(nodes: Sequence[str], edges: Sequence[tuple[str, str]]) -> list[str]:
    return topological_kahn(nodes, edges)


def louvain_fallback(edges: Sequence[tuple[Hashable, Hashable]], nodes: Iterable[Hashable] | None = None) -> list[list[Hashable]]:
    """Deterministic connected-component fallback when Leiden/Louvain packages are absent."""
    return connected_components(edges, nodes)


def dbscan_fallback(labels: Sequence[str], distance: Callable[[str, str], float], *, eps: float) -> list[list[str]]:
    return hierarchical_agglomerative(labels, distance, threshold=eps)


def gaussian_mixture_1d(values: Sequence[float], *, k: int = 2, steps: int = 25) -> list[dict[str, float]]:
    """Tiny 1-D GMM for soft archetype membership (stdlib)."""
    import math
    import statistics

    xs = [float(v) for v in values]
    if not xs:
        return []
    k = max(1, min(int(k), len(xs)))
    ordered = sorted(xs)
    means = [ordered[min(len(ordered) - 1, int(round((i + 0.5) * (len(ordered) - 1) / k)))] for i in range(k)]
    var = max(statistics.pvariance(xs) if len(xs) > 1 else 1.0, 1e-6)
    weights = [1.0 / k] * k
    for _ in range(steps):
        resp = []
        for x in xs:
            dens = []
            for m, w in zip(means, weights):
                dens.append(w * math.exp(-0.5 * (x - m) ** 2 / var) / math.sqrt(2 * math.pi * var))
            s = sum(dens) or 1e-12
            resp.append([d / s for d in dens])
        for j in range(k):
            nj = sum(r[j] for r in resp) or 1e-12
            weights[j] = nj / len(xs)
            means[j] = sum(r[j] * x for r, x in zip(resp, xs)) / nj
        var = 0.0
        for r, x in zip(resp, xs):
            for j in range(k):
                var += r[j] * (x - means[j]) ** 2
        var = max(var / len(xs), 1e-6)
    return [{"mean": m, "weight": w, "variance": var} for m, w in zip(means, weights)]
