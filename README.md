# Pillars DCM

Private development tree for Pillars Distribution Cushion Model v6.

Software: `6.0.0+WSAB.E2E.LR000000`  
Learning Revision: **LR000000** (not promoted)  
Predictive claim: **NONE**  
This is **not** an “optimized DCM 6.0”. Host performance is **not certified**.

## Operator

1. Open the operator console.
2. Run the synthetic slate, or upload one PrizePicks/Outlier HAR.
3. Every extracted row is accounted. Green Goblins never enter the card.
4. Event-once worlds: PRA is PTS+REB+AST in the same draw.
5. Download frozen `board.json`. Empty card is success.

CLI:

```
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runtime.mount_v541
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runner --synthetic --out dcm_v6/RUNS
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runner --resume dcm_v6/RUNS/<run_id>/checkpoint.json
```

Live HAR without operator evidence writes FileProvider incomplete, then resume after `evidence/` is filled. FixtureProvider is the ChatGPT-operable loop so player logs are not a user paste.

## Honest blockers

- Hash-verified v5.4.1 HAR decoder — canonical source bytes ABSENT (`bd1fb433…`)
- Host performance gates (instrumented, not certified)
- MLB PA engine as production (shadow only; modeled, not selected)
- Official CFB name→id map (names stored; IDs null)
- Live PrizePicks HAR not supplied in this workspace

Canonical v5.4.1 is never overwritten. Paste the three canonical files in chat (this sandbox cannot receive a Finder drop into `/workspace`) and re-run the mount gate.
