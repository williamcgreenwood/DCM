# Engineering pass — Phase 15 CFB synthetic E2E proof

- Pass id: `20260906T052400Z_grok_cfb-e2e-synthetic`
- Branch: `task/cfb-e2e-synthetic-20260906`
- Base: `main` @ `2b021217a006847a6d79d27d77d571509f6065c4` (PR #41 EventWorld NumPy)
- Agent: grok
- Scope: CFB positive + incomplete/conflicted synthetic E2E; private HAR aggregates-only; honest PROGRAM_STATUS

## What landed

1. `tests/test_cfb_e2e_synthetic_phase15.py` — labeled PATH_A / PATH_B / PATH_C.
2. Synthetic fixtures (committed; not live HAR):
   - `tests/research_fixtures/cfb_e2e_phase15_positive_har.json`
   - `tests/research_fixtures/cfb_e2e_phase15_incomplete_har.json`
3. PATH_A wires existing `run_dcm` + CFB Research OS / freeze APIs:
   HAR accounting → board/requirement/market graphs → evidence → MaterialFact features →
   ParameterSnapshots → conserved shared EventWorlds (NumPy backend) → probabilities →
   ≥1 PLAYABLE → portfolio 0–6 → `freezeState=FROZEN`.
4. PATH_B proves incomplete/conflicted boards emit HELD_FOR_RESEARCH / UNSUPPORTED /
   EXCLUDED_GOBLIN / LEAN|PASS|TRAP / FRONTIER_INTERIM — not silent zero-card success.
5. PATH_C accounts private box aggregates only when present; reports exact terminal
   limitation when `liveOrStarted>0`; never manufactures a card; never publishes HAR.

## CLI smoke (existing entrypoints)

```bash
PYTHONPATH=src python -m dcm --help
PYTHONPATH=src python -m dcm --synthetic --research fixture --cutoff 2026-08-29T00:00:00Z --out /tmp/dcm-smoke
PYTHONPATH=src python -m dcm.chat doctor
PYTHONPATH=src pytest -q tests/test_cfb_e2e_synthetic_phase15.py
```

Host-native CFB launch remains `python -m dcm.chat prepare|next-research|evidence-import|forecast`.

## Algorithmic Constitution consumption (proved on PATH_A)

- **BoardStore / ALG-INDEX-001**: `board_indexes.json` records `exactIdentityCount` + `ALG-INDEX-001` on the CFB launch path.
- **CELF / ALG-SCHED-001**: `acquisition_schedule.json` + algorithm telemetry on Research OS packing.
- **NumPy EventWorld**: `event_worlds_meta.json` shows `backend=numpy`, joint conservation, `rngVersion=dcm.cfb.event_world.rng.v1`.

## Honest completion matrix

| Field | Value |
|---|---|
| CFB_OPERATIONAL | PARTIAL (synthetic E2E green; live HAR card EXTERNAL) |
| OPERATIONAL_ACCEPTED_WITH_CURRENT_HAR | PARTIAL / EXTERNAL |
| RECOMMENDATION_ELIGIBLE | DEFERRED |
| PREDICTIVE_CERTIFIED | DEFERRED / NONE |
| learningRevision | LR000000 (unchanged) |
| productionRootCertified | false |
| hostPerformanceCertified | false |

## Explicit non-claims / blockers for live card

- No private HAR bytes committed or uploaded.
- Live/current HAR pregame card remains EXTERNAL (stale/live aggregates: `liveOrStarted>0` on box checkpoints).
- No LR promotion, no predictive superiority, no production picks.
