# DCM universal implementation matrix — 2026-08-31

Baseline refreshed through PR #19 CFB reference-implementation consumer pass on `grok/cfb-guarded-launch-today-20260903`. R0 constitution remains inherited. This matrix is code-path status, not predictive validation. LR remains
`LR000000`; predictive superiority remains `NONE`. Constitution version: `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`.

CFB software reference path is executable (19 ACTIVE markets, holdPlayable consumer, retrieval cascade queried, RoleEpoch EWMA/CUSUM/Page-Hinkley, JOINT_TEAM EventWorlds, archive retry/reconcile). Current-HAR acceptance is `CURRENT_REAL_HAR_ACCEPTANCE_PENDING_EXTERNAL_INPUT`.

Status meanings:

- **COMPLETE** — executable current path, runtime-integrated, tested and auditable for its stated scope.
- **PARTIAL** — real implementation exists but the universal/production contract is not yet fully satisfied.
- **STUB** — named production surface exists but is materially placeholder behavior.
- **MISSING** — required subsystem has no adequate implementation.
- **INCORRECT** — implementation exists but violates the universal directive or a hard invariant.
- **OBSOLETE** — superseded compatibility/prototype architecture that must not become canonical.

## P16 — Algorithmic Constitution (R0)

| Subsystem | Status | Evidence / action |
|---|---|---|
| Constitution document | COMPLETE for R0 | `docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md` loaded and hashed by `dcm.algorithms.constitution`. |
| Algorithm registry | COMPLETE for R0 | `configs/algorithm_registry.json` generated from `dcm.algorithms.catalog`; CI stale-check. |
| AlgorithmSelectionEngine | COMPLETE for R0 | Cheapest exact first; conditionals emit evaluation telemetry. |
| HAR AlgorithmExecutionPlan | COMPLETE for R0 | Runner persists `algorithm_execution_plan.json` before research. |
| ChatGPT-native CORE primitives | COMPLETE for R0 | Searching/indexing/sorting/grouping/scheduling/cache/stdlib ML in `dcm.algorithms`. |
| Weighted set-cover / submodular | COMPLETE as primitives | Registered CORE; live AcquisitionAction packing remains R1. |
| Silent retirement CI | COMPLETE for R0 | `tests/governance/` plus registry `--check`. |
| BoardGraph / RequirementGraph / AcquisitionAction | CFB COMPLETE for declared scope | Guarded CFB path emits graphs, live CELF packing, ResearchOSReadiness before research. Mixed-sport R1 remainder remains. |
| Drive-first indexed retrieval | PARTIAL + BLOCKED_EXTERNAL | Local DriveObjectCatalog identifies exact objects then fail-closes `NOT_CONFIGURED`. Drive credentials are external. |

## P0 — canonical spine / integrity

| Subsystem | Status | Evidence / action |
|---|---|---|
| Python single canonical engine | COMPLETE | Python runner is authoritative; viewer/UI is not a second probability engine. |
| Exact v5.4.1 root authentication | COMPLETE as root-of-trust verification | Exact source (3,222,380 bytes) and learning ledger (3,953,122 bytes) match both frozen SHA-256 values. Repository-local runtime mounting/release retrieval remains separate; production root remains closed. |
| Learning revision / predictive claim separation | COMPLETE | LR000000 and predictive NONE remain explicit. |
| HAR board accounting | COMPLETE for current supported capture paths | Existing P0–P8 tests enforce accounting, Goblin exclusion after counting, side/modifier fail-closed and started-event gates. |
| Green Goblin prohibition | COMPLETE | Extract/account then exclude from selectable population. |
| Red Demon stronger cushion | COMPLETE for current selection path | Existing grading/selection gates retain stricter modifier handling. |
| Offered-sides-only | COMPLETE | Unknown/unoffered side fails closed. |
| Temporal cutoff / event-start firewall | COMPLETE | Explicit decision cutoff and final start/status hard blockers. |
| Split certification semantics | COMPLETE | Archive/evidence/temporal/model/selection/root/predictive flags are separate; `locksCertified` is absent from canonical state and exists only as a compatibility helper function. |
| One canonical integration line | PARTIAL → converging | PR #10 is the single current architecture integration line. The prior universal-core and SportPlugin child PRs have been folded back into it. |
| Portable clean-environment install | COMPLETE for engineering runtime | CI installs package from repo root, runs CLI from clean cwd and synthetic E2E. Production data/root certification remains closed. |

