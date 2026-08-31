# Master implementation prompt — finish Pillars DCM as a ChatGPT-native universal forecasting engine

You are a senior principal engineer working directly on:

`https://github.com/williamcgreenwood/DCM.git`

Your job is to CONTINUE and FINISH the existing DCM. Do not restart it, simplify it into a generic prediction app, create a second forecasting engine, or declare unfinished scaffolds complete.

## 0. Mandatory starting procedure

Use the current canonical integration line, not stale `main`.

```bash
git fetch --all --prune
git checkout integration/v6-ml-architecture-20260830
git pull --ff-only
git rev-parse HEAD
```

Before editing, read in this order:

1. `AGENTS.md`
2. `docs/PROGRAM_STATUS.md`
3. `docs/PROGRAM_STATUS.json`
4. `docs/UNIVERSAL_IMPLEMENTATION_MATRIX_20260831.md`
5. `docs/CHATGPT_NATIVE_EXECUTION_SPEC.md`
6. `docs/UNIVERSAL_RESEARCH_ACQUISITION_SPEC.md`
7. newest records under `docs/engineering_passes/`
8. generated code inventory if present
9. current open PRs touching the integration line

Run the baseline suite before changing behavior. Never work from an assumed architecture.

Create a child branch from the exact current integration head. Never push implementation directly to main.

## 1. Immutable mission

Finish the whole DCM pass-by-pass until every software subsystem that can be completed in code is genuinely complete.

Final forecast architecture:

`HAR → complete universal research population → optimized host research → EvidenceGraph → FeatureStore → Role/Participation/Availability → Opportunity → conditional Efficiency → immutable ParameterSnapshots → joint EventWorld → PrimitiveOutcomeLedger → DerivedMarkets → P(MORE)/P(LESS)/P(PUSH) → uncertainty → line tolerance → grading → ranking → dependence-aware portfolio → final refresh → frozen forecast → settlement → calibration/learning sidecars`.

Python is the only canonical forecasting engine.

ChatGPT is the priority host. Grok must be able to use the same stable host contract.

No universal-core contract may require the concepts Player, Team, minutes, possessions, carries, routes, plate appearances, shots, maps, laps, holes, rounds, etc. Those belong in SportPlugins/adapters. Universal vocabulary is:

Sport, Competition, Event, Side, Affiliation, Subject, Counterparty, Environment, MarketDefinition, Offer, Evidence, Feature, State, ParameterSnapshot, EventWorld, PrimitiveOutcome, DerivedMarket, Probability, Uncertainty, Grade, Rank, Portfolio, Forecast, Settlement, LearningRevision.

## 2. Completion standard

A file or class existing is not completion.

A subsystem is 10/10 only when it is:

- executable;
- used on the canonical runtime path;
- schema-defined;
- fail-closed;
- deterministic where required;
- tested positively and negatively;
- cutoff/temporal safe;
- resumable where applicable;
- auditable end-to-end;
- included in the portable release;
- operable through the host-native interface where relevant;
- free of hidden production fixtures/stubs/fallbacks;
- reflected honestly in PROGRAM_STATUS and the implementation matrix.

If a requirement needs future settlements, licensed data or absent canonical bytes, implement the correct fail-closed boundary and mark it BLOCKED-EXTERNAL. Never fabricate completion.

## 3. Mandatory pass accounting

Every coding tranche MUST leave repository-visible history.

Before merge:

1. update `docs/PROGRAM_STATUS.md`;
2. update `docs/PROGRAM_STATUS.json`;
3. update `docs/UNIVERSAL_IMPLEMENTATION_MATRIX_20260831.md` for affected areas;
4. regenerate code inventory when Python surfaces changed:
   ```bash
   python scripts/build_code_inventory.py --write
   ```
5. create ONE NEW immutable pass record under `docs/engineering_passes/`.

The pass record must list exact starting SHA, changed files/modules/functions/classes/algorithms, tests, benchmark results if relevant, requirements finished, requirements still partial, new blockers, compatibility debt, next ordered tasks, and any claim changes.

Never edit an old pass log to hide a mistake. Add a corrective record.

