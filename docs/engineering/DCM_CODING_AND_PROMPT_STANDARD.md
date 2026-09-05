# DCM coding and prompt standard

Status: permanent engineering policy, effective for every future DCM change.

This document is the inheritance contract for humans, ChatGPT Work, Grok, and
any other coding agent. A prompt that touches DCM must either include these
requirements or explicitly reference this file. A change is not complete
because a module exists; it is complete only when the live runtime consumes
it, the output is traceable, and the relevant gates pass.

## 1. Begin with a bounded execution contract

Every task prompt must declare: objective; in-scope and out-of-scope areas;
repository, branch, base SHA, and target promotion; input files and their
privacy class; sport/league/market scope; forecast cutoff and timezone;
available host capabilities; expected artifacts; checkpoint interval; tests;
benchmark workload; and exact completion states. The agent must inspect live
repository truth before editing and must preserve unrelated user work.

Use separate labels for `SOFTWARE_CLOSED`, `HAR_ACCOUNTING_ACCEPTED`,
`OPERATIONAL_ACCEPTED_WITH_CURRENT_HAR`, `PREDICTIVE_CERTIFIED`, and
`PRODUCTION_ROOT_CERTIFIED`. Never turn a missing external dependency into a
passing claim. `LR000000` and predictive claim `NONE` remain the defaults.

## 2. One canonical engine and explicit boundaries

The public probability engine remains Python and is installed from
`artifacts/dcm_v6_workstream_ab`. Do not create a duplicate analytics,
probability, ranking, EvidenceGraph, SportPlugin, or persistence engine.
Python owns orchestration, domain rules, research adapters, schemas, and
fallbacks. SQL/DuckDB/Polars or Rust/PyO3 may be added only after a measured
representative bottleneck, with a portable fallback and semantic-equivalence
tests. The TypeScript UI is not a second analytics engine.

Every boundary has a typed contract, schema/version, units, timezone, cutoff,
authority, source hash, and failure state. Time and units are never inferred
from display strings. Unsupported sport × league × market combinations fail
closed.

## 3. Algorithmic Constitution is executable policy

Every algorithm used or proposed has a canonical ID in the registry, an
applicability condition, input/output contract, producer, downstream consumer,
fallback, complexity, determinism class, benchmark, test, and lineage fields.
The runtime must emit selection and execution telemetry for active algorithms;
registered-but-unused algorithms are not runtime evidence. Exact identity/hash
lookup and structured indexes precede fuzzy retrieval. Group once, reuse
packets, select top-k before expensive sorting, batch writes, and use
deterministic seeded streams. Algorithm retirement requires an ADR and
equivalence/benchmark evidence.

## 4. Research, modeling, and learning rules

The canonical reusable unit is Subject + Event / OfferSet. Build the hierarchy
Sport → Competition → Event → Affiliation/Subject/Counterparty/Environment →
MarketDefinition/Offer. The full board receives a terminal disposition; no
silent truncation or fabricated side, status, sample, line, or probability.
Model opportunity before efficiency; use conserved shared event worlds and
residual pools; distinguish modelability from playability; admit only genuine
`PLAYABLE_CANDIDATE` rows to production portfolio construction. Incomplete,
conflicting, stale, post-cutoff, or unverified-rule evidence may support a
diagnostic model but blocks production selection.

Forecasts and frozen features are immutable. Settlement and learning are
append-only, chronological, future-only, and separately versioned from
sporting outcomes and platform administration. No single result promotes a
rule or learning revision.

## 5. Storage and privacy are part of correctness

Raw HARs, cookies, tokens, credentials, response bodies with secrets, live
SQLite files, and private runtime dumps remain local quarantine. Persist only
redacted summaries, normalized claims, hashes, counts, and safe projections.
Use `dcm.runtime.storage_router` and the folder hierarchy in
`docs/engineering/DCM_DRIVE_HIERARCHY.md`; do not scatter files or upload an
entire run directory. Local indexes are queried before remote Drive fetches.
Drive/GitHub publication is an outbox action: stage atomically, hash, validate
schema/privacy, publish through the host connector, read back exact bytes/hash,
then advance the resume pointer. Remote failure leaves a truthful local
fallback and never upgrades an external gate.

## 6. Verification and handoff

For every tranche: add positive-path tests, incomplete/conflict/failure
abstention tests, temporal and determinism tests, restart/corruption/idempotency
tests, and a representative benchmark. Run compile/import, targeted tests,
full suite, fresh install/wheel, inventory/registry checks, and security scans.
Record commands, results, artifact hashes, branch/head, CI, unresolved
external gates, and whether any root-of-trust/LR/predictive/performance claim
changed. Commit small coherent changes, push a branch, verify remote blobs and
checks, and merge to `main` only through the normal review/check mechanism
when authorized. Never report a planned, registered, fixture-only, or
process-local component as production-complete.