## P1 — universal entity and research layer

| Subsystem | Status | Evidence / action |
|---|---|---|
| Universal entity vocabulary | COMPLETE (container layer) | `EntityKind`/references cover Sport, Competition, Event, Side, Affiliation, Subject, Counterparty, Environment, MarketDefinition and Offer. |
| SubjectOfferSet | COMPLETE | Canonical `Subject + Event`; non-player FIGHTER test proves no Player fabrication. |
| PlayerOfferSet | OBSOLETE as canonical / compatibility-only | Now generated one-way from PLAYER SubjectOfferSets for old consumers. |
| Complete Research Population | COMPLETE (canonical population construction) | V2 manifest contains universal entities and fan-out counts. |
| ResearchDependencyGraph | COMPLETE (first executable graph) | Universal node types only; no Player/Team nodes. |
| Universal host research plan | COMPLETE (planning artifact) | Emits reusable entity tasks and universal research questions. |
| Legacy TEAM/PLAYER request planner | OBSOLETE as canonical / adapter-only | `plan_research` now emits SPORT/COMPETITION/EVENT/AFFILIATION/SUBJECT/COUNTERPARTY/ENVIRONMENT/MARKET_DEFINITION/OFFER. PLAYER/TEAM remain lookup aliases inside adapters/coverage/packets. |
| SourceAdapterRegistry | PARTIAL | Versioned `source_catalog.json` plus basketball/official/platform adapters. Live fetch remains opt-in; no licensed provider is a hard dependency. |
| SportResearchSchema | PARTIAL to strong for guarded CFB | Basketball/gridiron semantic coverage is consulted for SUBJECT/AFFILIATION/COUNTERPARTY/EVENT/ENVIRONMENT. CFB host instructions now explicitly request 2026+2025 history, role/depth/transfer/system state, team tendencies, opponent defense, event and environment context. Remaining sports fail closed. |
| SubjectResearchPacket | PARTIAL | Universal wrapper + compatibility PlayerResearchPacket. |
| AffiliationResearchPacket | PARTIAL | Universal wrapper over team packets. |
| CounterpartyResearchPacket | PARTIAL | Canonical COUNTERPARTY requests; opponent packet still reuses affiliation evidence. |
| EventResearchPacket | PARTIAL | Current team-sport event packet plus universal wrapper. |
| EnvironmentResearchPacket | PARTIAL | First-class ENVIRONMENT requests and packet wrapper; sport-specific weather/surface still plugin-owned. |
| Canonical normalization | PARTIAL | Basketball/gridiron normalized histories exist; every production sport does not yet own a complete CanonicalStatSchema/HistoricalPerformanceSchema. |
| EvidenceGraph | COMPLETE (universal topology), PARTIAL (settlement-time freeze join) | V2 graph uses Subject/Affiliation/Counterparty. Freeze now attaches Feature, RoleState, ParticipationState, OpportunityState, EfficiencyState, ParameterSnapshot, Simulation, PropEvaluation, Selection, Forecast. Settlement/LearningObservation live in `settlement_lineage.json` so freeze bytes stay append-only. |
| Semantic evidence coverage | PARTIAL | Real field-level gates exist for basketball/gridiron; must move under SportResearchSchema instead of legacy PLAYER/TEAM branching. |
| Research cache / temporal evidence | COMPLETE for current provider path | As-of cache and pre-cutoff claim validation are executable. |
| Automatic host web acquisition | PARTIAL | `dcm-host next-research` + evidence-import is executable. CFB uses the same canonical ResearchStore/EvidenceGraph path with market-specific instructions and per-prop sufficiency. The host still performs the actual web fetch; Python never fabricates research. Current-live-HAR fresh ChatGPT acceptance remains open. |

## P2 — ML data / state layer