## 4. Top-priority ChatGPT-native host subsystem

Implement the public API/CLI defined in `docs/CHATGPT_NATIVE_EXECUTION_SPEC.md`.

The package must expose:

```bash
dcm-host doctor
dcm-host prepare
dcm-host next-research
dcm-host evidence-import
dcm-host coverage
dcm-host forecast
dcm-host report
dcm-host resume
dcm-host audit
dcm-host settle
dcm-host archive
```

and equivalent:

```bash
python -m dcm.chat ...
```

Recommended module layout:

```
dcm/chat/
  __init__.py
  cli.py
  session.py
  contracts.py
  state.py
  research_bridge.py
  evidence_import.py
  report.py
  archive.py
```

Recommended high-level Python API:

```python
from dcm.chat import HostSession

session = HostSession.prepare(...)
batch = session.next_research_batch(...)
session.import_evidence(...)
coverage = session.coverage()
forecast = session.forecast()
report = session.report()
```

CLI and Python API must call the same implementation.

The host must never need to know internal DCM module topology, manufacture claim hashes, invent reliability values, or calculate probabilities.

The DCM engine owns normalization, semantic scopes, hashing, coverage, feature/state/model execution, probabilities, grading, ranking and freeze.

The host owns web/tool research.

Do not make Python perform hidden internet scraping as a substitute for the host boundary.

## 5. Fresh ChatGPT execution acceptance

Repository access is not equivalent to package execution.

Create a real acceptance test beginning with ONLY:

1. exact DCM wheel/release artifact;
2. RELEASE_MANIFEST/HASHES;
3. host contract;
4. uploaded HAR.

No source checkout.
No prior chat memory.
No hidden PYTHONPATH.
No fixture research.
No manually supplied player logs.

Prove:

install → doctor → prepare HAR → research batches → host-observation import → semantic coverage → forecast → report → audit → frozen forecast.

The wheel must be produced by GitHub release/CI and exact git commit/hash must be recorded.

If GitHub is private, do not assume a generic read connector can mount code into a Python sandbox. Treat release retrieval/mount as an explicit host capability and fail clearly when unavailable.

## 6. P1 universal deep research — this is a major required build

The desired depth is analogous to a complete player + own-team + opponent + matchup investigation, but it must be universal for every sport and every Subject.

Read `docs/UNIVERSAL_RESEARCH_ACQUISITION_SPEC.md` and implement it, not a basketball-specific clone.

Canonical research hierarchy:

Sport
→ Competition
→ Event
→ Affiliation / Counterparty / Environment
→ Subject
→ MarketDefinition
→ Offer

### Required research behavior

For every eligible offer:

- research shared event/environment context once;
- research each Affiliation once;
- research each Counterparty once;
- research each Subject deeply once per event/as-of state;
- reuse those facts for every dependent offer;
- expand research based on offered market families;
- refresh volatile status/lineup/weather/line evidence near freeze;
- distinguish factual claims from sentiment/context;
- keep opportunity separate from efficiency;
- use role-comparable historical samples;
- shrink weak/small samples;
- store source lineage and as-of time.

### Subject packet universal categories

When applicable:

- identity/current affiliation;
- availability/status;
- expected participation/workload;
- role and RoleEpoch;
- full historical game/event logs available from approved sources;
- season/recent/role-comparable windows;
- opportunity variables;
- conditional efficiency;
- advanced metrics relevant to the market;
- teammate/depth/lineup dependencies;
- counterparty-specific or role-similar matchup evidence;
- travel/rest/workload;
- coaching/tactical change;
- current news/context.

### Affiliation packet

- roster/depth/rotation/lineup;
- injuries/suspensions;
- team style;
- opportunity environment;
- offensive/defensive or analogous efficiency;
- pace/tempo/plays/possessions/attempts when applicable;
- role allocation;
- matchup tendencies;
- season/recent form;
- schedule strength;
- rest/travel;
- coaching/tactical changes.

### Counterparty packet

Research to the same relevant depth as Affiliation, plus direct matchup suppression/allowance of the Subject’s opportunity and efficiency, likely direct personnel interaction, scheme/style effects and market-relevant strengths/weaknesses.

