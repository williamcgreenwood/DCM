# Pillars DCM — Agent Engineering Contract

This repository implements the Pillars Distribution Cushion Prop Model (DCM).
These instructions are authoritative for coding agents working in this repo.

## Mission

Continue the existing DCM architecture. Do not restart or replace it with a
simpler forecasting app. The production path is:

HAR capture(s)
→ deterministic request-scope reconciliation
→ immutable board freeze
→ Sport → Competition → Event → Affiliation / Subject / Counterparty / Environment → MarketDefinition / Offer research
→ frozen EvidenceGraph
→ opportunity model
→ conditional efficiency model
→ shared event worlds
→ primitive-stat ledger
→ versioned MarketDefinitions
→ independent MORE/LESS evaluation
→ uncertainty / line tolerance / robustness
→ PLAYABLE / LEAN / PASS / TRAP
→ posterior ranking
→ dependence-aware portfolio
→ immutable forecast
→ postgame settlement
→ audit
→ shadow calibration
→ future-only learning proposal

## Canonical roots of trust

- Never silently substitute a DCM version.
- Exact v5.4.1 source SHA-256:
  `bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474`
- Exact v5.4.1 learning-ledger SHA-256:
  `a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a`
- Accepted Phase B/C V1 schema SHA-256:
  `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`
- A reconstruction with a different SHA is not byte-identical canonical V1.
- If an exact canonical artifact is absent, fail closed. Never fabricate bytes
  or weaken the hash gate.
- LR remains `LR000000` until chronological unseen settlements satisfy an
  explicitly tested promotion contract.
- Predictive claim remains `NONE` until evidence earns a different claim.

## Algorithmic Constitution

The DCM inherits `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`. It is
mandatory, CI-gated, and inherited by all future versions unless a newer
constitution is adopted under an Architecture Decision Record.

- Canonical text: `docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md`
- Machine-readable registry: `configs/algorithm_registry.json`
- Runtime: `dcm.algorithms` (selection engine, HAR AlgorithmExecutionPlan)
- Silent algorithm retirement is prohibited.
- ChatGPT-native deterministic fallbacks are required for optional packages.
- Do not create a second EvidenceGraph, ResearchStore, probability, ranking,
  SportPlugin, or persistence engine to satisfy the constitution.

## Prop-board doctrine

Every board run must:

1. Extract/account for every provided prop before exclusions.
2. Remove Green Goblins only after extraction/accounting.
3. Respect only explicitly offered sides; unknown side metadata fails closed.
4. Apply stronger Red Demon thresholds/cushion. Demon status is demotion-only.
5. Model opportunity separately from efficiency.
6. Use role-comparable samples and shrink small samples toward declared priors.
7. Use sport-appropriate distributions and shared primitive worlds.
8. Evaluate MORE/HIGHER and LESS/LOWER independently when offered.
9. Grade every modeled prop PLAYABLE, LEAN, PASS, or TRAP.
10. Preserve directional preference for PASS/TRAP when evidence permits.
11. Calculate true directional unclamped line tolerance for serious candidates.
12. Never invent data, status, sample size, source state, or probability precision.
13. Never force a fixed card size.
14. Enforce unique players, combination/component exposure, event/team limits,
    correlation, and shared failure-path controls.
15. Normally select no more than two players from one event.
16. Return five selections only when five genuine Playables exist.

Probability is not Reliability, Data Quality, Volatility, Fragility, OOD Risk,
false-sign risk, rank stability, posterior regret, or Selection Score. Keep
those fields separate throughout the pipeline and reporting.

## HAR and temporal integrity

- Real HARs may contain cookies/tokens. Never replay them and never commit them.
- Persist sanitized scope identities and decoded market facts only.
- Multi-HAR composition is latest successful response PER canonical request scope.
- A later HAR that does not capture a scope does not erase prior valid state.
- A failed same-scope refresh retains prior valid state and records the failure.
- A verified successful empty same-scope response may clear that scope.
- NOT_CAPTURED_IN_THIS_HAR is not equivalent to an empty response.
- Forecast cutoff is authoritative. Post-cutoff snapshots/updates cannot leak in.
- Reverse input-file order must not change the composite result.
- Resume/cache/path/runtime metadata must not change forecast-semantic hashes.

## Research and evidence

Research is hierarchical and reusable:

Sport → Competition → Event → Affiliation / Subject / Counterparty / Environment → MarketDefinition / Offer

Team/player/opponent terminology belongs inside sport/platform adapters and compatibility views, not the universal core. The canonical research unit is SubjectOfferSet = Subject + Event. Do not independently research every prop when evidence can be reused.

Production evidence must be structured, timestamped, source/content hashed,
claim hashed, cutoff-safe, and traceable. Fixture/synthetic evidence is
engineering-only and can never create a production-selectable card.

Missing required evidence may still permit modeling for diagnostics, but must
block production selection when the relevant evidence contract says it is
required.

## Modeling

Opportunity is generated before conditional efficiency.

Composite markets derive from the same primitive world. Never independently
simulate a composite that is a deterministic function of primitives.

Conservation identities must hold in every simulated world where the identity
is physical/accounting truth.

Unsupported Sport × League × Market combinations fail closed.

## Settlement and learning

Keep these distinct:

sporting result
!= platform administrative state
!= pick comparison result
!= lineup economics

Forecast artifacts are immutable. Settlement, audit, calibration challenger,
and patch proposal records are append-only sidecars.

Audits distinguish model error from normal variance. Patch proposals apply only
to future forecasts. One isolated result must never become a permanent rule.

Calibration and Learning Revision promotion must use chronological unseen
forecasts and outcomes. No retrospective leakage.

