# Engineering pass — True dependency invalidation (Phase 6)

- **Timestamp:** `2026-09-06T04:26:50Z`
- **Agent:** grok
- **Branch:** `task/true-descendant-dag-20260906`
- **Base main:** `1fe6d21721cb` (PR #37 Research OS / CELF)

## Intent

Upgrade the content-addressed runtime `Dag` to **true changed-node → descendants**
invalidation used by the live research/import/model path. Prefer canonical run DAG
artifacts; keep type-scoped `invalidate_types` / `invalidate_for_delta` as explicit
legacy helpers only.

## Implementation

1. **`src/dcm/runtime/dag.py`**
   - `invalidate(changed_node_ids)` — deterministic BFS over reverse adjacency only
   - Permanent indexes via `children_map` / `reverse_adjacency_indexes` (byType,
     byIdentity, typeEdges) persisted in snapshots
   - Conceptual lineage installer `ensure_offer_lineage`:
     claim → FACT → FEATURE → PARAMETER → EVENT_WORLDS → GRADE → RANK
   - Portfolio link + explicit `mark_freeze` latch (`DagFrozenError` on later mutate)
   - `invalidate_line_descendants` is now **ID-scoped** from MARKET_LINE/LINE_SURFACE
     seeds (research-stable protected; unrelated GRADE/PARAMETER survive)
   - Role / weather helpers: `invalidate_role_lineage`, `invalidate_environment_lineage`
   - `invalidate_types` / `invalidate_for_delta` retained as coarse legacy helpers

2. **CFB import path**
   - `observation_execute` calls `dag.invalidate(...)` (ID-scoped)
   - `_ensure_offer_lineage` uses full conceptual chain
   - `_persist_run_dag` writes `runtime_dag.json` + `source_aware_import_dag.json`
   - Load order prefers canonical artifacts (`CANONICAL_DAG_ARTIFACTS`)

3. **Tests**
   - `tests/test_dag_true_invalidation.py` — reverse adjacency, scoped invalidation,
     research-stable line change, role/weather scoping, freeze latch, legacy delta
   - Strengthened `tests/test_cfb_source_aware_import.py` integration assertions

## Type-scoped vs ID-scoped

| Path | Before | After |
|------|--------|-------|
| observation / source-aware import | ID-scoped (`invalidate_descendants`) | ID-scoped (`invalidate`) + fuller lineage |
| `invalidate_line_descendants` | type wipe of LINE_DEPENDENT | ID-scoped from line seeds |
| `invalidate_for_delta` / `invalidate_types` | type wipe | unchanged legacy helper |

## Not claimed / remaining gaps (Phase 7+)

- Compact array / BoardStore two-representation architecture (Phase 7)
- Full EventWorld C++ / shared-world resimulation still deferred
- Live current-HAR operational CFB card remains EXTERNAL
- No LR promotion / predictive claim

## Validation

```
PYTHONPATH=src pytest -q tests/test_dag_true_invalidation.py \
  tests/test_runtime_lineage.py tests/test_cfb_source_aware_import.py \
  tests/test_e2e_runner.py::test_d_line_change_invalidates_descendants_not_research
```