### Event/environment packet

- start/status;
- venue/course/track/map/surface;
- format/segments;
- lineup/participants;
- weather/roof/wind/humidity/altitude where material;
- officials when materially supported;
- rest/travel/time zone.

### Market/offer packet

- exact stat definition;
- segment/period;
- overtime/extras/sets/maps/rounds;
- DNP/reboot/push;
- composite primitive derivation;
- offered sides;
- modifier;
- line history;
- final refresh.

Not every field applies to every sport. SportResearchSchema declares applicability and requiredness.

## 7. Replace legacy P1 provider semantics

Current legacy PLAYER/TEAM provider/request semantics must terminate at source/sport compatibility adapters.

Canonical acquisition must use:

SUBJECT
AFFILIATION
COUNTERPARTY
EVENT
ENVIRONMENT
SPORT
COMPETITION
MARKET_DEFINITION
OFFER

Build universal:

- SubjectResearchPacket
- AffiliationResearchPacket
- CounterpartyResearchPacket
- EventResearchPacket
- EnvironmentResearchPacket

Keep player/team views only as one-way compatibility projections for old code until consumers are migrated, then retire them.

Coverage must be semantic field coverage defined by SportResearchSchema, not “provider returned a row.”

## 8. SourceAdapterRegistry and SourceCatalog

Implement a versioned source catalog. Each source declares:

- authority tier;
- sports/competitions;
- fields/entity kinds;
- public/authenticated/licensed;
- API/table/page/news;
- historical depth;
- advanced metrics;
- freshness/update latency;
- cost/rate limits;
- identifier mapping;
- parser version;
- terms/licensing/storage policy;
- fallback chain;
- known failure modes.

Acquisition preference:

official structured source
→ configured licensed structured API
→ high-quality statistical database
→ official team/participant source
→ reputable news
→ generic search discovery/fallback.

Never hard-code one website as a universal dependency.

Authenticated/paid sources must be capability-based and optional. API keys/secrets never enter Git.

## 9. Optimized host research scheduler

Implement batched research, primarily by Event.

Use a priority score based on:

dependent-offer fanout
× information importance
× freshness need
× expected uncertainty reduction
÷ estimated acquisition cost.

The host should get compact batches like:

- one event;
- its affiliations/counterparties;
- environment;
- unresolved subjects;
- market definitions reused across offers.

Avoid one web search per prop.

The engine should request another batch only for missing/stale/conflicted evidence that can materially affect model/selection eligibility.

## 10. Evidence import boundary

ChatGPT/Grok should submit simple host observations:

```json
{
  "sourceUrl":"https://...",
  "retrievedAt":"...",
  "publishedAt":"...",
  "entityRef":{"kind":"SUBJECT","id":"..."},
  "evidenceType":"HISTORICAL_PERFORMANCE",
  "data":{}
}
```

DCM must:

- canonicalize identity;
- validate source policy;
- normalize sport-specific stats;
- enforce cutoff;
- calculate reliability/freshness per declared policy;
- create source/content/claim hashes;
- dedupe;
- record conflicts;
- attach EvidenceGraph lineage;
- update content-addressed cache.

No host-created cryptographic hashes or guessed reliability.

## 11. P2 to 10/10

Complete universal FeatureStore families:

IDENTITY
PARTICIPATION
ROLE
OPPORTUNITY
EFFICIENCY
AFFILIATION
COUNTERPARTY
MATCHUP
EVENT
ENVIRONMENT
RECENCY
WORKLOAD
AVAILABILITY
MARKET
PLATFORM.

Implement separate RoleStateModel and ParticipationModel interfaces.

Opportunity must precede efficiency.

ParameterSnapshot must be immutable and layered:

Subject
+ Affiliation
+ Counterparty
+ Event
+ Environment
+ Market
+ availability mixture
+ uncertainty metadata
+ evidence lineage.

Remove canonical player/team-specific payload assumptions.

## 12. P3 to 10/10 — every sport through one contract

The existing 24-component SportPlugin contract is mandatory.

