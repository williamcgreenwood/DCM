# PILLARS DCM v6 — UNIVERSAL WORKSTREAM A/B 46+ BLUEPRINT

**Purpose:** Turn `dcm_v6_workstream_ab` from a stranded football/E2E proof into a heavily documented, universal, fail-closed sports-plugin and PrizePicks-settlement foundation that makes later ChatGPT operation of DCM v6 simple, deterministic, artifact-first, and difficult to misuse.

**Important naming rule:** the historical **46-test package is the minimum acceptance seed**, not the final test ceiling. Once this package becomes universal across sports, the suite should expand into hundreds of parameterized, sport-specific, settlement, lineage, negative, integration, and golden-regression tests. Keep the original 46 as a frozen compatibility gate called `WSAB_BASELINE_46`.

**Predictive superiority:** NONE unless earned by future chronological evidence.

**Learning Revision:** LR000000 unless a separately governed future-only promotion passes.

---

## 0. THE PACKAGE'S JOB

`dcm_v6_workstream_ab` should do four things exceptionally well:

1. **Define the universal sport-plugin contract** used by every sport family.
2. **Build physically coherent EventWorld/PrimitiveStatLedger outputs** with opportunity separated from efficiency and exact conservation/identity rules.
3. **Translate a frozen WorldProjection through exact PrizePicks contracts** into Administrative → Comparison → Economic settlement without inventing platform rules.
4. **Provide ChatGPT with a tiny machine-readable control surface** so it does not have to reread or rediscover the architecture every time DCM v6 is operated.

It is **not** the final HAR/live-board runner by itself. The integrated v6 runner will connect:

`HAR -> board.json -> evidence -> EventWorld -> PrimitiveStatLedger -> MarketDefinition -> probabilities/line surfaces -> grade/rank/portfolio -> freeze -> settlement`.

WSAB supplies the universal physics + market-derivation + settlement contracts that the integrated runner calls.

---

# PART I — HARD NON-NEGOTIABLE CONTRACTS

## 1. Governance invariants

The package must make the following executable, not merely documented:

- Green Goblin may be extracted/analyzed/settled but can never enter production selection.
- Offered-sides-only selection.
- Red Demon extra cushion remains demotion-only until validated; no Demon can be easier to select than Standard.
- Empty card is valid; never force 5/6/12 legs.
- Probability is separate from Reliability, Data Quality, Volatility, Fragility, OOD Risk, False-Sign Risk, rank stability, and selection utility.
- Current outcomes cannot affect the current frozen forecast.
- Opportunity and efficiency are separate objects.
- Primitive values are immutable after freeze/hash.
- Derived values never overwrite primitives.
- Composites derive from the same world/ledger as components.
- Unknown state is explicit and fail-closed.
- Software version change does not imply Learning Revision change.
- Platform truth is separate from sports truth.
- Settlement rules and stat definitions are versioned.
- No fuzzy/nearest match for MarketDefinition or platform rule tables.

## 2. Universal causal chain

Every sport must map into the same causal ordering:

`Sport -> Event environment -> Discrete regime -> Team/side opportunity pool -> Role -> Player opportunity -> Conditional efficiency -> Primitive stats -> Derived stats -> MarketDefinition -> Frozen line/side comparison -> Administrative translation -> Economic translation`.

A sport may use a different physical path unit, but it may not invent a new global persistence architecture without a formal schema-mutation dossier.

---

# PART II — EXACT PACKAGE LAYOUT

## 3. Root package layout