| Subsystem | Status | Evidence / action |
|---|---|---|
| Immutable-as-of FeatureStore | PARTIAL | Feature families now include IDENTITY/PARTICIPATION/ROLE/OPPORTUNITY/EFFICIENCY/AFFILIATION/COUNTERPARTY/MATCHUP/EVENT/ENVIRONMENT/RECENCY/WORKLOAD/AVAILABILITY/MARKET/PLATFORM. Packet-shaped basketball/gridiron observations remain. |
| RoleStateModel | PARTIAL to strong for guarded CFB | Explicit CFB states cover returning starter/rotation, promoted starter, transfer starter/rotation, true freshman, new QB, new coordinator/system, injury return and role uncertain. Transfer opportunity does not carry over 1:1; universal SportPlugin-defined RoleStateSchema remains incomplete. |
| ParticipationModel | COMPLETE for basketball/gridiron current path / PARTIAL universal | `dcm.model.participation.ParticipationModel` fits minutes (basketball) and snaps (gridiron) independently; OpportunityModel consumes that output. Other sports fail closed. |
| OpportunityModel | PARTIAL to strong for guarded CFB | Explicit opportunity modeling now includes CFB pass/rush/routes workloads plus competitive/controlled-lead/blowout starter-curtailment regimes. Opportunity-only market sufficiency is independent of irrelevant efficiency evidence. General sport-neutral dispatch is incomplete. |
| EfficiencyModel | PARTIAL | Explicit efficiency separation exists in current engines. CFB yardage/conversion markets retain relevant efficiency support requirements while opportunity-only markets do not. General sport-neutral dispatch is incomplete. |
| Hierarchical shrinkage / role-comparable history | PARTIAL | Current packet/state logic has support/shrinkage concepts; not all sports have validated implementations. |
| Availability state / mixture | COMPLETE for current team-sport path | Active/out/questionable logic is executable and selection-blocking where required. |
| ParameterSnapshot | PARTIAL to strong for guarded CFB | Snapshots expose layered SUBJECT/AFFILIATION/COUNTERPARTY/EVENT/ENVIRONMENT/MARKET/AVAILABILITY/PARTICIPATION/OPPORTUNITY/EFFICIENCY containers plus evidence-hash lineage. CFB snapshots also expose minimum model support, strict PLAYABLE support, current/prior/role-comparable sample counts, role state and event-regime parameters. PLAYER/TEAM remain compatibility scopes_used. |
| ML model registry with training metadata | PARTIAL | Governance pieces exist; not every active parameter model is an earned trained ML champion. |
| No-fake-ML gate | COMPLETE as doctrine/gate | Predictive superiority remains NONE and LR000000; engineering simulations are not mislabeled trained superiority. |
| Governed signal operators | PARTIAL, executable foundation | Tranche B provides typed contracts, SportPlugin/MarketDefinition/unit/cutoff validation, deterministic DAG compilation, semantic dedupe/overlap groups, consumer/test activation gates, executor audit hashes, and a FeatureStore consumer. No donor operator is active from documentation alone; Tranche C+ capabilities remain future work. |

## P3 — sport physics

| Subsystem | Status | Evidence / action |
|---|---|---|
| SportPlugin contract | PARTIAL, executable | Full 24-component universal contract is now import-validated and emitted per run. Basketball/gridiron bindings expose exact IMPLEMENTED/PARTIAL gaps; `productionCompleteSports=[]` until every required component is IMPLEMENTED. |
| Basketball deep plugin | PARTIAL to strong | Joint worlds, minute conservation, market derivation and current research packets exist; still needs migration behind full SportPlugin contract and prospective validation. |
| Gridiron deep plugin | PARTIAL to strong | Guarded NFL/CFB physical support includes pass_yds, pass_att, pass_cmp, rush_yds, rush_att, rec_yds, receptions, pass_rush_yds and rush_rec_yds. CFB role-state, per-prop research sufficiency and workload-regime paths are executable; full universal plugin contract, exotic markets and prospective validation remain. |
| Baseball plugin | PARTIAL / SHADOW | MLB remains shadow, not production. |
| Combat, soccer, hockey, tennis, golf, esports, motorsport, etc. | MISSING or RESEARCH_ONLY for production depth | Universal architecture may name them; production capability has not been earned. |
| Joint EventWorld | COMPLETE for some current supported team-sport paths / PARTIAL universal | Shared event resources are modeled where implemented. CFB adds a shared competitive/controlled-lead/blowout regime draw that modifies opportunity/workload rather than directly forcing a prop side; not every sport has physics. |
| Resource competition | PARTIAL | Basketball joint minute/resource constraints exist; broader sport-specific resource competition varies. |
| PrimitiveOutcomeLedger | PARTIAL | Primitive/conservation infrastructure exists for current deep plugins; universal production coverage incomplete. |
| Conservation rules | COMPLETE where registered / PARTIAL universal | Fail-closed conservation checks exist; every future sport still needs its own suite. |
| MarketDefinitionRegistry | PARTIAL | Supported current markets are explicit; complete platform×sport×competition×period×DNP/reboot semantics are not universal yet. |
| Segment/period worlds | PARTIAL | Quarter support remains incomplete in current inventory; broader inning/set/round/map/hole segmentation is not complete. |

