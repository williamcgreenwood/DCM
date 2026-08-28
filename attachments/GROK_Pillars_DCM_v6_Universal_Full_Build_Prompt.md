# BEGIN PROMPT

# PILLARS DCM v6.0 — UNIVERSAL WORKSTREAM + FULL SYSTEM BUILD COMMAND FOR GROK

You are the lead statistical systems architect, probabilistic programmer, sports-modeling engineer, data engineer, platform-rules engineer, performance engineer, test engineer, model-risk auditor, release engineer, and integration owner for the **Pillars Distribution Cushion Model (DCM) v6.0**.

Your assignment is **implementation**, not brainstorming.

Build the universal `dcm_v6_workstream_ab` foundation and then integrate it, without modifying the canonical v5.4.1 installation in place, into a complete DCM v6 development tree whose end-state user story is:

```text
verified DCM v6 install
+ INBOX/current.har
        ↓
hash + sanitize + bounded HAR ingest
        ↓
immutable board.json
        ↓
research/evidence DAG
        ↓
Sport → EventWorld → PrimitiveStatLedger
        ↓
conservation + MarketDefinition
        ↓
P(Higher) / P(Lower) / P(Push) + line surfaces
        ↓
grade + rank + portfolio
        ↓
immutable freeze
        ↓
RUNS/<run_id>/
```

The final operator experience must be simple:

> Put one current PrizePicks HAR in `INBOX/current.har`, run one documented command, and receive a fully accounted `RUNS/<run_id>/` containing Run Integrity, immutable board state, evidence references, models/world manifests, grades, rankings, card-or-EMPTY, blockers, checkpoints, hashes, and later settlement/audit artifacts.

The internal architecture may be sophisticated. The user-facing operation must not be.

---

# 0. AUTHORITY ORDER — READ BEFORE WRITING CODE

Use the actual project files available in the Pillars project/workspace. Do not substitute memory for files.

Read and reconcile, in this order:

1. **Canonical Pillars DCM v5.4.1**
   - `Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt`
   - `Pillars_DCM_v5.4.1_Learning_Ledger.xlsx`
   - `Pillars_DCM_v5.4.1_INSTALL_SHA256.txt`
   - expected source SHA-256:
     `bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474`
   - expected ledger SHA-256:
     `a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a`

2. **DCM v6.0.0 Phase A/B/C Master Engineering Blueprint**
   - Document ID: `DCM-V6-BLUEPRINT-2026-08-27`
   - schema freeze: `PHASE_BC_SCHEMA_V1_2026-08-25`
   - declared canonical schema SHA-256:
     `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`
   - PrizePicks rule snapshot:
     `PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1`

3. **DCM Computational / Algorithmic Optimization Blueprint v2**
   - preserve every original Extreme Performance requirement A–N
   - preserve v2 sections 1–24
   - original Extreme Performance source SHA-256:
     `5316faca8580500d0e23474651905044ac8030c5b5ccd572532b6a1fba18a89d`

4. **ADR-V6-001 — Football Primitive Registry + E2E Settlement**
   - `DCM-ADR-V6-001-2026-08-27`

5. **Current WSAB executable tree and reports**
   - `dcm_v6_workstream_ab/`
   - `RELEASE_MANIFEST.txt`
   - WSAB implementation report
   - WSAB test report
   - historical baseline: 41 tests
   - intended compatibility baseline: `WSAB_BASELINE_46` after the five official-predicate tests are added

6. **Universal WSAB 46+ Blueprint**
   - use it as the packaging/operator/sport-plugin blueprint
   - do not reduce it back to a football-only tree

7. **Relevant Pillars project conversation history and artifacts**, especially:
   - **Identify DCM Optimization File** / the Extreme Performance and Optimization Blueprint work
   - **Implement Basketball Registry**
   - **Critique Forecasting Upgrade**
   - **DCM v6 Master Blueprint**
   - v5.0.0 through v5.4.1 HAR/runtime/audit/build conversations
   - prior complete-board audits and postmortems
   - CFL prop runs/audits
   - WNBA/NBA prop runs/audits
   - NFL preseason failures
   - MLB Pitcher Fantasy Score / Ryan Feltner lesson
   - UFC significant-strike modeling
   - KBO / NPB work
   - soccer, tennis, cricket, hockey, golf, MMA and other sport research in the Pillars project
   - Green Goblin / Red Demon / offered-side / line-tolerance / ranking-regret / hidden-winner analysis
   - all future-only learning / Oracle / Shadow governance discussions

If a referenced file or chat is unavailable in your workspace, write **MISSING / UNVERIFIED** in the build record and continue only where the missing evidence does not affect correctness. Do not invent bytes, hashes, test counts, platform rules, market definitions, or historical decisions.

---

# 1. WORKSPACE TRUTH AND LIFECYCLE LAW

Two workspaces are not automatically the same machine. Record truth per workspace.

Every build begins by creating/updating:

```text
LIFECYCLE.json
SOURCE_LINEAGE.json
PACKAGE_MANIFEST.json
BUILD_RECEIPT.json
SHA256SUMS.txt
```

Use explicit lifecycle states. Never let prose such as “accepted,” “done,” “live,” or “canonical” substitute for machine-readable status.

Required states include:

```text
DESIGNED
AUTHORIZED
IMPLEMENTED_STANDALONE
HASH_VERIFIED
SCHEMA_VERIFIED
BASELINE_TESTED
INTEGRATED_DEVELOPMENT
REGRESSION_VERIFIED
PERFORMANCE_VERIFIED
RELEASE_CANDIDATE
RELEASE_ACCEPTED
BLOCKED
UNVERIFIED
```

Canonical v5.4.1 must remain untouched. Create a development/integration copy. Never overwrite canonical bytes.

Software version changes do **not** change Learning Revision.

Keep:

```text
Learning Revision = LR000000
Predictive superiority claim = NONE
```

