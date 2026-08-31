# DCM universal implementation matrix — 2026-08-31

Baseline audited: PR #10 head `47f41c2617bec6eea62a5eecd90e3ffa1c1b0982`.
This matrix is code-path status, not predictive validation. LR remains
`LR000000`; predictive superiority remains `NONE`.

Status meanings:

- **COMPLETE** — executable current path, runtime-integrated, tested and auditable for its stated scope.
- **PARTIAL** — real implementation exists but the universal/production contract is not yet fully satisfied.
- **STUB** — named production surface exists but is materially placeholder behavior.
- **MISSING** — required subsystem has no adequate implementation.
- **INCORRECT** — implementation exists but violates the universal directive or a hard invariant.
- **OBSOLETE** — superseded compatibility/prototype architecture that must not become canonical.

## P0 — canonical spine / integrity

| Subsystem | Status | Evidence / action |
|---|---|---|
| Python single canonical engine | COMPLETE | Python runner is authoritative; viewer/UI is not a second probability engine. |
| Exact v5.4.1 root expectations | COMPLETE as gate | Expected source/ledger hashes are frozen; bytes are not mounted in repo, so production root remains closed. |
| Learning revision / predictive claim separation | COMPLETE | LR000000 and predictive NONE remain explicit. |
| HAR board accounting | COMPLETE for current supported capture paths | Existing P0–P8 tests enforce accounting, Goblin exclusion after counting, side/modifier fail-closed and started-event gates. |
| Green Goblin prohibition | COMPLETE | Extract/account then exclude from selectable population. |
| Red Demon stronger cushion | COMPLETE for current selection path | Existing grading/selection gates retain stricter modifier handling. |
| Offered-sides-only | COMPLETE | Unknown/unoffered side fails closed. |
| Temporal cutoff / event-start firewall | COMPLETE | Explicit decision cutoff and final start/status hard blockers. |
| Split certification semantics | COMPLETE | Archive/evidence/temporal/model/selection/root/predictive flags are separate; legacy `locksCertified` is derived compatibility only. |
| One canonical integration line | PARTIAL → converging | PR #10 is the current architecture integration line; PR #11 is stacked only to review this universal migration before folding back into #10. |
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
| Legacy TEAM/PLAYER request planner | OBSOLETE as canonical / ACTIVE compatibility | Still feeds current source-provider and sport-packet code; must be migrated behind adapter translation. |
| SourceAdapterRegistry | PARTIAL | Real basketball/official/platform adapters exist; provider coverage is not universal across every declared sport. |
| SportResearchSchema | PARTIAL | Semantic coverage exists for current basketball/gridiron paths, but no full generic SportResearchSchema registry with every required contract field. |
| SubjectResearchPacket | PARTIAL | Current PlayerResearchPacket is substantive and reused; universal SubjectResearchPacket container/adapter migration remains. |
| AffiliationResearchPacket | PARTIAL | Team packet is substantive for current team sports but remains sport-specific compatibility vocabulary. |
| CounterpartyResearchPacket | PARTIAL | Opponent packet reuses team evidence; universal counterparty kinds beyond team opponents are not yet implemented. |
| EventResearchPacket | PARTIAL | Current team-sport event packet exists; broader formats/course/map/fight/race semantics depend on future sport plugins. |
| EnvironmentResearchPacket | PARTIAL | Some event/weather/surface context exists; first-class universal environment acquisition is incomplete. |
| Canonical normalization | PARTIAL | Basketball/gridiron normalized histories exist; every production sport does not yet own a complete CanonicalStatSchema/HistoricalPerformanceSchema. |
| EvidenceGraph | COMPLETE (universal topology), PARTIAL (full lineage population) | V2 graph uses Subject/Affiliation/Counterparty; legacy claim scopes translate at boundary. Feature/Parameter/Simulation/Selection/Settlement nodes still need full runtime population. |
| Semantic evidence coverage | PARTIAL | Real field-level gates exist for basketball/gridiron; must move under SportResearchSchema instead of legacy PLAYER/TEAM branching. |
| Research cache / temporal evidence | COMPLETE for current provider path | As-of cache and pre-cutoff claim validation are executable. |
| Automatic host web acquisition | PARTIAL | Runtime emits host research plans/bundle contracts; actual web acquisition is host-agent work, not an in-engine HTTP scraper. Current adapter/provider translation is incomplete. |