## P4 — forecast / selection layer

| Subsystem | Status | Evidence / action |
|---|---|---|
| P(MORE)/P(LESS)/P(PUSH) | COMPLETE for current modeled markets | Push-aware probability contract exists. |
| Raw/calibrated/evidence-safe probability separation | COMPLETE as output contract | Calibration remains unearned/limited where chronological settlements are absent. |
| Aleatoric/epistemic/MC uncertainty separation | PARTIAL to strong | Current probability bundle separates uncertainty classes; universal model-specific uncertainty still expands with plugins. |
| Reliability/DataQuality/Volatility/Fragility separation | COMPLETE as doctrine/output | Not conflated with probability. |
| Line surface / unclamped tolerance | COMPLETE for serious current candidates | Existing line-surface logic retained. |
| PLAYABLE/LEAN/PASS/TRAP grading | COMPLETE for current path | No forced Playables. CFB `MODELED_DIAGNOSTIC` rows cannot use diagnostic modeling as a loophole to become PLAYABLE when strict evidence/role support is incomplete. |
| Demon stricter gates | COMPLETE | Modifier cannot promote weak selection. |
| Top 25 ranked vs qualified separation | COMPLETE | Ranked Top25 is not synonymous with bets; qualified list unpadded. |
| 0–6 card | COMPLETE | No forced six, no Lean padding. |
| Correlation/dependency portfolio controls | PARTIAL to strong | Existing unique-subject/event/conflict controls exist; universal simulated correlation/shared failure path coverage must expand with new sport worlds. |
| Final status/start refresh | PARTIAL | Hard gates exist; source freshness/late lineup/weather refresh depends on host evidence acquisition completeness. |
| Frozen forecast hash/lineage | COMPLETE for current runtime | Deterministic freeze artifacts exist. |

## P5 — audit / portability

| Subsystem | Status | Evidence / action |
|---|---|---|
| Deterministic audit pack | COMPLETE for current runtime | Run archive/hashes/integrity artifacts exist. |
| GitHub archive integration | COMPLETE engineering path | Host/CLI archive path exists without making model depend on Git auth. |
| Evidence trace from selection to source | COMPLETE in EvidenceGraph V2 for current packet path | Canonical trace is Offer→Subject→Claim→SourceDocument. |
| Feature→Parameter→Simulation→Selection full graph trace | PARTIAL to strong | Runtime graph is populated at freeze. Settlement/LearningObservation is a sidecar (`settlement_lineage.json`) so frozen forecast bytes are not rewritten. |
| Wheel/runtime ZIP/release manifest/SHA manifest | PARTIAL to strong | Release tooling exists and clean install is exercised in CI. Fresh-host execution still requires a canonical release artifact that is actually mounted/retrievable in the ChatGPT execution environment; GitHub read access alone is not sufficient. |
| No secret/raw private HAR archive | COMPLETE as security invariant | Current HAR/evidence sanitization and URL credential checks remain. |

## P6 — settlement / learning