```text
dcm_v6_workstream_ab/
├── 00_READ_ME_FIRST.md
├── CHATGPT_ENTRYPOINT.md
├── CHATGPT_CONTEXT_INDEX.json
├── COMMANDS.json
├── VERSION
├── RELEASE_MANIFEST.txt
├── PACKAGE_MANIFEST.json
├── SHA256SUMS.txt
├── SOURCE_LINEAGE.json
├── BUILD_RECEIPT.json
├── LIFECYCLE.json
├── FAILURE_CODES.md
├── CONTRACTS.md
├── SPORT_PLUGIN_PROTOCOL.md
├── PLATFORM_RULE_PROTOCOL.md
├── TEST_INDEX.json
├── CAPABILITY_SUMMARY.json
│
├── schemas/
│   ├── Phase_BC_Immutable_Contracts.json
│   ├── Sport_Plugin_Manifest.schema.json
│   ├── Market_Definition.schema.json
│   ├── Platform_Rule_Row.schema.json
│   ├── Participation_Facts.schema.json
│   ├── Evidence_Requirement.schema.json
│   └── Package_Lifecycle.schema.json
│
├── configs/
│   ├── sports/
│   ├── leagues/
│   ├── markets/
│   ├── capabilities/
│   ├── evidence/
│   └── platform/
│       └── prizepicks/
│           ├── rule_versions.json
│           ├── participation/
│           ├── reboot/
│           ├── dnp/
│           ├── minimum_guarantee/
│           ├── leaderboard/
│           └── scoring_sources/
│
├── dcm/
│   ├── contracts/
│   ├── sports/
│   │   ├── common/
│   │   ├── gridiron/
│   │   ├── basketball/
│   │   ├── baseball/
│   │   ├── soccer/
│   │   ├── hockey/
│   │   ├── racket/
│   │   ├── cricket/
│   │   ├── combat/
│   │   ├── golf/
│   │   ├── esports/
│   │   ├── lacrosse/
│   │   ├── handball/
│   │   ├── australian_rules/
│   │   ├── rugby/
│   │   ├── volleyball/
│   │   ├── motorsport/
│   │   └── generic/
│   ├── platform/
│   │   └── prizepicks/
│   ├── selection/
│   ├── validation/
│   ├── runtime/
│   └── integration/
│       └── v541/
│
├── fixtures/
│   ├── synthetic/
│   ├── golden/
│   ├── platform_rules/
│   ├── sanitized_har_contracts/
│   └── pillar_incidents/
│
├── tests/
│   ├── baseline_46/
│   ├── contracts/
│   ├── sports/
│   ├── platform/
│   ├── integration/
│   ├── negative/
│   ├── property/
│   ├── metamorphic/
│   └── golden/
│
├── docs/
│   ├── architecture/
│   ├── sports/
│   ├── platform/
│   ├── operations/
│   └── audits/
│
└── reports/
    ├── WSAB_Test_Report.md
    ├── WSAB_Implementation_Report.md
    ├── Sport_Capability_Matrix.csv
    ├── Platform_Rule_Coverage.csv
    ├── Schema_Traceability.csv
    └── Package_Integrity.json
```

---

# PART III — FILES THAT MAKE CHATGPT'S JOB EASY

## 4. `00_READ_ME_FIRST.md`

Maximum ~2 pages. It must tell any future ChatGPT session:

- what the package is;
- exact version/LR;
- what is canonical vs development;
- what it may and may not claim;
- exact first command to run;
- where manifests are;
- where sport/plugin status is;
- where platform rules are;
- how to fail closed;
- where to write run artifacts;
- how to resume.

The first line should be operational, for example:

`START HERE: verify PACKAGE_MANIFEST + SOURCE_LINEAGE, then read CHATGPT_CONTEXT_INDEX; do not recursively read the whole tree unless a referenced hash/status fails.`

## 5. `CHATGPT_ENTRYPOINT.md`

This is the permanent operator prefix. It should include:

- canonical pipeline;
- Green Goblin veto;
- offered-sides-only;
- Demon cushion;
- no forced card;
- exact platform rule lookup;
- current-outcome firewall;
- artifact-first output;
- rule for missing files (`UNVERIFIED`, never guess);
- rule for unknown sport/league/market (`UNSUPPORTED_FAIL_CLOSED`);
- rule for unknown PrizePicks administration (`UNKNOWN_PLATFORM_RULE`/`UNKNOWN_REBOOT_RULE`);
- exact expected output: Run Integrity, card/EMPTY, blockers, artifact paths/hashes, next deterministic action.

## 6. `CHATGPT_CONTEXT_INDEX.json`

This is the most important convenience artifact. It should prevent ChatGPT from repeatedly reopening the entire repository.

Minimum fields:

```json
{
  "package": "dcm_v6_workstream_ab",
  "version": "6.x+WSAB...",
  "learning_revision": "LR000000",
  "predictive_claim": "NONE",
  "canonical_baseline": {
    "version": "5.4.1",
    "source_hash": "...",
    "ledger_hash": "...",
    "status": "VERIFIED|DECLARED_UNVERIFIED|ABSENT"
  },
  "schema_freeze": {
    "id": "PHASE_BC_SCHEMA_V1_2026-08-25",
    "hash": "...",
    "verification_state": "..."
  },
  "sports": "configs/capabilities/sport_capability_registry.json",
  "platform_rules": "configs/platform/prizepicks/rule_versions.json",
  "commands": "COMMANDS.json",
  "tests": "TEST_INDEX.json",
  "failure_codes": "FAILURE_CODES.md",
  "entrypoint": "CHATGPT_ENTRYPOINT.md"
}
```

