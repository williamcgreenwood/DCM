# dcm_v6_workstream_ab

Executable Workstreams A and B only.

- A: football primitive registry (NFL + CFB physics; NFLP ledger allowed).
- B: WorldProjection → EntryContract → WorldLineupOutcome via one sport-independent settler.

This is not the live DCM runner. `runtime/pipeline.py` starts at an already-built world. It does not ingest `current.har`.

## What this package is not

HAR ingest, live-board normalizer, research/ranking/portfolio, MLB PA engine, other-sport registries, DPMM/GPLVM, Learning Revision promotion, six-pick fill, inferred NFLP reboot, fabricated CFB regular-season reboot.

## Canonical relationship

Do not edit v5.4.1 bytes in place. Expected source `bd1fb433…` and ledger `a9956ef1…` are recorded in `SOURCE_LINEAGE.json`. In the Grok sandbox those files are absent. In the ChatGPT Pillars project they are declared present. Merge is a later integration tree, not this folder mutating A.

Phase B/C freeze `6e78dacc…` is DECLARED_UNVERIFIED. Reconstruction inventory hash is in `SOURCE_LINEAGE.json`.

## Run tests

```
PYTHONPATH=. python3 -m pytest tests -q
```

Historical slice: 41 tests. This tree adds official-predicate tests (CFB phase, partial board, 3Q exit).

## Lifecycle

`IMPLEMENTED_STANDALONE` · software `6.0.0+WSAB.LR000000` · LR000000 · predictive claim NONE
