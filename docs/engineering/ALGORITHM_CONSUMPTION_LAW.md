# Permanent Algorithm Consumption Law

**Status:** MANDATORY / CI-GATED / INHERITED  
**Constitution:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`  
**Registry:** `configs/algorithm_registry.json`  
**Surfaces:** `AGENTS.md`, `docs/architecture/CONSTITUTION_INHERITANCE.md`, governance tests

This is the permanent order DCM SHALL use for search, index, ML, grouping, and
appending hot paths. Agents and future prompts may not invent silent one-off
algorithms when a registered constitution path exists.

## Permanent consumption order

1. **Exact-first indexes (BoardStore / BoardIndexes)** — answer identity and
   board lookups through `BoardStore` / `BoardIndexes` (ALG-INDEX-001 family).
   Do not add ad hoc O(N) scans over offer lists when an exact/composite index
   can answer the request.
2. **Research: cached facts → CELF / set-cover AcquisitionAction** — retrieve
   existing MaterialFacts / cache cascade first; schedule remaining coverage with
   `ALG-SCHED-001` (CELF) / weighted set-cover AcquisitionActions. Never plan
   one independent search per prop when shared Event/Team/Subject evidence can
   fan out.
3. **True descendant DAG invalidation** — invalidate only ID-scoped Dag
   descendants (reverse adjacency). Do not blanket-rebuild unrelated subgraphs
   after a material delta.
4. **Two-representation rule** — keep audit objects at I/O and freeze boundaries;
   use NumPy / SoA compact matrices for numerical compute inside the engine.
5. **EventWorld backends** — NumPy backend is the default with a mandatory
   portable Python `reference` fallback and bitwise `rngVersion` parity. C ABI
   / native extensions only after a measured win on representative real-evidence
   SLOs (never speculative).
6. **ML / grouping / appending** — go through registered Algorithmic Constitution
   IDs (`configs/algorithm_registry.json` + `AlgorithmSelectionEngine`). Silent
   one-off algorithms on hot paths are prohibited.

## Enforcement

- CI: `tests/governance/test_algorithm_constitution.py` (consumption-law surface),
  `scripts/validate_dcm_policy.py`, registry export check, retirement-requires-ADR.
- Runtime: HAR `AlgorithmExecutionPlan` before research; telemetry must name
  producer/consumer algorithm IDs for activated constitution consumers.
- Retirement remains prohibited without ADR + benchmarks.

## Explicit non-claims

This law does **not** certify host performance, predictive superiority, LR
promotion, or a live CFB production card. Learning revision remains `LR000000`;
predictive claim remains `NONE` until evidence earns otherwise.