## 7. `COMMANDS.json`

Future ChatGPT should not invent commands. Store exact supported commands for:

- verify package;
- verify canonical baseline;
- run baseline tests;
- run one sport plugin tests;
- run all sport contract tests;
- validate rule tables;
- validate schema hash;
- build package;
- generate manifests;
- run integration smoke;
- resume a checkpoint;
- settle a fixture;
- print capability matrix.

Each command stores prerequisites, expected exit code, output artifacts, and failure meaning.

## 8. `LIFECYCLE.json`

Every capability gets a machine lifecycle state:

`DESIGNED -> AUTHORIZED -> IMPLEMENTED_STANDALONE -> INTEGRATED -> REGRESSION_VERIFIED -> RELEASE_ACCEPTED`.

Never use natural-language "done" as lifecycle authority.

## 9. `CAPABILITY_SUMMARY.json`

This must answer in one read:

- sport family;
- league/competition;
- markets known from HAR/project history;
- primitive registry available?;
- opportunity model available?;
- efficiency model available?;
- conservation rules available?;
- MarketDefinition verified?;
- participation/DNP rule verified?;
- Reboot rule verified?;
- model production state;
- selection state;
- blocker code;
- tests proving the state.

States:

- `PRODUCTION_SUPPORTED`
- `SHADOW_SUPPORTED`
- `RESEARCH_ONLY`
- `UNSUPPORTED_FAIL_CLOSED`

---

# PART IV — THE UNIVERSAL SPORT PLUGIN PROTOCOL

## 10. Required interface for every sport family

Every sport plugin must expose the same conceptual interface:

```text
SportPluginManifest
LeagueRuleRegistry
PrimitiveStatRegistry
AppearanceModel
OpportunityModel
EfficiencyModel
EventWorldBuilder
PrimitiveLedgerBuilder
ConservationRuleSet
MarketDeriver
EvidenceRequirementRegistry
PlatformParticipationBinding
CapabilityRows
AuditHooks
```

## 11. `SportPluginManifest`

Required fields:

- sport_family_id;
- plugin_version;
- supported leagues/competitions;
- physical path unit;
- opportunity units;
- primitive schema version;
- conservation rule version;
- market binding version;
- evidence policy version;
- official scoring/provider references;
- known unsupported features;
- production state;
- test IDs;
- content hash.

## 12. Appearance is physical, not platform administration

Examples:

- basketball: possession/stint/minute;
- gridiron: drive/play/snap/route/target;
- baseball: PA/base-out/pitch/batter-faced;
- soccer: minute/touch/possession/action;
- hockey: shift/TOI/possession/shot event;
- tennis: point/game/set;
- cricket: ball/over/innings;
- MMA/boxing: fight second/round/state;
- golf: hole/stroke;
- esports: map/round/tick/objective state.

PrizePicks DNP/Reboot rules consume these physical facts but never define them.

## 13. Opportunity vs efficiency

Every plugin must explicitly declare which variables are opportunity and which are conditional efficiency.

Examples:

- Minutes vs points/minute.
- Targets vs catch rate/YPR.
- Plate appearances vs K/BB/contact rates.
- Service points vs ace/double-fault rate.
- Fight seconds vs strikes/minute.

A plugin that cannot separate these is not production-ready.

---

# PART V — SPORT FAMILY BLUEPRINTS

## 14. Gridiron family — NFL, CFB, CFL, UFL, preseason

### Core primitive topology

- offensive plays;
- dropbacks;
- pass attempts/completions;
- sacks/sack yards;
- designed rush attempts;
- scramble attempts;
- rush attempts/yards/TD;
- routes;
- targets/receptions/receiving yards/TD;
- interceptions;
- fumbles/lost if definition requires;
- field goal attempts/makes;
- XP attempts/makes;
- punts where supported.

### Hard identities

- `rush_att = designed_rush_att + scramble_att` under declared semantics;
- `dropbacks = pass_att + sacks_taken + scramble_att`;
- `receptions <= targets <= routes` where routes are represented;
- made <= attempts;
- team receiving yard/pass yard reconciliation under a frozen lateral/sack definition;
- no false `sum(player_snaps) == team_plays` identity.

### League-specific configs