| Subsystem | Status | Evidence / action |
|---|---|---|
| Full-board settlement | PARTIAL to strong | Settlement population/ledger tests exist for modeled populations; sport/platform exact rules are incomplete across universal coverage. |
| PrizePicks reboot/DNP rules | PARTIAL to strong | Current rule snapshots exist; platform/market expansion remains. |
| Learning Ledger immutability | COMPLETE as governance path | Historical forecasts are not retrospectively rewritten. |
| Proper scoring metrics | PARTIAL | Brier/log-loss/calibration infrastructure exists; CRPS/subgroup reporting and sufficient chronological samples remain incomplete. |
| Training dataset builder | PARTIAL | Dataset/sidecar infrastructure exists; universal feature lineage and mature settled population are not complete. |
| Walk-forward validation | PARTIAL | Governance exists; predictive promotion is not earned. |
| Champion/Challenger | PARTIAL | Promotion doctrine exists; no justified new Learning Revision yet. |
| Learning Revision promotion | COMPLETE as fail-closed governance, inactive | LR000000 correctly remains because prospective evidence has not earned promotion. |

## Highest-priority next code migrations

1. Run an actual current CFB HAR through ChatGPT-native research → EvidenceGraph → ParameterSnapshots → CFB EventWorld → probability/uncertainty → grading/ranking/freeze; treat this as operational acceptance, not redesign.\n2. Begin prospective CFB settlement capture and calibration evidence without promoting LR000000 prematurely.\n3. P380X Tranche C: Research Truth Integration using the existing StatePack/EvidenceGraph/freshness path.
2. Drive a fresh-host wheel+HAR acceptance test through `dcm-host` without a source checkout.
3. Close remaining PLAYER/TEAM claim lookups so they exist only inside source/sport adapters.
4. Close remaining PARTIAL SportPlugin bindings (FeatureSchema, EnvironmentModel, MarketDefinitionRegistry/minimal, ValidationSuite).
5. Finish one reference sport end to end under the 24-component interface.
6. Accumulate chronological settlements before any predictive or Learning Revision promotion.

## P7–P14 completion program

The detailed P0–P6 matrix remains the modeling/system audit. The following workstreams make the entire system operable and maintainable as a long-lived ChatGPT-first platform:

| Workstream | State | Required finish |
|---|---|---|
| P7 Host-native execution | PARTIAL | `dcm-host` / `python -m dcm.chat` / `HostSession` implemented over the existing runner: doctor, prepare, next-research, evidence-import, coverage, forecast, report, resume, audit, settle, archive, cfb-launch. Not 10/10: fresh-wheel current-HAR acceptance remains. |
| P8 Universal source acquisition | PARTIAL | Versioned source catalog, event-first batching, schema-driven coverage extras, host-observation import. Live fetch remains opt-in. |
| P9 Universal-core migration | STRONG PARTIAL | Planner/provider canonical scopes are universal. PLAYER/TEAM survive as adapter aliases and compatibility projections. |
| P10 Full sport coverage | EARLY | Every promoted sport independently satisfies all 24 SportPlugin components and plugin validation; unsupported sports fail closed. |
| P11 Release/fresh-host acceptance | PARTIAL | Exact wheel+manifest+hash retrieval and a fresh ChatGPT HAR-only acceptance test with no source checkout/prior memory. |
| P12 Research archive/index/reuse | PARTIAL | Content-addressed `ResearchStore` hydrates blobs (not pointers) for delta classification, entity/source/as-of indexes, append-only game-log merge, outcome memory that cannot decide reuse, and DAG invalidation by delta class. High-volume DB/object store still future. |
| P13 Performance/search/token optimization | PARTIAL | Fan-out × importance × freshness × uncertainty / cost scheduler, CELF live AcquisitionAction packing on the CFB path, and event batching exist. Host performance is not certified. |
| P14 Production operations/observability | PARTIAL | Host doctor, run_manifest, host_state, engineering-pass ledger. Full ops health/recovery remains. |
| P15 P380X donor signal governance | PARTIAL | Tranche A/B is executable and tested: 58/58 dispositions, zero implicit activations, typed compiler/registry/executor, deterministic hashes, semantic/cross-sport/unit/cutoff gates, and FeatureStore consumer. Research-truth, matchup, decision, learning, and portfolio donor tranches are not implemented by this pass. |

See `docs/PROGRAM_STATUS.md`, `docs/PROGRAM_STATUS.json`, `docs/CHATGPT_NATIVE_EXECUTION_SPEC.md`, and `docs/engineering_passes/`.
