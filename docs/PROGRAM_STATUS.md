# DCM Program Status

Canonical integration line: `integration/v6-ml-architecture-20260830` at merge commit `cdb428f6a05406184fe265b0a1e81abec92cd1f9` (through PR #17 CFB guarded launch).

Active R0 delivery: `grok/r0-algorithmic-constitution-20260903` targeting integration only. No merge to `main` is authorized.

This file is the human dashboard. It must be updated on every coding pass together with a new immutable pass record under `docs/engineering_passes/`.

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
| P0 Canonical spine / HAR / integrity | 10 | 9 | STRONG PARTIAL | preserve authenticated v5.4.1 roots in release retrieval; production root remains independently gated |
| P1 Universal research / evidence | 10 | 8 | STRONG PARTIAL | R1 BoardGraph / MarketDemandGraph / RequirementGraph / live AcquisitionAction packing; current CFB HAR host research |
| P2 Feature / state / parameter layer | 10 | 9 | STRONG PARTIAL | validate CFB role-comparable/current/prior support on real boards; activate only evidence-backed signal operators |
| P3 SportPlugin physics | 10 | 6 | PARTIAL | operationally accept the guarded CFB market set on a current board; continue remaining 24-component plugin bindings sport by sport |
| P4 Probability / uncertainty / grading / portfolio | 10 | 8 | STRONG PARTIAL | prospective CFB settlement/calibration evidence; universal shared-world/correlation coverage; final-refresh integration |
| P5 Audit / portability / ChatGPT-native execution | 10 | 8 | STRONG PARTIAL | current-HAR fresh ChatGPT acceptance; immutable release retrieval |
| P6 Settlement / calibration / learning | 10 | 6 | PARTIAL + EXTERNAL VALIDATION | exact platform coverage; CFB prospective settlements; CRPS/subgroups; chronological unseen settlements before promotion |
| P7 Host-native execution contract | 10 | 7 | PARTIAL | current CFB HAR forecast through host CLI on a fresh wheel; no second engine |
| P8 Universal source acquisition | 10 | 6 | PARTIAL | live adapter fetch beyond fixtures; conflict policy + licensed providers |
| P9 Universal core migration | 10 | 9 | STRONG PARTIAL | retire remaining PLAYER/TEAM claim lookups at packet/parameter adapters |
| P10 Full sport coverage | 10 | 3 | EARLY | each supported sport reaches 24/24 plugin components + validation suite |
| P11 Release + fresh-environment acceptance | 10 | 7 | PARTIAL | wheel/release + exact hash + current HAR-only fresh ChatGPT acceptance |
| P12 Research archive / index / reuse | 10 | 7 | PARTIAL | high-volume queryable store; retention/licensing enforcement beyond local blobs |
| P13 Performance / search / token optimization | 10 | 6 | PARTIAL | measured CPU/RSS/token certification; host-performance remains uncertified |
| P14 Production operations / observability | 10 | 5 | PARTIAL | run health/readiness, failure taxonomy, deterministic recovery, release gates |
| P15 P380X donor signal governance | 10 | 7 | PARTIAL | Tranche C research truth; exact donor definition compilation only from available archive bytes; evidence-earned activation only |
| P16 Algorithmic Constitution / strategy registry | 10 | 8 | STRONG PARTIAL | R0 complete in software: constitution, registry, selection engine, HAR plan, CI gates. R1 live Research OS graphs remain |

Constitution version `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903` is inherited. Learning revision remains `LR000000`; predictive superiority remains `NONE`; production-root certification remains false.

## R0 Algorithmic Constitution status

Implemented and tested on this branch:

- Permanent constitution document, schema, catalog-generated registry, and SHA-256 of exact committed registry bytes.
- `AlgorithmSelectionEngine` prefers cheapest exact deterministic strategies; HNSW/Leiden/CP-SAT conditionals emit evaluation telemetry when not activated.
- HAR `algorithm_execution_plan.json` is persisted by the canonical runner before research.
- Ranking uses Timsort for the full modeled population and heap partial Top-K for frontier isolation.
- Research batching consumes weighted set-cover as coverage telemetry and heap Top-K for event ordering without replacing EvidenceGraph/ResearchStore.
- Release manifests and `hashes.json` carry constitution/registry hashes; those hashes are excluded from `_CONTEXT_FIELDS` forecast identity.
- Governance tests under `tests/governance/` and CI `--check` gates prevent silent algorithm omission.

Not claimed by R0:

- BoardGraph / MarketDemandGraph / RequirementGraph / live AcquisitionAction packing (R1);
- Drive-first indexed retrieval as the primary query engine (storage law remains documented; existing ResearchStore/archive path is unchanged);
- live mixed-sport HAR research OS acceptance;
- production-root certification;
- predictive superiority.

## 2026 CFB guarded-launch status — merged via PR #17

The PR #17 branch established a bounded College Football guarded-launch path without claiming universal football completion or predictive validation. It is now on the integration HEAD above.

Implemented and tested:

- HAR accounting remains first; platform modifiers are handled after extraction and existing fail-closed integrity rules remain intact.
- CFB research completeness is evaluated per prop for modeling instead of using unrelated global missing evidence as a blanket board veto.
- Zero real evidence still preserves the existing `RESEARCH_REQUIRED / INCOMPLETE_CHECKPOINTED` fail-closed path.
- Minimum model support is separate from strict PLAYABLE support.
- Thin but defensibly parameterized rows may be `MODELED_DIAGNOSTIC`; diagnostic state cannot bypass the PLAYABLE firewall.
- Supported guarded-launch physical markets are `pass_yds`, `pass_att`, `pass_cmp`, `rush_yds`, `rush_att`, `rec_yds`, `receptions`, `pass_rush_yds`, and `rush_rec_yds`.
- Opportunity-only markets do not require irrelevant yardage-efficiency evidence; markets that depend on efficiency still require relevant efficiency support.
- ParameterSnapshots expose current-season, prior-season and role-comparable support plus explicit CFB role state.
- Explicit early-season role states include returning starter/rotation, promoted starter, transfer starter/rotation, true freshman, new QB, new coordinator/system, injury return and role uncertain.
- Transfer history is retained as evidence but prior-school opportunity share is not carried over 1:1.
- CFB EventWorld context includes competitive, controlled-lead and blowout/starter-curtailment workload regimes; these affect opportunity rather than directly forcing Higher/Lower.
- ChatGPT-native CFB research instructions request current 2026 and prior 2025 history, current team/opponent/event/venue/weather, depth/availability/transfer/system changes, team tendencies and opponent defense where market-relevant.
- Dedicated acceptance tests prove 8/8 fixture offers reach probability evaluation and that real-shaped partial evidence can continue per supported CFB prop while the overall bundle remains incomplete.

Not earned by the guarded launch:

- prospective CFB calibration;
- learned reliability thresholds;
- historical settlement validation sufficient for promotion;
- expanded exotic football markets;
- full 24/24 SportPlugin coverage;
- complete universal Research OS;
- production-root certification;
- host performance certification;
- predictive superiority.

A current September 2026 live CFB HAR has not been supplied. The existing sanitized August 29, 2026 HAR remains historical accounting evidence, not a current forecast acceptance.

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