NFL, CFB, CFL, UFL and preseason must not share platform rules merely because they share football primitives. League configuration owns field/rule/clock/roster/phase differences. Platform administration is separately keyed.

### Pillars-specific golden lessons

- NFL preseason rotation is a distribution, not "one half = N attempts";
- CFL passing depends heavily on attempt volume, weather, delay, replacement rushing usage and game script;
- same-offense props need shared dependency modeling.

## 15. Basketball family — NBA, WNBA, NCAA, FIBA/international, G League, EuroLeague where offered

### Primitives

Minutes, FGA, 3PA, 2PA, 3PM, 2PM, FGM, FTA, FTM, OREB, DREB, REB, AST, STL, BLK, TO, PTS.

### Derived

PRA, PR, PA, RA, stocks, fantasy score, combos.

### Identities

- `2PA = FGA - 3PA`;
- `FGM = 2PM + 3PM`;
- `REB = OREB + DREB`;
- `PTS = 2*2PM + 3*3PM + FTM`;
- made <= attempts;
- league-specific team minute conservation.

League minutes belong in `LeagueRuleRegistry`; never hard-code NBA 240 for WNBA/international leagues.

## 16. Baseball family — MLB, NPB, KBO, CPBL, LMB, Caribbean/international/WBC when offered

### Path model

PA -> count/base-out -> pitch/contact outcome -> baserunner state -> outs/runs.

### Hitter primitives

PA, AB, H, 1B, 2B, 3B, HR, BB, HBP, SO, SF, SH where definition requires, TB, R, RBI, SB, pitches seen.

### Pitcher primitives

BF, pitches, strikes, outs, K, BB, H, HR, ER/R, innings/outs, hook state.

### Identities

- H = 1B+2B+3B+HR;
- TB = 1B+2*2B+3*3B+4*HR;
- PA decomposition by league/stat semantics;
- pitching outs reconcile to innings representation;
- made-up MLB assumptions may not be copied to NPB/KBO.

### Golden lesson

Pitcher Fantasy Score must separate base performance from discrete Win/QS bonus states and preserve Bonus Leverage / side-flip risk.

## 17. Soccer family — EPL, UEFA, MLS, Liga MX, European leagues, women's leagues, international competitions

### Primitives / event actions

minutes, touches, pass attempts/completions, shots, shots on target, goals, assists, key passes/shots assisted, crosses, dribbles, tackles, interceptions, clearances, fouls, fouls drawn, offsides, goalkeeper shots faced/saves/goals allowed.

### Required modeling

- lineup/start/substitution regime;
- role/position;
- team possession/territory/attack state;
- opponent strength;
- set-piece role;
- goalkeeper state;
- competition-specific overtime/extra-time/penalty rules where relevant.

DNP/activity may be start-dependent; do not assume football/basketball semantics.

## 18. Hockey family — NHL and other leagues only when definitions/rules are verified

### Physical units

shift, TOI, team possession/shot event.

### Primitives

TOI, shots on goal, shot attempts where supported, goals, assists, points, blocks, hits, PIM, faceoffs where supported; goalie shots against, saves, goals allowed, win state/shutout where platform definition requires.

### Identities

- goalie shots against = saves + goals allowed under the official scoring definition/exclusions;
- points = goals + assists when the market definition uses standard hockey points;
- TOI and shift logic must be league/position aware.

## 19. Tennis family — ATP/WTA/Challenger/ITF/team events when offered

Path: point -> game -> set -> match.

Primitives: service points, return points, aces, double faults, breaks, games won/lost, sets, tiebreaks.

Derived: total games, total sets, fantasy.

Aces/DF must scale from service opportunity. Total Games and Games Won must derive from the same match path.

## 20. Cricket family — T20, ODI, Test and other formats must be separate configs

Path: ball -> over -> innings -> match.

Primitives: balls faced/bowled, runs, fours, sixes, wickets, dot balls and other verified market stats.

Format is mandatory. Never mix T20/ODI/Test priors or opportunity limits.

## 21. Combat family — UFC/MMA and boxing

### MMA/UFC

Shared fight clock for both fighters. Primitives: significant strike attempts/lands, total strike attempts/lands if supported, takedown attempts/lands, control time, knockdowns, submission attempts, fight seconds, finish state/method.

Hard rules: landed <= attempted; control <= fight time; both fighters share finish/time; decision vs finish exclusivity.

### Boxing