Each promoted sport must have 24/24 IMPLEMENTED and import-resolved:

IdentityContract
ResearchSchema
SourceAdapterRegistry
CanonicalStatSchema
HistoricalPerformanceSchema
RoleStateSchema
ParticipationModel
OpportunityModel
EfficiencyModel
AffiliationModel
CounterpartyModel
EnvironmentModel
EventWorldModel
PrimitiveOutcomeSchema
ConservationRules
MarketDefinitionRegistry
DistributionRegistry
FeatureSchema
MLModelRegistry
CalibrationPolicy
AvailabilityPolicy
SettlementRules
RebootDNPPolicy
ValidationSuite.

No generic production fallback.

Build sports universally over time. Do not make universal core basketball-specific.

Recommended completion order follows actual PrizePicks/board value and shared architecture, but never label an unfinished sport production-complete.

Examples of sport-specific research/model families belong inside plugins:

- basketball: minutes/usage/touches/shot profile/potential assists/rebound chances/pace;
- gridiron: snaps/routes/targets/carries/air yards/red-zone/pressure/coverage/weather;
- baseball: PA/batting order/handedness/pitch mix/K-BB/contact/xwOBA/barrels/park/bullpen;
- hockey: TOI/line/PP role/shot attempts/xG/goalie/matchup;
- soccer: minutes/starts/xG/xA/shots/touches/set pieces/possession/opponent style;
- combat: round pace/striking/takedowns/control/opponent defense/weight/context;
- tennis: surface/serve/return/hold/break/aces/double faults/workload;
- golf: strokes-gained families/course fit/weather/tee-time conditions;
- motorsport: qualifying/race pace/track/tire/weather/grid;
- esports: map pool/role/rounds/economy/KD/usage/opponent map strength.

These examples are plugin requirements only, never universal nouns.

## 13. P4 to 10/10

For every modeled offer:

- independently evaluate MORE and LESS when offered;
- explicit PUSH;
- raw vs calibrated vs evidence-safe probability;
- aleatoric, epistemic and Monte Carlo uncertainty;
- Reliability, Data Quality, Volatility, Fragility, OOD risk and Selection Score separate from probability;
- true unclamped directional line tolerance;
- PLAYABLE / LEAN / PASS / TRAP;
- direction for PASS/TRAP when supportable;
- no forced Top 5/6/12;
- Top25 ranked findings separate from qualified bets;
- 0–6 card;
- unique subjects;
- combination-component exposure;
- event/affiliation concentration;
- simulated correlation and shared failure paths;
- final status/line/environment refresh before freeze.

## 14. P5 to 10/10

Complete:

- host-native API/CLI;
- full EvidenceGraph lineage:
  SourceDocument → EvidenceClaim → Feature → State → Parameter → ParameterSnapshot → Simulation → PropEvaluation → Selection → Forecast → Settlement → LearningObservation;
- deterministic audit pack;
- portable wheel;
- release manifest/hashes;
- exact git commit identity;
- clean environment;
- fresh ChatGPT acceptance;
- no raw HAR/secrets in archives;
- research/run archive packs.

## 15. P6 to 10/10 software

Complete software for:

- full-board settlement;
- exact platform-specific sporting result vs administrative status vs pick result vs lineup economics;
- DNP/reboot/push rules;
- immutable Learning Ledger;
- Brier;
- log loss;
- CRPS where applicable;
- calibration curve/ECE/reliability diagrams;
- subgroup diagnostics;
- chronological walk-forward;
- champion/challenger;
- promotion gates;
- future-only patches.

Do NOT advance LR000000 or predictive claim NONE until real chronological unseen settlements earn it. That portion may remain BLOCKED-EXTERNAL while the software reaches 10/10.

## 16. P7–P14 program

Use `docs/PROGRAM_STATUS.json` as canonical machine-readable status.

Finish:

P7 Host-native execution.
P8 Universal source acquisition.
P9 Universal-core migration.
P10 Full sport coverage.
P11 Release/fresh-host acceptance.
P12 Research archive/index/reuse.
P13 Performance/search/token optimization.
P14 Production operations/observability.

