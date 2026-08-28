# Pillars DCM

Private development tree for Pillars Distribution Cushion Model v6.

Software: `6.0.0+WSAB.HARSPINE.LR000000`  
Learning Revision: **LR000000** (not promoted)  
Predictive claim: **NONE**  
This is **not** an “optimized DCM 6.0”.

## Operator

1. Open the operator console.
2. Run the synthetic slate, or upload one PrizePicks/Outlier HAR.
3. Every extracted row is accounted. Green Goblins never enter the card.
4. Download frozen `board.json`. Empty card is success.

CLI:

```
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runtime.mount_v541
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runtime.har_run --synthetic --out dcm_v6/RUNS
```

## Honest blockers

- Hash-verified v5.4.1 HAR decoder — canonical source bytes ABSENT (`bd1fb433…`)
- Content-addressed research DAG / host performance gates
- MLB PA engine as production (shadow only)
- Official CFB name→id map (names stored; tests use fixture IDs)

Canonical v5.4.1 is never overwritten. Drop the three canonical files in `dcm_v6/INBOX/` and re-run the mount gate to copy-forward a verified development copy.