Shared round/fight clock. Primitives: punches attempted/landed by verified category, knockdowns, rounds completed, finish/decision state.

Hard rules: landed <= attempted; one shared fight termination; rounds/time cannot exceed scheduled; decision and stoppage are mutually exclusive terminal states.

Never reuse UFC strike semantics for boxing.

## 22. Golf family

Path: hole -> stroke -> round -> tournament.

Primitives: strokes, birdies/eagles/bogeys, pars, fairways/GIR only if exact market definitions require them, finishing position states.

Use course/weather/field strength and cut-state uncertainty. Strokes-gained can be evidence/latent input; do not automatically treat it as a platform primitive.

## 23. Esports family

Esports must be title/version specific. The plugin key includes game title and patch/ruleset.

Possible path units: map, round, objective, kill event, time/tick.

Do not create one "ESPORTS" normal model. LoL, CS2, Valorant, CoD, Dota and other titles require separate rule/config packs even if they reuse common event infrastructure.

## 24. Lacrosse / handball / Australian rules / rugby / volleyball / motorsports and future sports

Each gets a plugin pack only after:

1. physical path unit is defined;
2. primitives and conservation rules are defined;
3. league/competition rules are versioned;
4. PrizePicks MarketDefinitions are verified;
5. DNP/participation semantics are verified;
6. tests exist.

Until then, the board rows are extracted and inventoried but `UNSUPPORTED_FAIL_CLOSED` for selection.

The architecture must allow a brand-new sport to be added without editing core settlement or global schema classes.

---

# PART VI — PRIZEPICKS PLATFORM LAYER

## 25. Exact rule-table key

Every rule must be retrievable by an exact key equivalent to:

`Platform + ProductType + EntryType + League + BoardID + Market + Modifier + Side + RuleVersion + Situation`.

No nearest-match fallback.

## 26. Separate product types

At minimum represent:

- PLAYER_PICKS;
- TEAM_PICKS;
- CULTURE_PICKS (outside sports model by default);
- future platform products.

Do not mix Team Pick economics/settlement with Player Pick stat projections.

## 27. Settlement dimensions

AdministrativeState:

`ACTIVE, DNP, REBOOT, CANCELLED, INVALID_MARKET, UNRESOLVED`

ComparisonState:

`WIN, LOSS, TIE, NOT_APPLICABLE`

EconomicState:

`COUNTS_AS_WIN, COUNTS_AS_LOSS, TIER_REDUCTION, REMOVED, UNRESOLVED`

Physical outcome is resolved first, platform administration second, economics last.

## 28. Participation Facts

Create `ParticipationFacts` as a platform-neutral physical record. Example fields are optional and sport-specific payload values:

- started;
- active;
- entered_event;
- left_first_half;
- returned_second_half;
- plate_appearances;
- innings/outs;
- kicks/punts;
- minutes/TOI;
- fight_seconds;
- maps/rounds entered.

The Reboot/DNP engine consumes these facts through versioned rules.

## 29. PrizePicks rule snapshots

Store official snapshots with:

- rule ID;
- effective date;
- source URL/source ID;
- captured_at;
- source hash/content hash;
- leagues covered;
- board/product restrictions;
- qualifying market/stat classes;
- side restriction;
- participation predicate;
- exclusions;
- verification state.

If a sport has no verified active Reboot rule, do not copy NFL/NBA logic. Use explicit `NO_VERIFIED_REBOOT_RULE` or `UNKNOWN_REBOOT_RULE` according to evidence state.

## 30. Minimum Guarantee and Leaderboard

Keep distinct:

- physical result;
- pick result;
- Minimum Guarantee table;
- Leaderboard scoring;
- group-score context;
- final return.

Final return is `max(R_LB, R_MG)` when both are modeled. Leaderboard EV is UNMODELED without a valid group distribution/context.

`P(payout > 0)` is not `P(net > 0)`.

---

# PART VII — MARKET AND CAPABILITY REGISTRY

## 31. MarketDefinition

Exact key:

`Platform, League, Market, DefinitionVersion`.

Required fields:

- canonical market;
- semantic type (`PRIMITIVE|DERIVED|COMPOSITE|PLATFORM_SCORE`);
- output unit;
- source primitive keys;
- formula;
- overtime/extra-time policy;
- push policy;
- official source/scoring provider;
- participation policy version;
- Reboot rule version;
- verification status/hash.

## 32. Capability gate

A market is production selectable only if ALL are true:

