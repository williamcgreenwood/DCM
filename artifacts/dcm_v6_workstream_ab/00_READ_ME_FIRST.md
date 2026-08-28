START HERE: verify PACKAGE_MANIFEST + SOURCE_LINEAGE, then read CHATGPT_CONTEXT_INDEX; do not recursively read the whole tree unless a referenced hash/status fails.

# dcm_v6_workstream_ab

Universal sport-plugin + PrizePicks settlement foundation for Pillars DCM v6.

- Software: see VERSION (`6.0.0+WSAB.LR000000`)
- Learning Revision: **LR000000**
- Predictive claim: **NONE**
- Lifecycle: **IMPLEMENTED_STANDALONE** (not RELEASE_ACCEPTED)

This package is **not** the live HAR runner by itself. It proves:

1. Universal plugin contract (fail closed if missing).
2. Football + basketball physics / conservation / composites-from-ledger.
3. Sport-agnostic `settle_world_lineup`.
4. Operator control surface so ChatGPT does not rediscover the architecture.

Canonical v5.4.1 must remain untouched. Expected source `bd1fb433…`, ledger `a9956ef1…`. In this workspace those bytes are **ABSENT**.

Phase B/C freeze `6e78dacc…` is **DECLARED_UNVERIFIED**. Reconstruction inventory is not the freeze.

## First command

```
PYTHONPATH=. python3 -m pytest tests/test_football_registry.py tests/test_e2e_world_to_lineup.py tests/test_lineage_and_schema.py tests/test_official_predicates.py -q
```

That is `WSAB_BASELINE_46`.

Then: `cat CHATGPT_CONTEXT_INDEX.json`

Fail closed on unknown sport/league/market/rule. Never generic Normal → PLAYABLE.

Write run artifacts under `RUNS/<run_id>/` when the integrated runner exists. Resume from checkpoints, not chat memory.
