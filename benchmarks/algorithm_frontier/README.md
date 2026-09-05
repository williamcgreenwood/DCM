# Algorithm frontier benchmarks

Engineering smoke only. These numbers are not host-performance certification and
are not predictive validation.

Run:

```bash
python benchmarks/algorithm_frontier/core_smoke.py
```

R0 measures stdlib CORE primitives (hash lookup, BM25, grouping, Bloom, Timsort,
heap Top-K, set cover, CELF, Merkle, LRU). Optional packages are not required.
