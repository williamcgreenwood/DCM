#!/usr/bin/env python3
"""Stdlib CORE algorithm smoke. Not host-performance certification."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "artifacts" / "dcm_v6_workstream_ab"))

from dcm.algorithms.cache import LRUCache
from dcm.algorithms.grouping import UnionFind, composite_group
from dcm.algorithms.indexing import BloomFilter, merkle_root
from dcm.algorithms.searching import bm25, exact_hash_lookup, submodular_lazy_greedy, weighted_set_cover
from dcm.algorithms.sorting import heap_topk, timsort


def _timed(name: str, fn):
    t0 = time.perf_counter()
    result = fn()
    ms = (time.perf_counter() - t0) * 1000.0
    return {"name": name, "ms": round(ms, 4), "ok": result is not None and result is not False}


def main() -> int:
    table = {f"k{i}": i for i in range(10_000)}
    docs = [("a b c " * 20).split() for _ in range(200)]
    rows = [{"event": i % 50, "player": i % 17, "v": i} for i in range(2000)]
    universe = list(range(40))
    bundles = {f"b{i}": {(i + j) % 40 for j in range(6)} for i in range(30)}
    report = {
        "schema": "pillars_dcm.algorithm_frontier_smoke.v1",
        "hostPerformanceCertified": False,
        "results": [
            _timed("exact_hash_lookup", lambda: exact_hash_lookup(table, "k42")),
            _timed("bm25", lambda: bm25(["a", "c"], docs)),
            _timed("composite_group", lambda: composite_group(rows, ("event", "player"))),
            _timed("union_find", lambda: _uf()),
            _timed("timsort", lambda: timsort(range(5000, 0, -1))),
            _timed("heap_topk", lambda: heap_topk(list(range(5000)), 25)),
            _timed("bloom", lambda: _bloom()),
            _timed("set_cover", lambda: weighted_set_cover(universe, bundles)),
            _timed("celf", lambda: submodular_lazy_greedy(
                [f"b{i}" for i in range(20)],
                lambda item, chosen: float(len(bundles[item] - {int(x[1:]) for x in chosen if x[1:].isdigit()})) if False else float(len(bundles[item])),
                lambda _item: 1.0,
                k=5,
            )),
            _timed("merkle", lambda: merkle_root([f"h{i}" for i in range(64)])),
            _timed("lru", lambda: _lru()),
        ],
    }
    assert report["hostPerformanceCertified"] is False
    assert all(r["ok"] for r in report["results"])
    out = Path("/tmp/dcm-algorithm-frontier-smoke.json")
    try:
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass
    print(json.dumps({"ok": True, "n": len(report["results"]), "hostPerformanceCertified": False}))
    return 0


def _uf():
    uf = UnionFind()
    for i in range(1000):
        uf.union(i, i // 2)
    return len(uf.components())


def _bloom():
    bf = BloomFilter()
    for i in range(500):
        bf.add(f"k{i}")
    return "k42" in bf and "missing" not in bf


def _lru():
    cache = LRUCache(64)
    for i in range(200):
        cache.put(i, i)
    return cache.get(199) == 199


if __name__ == "__main__":
    raise SystemExit(main())