- exact MarketDefinition verified;
- sport plugin exists;
- league config exists;
- opportunity model exists;
- efficiency model exists;
- distribution/event model exists;
- conservation tests exist;
- unit tests exist;
- integration tests exist;
- platform participation rule known enough to settle;
- no active blocker.

Unknown market is not routed into a generic normal distribution.

---

# PART VIII — EVIDENCE AND RESEARCH REQUIREMENTS BY SPORT

## 33. Universal evidence hierarchy

Research once at the highest reusable scope:

`Sport -> Event -> Team/Side -> Player -> Market`.

Every evidence claim is stored once with stable ID/hash and referenced by dependent props.

## 34. Required evidence categories

Universal:

- schedule/start time;
- event identity;
- venue;
- lineup/roster/starting status;
- injury/availability;
- role;
- recent and season opportunity;
- conditional efficiency;
- opponent strength;
- rest/travel;
- market/stat definition;
- platform board/side/modifier;
- meaningful line movement;
- weather/environment where relevant.

Sport-specific examples:

- NFL/CFB/CFL: depth chart, QB rotation, snap/route/carry/target share, offensive line, weather, pace/game script.
- Basketball: starting five, rotation, minutes cap, usage, teammate availability, pace/possessions.
- Baseball: lineup slot, starting pitcher, bullpen, park/weather, PA/BF/pitch limits, handedness.
- Soccer: confirmed XI, role/position, set pieces, substitution/minutes risk, possession/territory matchup.
- Hockey: lines/pairings, PP unit, goalie starter, TOI, opponent shot environment.
- MMA/boxing: scheduled rounds, weight class, opponent, style/state occupancy, pace, finish hazard.
- Cricket: format, batting order, bowling role, venue/pitch, weather.
- Tennis: surface, serve/return profile, match format, injury, schedule/rest.

---

# PART IX — THE BASELINE 46 TESTS

## 35. Freeze the original 41 as compatibility tests

Preserve the original three historical files (or equivalent named frozen tests):

- football registry/conservation — 16;
- E2E world-to-lineup — 20;
- lineage/schema — 5;

Total: 41.

They remain a compatibility gate even after tests are reorganized.

## 36. Add five official-predicate tests to reach the 46-test seed

The 46-test revision should add a frozen `test_official_predicates.py` with five policy-boundary cases such as:

1. CFB regular-season event does not inherit CFP Reboot.
2. CFB bowl event does not inherit CFP Reboot.
3. CFB unknown/unverified game phase fails `UNRESOLVED`.
4. NFL partial-game/non-full-game board does not qualify for the full-game Reboot path.
5. NFL second-half/third-quarter exit is not treated as a first-half/no-return Reboot.

If the actual 46-test package uses different exact test names, preserve its names and map these required properties in `TEST_INDEX.json`.

## 37. Do not stop at 46

Universalization requires automatic contract suites. Minimum future categories:

- plugin interface tests;
- primitive semantic tests;
- conservation/property tests;
- opportunity/efficiency separation tests;
- market derivation identity tests;
- platform rule lookup tests;
- participation/DNP/Reboot tests;
- deterministic hashing tests;
- serialization roundtrip tests;
- schema freeze tests;
- unsupported-market fail-closed tests;
- cross-sport settlement parity tests;
- golden Pillars failure-mechanism tests.

Target is not a vanity count. Every production sport-market cell must have traceable tests.

---

# PART X — GOLDEN PILLARS REGRESSION LIBRARY

## 38. Historical mechanisms to encode

Create sanitized synthetic/golden fixtures representing lessons already encountered in Pillars:

- WNBA 200-minute redistribution / teammate role change;
- NFL preseason QB rotation uncertainty;
- CFL passing-attempt/weather/delay/replacement-run-volume miss;
- explosive single-play Lower risk;
- UFC significant-strike scaling and terminal burst;
- Ryan Feltner / pitcher fantasy discrete Win/QS bonus flip;
- KBO DNP/selection-grade separation;
- Green Goblin absolute selection veto;
- Red Demon extra cushion;
- same-event/shared-QB dependency;
- line movement after freeze;
- source-scope/HAR reconstruction errors;
- role-epoch mismatch.

These fixtures protect mechanisms, not hindsight picks.

---

# PART XI — INTEGRATION WITH CANONICAL v5.4.1 AND FUTURE v6

## 39. Keep canonical v5.4.1 untouched

Provide an integration adapter, never in-place edits.

`dcm/integration/v541/` should contain:

