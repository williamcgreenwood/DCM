# Engineering Pass — CFB guarded launch today (Research OS slice)

- **Timestamp:** 2026-09-03T21:32:00Z
- **START_SHA:** `59ea12487ad2e747a15427ba6bb9babd1b9f5907` (integration HEAD after PR #18 merge)
- **BRANCH:** `grok/cfb-guarded-launch-today-20260903`
- **TARGET:** `integration/v6-ml-architecture-20260830` only
- **PRESERVED:** `grok/r1-research-os-20260903` was absent locally and on GitHub (404). Nothing to checkpoint.
- **CONSTITUTION:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`
- **ALGORITHM_REGISTRY_SHA256:** `9327ec9884e7a55a7854f27d85fd062d6b959794197670db14b7932428e885ca`
- **CODE_INVENTORY:** 253 modules / 1,748 symbols / 0 parse errors
- **INVENTORY_HASH:** `612a8cd82cfb25a767ad4e3bae86d302bfb713905937619376fc08669c0eae9e`
- **FULL_PYTEST:** 377 passed / 0 failed
- **LEARNING_REVISION:** `LR000000`
- **PREDICTIVE_CLAIM:** `NONE`
- **PRODUCTION_ROOT_CERTIFIED:** false

## Objective

Make today's CFB HAR path executable as a guarded vertical slice:

HAR → account (Goblins after accounting) → identity → supported MarketDefinitions → AlgorithmExecutionPlan → BoardGraph / MarketDemandGraph / RequirementGraph → reusable-evidence lookup → AcquisitionActions → host batches → evidence → ParameterSnapshots → EventWorlds → P(Higher)/P(Lower) + separate uncertainty fields → grade → Top100 → frontier → Top25 → 0–6 PLAYABLES → freeze.

This is **not** a claim that full R1 or v3 is complete.

## What this pass implemented

- `dcm.research.indexes.BoardIndexes` / `EvidenceIndexes`: hash, composite, SQLite, Bloom, Aho-Corasick, inverted, content-hash, bitsets. Cheapest exact first.
- `dcm.research.os_graphs`: BoardGraph, MarketDemandGraph, RequirementGraph using Union-Find, connected components, Tarjan SCC, Kahn topo, CSR, hypergraph incidence. Emitted **before** `collect()`.
- `dcm.research.acquisition`: AcquisitionAction fanout + live `LazyGreedyScheduler` (ALG-SCHED-001) + weighted set-cover + value-density / FFD packing. SPORT/COMPETITION mass no longer starves EVENT/TEAM batches.
- `dcm.algorithms.telemetry.AlgorithmTelemetry`: algorithm_id → applicability → producer → consumer → fallback → execution count → artifact.
- `dcm.cfb`: HAR accounting, Top100/Top25/Playables reports with required columns, `dcm-host cfb-launch`.
- Runner freeze carries `cfbTop100Count` / `cfbTop25Count` / `cfbPlayablesCount`.
- Host `next-research` passes board rows so CELF is the live selector, not telemetry-only.

No new CFB MarketDefinitions. Guarded set remains `pass_yds, pass_att, pass_cmp, rush_yds, rush_att, rec_yds, receptions, pass_rush_yds, rush_rec_yds`.

## Measured results (do not generalize)

### Fixture HAR `cfb_guarded_launch_har.json` + acceptance web-claim bundle

- raw CFB 8 / Goblin 0 / supported 8 / unsupported 0
- ParameterSnapshots 8 / EventWorlds independentEventCount 1 / conservation held
- modeled 8, all `MODELED_DIAGNOSTIC`
- Top100 8 (LEAN + 7 PASS) — **not recommendations**
- Top25 8
- true Playables 0 (never forced)
- AcquisitionActions after evidence reuse: 3 remaining (ENVIRONMENT/COMPETITION/SPORT); 21/24 requirements already complete via reusable lookup
- average/max fanout on remaining actions: 8 / 8
- freeze `RESEARCHED_MODELED_TOP25`, LR000000, predictive NONE
- frozenForecastHash `ea38641905d7b60579429a8ca2c3e7c21cac5fbddae2b05c46410d9451153d0a`
- FixtureProvider-only path cannot create production Playables (tested)

### Compact live HAR `prizepicks_compact.har` (not today's board)

- raw CFB 20 / Goblin 6 / non-Goblin 14 / supported 9 / unsupported 5 (`pass_td`, `player_td`)
- meaningfulTop100 false
- 38 AcquisitionActions, live pack selected 24

### Aug 29 sanitized HAR `prizepicks_20260829.sanitized.har` (historical, not 2026-09-03)

- 11113 rows / raw CFB 1568 / Goblin 229 / non-Goblin 1339 / supported 308 / unsupported 1031
- meaningfulTop100 true on supported count → **no new markets activated**
- offeredSideUnknown 1293; liveOrStarted 1
- 994 AcquisitionActions; CELF candidates 25; packed first batch EVENT + ENVIRONMENT + AFFILIATION (event/team before player)
- unique-offer budget used 435
- BoardGraph 12970 nodes; RequirementGraph 994 nodes
- No current 2026-09-03 CFB HAR was present in `/workspace` or this repo

Unmapped raw labels (`rush_yards`, `pass_attempts`, `pass_completions`, …) were **not** turned into new MarketDefinitions today.

## Tests added/changed

- `artifacts/dcm_v6_workstream_ab/tests/test_cfb_research_os.py`
- host batching assertion now `celf_acquisition_action_then_event_pack`
- existing `test_cfb_guarded_launch.py` preserved and still passing

Validation:

```
PYTHONPATH=artifacts/dcm_v6_workstream_ab:. python3 -m pytest -q
# 377 passed
python3 scripts/export_algorithm_registry.py --check
python3 benchmarks/algorithm_frontier/core_smoke.py
python3 scripts/build_code_inventory.py --check
```

## Workstream scores

- P1: 8 → 9. CFB BoardGraph/RequirementGraph/live AcquisitionAction packing now run on the canonical runner before research. Mixed-sport universal R1 and a current live CFB HAR forecast remain open.
- P16: 8 → 9. Live CELF selector + algorithm telemetry on the CFB path. Challenger ML families still not production.
- P7: 7 unchanged. `cfb-launch` added; fresh-wheel current-HAR acceptance is still open.
- LR / predictive / production-root / host-performance: unchanged.

## Deferred until after today

- Full mixed-sport R1 certification
- Drive-first indexed retrieval
- UFC / tennis / soccer / remaining SportPlugin 24/24
- Aesthetic UI
- Frontier ML challengers (TabPFN, GNN, diffusion, …)
- Ingest aliases for unmapped football labels
- Prospective settlement / LR promotion
- Production-root certification

## Next exact command

When a current CFB HAR is uploaded:

```
python -m dcm.chat cfb-launch --har <HAR> --run-root dcm_v6/RUNS --cutoff-from-capture --research file
python -m dcm.chat next-research --run <run>
# host: EVENT/TEAM before PLAYER; one source populates every board-relevant entity
python -m dcm.chat evidence-import --run <run> --input host_observations.jsonl
python -m dcm.chat coverage --run <run>
# repeat until per-prop modelable flags are explicit
python -m dcm.chat forecast --run <run> --research bundle
python -m dcm.chat report --run <run>
```

Do not compute probabilities in the host. Empty cards are legal.
