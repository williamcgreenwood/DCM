# DCM v6 development tree

Software: `6.0.0+WSAB.E2E.LR000000`  
Learning Revision: **LR000000** (not promoted)  
Predictive claim: **NONE**  
Lifecycle: **INTEGRATED_DEVELOPMENT** — not RELEASE_ACCEPTED, not “optimized DCM 6.0”.
ChatGPT operable: **TRUE** via FixtureProvider (not live box scores).
Host performance: **NOT CERTIFIED**.

This tree is a **development copy**. It does not mutate canonical v5.4.1.

## What ships

1. v5.4.1 **mount gate** — copy-forward only after SHA-256 match. Bytes ABSENT.
2. HAR → immutable `board.json` with full-board accounting.
3. E2E runner: research DAG → event-once worlds → line surface → grade → rank → portfolio → freeze.
4. WSAB football/basketball plugins bound to board rows.

## Still blocked (honest)

| Item | State |
| --- | --- |
| Hash-verified v5.4.1 HAR decoder | BLOCKED — source bytes ABSENT |
| Host performance gates | INSTRUMENTED_NOT_CERTIFIED |
| MLB PA engine as production | SHADOW only |
| Official CFB name→id map | names stored; IDs null |
| Live PrizePicks HAR | not supplied |
| Any “optimized DCM 6.0” claim | FORBIDDEN at LR000000 |

## Operator path

```
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runner --synthetic --out dcm_v6/RUNS
```

Goblins never enter the card. Empty card is success. Offered sides only.
