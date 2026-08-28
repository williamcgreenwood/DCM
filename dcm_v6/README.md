# DCM v6 development tree

Software: `6.0.0+WSAB.HARSPINE.LR000000`  
Learning Revision: **LR000000** (not promoted)  
Predictive claim: **NONE**  
Lifecycle: **INTEGRATED_DEVELOPMENT** — not RELEASE_ACCEPTED, not “optimized DCM 6.0”.

This tree is a **development copy**. It does not mutate canonical v5.4.1.

## What this turn actually ships

1. v5.4.1 **mount gate** — copy-forward only after SHA-256 match. Bytes are
   still ABSENT in this workspace, so the mount is fail-closed.
2. HAR → immutable `board.json` with full-board accounting (extract Goblins
   *before* exclusion).
3. WSAB football/basketball plugins **bound** to normalized board rows.
   Settlement still requires a primitive ledger; HAR ingest does not invent one.

## Still blocked (honest)

| Item | State |
| --- | --- |
| Hash-verified v5.4.1 HAR decoder | BLOCKED — source bytes ABSENT |
| Content-addressed research DAG / host perf gates | DESIGNED, not verified |
| MLB PA engine as production | SHADOW only |
| Official CFB name→id map | names stored; tests still use fixture IDs |
| Any “optimized DCM 6.0” claim | FORBIDDEN at LR000000 |

## Operator path

Drop `current.har` in `INBOX/`, run DCM in the operator console, or:

```
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runtime.har_run --synthetic --out dcm_v6/RUNS
```

Goblins never enter the card. Empty card is success. Offered sides only.
