# DCM Program Status

Canonical integration line: `integration/v6-ml-architecture-20260830` at merge commit `8311b2aaeef16b508b6ef21c01c22ad990b9ad5d` (through PR #15).

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
| P1 Universal research / evidence | 10 | 8 | STRONG PARTIAL | live host observation loop closing SportResearchSchema coverage; remaining adapter PLAYER/TEAM lookups |
| P2 Feature / state / parameter layer | 10 | 9 | STRONG PARTIAL | activate only validated signal operators with real producers/consumers; packet-shaped FeatureStore observations |
| P3 SportPlugin physics | 10 | 6 | PARTIAL | close remaining 24-component plugin bindings sport by sport; no generic production fallback |
| P4 Probability / uncertainty / grading / portfolio | 10 | 8 | STRONG PARTIAL | universal shared-world/correlation coverage; final-refresh integration |
| P5 Audit / portability / ChatGPT-native execution | 10 | 8 | STRONG PARTIAL | exact-wheel fresh ChatGPT HAR acceptance; immutable release retrieval |
| P6 Settlement / calibration / learning | 10 | 6 | PARTIAL + EXTERNAL VALIDATION | exact platform coverage; CRPS/subgroups; chronological unseen settlements before promotion |
| P7 Host-native execution contract | 10 | 7 | PARTIAL | forecast/settle through host CLI on a fresh wheel+HAR; no second engine |
| P8 Universal source acquisition | 10 | 6 | PARTIAL | live adapter fetch beyond fixtures; conflict policy + licensed providers |
| P9 Universal core migration | 10 | 9 | STRONG PARTIAL | retire remaining PLAYER/TEAM claim lookups at packet/parameter adapters |
| P10 Full sport coverage | 10 | 3 | EARLY | each supported sport reaches 24/24 plugin components + validation suite |
| P11 Release + fresh-environment acceptance | 10 | 7 | PARTIAL | wheel/release + exact hash + HAR-only fresh ChatGPT acceptance |
| P12 Research archive / index / reuse | 10 | 7 | PARTIAL | high-volume queryable store; retention/licensing enforcement beyond local blobs |
| P13 Performance / search / token optimization | 10 | 6 | PARTIAL | measured CPU/RSS/token certification; host-performance remains uncertified |
| P14 Production operations / observability | 10 | 5 | PARTIAL | run health/readiness, failure taxonomy, deterministic recovery, release gates |
| P15 P380X donor signal governance | 10 | 7 | PARTIAL | Tranche C research truth; exact donor definition compilation only from available archive bytes; evidence-earned activation only |

## P380X Tranche A/B status

Tranche A accounts for all 58 principal donor components without activating any of them. Exact donor ZIP bytes were not available, so the recorded archive state is `EXACT_ARCHIVE_BYTES_UNAVAILABLE`; the disposition matrix is doctrine/reference data outside the runtime package.

Tranche B provides an executable typed `SignalOperatorSpec`, deterministic compiler/registry, lifecycle and consumer activation gates, SportPlugin/MarketDefinition/unit/temporal validation, dependency DAG and cycle rejection, semantic duplicate suppression, overlap groups, a compact executor, and a canonical FeatureStore consumer. This completes the bounded governance foundation, not the later donor capabilities. No donor forecasting operator is production-active merely because its matrix entry exists.

Learning revision remains `LR000000`; predictive superiority remains `NONE`; production-root certification remains false.

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

- `AGENTS.md` — coding-agent law.
- `docs/PROGRAM_STATUS.md` — human dashboard.
- `docs/PROGRAM_STATUS.json` — machine-readable workstream registry.
- `docs/UNIVERSAL_IMPLEMENTATION_MATRIX_20260831.md` — detailed P0–P6 subsystem audit.
- `docs/engineering_passes/` — append-only pass records.
- `docs/CHATGPT_NATIVE_EXECUTION_SPEC.md` — host/runtime contract.
- `scripts/build_code_inventory.py` — generated module/class/function inventory.

No agent may claim “complete” without updating these records and proving the corresponding tests.
