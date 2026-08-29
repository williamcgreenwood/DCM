# DCM v6 E2E completion report

Software: `6.0.0+WSAB.E2E.LR000000`  
Learning Revision: `LR000000`  
Predictive claim: `NONE`  
`OPTIMIZED_DCM_6_0`: **false**  
`HOST_PERFORMANCE_CERTIFIED`: **false**  
`CHATGPT_OPERABLE_DCM`: **true** (FixtureProvider — not live box scores)  
`SOFTWARE_E2E_COMPLETE`: **true** for the executable spine

Inspected GitHub `main` SHA before this branch: `7bd665331a813597f4d959cb527eedc10744b529`.

## What was missing on main

HAR → `board.json` existed. There was no top-level runner that continued through hierarchical research, event-once worlds, unclamped line surfaces, grading, ranking, portfolio, DAG/checkpoint, and freeze.

TypeScript `model.ts` sampled PRA independently of PTS/REB/AST (doctrine violation).

## What was implemented

- `python -m dcm.runner --synthetic|--input|--resume`
- Content-addressed DAG + atomic checkpoint
- ResearchProvider (Fixture + File) + EvidenceClaim + TemporalFirewall
- Event-once basketball/football/baseball samplers; PRA derived
- Unclamped line surface from shared sorted worlds
- Demon demotion-only grading
- Portfolio unique-player / event-cap / composite overlap
- SQLite append-only index
- Performance timers that **do not** write PeakRSS PASS
- Operator console Research + DAG tabs
- Tests A–J (B skipped until a live HAR is attached)

## Inherited

WSAB_BASELINE_46, football ADR-V6-001, PrizePicks settlement split, HAR spine, v5.4.1 mount gate (ABSENT).

## Remaining external blockers

1. Canonical v5.4.1 source bytes (hash `bd1fb433…`) — decoder stays `NOT_MOUNTED`
2. Official CFB PrizePicks player_id map
3. Intended-host performance certification
4. Live PrizePicks HAR in `dcm_v6/INBOX/current.har`
5. MLB PA production promotion (engine is SHADOW)

## Command

```
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runner --synthetic --out dcm_v6/RUNS
```

Operator: **Run DCM** on the console. LR stays `LR000000`.
