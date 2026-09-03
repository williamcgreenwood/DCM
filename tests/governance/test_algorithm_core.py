"""Behavioral CORE primitive tests. Names must stay importable."""
from __future__ import annotations

from dcm.algorithms.cache import LRUCache
from dcm.algorithms.graph import cycles
from dcm.algorithms.grouping import UnionFind, composite_group, tarjan_scc
from dcm.algorithms.indexing import BloomFilter, merkle_root, open_memory_index
from dcm.algorithms.ml_families import empirical_bayes_shrink, ewma, isotonic_regression
from dcm.algorithms.registry import load_algorithm_registry, resolve_implementation
from dcm.algorithms.scheduling import LazyGreedyScheduler, greedy_value_density_pack
from dcm.algorithms.searching import (
    AhoCorasick,
    InvertedIndex,
    bm25,
    exact_hash_lookup,
    minhash_signature,
    simhash,
    submodular_lazy_greedy,
    weighted_set_cover,
)
from dcm.algorithms.sorting import heap_topk, timsort, topological_kahn


def test_algorithm_core_symbols_resolve():
    for rec in load_algorithm_registry():
        if rec.lifecycle == "REQUIRED_CORE":
            assert resolve_implementation(rec) is not None


def test_exact_hash_and_grouping():
    assert exact_hash_lookup({"a": 1}, "a") == 1
    rows = [{"e": "x", "p": "a"}, {"e": "x", "p": "b"}, {"e": "y", "p": "a"}]
    groups = composite_group(rows, ("e",))
    assert len(groups[("x",)]) == 2
    uf = UnionFind()
    uf.union("a", "b")
    uf.union("b", "c")
    assert uf.find("a") == uf.find("c")


def test_bm25_aho_and_duplicates():
    scores = bm25(["red", "ball"], [["red", "ball"], ["blue", "sky"], ["red", "red", "ball"]])
    assert scores[2] > scores[1]
    idx = InvertedIndex()
    idx.add(0, ["alpha", "beta"])
    idx.add(1, ["beta", "gamma"])
    assert idx.boolean_and(["beta"]) == [0, 1]
    ac = AhoCorasick()
    ac.add("alpha")
    ac.add("beta")
    ac.build()
    hits = {pat for _, pat in ac.find("xxalphayybeta")}
    assert hits == {"alpha", "beta"}
    sig_a = minhash_signature("the cat sat on the mat".split())
    sig_b = minhash_signature("the cat sat on the mat".split())
    assert sig_a == sig_b
    assert simhash("aaaa bbbb".split()) != 0


def test_set_cover_and_lazy_greedy_agree_on_fixture():
    universe = {1, 2, 3, 4}
    sets = {"A": {1, 2}, "B": {2, 3}, "C": {4}, "D": {1, 2, 3, 4}}
    chosen, leftover = weighted_set_cover(universe, sets, {"A": 1, "B": 1, "C": 1, "D": 5})
    assert not leftover
    assert "D" not in chosen or chosen == ["D"]
    items = ["A", "B", "C"]

    def gain(item: str, selected: frozenset[str]) -> float:
        have: set[int] = set()
        for s in selected:
            have |= sets[s]
        return float(len(sets[item] - have))

    selected = submodular_lazy_greedy(items, gain, lambda _i: 1.0)
    sched = LazyGreedyScheduler(gain, lambda _i: 1.0)
    assert sched.run(items) == selected
    packed = greedy_value_density_pack(["A", "B", "C"], {"A": 2, "B": 2, "C": 1}, {"A": 1, "B": 1, "C": 1}, capacity=2)
    assert packed[0] in {"A", "B"}


def test_sort_index_cache_ml():
    assert timsort([3, 1, 2]) == [1, 2, 3]
    assert heap_topk([1, 9, 3, 7, 5], 3) == [9, 7, 5]
    assert topological_kahn(["a", "b", "c"], [("a", "b"), ("b", "c")]) == ["a", "b", "c"]
    sccs = tarjan_scc({"a": ["b"], "b": ["a"], "c": []})
    assert any(set(c) == {"a", "b"} for c in sccs)
    assert cycles({"a": ["a"]})
    bf = BloomFilter()
    bf.add("k")
    assert "k" in bf
    assert merkle_root(["a", "b"])
    conn = open_memory_index()
    conn.execute("INSERT INTO records VALUES (?,?,?,?,?,?)", ("e", "c", "v", "o", "cut", "{}"))
    assert conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 1
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert "a" not in cache
    assert empirical_bayes_shrink(10, 2, 4, 2) == 7.0
    assert ewma([1, 1, 1]) == [1, 1, 1]
    iso = isotonic_regression([1, 2, 3], [3, 1, 2])
    assert iso == sorted(iso)
