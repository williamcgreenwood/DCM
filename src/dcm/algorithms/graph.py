"""Graph and hypergraph helpers bound to constitution algorithm IDs."""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from dcm.algorithms.grouping import tarjan_scc
from dcm.algorithms.indexing import CSRGraph, HypergraphIncidence
from dcm.algorithms.searching import bfs, bidirectional_search, dfs
from dcm.algorithms.sorting import topological_kahn


def build_csr(edges: Iterable[tuple[str, str]]) -> CSRGraph:
    return CSRGraph(edges)


def cycles(adj: Mapping[str, Sequence[str]]) -> list[list[str]]:
    return [comp for comp in tarjan_scc(adj) if len(comp) > 1 or comp[0] in adj.get(comp[0], ())]


def dag_or_reject(nodes: Sequence[str], edges: Sequence[tuple[str, str]]) -> list[str]:
    return topological_kahn(nodes, edges)


def traverse(adj: Mapping[str, Sequence[str]], start: str, *, method: str = "bfs") -> list[str]:
    if method == "dfs":
        return dfs(adj, start)
    return bfs(adj, start)


def shortest_undirected(adj: Mapping[str, Sequence[str]], start: str, goal: str) -> list[str] | None:
    return bidirectional_search(adj, start, goal)


def hypergraph_from_bundles(bundles: Mapping[str, Sequence[str]]) -> HypergraphIncidence:
    hg = HypergraphIncidence()
    for edge_id, members in bundles.items():
        hg.add_edge(edge_id, members)
    return hg