## Determinism

Content hashes bind semantic state only. Do not include:

- wall-clock completion timestamps;
- temp/output paths;
- process IDs;
- cache hit counters;
- SQLite row IDs;
- incidental dictionary/list order;
- resume flags that cannot legally change a frozen run.

Checkpoint/resume output must match uninterrupted execution for identical
frozen inputs and configuration.

Random streams must be deterministic from declared semantic identities. Worker
scheduling must not silently change model semantics.

## Performance

Correctness precedes optimization. Measure before certifying.

Benchmark representative boards and record wall time, CPU time, peak RSS,
world count, research count/reuse, cache hits, and artifact/database sizes.

Prefer event/affiliation/subject/counterparty evidence reuse, DAG invalidation, content-addressed
caching, adaptive simulation, bounded parallelism, deterministic RNG streams,
streaming ingest, indexed storage, and batched writes when tests prove semantic
equivalence.

Never set `hostPerformanceCertified=true` without measured evidence.

## Development workflow

- Direct implementation pushes and force-updates to `main` are prohibited.
  Validated implementation is expected to reach `main` through a reviewable
  PR, required checks, and the repository's normal merge mechanism when the
  current project owner authorizes promotion. A draft PR or a green local
  test is not itself a merge authorization.
- Work on a branch and PR.
- Inspect current HEAD before editing; another agent may have changed the branch.
- Use small coherent commits.
- Run targeted tests and the full relevant suite.
- Keep CI green before merging.
- No raw HARs, secrets, tokens, cookies, credentials, or private runtime output
  in commits.
- Do not merge merely because code compiles.
- Do not mark v6 production-complete while a required acceptance gate is false.
- Every new prompt or coding request that touches DCM inherits
  `docs/engineering/DCM_CODING_AND_PROMPT_STANDARD.md`. The prompt must state
  scope, inputs, cutoff, privacy boundary, algorithm IDs, producer/consumer,
  tests, checkpoint, and release gates before implementation begins.
- Drive writes must follow `dcm.runtime.storage_router` and the documented
  folder registry. The engine may emit a route, but only a host connector may
  upload and must read back the exact object hash.

Primary Python package:
`artifacts/dcm_v6_workstream_ab/dcm`

Primary tests:
`artifacts/dcm_v6_workstream_ab/tests`

Standard validation from `artifacts/dcm_v6_workstream_ab`:

```bash
python -m compileall -q dcm tests
PYTHONPATH=. DCM_FAST_WORLDS=64 DCM_SERIOUS_WORLDS=128 pytest -q
```

## Agent reporting

For each completed tranche report:

- files changed;
- tests added/updated;
- tests run and result;
- exact commit SHA;
- unresolved blockers;
- whether any root-of-trust, LR, predictive, or performance claim changed.

If a requirement cannot be completed because exact canonical bytes, future
settlements, official data, or external evidence do not exist, implement the
correct fail-closed boundary and state the precise external dependency. Never
fill the gap by invention.


## Mandatory program-status governance

Every coding pass must update repository-visible progress. Before merge, the agent must:

1. inspect `docs/PROGRAM_STATUS.json`, `docs/PROGRAM_STATUS.md`, the universal implementation matrix, and the most recent `docs/engineering_passes/` records;
2. add one new immutable engineering-pass record;
3. update any changed workstream score/status and explain the executable evidence;
4. add newly discovered missing work rather than hiding it;
5. run/update the code inventory generator when Python modules/classes/functions change;
6. leave an ordered next-pass task list.

A pass that changes code but does not update the pass ledger is incomplete.

Status must be based on executable integration, not file/module existence. No agent may downgrade a known blocker silently or mark a scaffold/fixture/shadow path COMPLETE.

## ChatGPT/Grok host-native law

ChatGPT is the priority execution host; Grok may implement the same public host contract. The canonical contract is `docs/CHATGPT_NATIVE_EXECUTION_SPEC.md`.

The DCM must expose a small stable host API/CLI instead of requiring the host to understand internal modules. Required host operations are runtime doctor, HAR prepare, next optimized research batch, evidence import, coverage, forecast, report, resume, audit and settlement.

Repository read access is not runtime execution. Fresh-host acceptance requires an exact installable release artifact plus manifest/hashes. The host may perform web/tool research, but Python remains the only forecasting/model engine.

Host observations must be simple source/entity/data records. The engine owns canonical scope resolution, normalization, cutoff checks, source policy, reliability/freshness rules, semantic hashing, dedupe/conflicts and EvidenceGraph lineage.

## Universal research depth law

The research depth demonstrated by any named player/team/matchup example is a depth benchmark only. Universal core contracts must remain Sport/Competition/Event/Affiliation/Subject/Counterparty/Environment/MarketDefinition/Offer based.

Every SportPlugin must declare required/applicable subject, affiliation, counterparty, event, environment and market fields. The research scheduler must acquire reusable evidence once and fan it out to dependent offers. No one-search-per-prop architecture is acceptable.

Source acquisition must use a versioned source catalog with authority, coverage, authentication, latency, cost/rate limits, licensing/storage constraints, identifier mapping and fallback ordering. Official sources and configured structured APIs should precede generic search when they cover the needed field.

## Research and run storage law

Never commit raw private HARs, credentials, cookies, tokens or prohibited copyrighted source dumps. GitHub may contain compact normalized evidence/provenance, content hashes, research indexes, run manifests and audit artifacts when permitted.

High-volume or high-churn research must use a content-addressed artifact/database/object-store layer referenced from GitHub by stable manifests/hashes rather than bloating Git history.