- baseline hash verifier;
- v5 market/identity -> v6 contract mapper;
- v5 EventSimulator output -> EventWorld adapter;
- v5 HAR-normalized board -> v6 market identity adapter;
- compatibility report generator;
- merge conflict inventory.

## 40. Standard future v6 callable interface

The final integrated DCM v6 should expose one documented application API:

```text
verify_install()
run_from_har(path, cutoff, config) -> RunResult
resume_run(run_id) -> RunResult
settle_run(run_id, official_results, platform_evidence) -> SettlementResult
audit_run(run_id) -> AuditResult
```

Future ChatGPT should never need to infer which script to use.

---

# PART XII — RUNTIME ARTIFACT CONTRACT THAT CHATGPT CONSUMES

## 41. One HAR in, one run directory out

```text
INBOX/current.har
   -> RUNS/<run_id>/
      ├── run_integrity.json
      ├── board.json
      ├── evidence_manifest.json
      ├── event_inventory.json
      ├── capability_report.json
      ├── world_manifest.json
      ├── primitive_ledger_manifest.json
      ├── market_projection_manifest.json
      ├── grades.json
      ├── ranking.json
      ├── card.json
      ├── blockers.json
      ├── freeze.json
      ├── checkpoint.json
      ├── hashes.txt
      └── logs/
```

`board.json` is frozen immediately after successful ingest and must include input HAR hash, parser version, all extracted rows, Green Goblin count/exclusions, unresolved rows, event IDs, projection IDs, lines, modifiers, and offered sides.

## 42. Chat-facing output

Chat prints only:

- Run Integrity;
- CARD or EMPTY;
- essential blockers;
- compact findings requested by user;
- artifact paths/hashes;
- next deterministic action.

No full HAR, full board, full logs, or repeated source dump in chat.

---

# PART XIII — CONTENT-ADDRESSED DAG / CHECKPOINT INTERFACE

## 43. Node key

`NodeType + CanonicalIdentity + ForecastCutoff + SourceVersionSet + ConfigHash + SchemaVersion + ParentHashes`.

## 44. Required node states

`PENDING, RUNNING, COMPLETE_VERIFIED, BLOCKED, INVALIDATED, FAILED_RETRYABLE, FAILED_TERMINAL`.

## 45. Required node classes/interfaces

- InstallVerificationNode
- HARIndexNode
- BoardNormalizationNode
- EvidenceClaimNode
- EventEvidenceNode
- TeamStateNode
- PlayerRoleNode
- EventWorldSetNode
- PrimitiveLedgerNode
- ConservationNode
- MarketProjectionNode
- LineSurfaceNode
- GradeNode
- DependenceGraphNode
- PortfolioNode
- FreezeNode
- SettlementNode
- LearningCandidateNode

WSAB does not need to execute all of these today, but it should define the contracts expected by the integrated v6 runner.

## 46. Atomic checkpoints

Every major boundary stores hashes, completed/pending/invalidated nodes, rule versions, registry versions, seeds, artifacts, row counts, blockers, and next action. Resume must be independent of chat memory.

---

# PART XIV — BUILD PROCESS FROM START TO FINISH

## 47. Stage 0 — input authority lock

Inputs:

- canonical v5.4.1 source + install hash + ledger;
- Phase B/C schema bytes;
- Master Blueprint;
- ADR-V6-001;
- Optimization Blueprint v2;
- PrizePicks rule snapshots;
- WSAB source tree;
- Pillars golden audits/fixtures.

Hash everything. Mark missing bytes `UNVERIFIED`; never reconstruct and claim canonical identity.

## 48. Stage 1 — freeze package metadata

Create VERSION, SOURCE_LINEAGE, LIFECYCLE, PACKAGE_MANIFEST, SHA256SUMS, BUILD_RECEIPT, TEST_INDEX, CAPABILITY_SUMMARY.

## 49. Stage 2 — freeze common contracts

Verify no accidental common-schema mutation. If a sport seems to require a new global field, stop and write a mutation dossier instead of silently adding it.

## 50. Stage 3 — freeze plugin SDK

Implement common interfaces and automatic plugin contract tests.

## 51. Stage 4 — migrate historical football WSAB

Preserve 41 tests; add official predicate five; preserve deterministic hash behavior and the "timestamp excluded from semantic content hash" rule.

## 52. Stage 5 — make basketball the second complete plugin

Reuse the live primitive topology and prove identical settlement adapter behavior.

