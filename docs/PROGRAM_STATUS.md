# DCM Program Status

Canonical integration line: `integration/v6-ml-architecture-20260830` at merge commit `59ea12487ad2e747a15427ba6bb9babd1b9f5907` (through PR #18 R0 Algorithmic Constitution).

Active canonical-main CFB closure slice: `chatgpt/canonical-main-cfb-standard-20260905`, based on verified v2 closure head `ebf636e947647010a91bcd973b314465f0b236b1`. The current project owner authorizes promotion to `main` only through a reviewable PR and required checks; direct and force pushes remain prohibited.

This file is the human dashboard. It must be updated on every coding pass together with a new immutable pass record under `docs/engineering_passes/`.

Current bounded execution increment: `P0-COMPACT-BOARDSTORE-SOA-20260906` adds the two-representation BoardStore (audit dicts + int32/NumPy SoA indexes) and compact Feature/Parameter matrix helpers. CFB launch still consumes BoardIndexes at the public boundary.
`docs/engineering/DCM_CODING_AND_PROMPT_STANDARD.md`; Drive writes follow
`docs/engineering/DCM_DRIVE_HIERARCHY.md` and `dcm.runtime.storage_router`.


## 2026-09-06 BoardStore + compact arrays (Phase 7–8)

`task/compact-boardstore-soa-20260906` (base `main` @ `8fdd520c388b`, PR #38). Canonical `BoardStore` keeps one audit copy per offer; compute indexes use int32 row IDs / bitmaps; SQLite stores keys+row_id only (no per-row `json.dumps` payload). `compact.py` provides IdMap, CompactNumericBoard (line/mean/variance/reliability/fragility/ood), and Feature/Parameter matrices with audit round-trip. `BoardIndexes` is BoardStore-backed without breaking CFB launch APIs.

Does **not** claim host-performance certification, EventWorld C++, or a current live CFB forecast. Feature/Parameter matrices are available to producers/consumers but not yet the primary launch path. Phase 9 = profiling.

## 2026-09-06 true dependency invalidation (Phase 6)

`task/true-descendant-dag-20260906` (base `main` @ `1fe6d21721cb`, PR #37). Runtime `Dag.invalidate` walks reverse adjacency only; `invalidate_line_descendants` is ID-scoped; CFB `execute_source_aware_observations` persists canonical `runtime_dag.json` with claim→fact→feature→parameter→worlds→grade→rank links. Legacy `invalidate_types` / `invalidate_for_delta` remain for coarse deltas. Freeze latch (`mark_freeze` / `DagFrozenError`) ends backward DAG mutation after seal.

Does **not** claim compact arrays, EventWorld C++, or a current live CFB forecast.

## 2026-09-06 Research OS closed-loop slice

`task/research-os-closed-loop-20260906` hardens the grouped CFB Research OS path already on main (graphs, CELF packing, source-aware import). This pass adds persistable **AcquisitionActionGraph**, post-import MaterialFactResolution + CELF reschedule so the **next host batch shrinks** when coverage moves, and proves `ALG-SCHED-001` with `downstream_used` telemetry on the closed loop. Lazy `dcm.chat` exports remove a pre-existing import cycle with `observation_execute`.

Does **not** claim a current live CFB forecast. Remaining operational blockers stay EXTERNAL (current HAR + host-acquired evidence, live adapters, prospective settlements).

## 2026-09-06 requirement ledger v1

`main` is at `c01724382f478ddb4221a098e37e98f55fcd9ffe` after PR #35 (`src/dcm` relocate). Pass `20260906T040000Z_grok_requirement-ledger-v1` publishes canonical `docs/requirements/REQUIREMENT_LEDGER.v1.json` + `REQUIREMENT_CROSSWALK.md` from the handoff seed (HANDOFF-001…042 expanded to atomic REQ-* IDs). Statuses are honest vs live `src/dcm`. P380X remains a candidate SignalOperator catalog (compile-to-active-DAG); ZIP quarry code was not installed into the runtime package. CFB operational acceptance remains EXTERNAL pending current HAR + host-acquired evidence.

## 2026-09-06 package layout relocate

PR #34 merged to `main` at `b0e44d5886adb98cb84dbf466ee3a3fc1fee28b1`; PR #35 merged at `c01724382f478ddb4221a098e37e98f55fcd9ffe` completing the `src/dcm` relocate (TypeScript operator UI under `web/src`). `artifacts/dcm_v6_workstream_ab` remains archive-only.

## Status scale

- 10/10 COMPLETE: executable, integrated, tested, auditable, portable for declared scope; no hidden stub/fallback.
- 8–9/10 STRONG PARTIAL: substantive path exists; bounded gaps remain.
- 5–7/10 PARTIAL: useful implementation exists but production contract is materially incomplete.
- 1–4/10 STUB/EARLY: scaffold/prototype or narrow fixture path.
- 0/10 MISSING: required subsystem absent.
- BLOCKED-EXTERNAL: correct software boundary exists but completion requires future settlements, licensed/private data, or unavailable canonical bytes.

## Program dashboard

| Workstream | Target | Current | State | Next acceptance gate |
|---|---:|---:|---|---|
| P0 Canonical spine / HAR / integrity | 10 | 9 | STRONG PARTIAL | preserve fractional capture precision for `--cutoff-from-capture`; authenticated v5.4.1 root remains independently gated |
| P1 Universal research / evidence | 10 | 9 | STRONG PARTIAL | use source-aware grouped host actions to import shared CFB evidence → modeled Top100/Top25/0–6 Playables; mixed-sport R1 remainder |
| P2 Feature / state / parameter layer | 10 | 9 | STRONG PARTIAL | validate CFB role-comparable/current/prior support on real boards; activate only evidence-backed signal operators |
| P3 SportPlugin physics | 10 | 8 | STRONG PARTIAL | 19 CFB PRODUCTION markets executable; remaining 24-component plugin bindings sport by sport; current-board operational acceptance |
| P4 Probability / uncertainty / grading / portfolio | 10 | 9 | STRONG PARTIAL | prospective CFB settlement/calibration evidence; mixed-sport shared-world coverage |
| P5 Audit / portability / ChatGPT-native execution | 10 | 8 | STRONG PARTIAL | current-HAR fresh ChatGPT acceptance; immutable release retrieval |
| P6 Settlement / calibration / learning | 10 | 6 | PARTIAL + EXTERNAL VALIDATION | retain FRONTIER_INTERIM checkpoints outside settlement eligibility; exact platform coverage; CFB prospective settlements; CRPS/subgroups; chronological unseen settlements before promotion |
| P7 Host-native execution contract | 10 | 8 | STRONG PARTIAL | validate source-aware host-action batches on the current CFB HAR; no second engine |
| P8 Universal source acquisition | 10 | 7 | PARTIAL | live adapter fetch beyond fixtures; licensed providers remain optional |
| P9 Universal core migration | 10 | 9 | STRONG PARTIAL | retire remaining PLAYER/TEAM claim lookups at packet/parameter adapters |
| P10 Full sport coverage | 10 | 3 | EARLY | each supported sport reaches 24/24 plugin components + validation suite |
| P11 Release + fresh-environment acceptance | 10 | 7 | PARTIAL | wheel/release + exact hash + current HAR-only fresh ChatGPT acceptance |
| P12 Research archive / index / reuse | 10 | 8 | STRONG PARTIAL | Drive credentials; high-volume queryable store; retention/licensing enforcement beyond local blobs |
| P13 Performance / search / token optimization | 10 | 8 | STRONG PARTIAL | Phase 9 profile BoardStore/SoA on representative boards; measured CPU/RSS/token certification; host-performance uncertified |
| P14 Production operations / observability | 10 | 5 | PARTIAL | run health/readiness, failure taxonomy, deterministic recovery, release gates |
| P15 P380X donor signal governance | 10 | 8 | STRONG PARTIAL | Tranche C MaterialFact/source-truth runtime closure; next typed role/matchup/context operators; exact donor archive bytes and later tranches remain external/future |
| P16 Algorithmic Constitution / strategy registry | 10 | 9 | STRONG PARTIAL | CFB live CELF + telemetry done; remaining mixed-sport R1; keep CI gates; no silent algorithm retirement |

Constitution version `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903` is inherited. Learning revision remains `LR000000`; predictive superiority remains `NONE`; production-root certification remains false.

## R0 Algorithmic Constitution status

Merged to integration via PR #18 at `59ea12487ad2e747a15427ba6bb9babd1b9f5907`.

## 2026-09-03 CFB guarded-launch Research OS slice

This slice makes BoardGraph / RequirementGraph / live AcquisitionAction packing executable on the canonical CFB path. It does **not** complete mixed-sport R1 or claim a current live forecast.

Implemented and tested:

- HAR accounting first; Goblins excluded from selection only after accounting.
- AlgorithmExecutionPlan before research; algorithm telemetry with producer/consumer/count.
- BoardGraph, MarketDemandGraph, RequirementGraph persist before `collect()`.
- AcquisitionActions grouped by EVENT/TEAM/SUBJECT; live selector is `ALG-SCHED-001` (CELF), not a static queue.
- SPORT/COMPETITION mass cannot consume the unique-offer budget and starve EVENT/TEAM batches.
- Per-prop modelable ≠ playable flags independent of global research completion.
- Ranking: filter CFB → heap Top-K → Timsort; Top100/Top25/0–6 Playables never padded.
- `dcm-host cfb-launch` host workflow. Host does not compute probabilities.
- No new markets. Aug 29 supported population is 308 ≥ 100.

Measured:

- Fixture + web-claim bundle: 8 modeled diagnostic, Top100=8, Top25=8, Playables=0, freeze LR000000/NONE.
- Compact live HAR: 20 CFB / 6 Goblin / 9 supported non-Goblin.
- Aug 29 sanitized HAR: 1568 CFB / 229 Goblin / 308 supported; 994 actions; first packed batch EVENT+ENVIRONMENT+AFFILIATION.
- No 2026-09-03 live CFB HAR was supplied.

Not earned:

- production PLAYABLEs from a current board
- prospective CFB calibration
- LR promotion
- production-root certification
- host performance certification
- predictive superiority
- full mixed-sport Research OS

## 2026-09-03 CFB reference-implementation consumer pass

Continues PR #19 from `ec1865e`. Does **not** complete mixed-sport R1 or claim a current live forecast.

Software consumers closed this pass:

- `holdPlayable` demotes PLAYABLE in MODEL + frontier recompute
- RoleEpoch executes EWMA/CUSUM/Page-Hinkley
- Retrieval cascade queried (BM25/BM25F/Trie/fuzzy/MinHash/SimHash/LSH/RRF/MMR/bitmaps) with registry-correct telemetry IDs
- Source-health success recording; Drive catalog fail-closed; archive retry/reconcile; freeze merkle
- Joint CFB EventWorlds `JOINT_TEAM` conservation meta; refresh re-grades on line change
- Settlement of MODELED_DIAGNOSTIC; expanded failure taxonomy
- 19 ACTIVE CFB MarketDefinitions already in tree (aliases + genuine unsupported)

Measured: 397 pytest passed; inventory 268/1858 hash `0f6693681e3ed41d7abcf3a5feec2d4a758301817f0fc54d639e2ada4e669384`.

Not earned: current 2026-09-03 HAR (`CURRENT_REAL_HAR_ACCEPTANCE_PENDING_EXTERNAL_INPUT`); LR promotion; production-root certification; Drive credentials.

## 2026-09-04 CFB semantic-completion pass

Continues PR #19 from `7c961075ed2f6a1d938f20c2b7ffb294cb4d7d1c`. Makes algorithms ACTIVE only when they change the forecast.

Closed this pass:

- `NO_CEREMONIAL_ALGORITHM_EXECUTION` telemetry gate (`downstream_used` + CI). Launch no longer sample-queries FTS/fuzzy/RRF/MMR/LSH.
- Identity-first `BoardIndexes.resolve_identities`: exact/composite/SQLite/Bloom always; fuzzy/FTS/cascade only on projectionId miss.
- Residual EventWorlds: board membership is not 100% of team opportunity; unmodeled rush/target/pass buckets; kickers isolated.
- Source-health routes AcquisitionActions; `CFB_SPORTS_REFERENCE` (`college_football_reference`) replaces `CFB_PFR`; OPEN → cooldown → HALF_OPEN with real timestamps; fallbacks traversed.
- Cache cascade L0–L6: claims stored, requests looked up (no self-put-get); L4 as-of; L5 Drive identify of evidence hashes.
- Co-extraction of host-acquired structured pages only (`NO_ACQUIRED_STRUCTURED_PAGE` when none).
- MaterialFact contentHash includes fact values; `facts_to_features` consumed by ParameterSnapshots; ISO temporal cutoff.
- Frontier EVSI from AcquisitionAction fanout/cost/authority; pass count increments only on material state change.
- Line-only refresh reuses worlds; material-state refresh resimulates.
- Isotonic/conformal INACTIVE at LR000000. Champion selector SHADOW_DIAGNOSTIC; actual producer is Empirical Bayes in snapshots.
- CFB Market Execution Matrix for 19 ACTIVE markets.

Measured: 412 pytest passed; inventory 270/1897 hash `5c6889973fc05662a469b1f912469c164775e765c6916f9e7a1f37b23c64f5de`.

Verdict: `CFB_REFERENCE_IMPLEMENTATION_SOFTWARE_COMPLETE`. Current-HAR operational acceptance remains `CFB_CURRENT_HAR_OPERATIONAL_ACCEPTANCE_PENDING`. Do not merge to main.

## 2026-09-04 CFB freeze-gate / incremental-runtime pass

Continues PR #19 from `0e5e2275742246211cb20ba4e5d17b7908106ab2`. Closes remaining ChatGPT-audit semantic defects. Not an expansion.

Closed this pass:

- MaterialFacts overlay packets before RoleEpoch/opportunity/efficiency fit; snapshot hash includes fact hashes.
- Material refresh rebuilds ParameterSnapshots + shared joint EventWorlds, then full probability/risk bundle + rerank. Line-only reuses worlds.
- Shared CFB EventWorlds for a lone board player; `OpportunityShareEstimate` is evidence-driven; starter QB is not capped at 92%; kickers isolated.
- Freeze blocked when Top25 is not FINAL or stop reason is `EXTERNAL_HOST_REQUIRED` (`forecastFrozen=false`, `AWAITING_FRONTIER_RESEARCH`).
- `FrontierPassState` binds before/after snapshot/world/feature/fact/probability/ranking/Top25 hashes.
- Requirement completion is semantic (`evaluate_request`); STATUS evidence does not complete GAME_HISTORY.
- Exact projectionId path does not Bloom/composite/SQLite-query known IDs.
- L5 semantic key `(scope, scope_id, claim_type)` → content hashes → exact fetch. No false L5 without catalog.
- Source health persists; 0.0 success stays 0.0; HALF_OPEN is one trial; CELF expectedGain uses routed health.
- Market execution matrix stages are proven from runtime contracts; 19/19 ACTIVE complete.
- Incremental Research OS: static graphs reused when the HAR fingerprint matches; facts/catalog/cache reused when claims fingerprint matches; acquisition rebuilt only when frontier fingerprint changes; requirement bitmaps cover the full request set.
- ParameterSnapshot cache by projectionId, invalidated on material refresh. Stage telemetry HAR/RESEARCH/MODEL/RANK/FREEZE.

Measured: 435 pytest passed; inventory 272/1945 hash `d25db58371c5acd9cb85d377373ff71c08616f20e91dea82ab77c31193375686`.
Engineering synthetic throughput (not certified): 100 rows 8.05s / 170MB; 1000 rows 131.6s / 1446MB. Improved vs the prior freeze-gate snapshot, still above the original ~96s/932MB 1000-row engineering baseline because semantic work is now real.

Verdict: `CFB_REFERENCE_IMPLEMENTATION_SOFTWARE_COMPLETE` for the declared CFB software path. Current-HAR operational acceptance remains pending external input. Host-performance uncertified. Do not merge to main.

## 2026-09-04 CFB semantic-closure / frontier-firewall pass

Continues from the green PR #19 head at `958d4c28cc8955b89cd4e19fe6350c2bf752af9` on `chatgpt/cfb-semantic-closure-v3-20260904` through PR #20. The canonical integration branch remains `integration/v6-ml-architecture-20260830`; `main` is untouched.

Closed this pass:

- interim frontier state is explicit: `FRONTIER_INTERIM` / `AWAITING_FRONTIER_RESEARCH`;
- interim runs emit `frontier_checkpoint.json` without a frozen forecast hash, hash sidecar, FrozenForecast ledger row, or settlement eligibility;
- postgame verification and GitHub archive certification fail closed when the frozen artifact is absent or interim;
- final freeze binds state and frontier checkpoint hashes, and only request-complete bundles or the established engineering fixture mode can reach the final freeze artifact;
- MaterialFact resolution deduplicates same-lineage claims, resolves latest-as-of claims, records explicit states, and holds unresolved contradictions conservatively;
- conformal widening remains inactive at `LR000000` until chronological unseen settlement evidence earns calibration;
- bootstrap, reference-architecture, dynamic-control, and universal-trace documents make the ChatGPT-native and post-freeze boundaries explicit.

Measured:

- CI run 242 passed: pytest stage, algorithm constitution check, generated inventory check, and benchmark smoke;
- pytest coverage is 439 tests; generated inventory is 272 modules / 1,949 symbols with hash `93bf2cba429490decfdfd89dbce57973348e121ea521e63da40b0835d0117a1c`;
- benchmark smoke remains engineering-synthetic throughput only; host-performance certification is not earned.

Not earned:

- current live CFB HAR and host-acquired evidence;
- prospective settlements, calibration promotion, or any LR/predictive claim;
- production-root or host-performance certification;
- exact P380X donor ZIP bytes and mixed-sport R1 completion.

Verdict: `CFB_REFERENCE_IMPLEMENTATION_SOFTWARE_COMPLETE` for the declared CFB software path. Current-HAR operational acceptance remains `CFB_CURRENT_HAR_OPERATIONAL_ACCEPTANCE_PENDING`. Do not merge to `main`.

## 2026-09-04 Luna Max completion-context implementation pass

Continues on `chatgpt/cfb-production-closure-v2-20260904` through implementation commit `1d2490ceef086248a00d27866574ab7b7ad7c3bf` and generated-inventory repair commits `16138a4b1efc7a48e62f5c2ac79b8242f5294f0c` / `5bc75dced241a3081b16363b9a54b22663a00497`; draft PR #21 targets `integration/v6-ml-architecture-20260830`. Current branch head is `d6cebdc2a8ef4ecc738cacec452086d0f59dd5d9`; required GitHub CI runs #248, #249, and #250 are green; `main` is untouched.

Closed in software for the declared CFB/offline scope:

- durable exact-first cache payload-hash verification with fail-closed fallback;
- deterministic source-health and checkpoint timing, fsync/publish validation, idempotent checkpoint outbox, and local reconciliation;
- safe HAR ingress summaries with raw bytes/path values excluded from manifests, logs, archives, GitHub, and Drive;
- live CFB signal registry/executor/FeatureStore consumption with output hashes;
- temporal MaterialFact succession/correction handling and runtime lineage;
- explicit CFB statistical-versus-platform authority, field semantics, identity rules, and 19 active-market settlement mappings;
- reject-only decision integrity and operational Run/Job/InputDataset/HAROffer/ResearchRequirement/AcquisitionAction/MaterialFact/EventWorld/ProbabilityBundle/Decision/Portfolio/FrozenForecast/SignalEvaluation lineage nodes;
- generated code inventory and algorithm registry artifacts.

Measured acceptance:

- focused completion-context, lineage, and archive tests: **30 passed**;
- broad non-historical suite: **442 passed**;
- source compile, generated inventory check, algorithm registry check, and algorithm frontier benchmark smoke: **PASS**;
- fresh wheel: **PASS**, SHA-256 `c8b2adb426207d53d84c3e198c5a26f7084c1f21c248e0f688aa4b19ab601c5f`;
- fresh synthetic run: 6 rows, 2 modeled, 0 Playables, `RESEARCHED_MODELED_TOP25`, production root false;
- fresh supplied HAR: 4,307 rows; account-only and full fixture runs completed with 0 Playables; full run emitted 19 active CFB mappings, safe boundary/checkpoint artifacts, and a 143,293-node / 283,371-edge operational EvidenceGraph;
- supplied HAR accounting: 4,248 CFB rows, 948 Goblins excluded only after accounting, 164 model-eligible rows, 3,122 unresolved side rows, 14 unsupported CFB rows, 40 CFB events, 824 subjects, 80 teams;
- raw supplied HAR SHA-256 `ad3a10271c511266c1a52869658362e07002aad9f453eb77108f35c82e2f96d7`; raw artifact was not committed or uploaded.

Execution-closure gates:

| Gate | State | Evidence / boundary |
|---|---|---|
| G0_SESSION_TRUTH | PASS | capability/timebox, authority, input hash, branch, and run manifests emitted |
| G1_PRIVACY_BOUNDARY | PASS | raw ingress quarantined; fresh archive integrity passed; safe summaries only |
| G2_RESTARTABLE_STATE | PASS_WITH_EXTERNAL_READBACK | crash-safe local checkpoint/outbox/reconciliation tests pass; final Drive/GitHub checkpoint readback and required CI run #248 recorded |
| G3_RUNTIME_CONSUMPTION | PASS_FOR_DECLARED_CFB_SCOPE | signals, rules, decisions, checkpoints, and lineage are consumed by the canonical runner |
| G4_LINEAGE_SCHEMA | PASS_FOR_DECLARED_CFB_SCOPE | canonical content hashes and explicit edge provenance validated |
| G5_CFB_RULES | PARTIAL | 19/19 mappings and dated snapshot emitted; platform settlement authority is not verified for production |
| G6_EVALUATION_FIREWALL | PASS_OFFLINE | cutoff/accounting/full-population/future-only guards pass; calibration evidence is absent |
| G7_RELEASE | PARTIAL | fresh wheel and E2E runs pass; host-performance/current-live research remain unverified; required remote CI run #250 passed |

Unearned states remain explicit: `SOFTWARE_CLOSED=PASS` for the declared offline scope; `HAR_ACCOUNTING_ACCEPTED=PASS`; `OPERATIONAL_ACCEPTED_WITH_CURRENT_HAR=PARTIAL`; `PREDICTIVE_CERTIFIED=DEFERRED`; `PRODUCTION_ROOT_CERTIFIED=FAIL`. Learning remains `LR000000`, predictive claim `NONE`, and no production picks are issued.

The unfiltered historical suite is not claimed green: four tests remain externally blocked because the repository's legacy `prizepicks_20260829.sanitized.har` is an empty fixture while its tests require 11,113 rows. No replacement rows were fabricated.

## P380X Tranche A/B status

Tranche A accounts for all 58 principal donor components without activating any of them. Exact donor ZIP bytes were not available, so the recorded archive state is `EXACT_ARCHIVE_BYTES_UNAVAILABLE`; the disposition matrix is doctrine/reference data outside the runtime package.

Tranche B provides an executable typed `SignalOperatorSpec`, deterministic compiler/registry, lifecycle and consumer activation gates, SportPlugin/MarketDefinition/unit/temporal validation, dependency DAG and cycle rejection, semantic duplicate suppression, overlap groups, a compact executor, and a canonical FeatureStore consumer. This completes the bounded governance foundation, not the later donor capabilities. No donor forecasting operator is production-active merely because its matrix entry exists.

## Definition of “finished”

The DCM is not “finished” because modules exist. A subsystem reaches 10/10 only when:

1. the runtime calls it on the canonical path;
2. unsupported inputs fail closed;
3. no fixture/stub can create production output;
4. inputs/outputs have explicit schemas and semantic hashes;
5. deterministic tests cover positive, negative, temporal and resume cases;
6. the audit graph can trace outputs to evidence and code/release identity;
7. the portable wheel works outside the repository;
8. ChatGPT can drive it through the host-native contract without knowing internal module topology;
9. the subsystem’s status is reflected in `PROGRAM_STATUS.md`, the universal matrix, and a pass log;
10. any unearned predictive/learning claim remains closed.

## Required repository control files

- `AGENTS.md` — coding-agent law, including Algorithmic Constitution inheritance.
- `docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md` — permanent inherited constitution.
- `configs/algorithm_registry.json` — machine-readable algorithm registry.
- `docs/PROGRAM_STATUS.md` — human dashboard.
- `docs/PROGRAM_STATUS.json` — machine-readable workstream registry.
- `docs/UNIVERSAL_IMPLEMENTATION_MATRIX_20260831.md` — detailed subsystem audit.
- `docs/CURRENT_WORK_HANDOFF.md` — current clean continuation point.
- `docs/engineering_passes/` — append-only pass records.
- `docs/CHATGPT_NATIVE_EXECUTION_SPEC.md` — host/runtime contract.
- `scripts/build_code_inventory.py` — generated module/class/function inventory.
- `scripts/export_algorithm_registry.py` — catalog → committed registry bytes.

No agent may claim “complete” without updating these records and proving the corresponding tests.
Learning revision remains `LR000000`; predictive superiority remains `NONE`; production-root certification remains false.
