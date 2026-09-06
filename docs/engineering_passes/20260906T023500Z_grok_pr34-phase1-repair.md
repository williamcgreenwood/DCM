# Engineering Pass: PR #34 phase-1 source-aware-import repair

- **Pass ID:** `20260906T023500Z_grok_pr34-phase1-repair`
- **Starting branch/SHA:** `task/cfb-grouped-research-20260905` @ `4d16b442` (PR #34 tip)
- **Base merged:** PR #33 @ `24007ef5bd6af38d44f6f004eb19300bb0fc07ab`
- **Ending branch:** `task/cfb-grouped-research-20260905`
- **Objective:** repair confirmed defects in the source-aware observation execute
  loop before merge — indexes, ResearchStore sport/entityKind, scoped DAG
  descendant invalidation, and a consumer path beyond ParameterSnapshot hash.

## Implementation

- `observation_execute._affected_rows` and offer fanout resolve via
  `BoardIndexes` (`by_event` / `by_affiliation` / `by_subject` / `exact_offer`
  with `downstream_used=True`). COUNTERPARTY uses a one-shot opponent map built
  once per execute (BoardIndexes has no `by_counterparty`).
- `ResearchStore.put_claim` sport derived from board / host_state / row
  league→family (default `CFB`); `entityKind` is `semantic_scope` only.
  Regression asserts `pointer["sport"]` is never EVENT/SUBJECT/AFFILIATION.
- `Dag.children_map` + `Dag.invalidate_descendants(node_ids)` reverse-adjacency
  helper; `Dag.from_snapshot` to load existing run DAG artifacts when present.
  Execute builds claim→PARAMETER→EVENT_WORLDS→GRADE for touched offers and
  invalidates only those PARAMETER lineages (unrelated offer nodes spared).
- Consumer ablation: `resolve_material_facts` → `facts_to_features` contentHash
  change, plus snapshot-derived `probability_bundle` + `grade` helper hashes.
  Persisted under `parameters/source_aware_import_consumer.json`.
- Regenerated `docs/generated/CODE_INVENTORY.{json,md}`.

## Validation

- `pytest -q tests/test_cfb_source_aware_import.py tests/test_research_store.py tests/test_cfb_research_os.py tests/test_host_native.py` — **31 passed**.
- Additional smoke: `test_cfb_semantic_completion`, lineage/dag invalidate tests green.

## Honest state and remaining gaps

- **Proven:** ParameterSnapshot hash change; MaterialFact/feature consumer hash
  change; probability_bundle + grade helper change; scoped descendant
  invalidation for touched PARAMETER IDs.
- **Not proven / deferred:** full EventWorld set resimulation and runner shared-
  world probability path; a general-purpose evidence graph engine beyond the
  bounded claim→parameter→worlds→grade links for touched offers.
- **Next:** merge PR #34 after green CI, then live HAR evidence-import.
- Learning remains `LR000000`; predictive claim `NONE`; no production-root
  certification. No `*.har` files read or committed.
