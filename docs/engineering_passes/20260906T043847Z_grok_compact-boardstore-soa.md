# Engineering pass — Two-representation BoardStore + compact arrays (Phase 7–8)

- **Timestamp:** `2026-09-06T04:38:47Z`
- **Agent:** grok
- **Branch:** `task/compact-boardstore-soa-20260906`
- **Base main:** `8fdd520c388bebcb6090fe1742a6d1d52d18e254` (PR #38 True DAG)

## Intent

Introduce the permanent two-representation data architecture:

- **Audit:** dataclasses / typed Python / versioned JSON / stable string IDs / hashes
- **Compute:** int32 IDs, NumPy SoA columns, bitmaps, contiguous buffers

Preserve BoardIndexes / CFB launch API boundaries (behavior-preserving).

## Implementation

1. **`src/dcm/board_store.py`** — canonical single-copy `BoardStore`
   - `row_id` int32; one audit dict per offer
   - Indexes: event/subject/affiliation/market/league → `np.int32` posting lists + eligibility bitmaps
   - SQLite: keys + `row_id` only (no `json.dumps(row)` payload duplication)
   - Mapping back to Offer/Event/Subject/Market string IDs
   - Exact-first cascade still owned by `BoardIndexes` (Algorithmic Constitution)

2. **`src/dcm/compact.py`** — compact compute helpers
   - `IdMap` string↔int32
   - `CompactNumericBoard` SoA: line/mean/variance/reliability/fragility/ood
   - `FeatureMatrix` / `ParameterMatrix` + pack/unpack to audit dicts
   - Round-trip ID map checker; SoA `line_sum` microbench path

3. **`src/dcm/research/indexes.py`**
   - `BoardIndexes` backed by `BoardStore` (optional injected `store=`)
   - Legacy `offer_by_id` / `by_event` / … string views preserved for CFB launch
   - Shared single-copy row dicts

4. **Deps:** `numpy>=1.26` added to `pyproject.toml` (was empty)

5. **Tests:** `tests/test_board_store_compact.py`

## Compact vs still dict-heavy (honest)

| Area | Compact now | Still dict-heavy |
|------|-------------|------------------|
| Board row storage | single-copy + SoA indexes | public APIs return dicts (intentional) |
| Hot numeric board fields | NumPy columns when present | grade/parameter producers still emit dicts |
| FeatureStore records | packable via `feature_matrix_from_records` | live FeatureStore path still jsonl/dicts |
| Parameter snapshots | packable via `parameter_matrix_from_snapshots` | `build_parameter_snapshot` still dict |
| EvidenceIndexes SQLite | — | still stores full claim JSON payloads |
| EventWorld / C++ | — | deferred (Phase 9+) |

## Not claimed / gaps before Phase 9 profiling

- No host-performance certification; microbench is smoke only
- Feature/Parameter matrices not yet wired as the primary CFB launch path
- EvidenceIndexes payload dedupe not in this pass
- No RNG semantic changes; no C++; no HAR commit
- Live current-HAR operational CFB card remains EXTERNAL
- Phase 9: profile representative boards, measure RSS/CPU, decide further SoA adoption

## Validation

```
PYTHONPATH=src pytest -q tests/test_board_store_compact.py \
  tests/test_cfb_semantic_completion.py tests/test_cfb_freeze_gate.py \
  tests/test_cfb_reference_implementation.py tests/test_cfb_source_aware_import.py
python scripts/build_code_inventory.py --check
```
