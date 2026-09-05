# DCM Drive hierarchy and write protocol

The project root is a human-readable `Pillars DCM` folder. Its child keys are
stable, numeric, and registered once in the host-controlled folder registry.
Folder IDs are environment-specific; the engine never guesses or creates
them. A host connector may create a missing child only after validating its
parent and writing the updated registry.

```text
Pillars DCM/
├── 00_control/       prompts, manifests, WORK_STATE, hashes
├── 01_inputs/        redacted input summaries and source indexes
├── 02_research/      normalized claims, facts, evidence, acquisition logs
├── 03_features/      feature stores, snapshots, signal records
├── 04_models/        worlds, parameters, calibration and model artifacts
├── 05_runs/          CFB run outputs and immutable forecast objects
├── 06_settlements/   outcome and platform settlement records
├── 07_learning/      chronological evaluation and future-only proposals
├── 08_reports/       user-facing reports and safe summaries
└── 09_engineering/   checkpoints, tests, benchmarks, CI and audit passes
```

Every object has a stable kind, sport, period, run ID, schema, content hash,
privacy class, and dependency hashes. Names are deterministic and routes are
written at run time by `dcm.runtime.storage_router`. Do not upload raw HAR,
cookies, tokens, credentials, response bodies containing secrets, SQLite
databases, or an unfiltered run directory. SQLite and local indexes remain
local; Drive stores immutable objects and safe manifests.

Write protocol: local atomic stage → SHA-256 and schema/privacy validation →
append idempotent outbox intent → host upload → exact object metadata/content
read-back → mark remote acknowledged → update resume pointer; the connector
must read back the exact object before acknowledgement. A failed or
unverified remote write is `LOCAL_ONLY_EXTERNAL_UNVERIFIED`, never `SYNCED`.
Duplicate idempotency keys return the original object; divergent bytes fail
closed. Folder registry and route manifests contain IDs and hashes only, never
credentials.