## 53. Stage 6 — add sport families in risk order

Recommended engineering sequence:

1. baseball/MLB -> NPB/KBO league packs;
2. MMA/UFC -> boxing combat sibling;
3. soccer;
4. hockey;
5. tennis;
6. cricket;
7. golf;
8. CFL/UFL and other gridiron configs after core NFL/CFB;
9. esports by title;
10. lacrosse/handball/Australian rules/rugby/volleyball/motorsport as verified demand appears.

Do not call a new plugin production merely because the interface compiles.

## 54. Stage 7 — platform rule coverage

For each league/product/board/market family, snapshot scoring, DNP/activity, Reboot, push/tie, board restrictions, display payout semantics, and official source.

Unknown rows fail closed.

## 55. Stage 8 — capability registry generation

Generate machine-readable Sport x League x Market x Model x Definition x PlatformRule x Test coverage matrix.

## 56. Stage 9 — package tests

Run:

- frozen baseline 46;
- plugin contract suite;
- sport tests;
- platform tests;
- negative tests;
- golden tests;
- lineage/hash tests.

## 57. Stage 10 — integration smoke against v5.4.1 development copy

Do not modify canonical v5 bytes. Verify adapters can consume sanitized historical board/event structures and produce v6 contracts.

## 58. Stage 11 — manifests and package hash

Regenerate every manifest only from final bytes; hash tree; create release package; verify extraction roundtrip.

## 59. Stage 12 — lifecycle promotion

A plugin/capability is promoted only when its required contract, definition, rule and tests are proven. Package release does not promote predictive learning.

---

# PART XV — DOCUMENTATION STANDARD

## 60. Every module needs a header contract

Every production module begins with:

- purpose;
- inputs;
- outputs;
- invariants;
- fail-closed states;
- hashing/immutability behavior;
- thread/process safety assumptions;
- upstream/downstream dependencies;
- tests that prove it;
- known limitations.

## 61. Every sport gets one operator page

`docs/sports/<sport_family>.md` must contain:

- sport/league mapping;
- path unit;
- opportunity units;
- primitive list;
- derived list;
- conservation rules;
- evidence needs;
- model families;
- platform definitions;
- DNP/Reboot status;
- supported markets;
- unsupported markets;
- tests;
- known failure mechanisms.

## 62. Every platform rule snapshot gets one provenance page

Never encode a rule without source, effective date, hash, verification state and explicit scope.

---

# PART XVI — WHAT MUST NEVER BE IN THE PACKAGE

## 63. Security and contamination exclusions

Do not package:

- live HAR files;
- authorization headers;
- cookies;
- CSRF/session/access tokens;
- user account/entry history unless explicitly sanitized for an audit artifact;
- secret provider credentials;
- personal identifiers;
- raw browsing sessions.

Do not let post-settlement outcomes live in the pre-freeze production evidence namespace.

---

# PART XVII — ACCEPTANCE STANDARD

## 64. What would make this workstream "extremely easy" for ChatGPT

A future ChatGPT should be able to do the following without architecture archaeology:

1. Read `00_READ_ME_FIRST.md`.
2. Read `CHATGPT_CONTEXT_INDEX.json`.
3. Execute the exact verify command from `COMMANDS.json`.
4. Inspect `CAPABILITY_SUMMARY.json` for the sport/league/market.
5. Inspect only the referenced platform rule row and sport plugin docs.
6. Call the standard v6 application interface.
7. Read `RUNS/<run_id>/run_integrity.json`, `card.json`, and `blockers.json`.
8. Respond compactly.

If ChatGPT has to search hundreds of source files just to learn how to start a run, the package is not operator-friendly enough.

## 65. Final acceptance statement

The universal WSAB package is ready to serve as DCM v6's sport/platform foundation only when:

- baseline 46 remains green;
- every production sport plugin passes universal contract tests;
- every production market has exact MarketDefinition and capability evidence;
- platform rules fail closed outside verified scope;
- settlement is sport-agnostic and exact;
- sport physics remains separate from platform administration;
- all package bytes are hash-manifested;
- ChatGPT control/index files are complete;
- canonical v5.4.1 remains untouched;
- integration occurs only in a development tree;
- LR remains LR000000 absent future promotion evidence.

**The goal is not to hard-code every sport on Earth into one giant script. The goal is to make every new sport a bounded, versioned, testable plugin that cannot contaminate the shared DCM architecture and cannot become selectable until its exact contracts are proven.**