unless a separately governed future-only promotion earns a new LR.

---

# 2. NON-NEGOTIABLE DCM LAW

Make these executable invariants, not comments:

- Simulate a sporting event once as a shared world.
- Related markets derive from one immutable `PrimitiveStatLedger`.
- Never independently simulate composites such as PRA, pass+rush yards, rush+rec yards, fantasy score, H+R+RBI, etc.
- Opportunity and efficiency are separate objects.
- Structural conservation identities must hold in every world, not merely in expectation.
- Derived values may never overwrite primitive values.
- Unknown state is explicit.
- No fuzzy or nearest-match `MarketDefinition`.
- No fuzzy or nearest-match platform settlement rule.
- Primitive-stat validity is not the same thing as PrizePicks selectability.
- Green Goblins may be extracted, modeled, settled and audited but can **never** enter production selection.
- Red Demons require extra cushion; Demon treatment may only make selection harder, never easier.
- Respect offered sides only.
- Unknown offered side fails closed.
- Do not force 5, 6, 12, or any other card size.
- PLAYABLE is the only normal production-selection grade.
- LEAN, PASS, TRAP, UNKNOWN are not normal production legs.
- A legal empty card is success.
- Probability must remain separate from Reliability, Data Quality, Volatility, Fragility, OOD Risk, False-Sign Risk, rank stability and selection utility.
- Current-slate outcomes may never affect that slate’s frozen forecast.
- Preserve physical separation of:
  `PRODUCTION_BLIND`, `ORACLE_DISCOVERY`, `SHADOW_WALK_FORWARD`.
- Tracking systems such as Statcast, Next Gen Stats, SportVU/Second Spectrum, Hawk-Eye, ball tracking, vendor AI, WAR, etc. are evidence/features, not sport primitives unless a versioned MarketDefinition explicitly maps them.
- Settlement follows:
  Administrative → Comparison → Economic.
- Tie ≠ DNP ≠ Reboot.
- Displayed payout at submission is the contract.
- Final return is `max(Leaderboard, Minimum Guarantee)` where Leaderboard is modeled.
- Do not treat `P(payout>0)` as `P(net>0)`.
- Leaderboard EV without group-score distribution remains `UNMODELED`.

---

# 3. FROZEN CORE OBJECT MODEL

Preserve the Phase B/C contract. No sport may invent a parallel ledger/world/settlement architecture merely because its physics differ.

The universal chain is:

```text
FrozenEvidence
→ ParameterSnapshot
→ EventWorldSet
→ EventWorld
→ PrimitiveStatLedger
→ ConservationRule / InvariantResult
→ MarketDefinition
→ WorldProjectionResult
→ probability / line surface
→ grade / rank / portfolio
→ immutable freeze
→ EntryContract
→ WorldPickState
→ WorldLineupOutcome
→ official settlement
→ future-only learning
```

Persistent objects carry at minimum:

```text
schema_version
created_at_utc
learning_revision
source_hashes
content_hash
```

Timestamps and non-semantic metadata must not contaminate semantic content hashes.

Hash lineage must be explicit and must never silently replace an already-populated stage hash.

Recommended lineage:

```text
EvidenceGraphHash
→ ParameterSnapshotHash
→ EventWorldSetHash
→ PrimitiveLedgerHash
→ MarketDefinitionHash
→ WorldProjectionHash
→ Grade/Rank/Portfolio hashes
→ FreezeHash
→ EntryContractHash
→ SettlementRuleHash
→ WorldLineupOutcomeHash
→ SettlementHash
```

---

# 4. UNIVERSAL WSAB PACKAGE — BUILD THIS FIRST

Evolve `dcm_v6_workstream_ab` into the universal sport/plugin + PrizePicks contract foundation.

The historical 41 tests remain frozen regression coverage.

Add the five official-predicate tests and declare:

```text
WSAB_BASELINE_46
```

The final universal package is **46+**, not limited to 46. Expect hundreds of generated and sport-specific tests.