## P2 — ML data / state layer

| Subsystem | Status | Evidence / action |
|---|---|---|
| Immutable-as-of FeatureStore | PARTIAL | Real feature-store artifacts exist; schema is still shaped by current basketball/gridiron packet paths rather than fully universal feature families. |
| RoleStateModel | PARTIAL | Role epochs/state logic exists for current subjects; universal SportPlugin-defined RoleStateSchema is incomplete. |
| ParticipationModel | PARTIAL | Basketball minutes/gridiron opportunity state paths exist; universal ParticipationState plugin contract is incomplete. |
| OpportunityModel | PARTIAL | Explicit opportunity modeling exists in current engines. General sport-neutral dispatch is incomplete. |
| EfficiencyModel | PARTIAL | Explicit efficiency separation exists in current engines. General sport-neutral dispatch is incomplete. |
| Hierarchical shrinkage / role-comparable history | PARTIAL | Current packet/state logic has support/shrinkage concepts; not all sports have validated implementations. |
| Availability state / mixture | COMPLETE for current team-sport path | Active/out/questionable logic is executable and selection-blocking where required. |
| ParameterSnapshot | PARTIAL | Real snapshots feed current simulations; universal layered SUBJECT/AFFILIATION/COUNTERPARTY/EVENT/ENVIRONMENT container coverage is incomplete. |
| ML model registry with training metadata | PARTIAL | Governance pieces exist; not every active parameter model is an earned trained ML champion. |
| No-fake-ML gate | COMPLETE as doctrine/gate | Predictive superiority remains NONE and LR000000; engineering simulations are not mislabeled trained superiority. |

## P3 — sport physics

| Subsystem | Status | Evidence / action |
|---|---|---|
| SportPlugin registry | PARTIAL | Capability manifests exist, but the full required contract (Identity/Research/CanonicalStats/Role/Participation/Opportunity/Efficiency/EventWorld/Primitive/Market/Calibration/Settlement/etc.) is not yet represented as one validated interface. |
| Basketball deep plugin | PARTIAL to strong | Joint worlds, minute conservation, market derivation and current research packets exist; still needs migration behind full SportPlugin contract and prospective validation. |
| Gridiron deep plugin | PARTIAL to strong | Opportunity/yardage worlds and current research paths exist; full universal plugin contract and broader market coverage remain. |
| Baseball plugin | PARTIAL / SHADOW | MLB remains shadow, not production. |
| Combat, soccer, hockey, tennis, golf, esports, motorsport, etc. | MISSING or RESEARCH_ONLY for production depth | Universal architecture may name them; production capability has not been earned. |
| Joint EventWorld | COMPLETE for some current supported team-sport paths / PARTIAL universal | Shared event resources are modeled where implemented; not every sport has physics. |
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
| PLAYABLE/LEAN/PASS/TRAP grading | COMPLETE | No forced Playables. |
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
| Feature→Parameter→Simulation→Selection full graph trace | PARTIAL | Required node types/edges are not yet fully populated end-to-end. |
| Wheel/runtime ZIP/release manifest/SHA manifest | PARTIAL to strong | Release tooling exists, but universal migration must be included and clean-environment release certification rerun. |
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

1. Replace host/provider canonical semantics with universal
   `SUBJECT/AFFILIATION/COUNTERPARTY/ENVIRONMENT` requests and keep
   `PLAYER/TEAM` only inside sport/source adapters.
2. Move field-level evidence requirements into a real per-sport
   `SportResearchSchema` registry.
3. Replace player/team packet APIs with universal Subject/Affiliation/
   Counterparty packet contracts while preserving sport-specific payloads.
4. Expand EvidenceGraph runtime population through
   Feature → Role/Participation → ParameterSnapshot → Simulation →
   PropEvaluation → Selection → Settlement → LearningObservation.
5. Make the full `SportPlugin` interface executable and validate capability
   only when every required component is registered and tested.
6. Finish one reference sport end to end under that interface, then promote no
   additional sport beyond SHADOW/RESEARCH until its deep plugin is complete.
7. Complete portable release regeneration and fresh-conversation acceptance
   using only canonical runtime + HAR.
8. Accumulate chronological settlements before any predictive or Learning
   Revision promotion.
