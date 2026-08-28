START HERE: verify PACKAGE_MANIFEST + SOURCE_LINEAGE, then read CHATGPT_CONTEXT_INDEX; do not recursively read the whole tree unless a referenced hash/status fails.

# dcm_v6_workstream_ab

Universal sport-plugin + PrizePicks settlement foundation for Pillars DCM v6, now with a development HAR → board.json spine.

- Software: see VERSION (`6.0.0+WSAB.HARSPINE.LR000000`)
- Learning Revision: **LR000000**
- Predictive claim: **NONE**
- Optimized DCM 6.0 claim: **FALSE**
- Lifecycle: **INTEGRATED_DEVELOPMENT** (not RELEASE_ACCEPTED)

Canonical v5.4.1 must remain untouched. Expected source `bd1fb433…`, ledger `a9956ef1…`. In this workspace those bytes are **ABSENT**. The mount gate copies only after SHA-256 match into `dcm_v6/canonical_mount/v5.4.1_copy/`.

The HAR adapter here is **v6-new**. It is not a hash-verified v5.4.1 decoder.

## First commands

```
PYTHONPATH=. python3 -m pytest tests/test_football_registry.py tests/test_e2e_world_to_lineup.py tests/test_lineage_and_schema.py tests/test_official_predicates.py -q
PYTHONPATH=. python3 -m pytest tests/test_har_ingest.py tests/test_v541_mount.py -q
PYTHONPATH=. python3 -m dcm.runtime.har_run --synthetic --out /workspace/dcm_v6/RUNS
```

Fail closed on unknown sport/league/market/rule. Never generic Normal → PLAYABLE.

Write run artifacts under `dcm_v6/RUNS/<run_id>/`. Resume from checkpoints, not chat memory.