Required root layout:

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
├── schemas/
├── configs/
├── dcm/
├── fixtures/
├── tests/
├── docs/
└── reports/
```

The purpose of the root control files is to make future ChatGPT operation trivial. ChatGPT should not have to recursively rediscover the repository on every run.

`00_READ_ME_FIRST.md` must contain the exact first verification step.

`CHATGPT_CONTEXT_INDEX.json` must point to:
- package identity
- baseline identity
- schema identity
- capability registry
- platform rule registry
- commands
- tests
- failure-code registry
- operator entrypoint

`COMMANDS.json` must store exact commands for:
- package verification
- baseline verification
- schema verification
- baseline 46 tests
- individual sport tests
- all contract tests
- platform-rule validation
- integration smoke
- build/package
- run from HAR
- resume run
- settlement
- audit
- manifest generation

`CAPABILITY_SUMMARY.json` must answer, without repository archaeology:

```text
sport
league
product_type
market
definition_version
physics_plugin_status
market_definition_status
platform_participation_status
platform_reboot_status
production_selection_state
blocker_codes
```

---

# 5. UNIVERSAL SPORT PLUGIN SDK

Do not create a giant generic `sports.py`.

Use sport-family plugins under:

```text
dcm/sports/
├── common/
├── gridiron/
├── basketball/
├── baseball/
├── soccer/
├── hockey/
├── racket/
├── cricket/
├── combat/
├── golf/
├── esports/
├── lacrosse/
├── handball/
├── australian_rules/
├── rugby/
├── volleyball/
├── motorsport/
└── generic/
```

Every plugin must expose the same conceptual contract:

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

A new sport can appear in a HAR and be inventoried without being selected.

Default unknown behavior:

```text
SPORT_DISCOVERED
→ MARKETS_INVENTORIED
→ PLUGIN_MISSING or RULE_MISSING
→ UNSUPPORTED_FAIL_CLOSED
```

Never:

```text
UNKNOWN SPORT
→ GENERIC NORMAL DISTRIBUTION
→ PLAYABLE
```

---

# 6. SPORT FAMILY REQUIREMENTS

## 6.1 Basketball — NBA, WNBA, NCAA M/W, G League, FIBA/international

Basketball is the first live Phase B registry. Preserve and expand it.

Primitive topology must include:

```text
Minutes
FGA
3PA
2PA
3PM
2PM
FGM
FTA
FTM
OREB
DREB
REB
AST
STL
BLK
TO
PTS
```

Derived/composite only:

```text
PRA
PR
PA
RA
Blocks+Steals
Fantasy Score
other verified combos
```

Exact identities per world:

```text
2PA = FGA - 3PA
FGM = 2PM + 3PM
REB = OREB + DREB
PTS = 2*2PM + 3*3PM + FTM
made <= attempts
team/player minute conservation under exact league rules
```

Do not hard-code NBA 240 team-minutes for WNBA or international leagues. League rules own regulation length, OT structure and team-minute totals.

Preserve:
- shared event worlds
- possession/stint path where useful
- minutes/usage/shot-mix opportunity separation
- exact component-derived fantasy/combo stats
- capability-registry bindings
- the fix that eliminates hand-maintained market-family gaps such as FGA/FTA/3PA being supported but not recognized

## 6.2 Gridiron — NFL, NFL postseason, NFL preseason, CFB, CFL, UFL

Physical topology must support:

```text
team plays
drives
snaps
dropbacks
pass attempts
completions
sacks
scrambles
designed rushes
rush attempts
routes
targets
receptions
passing yards/TD/INT
rushing yards/TD
receiving yards/TD
kicker attempts/makes
punter attempts
role-specific defensive primitives where actual markets require them
```

Core identities:

```text
rush_att = designed_rush_att + scramble_att
dropbacks = pass_att + sacks_taken + scramble_att
team_off_plays = pass_att + rush_att + sacks_taken
pass_cmp <= pass_att
receptions <= targets <= routes
made <= attempts
```

Do **not** impose:
`sum(player_snaps) == team_plays`.

NFL/CFB/CFL/UFL may share physical topology but must have separate:
- league rules
- priors
- tempo
- roster/clock/field rules
- evidence defaults
- market definitions
- platform participation/reboot maps

Preseason workload uncertainty is a distribution, not “one half = deterministic attempts”.

Keep NFL preseason settlement fail-closed unless a verified rule snapshot exists.

CFB PrizePicks administrative rules may not inherit NFL rules. Current dated rules must remain versioned and exact. Regular season, bowls, CFP and other phases must be distinguishable.

## 6.3 Baseball — MLB, NPB, KBO, CPBL, LMB, WBC/international

Make baseball one of the strongest plugins.

Path unit:
`plate appearance / pitch / base-out state` where ordering matters.

Hitter primitives:

```text
PA
AB
H
1B
2B
3B
HR
BB
HBP
SO
R
RBI
TB
SB
Pitches Seen
```

Pitcher primitives:

```text
BF
Pitches
Strikes
Outs
K
BB
H
HR
ER
Hook state
```

Required identities include:

```text
H = 1B + 2B + 3B + HR
TB = 1B + 2*2B + 3*3B + 4*HR
PA identity under the exact league/stat-definition version
```

Do not confuse PA with AB.

Preserve the Ryan Feltner lesson:
base continuous fantasy production can sit below a line while Win/QS discrete bonuses flip final Fantasy Score.

Implement and test:

```text
BaseFantasyScore
FinalFantasyScore
BonusLeverageIndex
```

KBO/NPB reuse architecture, not MLB parameters.

## 6.4 Soccer

Shared match world:

```text
minutes
touches
passes
shots
shots_on_target
goals
assists
shots_assisted/chances_created
crosses
dribbles
tackles
interceptions
clearances
fouls
fouls_drawn
offsides
goalkeeper_shots_faced
goalkeeper_saves
goalkeeper_goals_allowed
```

Model:
- starting XI
- role/position
- substitution risk
- set-piece role
- team possession
- opponent state
- competition format
- extra time only when exact market definition includes it

Goalkeeper stats derive from the same opponent-shot world.

## 6.5 Hockey

Shared hockey event world with:

```text
TOI
shifts
SOG
goals
assists
points
blocked_shots
hits
PIM
faceoff events where relevant
goalie shots_against
saves
goals_allowed
```

Use exact official stat definitions. Only enforce identities that are definition-valid.

Example when valid:
`shots_against = saves + goals_allowed`.

## 6.6 Tennis and racket sports

Path:
`point → game → set → match`.

Model:
- serve state
- return state
- aces
- double faults
- holds/breaks
- break points
- games won
- total games
- tiebreaks
- sets
- fantasy components only from verified definitions

ATP, WTA, Challenger, ITF and team formats must be competition-configured, not flattened.

## 6.7 Cricket

Path:
`ball → over → innings → match`.

Separate T20, ODI, Test and other formats.

Primitives/configs may include:
- balls
- runs
- fours
- sixes
- wickets
- strike
- overs
- innings state
- batter/bowler opportunity
- dismissal types where required

No generic “cricket” distribution across formats.

## 6.8 MMA / UFC

One shared fight world for both fighters.

Primitives:

```text
fight_seconds
state_occupancy
significant_strike_attempts
significant_strike_landed
takedown_attempts
takedown_landed
control_time
knockdowns
submission_attempts
finish_state
finish_method
```

Hard bounds:
- landed <= attempted
- fight time <= scheduled time
- both fighters share one finish time
- decision vs finish exclusivity

Preserve prior significant-strike scaling lessons. Per-minute rates must use correct time units.

## 6.9 Boxing

Do not reuse UFC Significant Strike semantics.

Separate combat sibling plugin:

```text
round
fight_second
punch_attempts
punch_landed
knockdowns
stoppage
decision
```

Shared finish time and landed <= attempted.

## 6.10 Golf

Path:
`hole → stroke → round → tournament`.

Competition/tour config:
PGA, LPGA, LIV, DP World, majors and other exact formats.

Do not make Strokes Gained itself a PrizePicks primitive unless the market definition says so; it may be evidence for parameter estimation.

## 6.11 Esports

Never create one universal “ESPORTS” physics model.

Key the plugin by:
- game title
- patch/version
- map/round/objective format
- tournament format

Examples may include LoL, CS2, Valorant, CoD, Dota and others, but each requires its own market/stat semantics.

## 6.12 Additional supported architecture

Provide plugin/config slots for:
- lacrosse
- handball
- Australian rules
- rugby union
- rugby league
- volleyball
- motorsport
- other international competitions

Do not mark them production-supported until exact physics, MarketDefinitions, evidence requirements, tests and platform-rule rows exist.

---

# 7. PRIZEPICKS PLATFORM ENGINE

Treat PrizePicks as a separate, versioned platform plugin.

Never let sport physics and platform settlement contaminate each other.

Required key for exact lookup should include enough dimensions to avoid false matches, conceptually:

```text
Platform
+ ProductType
+ EntryType
+ League
+ BoardID
+ Market
+ Modifier
+ Side
+ RuleVersion
+ Situation
```

Support ProductType separation such as:

```text
PLAYER_PICKS
TEAM_PICKS
CULTURE_PICKS
```

unless the current official platform state uses different exact names.

Core `EntryContract` must freeze:
- platform
- platform_rule_version
- submitted_at
- entry_type
- product_type
- stake
- currency
- picks
- minimum_guarantee_definition_id
- leaderboard_definition_id
- payout_display_hash
- contract_hash

Each pick freezes:
- projection_id
- player/team/event identities
- market_definition_id
- line
- side
- modifier
- offered_side_verified
- leaderboard_point_weight
- reboot_rule_version
- participation_rule_version

Settlement order:

```text
AdministrativeState
→ ComparisonState
→ EconomicState
```

Administrative examples:
`ACTIVE, DNP, REBOOT, CANCELLED, INVALID_MARKET, UNRESOLVED`.

Comparison:
`WIN, LOSS, TIE, NOT_APPLICABLE`.

Economic:
`COUNTS_AS_WIN, COUNTS_AS_LOSS, TIER_REDUCTION, REMOVED, UNRESOLVED`.

Exact accounting invariants:
- active + administrative removals = frozen contract count
- wins + losses + ties/pushes = active comparison count
- tie remains in eligibility population where the frozen rule says so
- DNP/Reboot removal is distinct from tie
- same-team refund logic runs after administrative removal where the frozen contract requires it

Never infer payout from lineup size.
Never nearest-match an unknown payout table.
Unknown rule row → explicit failure code.

Keep:
- Leaderboard return UNMODELED without group distribution
- final return = max(LB, MG) when LB is actually modeled
- MG as lower-bound/partial result when LB is unmodeled
- P(payout>0) separate from P(net>0)

Version and hash every official rule snapshot.

If current web research is used to update PrizePicks rules:
- store source URLs/IDs, observed time, effective date, snapshot hash
- create a **new rule version**
- do not mutate historical snapshots
- do not copy one sport’s rule into another sport because it “seems similar”

---

# 8. HAR INGEST — THE SPINE OF THE FINAL DCM

The final DCM v6 must have a production entrypoint from HAR.

Use the strongest v5.4.1 HAR logic as the baseline and improve it without losing security or accounting.

HAR rules:

- chunk-hash input
- never ship raw HAR in canonical release
- never persist auth cookies/tokens/session/CSRF/device/account secrets
- no request replay
- deny identity/account/entry endpoints unless explicitly needed for non-sensitive structural validation
- allowlist relevant market endpoints
- bounded-memory parsing
- two-pass or equivalent selective indexing/decoding
- deduplicate byte-identical responses
- reconstruct latest-as-of market state per request scope
- preserve line/modifier/side/status change history

Identity contracts remain distinct:

```text
MarketEntityKey
OfferSnapshotKey
FrozenCandidateID
```

After successful ingest, immediately freeze `board.json`.

`board.json` must contain:
- HAR hash
- parser version
- capture start/end
- forecast cutoff
- event IDs
- projection IDs
- player/team/league identities
- market/stat definition reference
- exact line
- modifier
- offered sides
- Goblin/Demon flags
- timestamps
- row counts
- unresolved rows
- exclusion reason codes
- source-scope information

`current.har` is inbox-only. Downstream compute operates from immutable normalized artifacts whenever possible.

Full-board accounting is mandatory. Every extracted prop receives either:
- a modeled/graded result
- or an explicit fail-closed/blocker state

Never silently drop rows to save tokens or compute.

---

# 9. EVIDENCE / RESEARCH DAG

Research hierarchically:

```text
Sport
→ Event
→ Team
→ Player
→ Market
```

Compute/research each fact at the highest reusable scope exactly once.

Create an `EvidenceClaimStore`.

Each reusable claim stores:

```text
EvidenceID
SourceID
PublishedAt
ObservedAt
KnownAt
SemanticScope
ClaimType
Supports
Conflicts
Reliability
Freshness
TTL
ContentHash
```

Examples:
- event venue/weather
- team lineup/injury
- player availability
- minutes/snaps/routes/PA role
- opponent strength
- pace/possessions
- travel/rest
- stat-definition evidence
- market movement evidence

Prop records reference claim IDs instead of duplicating prose.

Use VOI scheduling:
research questions most likely to change probability, grade, Top-K membership, line tolerance or portfolio membership first.

Do not spend repeated searches reducing irreducible aleatoric uncertainty.

Current web evidence must never cross the forecast cutoff.

---

# 10. MODELING DOCTRINE

The causal stack remains:

```text
event environment
→ discrete uncertain regime
→ team/side opportunity pool
→ player role
→ player opportunity
→ conditional efficiency
→ primitive stats
→ derived stats
→ market distribution
```

Do not fit Higher/Lower as an isolated classifier divorced from event physics.

Use hierarchical shrinkage for small samples.

Represent discrete uncertainty explicitly:
- starter active/limited/out
- normal vs short rotation
- roof/open weather regime
- QB rotation states
- hook/finish states
- lineup states

Do not flatten genuine state uncertainty into arbitrary deterministic penalties.

Use path simulation where ordering matters:
- basketball possession/stint
- football drive/play
- baseball PA/base-out
- tennis point/game/set
- cricket ball/over/innings
- UFC fight-time
- golf hole/stroke
- etc.

Use aggregate models where path ordering adds little incremental value.

---

# 11. PROBABILITY, LINE SURFACES AND GRADE

For each prop calculate:
- P(Higher)
- P(Lower)
- P(Push) where applicable
- raw/model probability
- calibrated/evidence-safe probability where active
- uncertainty interval / lower bound
- Monte Carlo SE where simulation-based
- Reliability
- Data Quality
- Volatility
- Fragility
- OOD Risk
- False-Sign Risk
- selection utility
- line-surface diagnostics

Evaluate Higher and Lower independently, but select only offered sides.

For serious candidates compute full empirical line surfaces with common random numbers:
- offered-line probability
- break-even line
- playable-break line
- edge elasticity
- robustness area
- true unclamped line tolerance
- near-threshold mass
- opportunity clearing geometry

For strict Higher-like count markets where mathematically meaningful:

```text
ClearingOpportunity =
floor(Line / ConservativeEfficiency) + 1
```

Store:
- expected opportunity
- opportunity SD
- opportunity Z
- probability workload clears requirement
- workload straddle state

Grade every prop:
`PLAYABLE, LEAN, PASS, TRAP`.

PASS/TRAP should include directional preference when evidence permits.

Do not force a Top 5/6/12.

Return five only if five true PLAYABLES exist.

Portfolio must enforce:
- unique player
- Green Goblin veto
- Demon thresholds
- offered-side validity
- event caps
- same-player multi-market control
- same-team/shared-QB/shared-rotation/shared-weather/shared-injury dependence
- shared failure paths
- normally <= 2 players from one event unless explicit validated exception

---

# 12. CALIBRATION, BEL AND RESEARCH-ONLY CHALLENGERS

Preserve Phase A method roles:

```text
BEL_CHI2      diagnostic
BEL_FIXED_B   main temporal robustness challenger
ABEL          convex-hull robustness
PBEL          block-choice robustness
BEL_BARTLETT  research-only higher-order small-b
```

Do not use the simple i.i.d. EL Bartlett scalar for overlapping dependent BEL.

Politis–White may generate block-length candidates. It is not a theorem that the resulting L is BEL-coverage optimal.

BlockPlan must preserve:
- training-only selector
- training cutoff before evaluation
- regime boundaries
- selector version/hash
- fixed-b critical-value version where used

Research challengers:
- DPMM efficiency residual models
- Bayesian GP-LVM + ARD
- GPDM only after GPLVM proves sequential value
- other mixture/state-space/hierarchical challengers

No challenger receives production authority based on sophistication, clustering, reconstruction quality or in-sample fit.

Promotion requires future-only chronological improvements in proper scores, calibration, ranking and subgroup safety.

---

# 13. CONTENT-ADDRESSED DAG RUNTIME

Implement the Optimization Blueprint v2 execution model.

Every expensive/reusable stage becomes a node with deterministic key derived from:

```text
NodeType
+ CanonicalIdentity
+ ForecastCutoff
+ SourceVersionSet
+ ConfigHash
+ SchemaVersion
+ ParentHashes
```

Required states:

```text
PENDING
RUNNING
COMPLETE_VERIFIED
BLOCKED
INVALIDATED
FAILED_RETRYABLE
FAILED_TERMINAL
```

Recommended node types:

```text
InstallVerificationNode
SchemaRegistryNode
PlatformRuleTableNode
HARIndexNode
MarketSnapshotDeltaNode
BoardNormalizationNode
EvidenceClaimNode
EventEvidenceNode
TeamStateNode
PlayerRoleNode
ParameterSnapshotNode
EventWorldSetNode
PrimitiveLedgerNode
ConservationNode
MarketProjectionNode
LineSurfaceNode
CalibrationNode
GradeNode
DependenceGraphNode
RankNode
PortfolioNode
FreezeNode
SettlementNode
AuditNode
LearningCandidateNode
LedgerExportNode
ReleasePackageNode
```

Cache immutable outputs by content identity.

Invalidate only descendants of changed nodes.

Examples:
- line only → market surface/grade/rank/portfolio
- side/modifier → offer-dependent descendants
- status → player role + teammates + event worlds + descendants
- weather → affected event worlds + descendants
- platform rule version → settlement/economic descendants
- unchanged snapshot → no recomputation

---

# 14. PERFORMANCE / OPTIMIZATION CONTRACT

Do not call DCM “optimized” because it uses NumPy, caching or parallelism.

Instrument before redesign.

Measure every major stage:
- install verification
- source reconstruction
- HAR indexing
- HAR response decoding
- offer dedup
- board normalization
- registry bootstrap
- history loading
- evidence acquisition
- feature construction
- event grouping
- simulation
- market derivation
- probability
- calibration
- line surfaces
- ranking
- portfolio
- freeze
- workbook/ledger update
- package generation

Record:

```text
Stage
InputRows
OutputRows
WallSeconds
CPUSeconds
PeakRSSBytes
PeakPythonBytes
AllocationCount
BytesRead
BytesWritten
CacheHits
CacheMisses
ToolCalls
InputTokensWhenObservable
OutputTokensWhenObservable
RetryCount
CheckpointID
```

Maintain `Bottleneck_Register.json` with:
- location
- cause
- complexity before/after
- measured cost before/after
- fix
- correctness test
- regression threshold

Optimize only measured hot paths.

Use where measurements justify:
- NumPy/vectorized kernels
- contiguous arrays / structure-of-arrays
- integer/category encoding
- precomputed tables
- sufficient statistics
- batched probabilities
- event-once/markets-many
- common random numbers
- QMC
- adaptive simulation
- online aggregation
- bounded process pools for CPU
- bounded thread pools for I/O
- batched writes
- optional accelerated path with portable fallback

Never launch one worker per prop.

Benchmark sequential vs parallel.

Given identical inputs/config/seeds, parallel and sequential results must match within frozen numerical tolerances.

---

# 15. FIVE COMPUTE TIERS

Make the five tiers literal:

1. validated analytical/closed-form
2. board-wide fast pass
3. serious-candidate refinement
4. near-boundary/rank/tolerance refinement
5. selected-portfolio joint refinement

Do not retain all worlds for all props.

Use online statistics for:
- mean
- variance
- covariance
- P(Higher)/P(Lower)/P(Push)
- tails
- convergence
- bounded-memory quantiles

Retain full shared worlds only where justified:
- correlated derivation
- serious line surfaces
- portfolio dependence
- audit/golden fixtures
- posterior predictive checks

Stop increasing worlds once Monte Carlo error is too small to change:
- directional sign
- grade
- Top-K placement
- line tolerance
- portfolio membership

Record MCSE/convergence for serious candidates.

---

# 16. ADAPTIVE EXECUTION PLANNER + RESOURCE GOVERNOR

Implement `AdaptiveExecutionPlanner` and `ResourceGovernor`.

Planner inputs:
- CPU availability
- memory
- disk/spill availability
- board size
- event count
- sport mix
- time to cutoff
- measured task cost
- cache state

Planner chooses:
- sequential vs parallel
- worker count
- event batch size
- evidence batch size
- simulation batch size
- in-memory vs spill
- fast-pass/refinement budgets
- execution order

ResourceGovernor enforces:
- memory ceiling
- cache ceilings
- temp-disk ceiling
- worker ceiling
- research/tool budget
- simulation budget
- deadline budget

Pressure response:
1. stop starting new work
2. finish atomic work
3. evict safe cache
4. release objects
5. reduce concurrency
6. suppress noncritical diagnostics
7. spill if configured
8. checkpoint
9. resume boundedly

Never silently drop props.

---

# 17. SPARSE DEPENDENCY / PORTFOLIO GRAPH

Do not build dense full-board N² relationships by default.

Create edges only for meaningful shared mechanisms:

```text
same_event
same_team
same_player
same_QB_or_unit
competing_opportunity
shared_injury_state
shared_weather
shared_source_dependency
component_composite_identity
explicit_market_link
```

Use sparse graph operations for ranking/portfolio dependence.

---

# 18. CHECKPOINT / INTERRUPTION RESILIENCE

Every major DAG boundary writes an atomic checkpoint.

Checkpoint contains:

```text
Run ID
DCM version
Learning Revision
input hashes
config hash
forecast cutoff
completed node hashes
pending nodes
invalidated nodes
provider/evidence state
registry versions
platform rule versions
cache manifest
model-state hashes
seed manifest
artifact refs
row counts
stage diagnostics
unresolved blockers
next deterministic action
checkpoint hash
```

Write:
temporary file → validate → atomic rename.

On resume:
verify every referenced hash before continuing.

Interruption tests must cover:
- HAR indexing
- chronological reconciliation
- registry bootstrap
- evidence acquisition
- partial event simulation
- primitive ledger
- ranking
- settlement
- ledger/workbook update prep
- package creation before final hashing

---

# 19. CHATGPT / OPERATOR-FIRST PACKAGING

The final DCM must be easy for ChatGPT to operate.

Chat-facing output normally contains only:
- Run Integrity
- strict card or EMPTY
- compact qualified findings if requested
- essential blockers
- audit summary
- artifact links/hashes
- next deterministic action

Large board data, source, logs, evidence, ledgers, worlds and detailed audit belong in artifacts.

Never paste raw HAR into chat.

When context/token pressure rises:
1. checkpoint
2. compact completed-stage summary
3. preserve paths/hashes/schemas/blockers/next action
4. remove duplicate prose
5. continue from artifacts
6. never skip props/tests/research or fabricate completion

Create both:
- `DCM_CHAT_OPERATOR_V6`
- `DCM_WORK_OPERATOR_V6`

The operator should be able to verify the installation and launch the documented run without repository archaeology.

---

# 20. BASELINE 46 + UNIVERSAL TEST ARCHITECTURE

Freeze the original WSAB 41 tests.

Add five official-predicate tests for at minimum:
1. CFB regular season does not inherit CFP reboot
2. CFB bowl does not inherit CFP reboot
3. unknown CFB game phase → UNRESOLVED
4. NFL partial board does not inherit full-game reboot
5. second-half/3Q exit is not first-half/no-return reboot

Then declare:
`WSAB_BASELINE_46`.

After that, expand into hundreds of tests.

Every sport plugin automatically gets:
- manifest validation
- registry validation
- valid-world conservation
- corrupt-world rejection
- primitive/derived separation
- composite identity
- hash replay stability
- unknown market fail-closed
- exact MarketDefinition lookup
- unknown platform rule fail-closed
- offered-side enforcement
- Goblin rejection
- Demon stricter-than-standard
- same settlement adapter
- no forced card
- P(H)+P(L)+P(Push)=1
- line monotonicity
- opportunity monotonicity where applicable

Use test layers:
- unit
- moment
- property
- metamorphic
- integration
- golden historical
- HAR fixtures
- leakage/firewall
- performance regression
- interruption/resume
- sequential/parallel parity

---

# 21. TURN PILLARS HISTORY INTO GOLDEN REGRESSION FIXTURES

Mine the Pillars project history and Learning Ledger for known mechanisms.

At minimum create mechanism fixtures for:

```text
WNBA_MINUTE_REALLOCATION
NFL_PRESEASON_QB_ROTATION
CFL_ATTEMPT_WEATHER_DELAY
CFL_REPLACEMENT_RUSH_VOLUME
EXPLOSIVE_LOWER_SINGLE_PLAY
UFC_SIGNIFICANT_STRIKE_SCALING
UFC_TERMINAL_BURST
PITCHER_WIN_QS_BONUS_FLIP
KBO_DNP_SELECTION_ERROR
GREEN_GOBLIN_VETO
DEMON_EXTRA_CUSHION
SAME_QB_OFFENSE_DEPENDENCY
LINE_MOVEMENT_AFTER_FREEZE
SOURCE_SCOPE_ERROR
ROLE_EPOCH_MISMATCH
ZERO_ELIGIBILITY_BOOTSTRAP_FAILURE
UNVERIFIED_STAT_DEFINITION_FAILURE
```

Do not encode one loss as a permanent predictive rule.

Golden fixtures protect mechanisms and contracts, not hindsight picks.

Audit must distinguish:
- model error
- opportunity error
- efficiency error
- status/lineup error
- source/definition error
- discrete state error
- ranking error
- portfolio error
- normal variance/tail outcome

---

# 22. BUILD / SPRINT SEQUENCE

Use this sequence unless a hard dependency proves a change is required.

## Sprint 0 — Canonical Baseline + Contract Reconciliation
- verify v5.4.1 source/ledger hashes
- inventory WSAB
- freeze `WSAB_BASELINE_46`
- verify or mark schema hash state
- create lifecycle/source-lineage/package manifests
- no merge until identity is clear

## Sprint 1 — HAR Ingress + Immutable `board.json`
- reconstruct/use v5.4.1 HAR engine
- security firewall
- bounded parse
- board normalization
- exact accounting
- synthetic + historical HAR fixtures
- one `INBOX/current.har` contract

## Sprint 2 — Content-Addressed DAG + Checkpoint Runtime
- node keys/states
- cache
- descendant invalidation
- SQLite/runtime index if appropriate
- atomic resume

## Sprint 3 — v5 Forecast Engine → v6 World/Ledger Integration
- development copy only
- bridge v5 evidence/model inputs into EventWorld/PrimitiveLedger
- event-once/markets-many
- no canonical mutation

## Sprint 4 — Basketball + Football Production Integration
- preserve live basketball primitive registry
- integrate NFL/CFB WSAB
- CFL/UFL physical config where supported
- exact platform-rule separation
- carry baseline 46 forward

## Sprint 5 — Planner / Governor / Memory Architecture
- stage metrics
- columnar hot paths
- bounded caches
- adaptive simulation
- spill
- sequential/parallel benchmark

## Sprint 6 — Research DAG + Evidence Claim Store
- hierarchical evidence reuse
- VOI scheduler
- TTL/freshness
- token budget
- source contradiction/reliability

## Sprint 7 — Performance + Interruption Hardening
- baseline/final benchmarks
- largest HAR
- 2× board stress
- repeated-run leak test
- crash/resume
- parallel determinism
- bottleneck register

## Sprint 8 — Canonical v6 Release Qualification
- full regression suite
- quality gates
- performance artifacts
- migration report
- release-blocker checklist
- clean install package

## Sport expansion after the core runner is green
Prioritize:
1. MLB/Baseball → NPB/KBO/international
2. MMA/UFC → boxing
3. soccer + hockey
4. tennis + cricket + golf
5. remaining gridiron/international configs
6. esports
7. long-tail sports demand-driven

Do not block universal architecture on writing speculative settlement rules for every sport.

---

# 23. REQUIRED PERFORMANCE ARTIFACTS

Generate at minimum:

```text
Performance_Baseline.json
Performance_Final.json
Performance_Comparison.md
Bottleneck_Register.json
Complexity_Audit.md
Memory_Lifecycle.md
DAG_Execution_Profile.json
Cache_Reuse_And_Invalidation_Report.md
Primitive_Ledger_Performance_Report.md
Simulation_Convergence_Report.md
Research_Efficiency_Report.md
Token_Budget_Report.md
Resource_Governor_Report.md
Checkpoint_Resume_Runbook.md
Interruption_Recovery_Test_Report.md
Algorithm_Quality_Performance_Frontier.md
Performance_Attribution_Report.md
```

Do not fabricate these files.

A performance artifact exists only if the stated workload was actually executed and measured in that environment.

---

# 24. QUALITY / RELEASE GATES

Optimization is invalid if it materially worsens without an accepted measured quality gain:
- Brier
- log loss
- calibration
- CRPS
- interval coverage
- false-sign risk
- rank stability
- line monotonicity
- primitive identities
- deterministic reproducibility
- board accounting
- evidence coverage
- interruption recovery
- duplicate research/tool calls

Release blockers include:
- no E2E production profiling
- unverified canonical identity
- content-addressed DAG not exercised
- unbounded HAR memory
- duplicate event simulation
- non-immutable primitive ledgers
- composites simulated independently
- unbounded caches
- repeated-run memory growth
- adaptive convergence absent
- dense unnecessary board correlation
- unbounded/unproven parallelism
- exact rule tables missing
- duplicate research unbounded
- checkpoints absent
- interruption tests failing
- token controls absent
- performance artifacts missing
- quality regressions
- canonical package lineage unclear

No paragraph can substitute for a passing artifact + hash + metric.

---

# 25. REQUIRED RUN DIRECTORY

The final live runner must write:

```text
RUNS/<run_id>/
├── run_integrity.json
├── board.json
├── event_inventory.json
├── evidence_manifest.json
├── capability_report.json
├── parameter_snapshot_manifest.json
├── world_manifest.json
├── primitive_ledger_manifest.json
├── conservation_report.json
├── market_projection_manifest.json
├── probability_report.json
├── line_surfaces.json
├── grades.json
├── ranking.json
├── portfolio.json
├── card.json
├── blockers.json
├── freeze.json
├── checkpoint.json
├── hashes.txt
└── logs/
```

`card.json` may legitimately be empty.

---

# 26. FINAL PUBLIC API

The integrated v6 package should expose one documented application surface:

```python
verify_install()