Do not treat these as documentation-only phases.

## 17. GitHub organization and research storage

Keep the repo navigable.

Do not commit:

- raw private HARs;
- cookies/tokens/credentials;
- giant raw scraped pages;
- unlicensed copyrighted databases;
- huge high-churn binary datasets.

GitHub should contain:

- code;
- schemas;
- source catalog;
- adapter metadata;
- compact normalized evidence/provenance when permitted;
- research indexes;
- release manifests/hashes;
- audit/run manifests;
- pass logs;
- generated code inventory.

Use content-addressed research.

Suggested logical paths:

```
docs/
  PROGRAM_STATUS.md
  PROGRAM_STATUS.json
  engineering_passes/
  generated/
dcm/
  chat/
  research/
  sports/
research_store/
  indexes/
  manifests/
  compact/
audit/
releases/
```

Do not create millions of tiny Git objects. For large/high-churn historical data, use a queryable artifact/database/object-store layer with GitHub manifests/hashes and compact indexes.

## 18. Performance requirements

Measure rather than guess.

Optimize:

- research fan-out/reuse;
- source-priority routing;
- content-addressed cache;
- incremental DAG invalidation;
- batched host research;
- batched disk writes;
- bounded concurrency;
- deterministic RNG streams;
- adaptive Monte Carlo;
- columnar/vectorized computations where semantically safe;
- event-world reuse across markets;
- reduced serialization;
- indexed lookups;
- token-efficient research batches.

Record:

- wall time;
- CPU time;
- peak RSS;
- board size;
- unique entities;
- research requests vs reused evidence;
- cache hit rate;
- web/search batch counts;
- host token estimates when measurable;
- simulations/worlds;
- artifact size.

Never set hostPerformanceCertified without measured evidence.

## 19. Testing requirements

For each changed subsystem add targeted tests plus full suite.

Required categories over the program:

- schema;
- identity;
- malformed HAR;
- multi-HAR reconciliation;
- cutoff leakage;
- status/start;
- offered sides;
- Goblin/Demon;
- universal non-player Subject;
- research population completeness;
- source fallback/conflict;
- semantic coverage;
- stale evidence;
- role epoch;
- participation;
- opportunity/efficiency separation;
- conservation;
- shared-world composites;
- push probability;
- uncertainty;
- grading;
- ranking;
- portfolio correlation;
- resume determinism;
- release clean install;
- fresh-host acceptance;
- settlement;
- learning leakage/promotion denial;
- performance regression.

## 20. Required end-of-pass output

Do not merely say “done.”

Report:

- exact start SHA;
- exact end SHA;
- branch/PR;
- files changed;
- modules/functions/classes changed;
- algorithms/contracts implemented;
- test commands and exact results;
- benchmark deltas;
- workstream scores before/after;
- completed items;
- remaining partial/missing items;
- newly discovered blockers;
- compatibility debt;
- next ordered tasks;
- LR/predictive/root/performance claim status.

Merge the child PR into the single integration branch only after the latest exact head is green. Do not merge the integration line to main until all software acceptance gates are legitimately satisfied.

## 21. Immediate next implementation order

Unless current HEAD already completed these, prioritize:

1. commit generated AST code inventory;
2. implement `dcm.chat`/`dcm-host` host session and CLI;
3. migrate canonical provider/request semantics to universal entities;
4. implement universal research packets;
5. implement SourceCatalog/SourceAdapter capability registry;
6. implement optimized iterative research batching;
7. implement simple host-observation evidence import;
8. make semantic coverage SportResearchSchema-driven;
9. universalize FeatureStore;
10. universalize ParameterSnapshot;
11. fully populate EvidenceGraph lineage;
12. close SportPlugin PARTIAL bindings one sport at a time;
13. build fresh ChatGPT wheel+HAR acceptance;
14. expand sport coverage;
15. finish settlement/calibration software;
16. optimize measured performance;
17. continue until all code-completable P0–P14 rows honestly reach 10/10.

Do not rebuild from scratch. Do not skip ahead with fake completion. Make the current DCM incrementally executable, universal, auditable and ChatGPT-native.