run_from_har(
    path="INBOX/current.har",
    cutoff=...,
    config=...
)

resume_run(run_id)

settle_run(
    run_id,
    official_results,
    platform_evidence
)

audit_run(run_id)
```

Do not make the operator choose between a dozen undocumented orchestrators.

One command should launch a run.

One run ID should identify all artifacts.

---

# 27. CLEAN FINAL INSTALLATION

The canonical Pillars install should ultimately preserve the established clean delivery pattern:

```text
Pillars_DCM_v6.0.0_COMPLETE_PROJECT_SOURCE.txt
Pillars_DCM_v6.0.0_Learning_Ledger.xlsx
Pillars_DCM_v6.0.0_INSTALL_SHA256.txt
```

An optional ZIP may contain exactly those three canonical files.

Do not include:
- raw HAR
- credentials
- cookies
- access tokens
- private session data
- build temp directories

The COMPLETE PROJECT SOURCE must embed:
- doctrine
- source code
- schemas
- operator docs
- manifests
- tests
- sanitized fixtures
- capability registry
- platform rule registry
- runbook
- migration docs
- validation plan
- required performance/report generators

---

# 28. HOW TO EXECUTE THIS ASSIGNMENT

Do not answer with a design essay only.

Actually build the files.

At each sprint:

1. verify inputs and hashes
2. write/update `LIFECYCLE.json`
3. write exact implementation plan for that sprint
4. modify only the development tree
5. add/modify tests before declaring success
6. run the relevant test suite
7. generate artifacts
8. hash artifacts
9. update manifests
10. write a sprint receipt
11. checkpoint
12. move to the next sprint only when exit criteria are met

If context/runtime ends:
- stop at an atomic checkpoint
- write exactly what is complete
- list pending nodes
- give the next deterministic command
- do not reconstruct completed work from memory on resume

Never rewrite completed sprints unless their parent hash changed.

---

# 29. WHAT NOT TO DO

Do not:
- modify canonical v5.4.1 in place
- silently change the Phase B/C common schema
- claim schema hash verification without bytes
- claim WSAB 46 if only 41 tests are present
- force a lineup size
- select Goblins
- weaken Demon gates
- invent offered sides
- invent platform rules
- copy NFL reboot logic into CFB/CFL
- copy NBA participation rules into soccer/hockey/etc.
- infer PrizePicks payout from lineup size
- treat Team Picks as Player Picks
- use one generic distribution for unknown markets
- independently simulate composite markets
- hide unsupported rows
- use post-cutoff evidence
- use current outcomes for current predictions
- bump Learning Revision because engineering improved
- call DPMM/GPLVM/Bartlett production-ready without future evidence
- call the runtime “optimized” without before/after measurement
- fabricate performance SLOs
- fabricate test counts
- fabricate source hashes
- create a dense O(N²) dependency matrix without need
- use one worker per prop
- retain all worlds for all props by default
- dump full HAR/ledger/source into chat output

---

# 30. REQUIRED FINAL DELIVERABLE SET

When the full program reaches release-candidate status, produce:

1. Engineering audit
2. Pillars archaeology matrix
3. canonical baseline/hash report
4. WSAB baseline-46 receipt
5. universal sport/plugin capability matrix
6. LeagueRuleRegistry coverage
7. MarketDefinition coverage
8. PrizePicks platform-rule coverage
9. HAR extraction/security/accounting report
10. DAG/cache/invalidation report
11. performance baseline/final comparison
12. memory lifecycle
13. simulation convergence report
14. research/token efficiency report
15. interruption/resume report
16. algorithm quality/performance frontier
17. full categorized test report
18. migration matrix v5.4.1 → v6
19. future-only validation plan
20. updated Learning Ledger preserving inherited rows
21. release blocker checklist
22. exact package manifests and SHA-256 values
23. clean canonical three-file installation
24. optional three-file delivery ZIP
25. concise operator README showing exactly how to use `INBOX/current.har`

---

# 31. ACCEPTANCE STATEMENT

Do not call the final system complete merely because code exists.

The target state is:

```text
CANONICAL BASELINE VERIFIED
+ WSAB BASELINE 46 VERIFIED
+ UNIVERSAL SPORT PLUGIN CONTRACT VERIFIED
+ HAR→board accounting VERIFIED
+ EventWorld→PrimitiveLedger VERIFIED
+ exact MarketDefinition boundary VERIFIED
+ PrizePicks settlement VERIFIED
+ DAG/checkpoint/invalidation VERIFIED
+ full-board grade/rank/portfolio VERIFIED
+ interruption/resume VERIFIED
+ performance/quality gates VERIFIED
+ canonical release hashes VERIFIED
```

Predictive superiority remains:

```text
NONE
```

until later chronological evidence earns a Learning Revision promotion.

The architecture must be universal by **fail-closed extensibility**, not by pretending every unknown sport/market is already modeled.

---

# 32. FIRST ACTION

Before writing new code, perform Sprint 0.

Return a concise Sprint 0 Run Integrity showing:

```text
workspace identity
canonical v5.4.1 source hash observed vs expected
canonical ledger hash observed vs expected
WSAB tree identity
current WSAB test inventory
whether baseline 46 exists
schema bytes/hash verification state
PrizePicks rule snapshot state
development-tree path
canonical-tree path
lifecycle state
blockers
next deterministic action
```

Then proceed with the actual build only after the baseline is reconciled.

# END PROMPT
