# PILLARS DCM v6.0 — GROK MASTER BUILD PROMPT
## CHATGPT-NATIVE FULL-BOARD PROP RESEARCH, FORECASTING, RANKING, AUDIT, AND CONTINUAL-LEARNING OPERATING SYSTEM

### COMMAND TO GROK

You are the principal systems architect and implementation owner for **Pillars DCM v6.0**.

This is an **IMPLEMENTATION COMMAND**, not a brainstorming request.

Build the DCM so that its normal user workflow inside the Pillars ChatGPT Project is:

```text
1. Canonical DCM v6 source is already stored in the Pillars Project.
2. User uploads ONE current HAR from PrizePicks or Outlier Bet.
3. ChatGPT verifies DCM + HAR hashes.
4. ChatGPT extracts the COMPLETE prop population from the HAR.
5. ChatGPT identifies every unique:
      sport → league → event → team → player → market.
6. ChatGPT gathers current, pre-cutoff evidence for those events/teams/players.
7. EVERY extracted non-Goblin prop is explicitly processed through DCM.
8. Unsupported / bad / weak props fail closed only AFTER being accounted for.
9. DCM ranks the complete modeled population.
10. Top 25 qualified Higher/Lower findings float to the top statistically.
11. Full Top 100+ and complete-board population remain persisted in artifacts.
12. ChatGPT returns a compact Top 25 with the evidence and calculations that
    caused each row to rank where it did.
13. After games finish, settle ALL frozen props, not just the Top 25.
14. Audit Top 25 vs ranks 26–100 vs the rest of the board.
15. Discover ranking/model failure patterns.
16. Propose future-only patches. Never rewrite a past forecast.
```

The DCM must be capable of hundreds or thousands of prop rows without silently skipping rows, fabricating research, inventing probabilities, or pretending an interrupted run finished.

The architecture may be large. The operator experience must be simple.

---

# 1. SOURCE AUTHORITY

Before implementation, load and reconcile all available Pillars sources, especially:

1. Canonical `Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt`
2. Canonical `Pillars_DCM_v5.4.1_Learning_Ledger.xlsx`
3. Canonical `Pillars_DCM_v5.4.1_INSTALL_SHA256.txt`
4. DCM v6 Master Blueprint / Phase A/B/C work
5. DCM Computational/Algorithmic Optimization Blueprint v2
6. Original Extreme Performance A–N requirements
7. ADR-V6-001
8. `dcm_v6_workstream_ab`
9. WSAB implementation/test reports
10. Universal WSAB 46+ blueprint
11. The Pillars chats/projects concerning:
    - Identify DCM Optimization File
    - Implement Basketball Registry
    - Critique Forecasting Upgrade
    - DCM 5.0–5.4.1 development
    - zero-eligibility registry failure
    - full-board audits
    - hidden-winner analysis
    - WNBA role/minute errors
    - NFL preseason workload
    - CFL work
    - MLB / NPB / KBO
    - Ryan Feltner / pitcher fantasy bonus flips
    - UFC significant strikes / fight state
    - soccer
    - tennis
    - cricket
    - hockey
    - golf
    - MMA / boxing
    - Green Goblins
    - Red Demons
    - offered-side enforcement
    - line tolerance
    - ranking regret
    - probability vs reliability
    - future-only Oracle/Shadow learning
12. Any Pillars Learning Ledger rows and postmortems relevant to sports/markets.

Expected canonical v5.4.1 hashes:

```text
SOURCE:
bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474

LEDGER:
a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a
```

Do not silently substitute a different DCM version.

If an artifact/chat is unavailable, record:

```text
MISSING
UNVERIFIED
AFFECTED_REQUIREMENTS
```

Do not invent what it contained.

---

# 2. THE PRIMARY PRODUCT REQUIREMENT

The DCM is not merely a library of sports equations.

It is a **ChatGPT-native, artifact-first forecasting operating system**.

The user’s intended interaction is:

```text
User:
"Run DCM on this HAR. Give me the Top 25."

ChatGPT:
- verifies installation
- verifies HAR
- processes full board
- researches the slate
- runs DCM
- freezes complete population
- returns Top 25 / card / blockers
- preserves the entire run for later audit
```

There must be no requirement for the user to manually:
- list players;
- copy game logs;
- identify teams;
- provide matchups;
- pre-sort props;
- decide which props are worth researching;
- calculate probabilities;
- manually merge DCM modules.

The HAR + canonical DCM + web-accessible evidence should be enough for the normal workflow.

---

# 3. CHATGPT ENVIRONMENT LAW

Design around what ChatGPT can reliably do, not an imagined always-on server.

## ChatGPT can be used to:

- read project files and uploaded files;
- reconstruct a portable Python source tree from a canonical source bundle;
- hash files;
- inspect and sanitize HAR bytes;
- execute bounded Python computations in the active session;
- use web search for current and historical public information;
- research players, teams, injuries, lineups, matchup news and statistics;
- reuse evidence across multiple props;
- create JSON/JSONL/CSV/SQLite/checkpoint artifacts;
- rank and audit complete prop populations;
- resume from persisted artifacts/checkpoints in later turns when the project context remains available;
- explain each Top 25 selection from stored evidence and model traces.

## Do NOT design around ChatGPT being able to:

- keep an arbitrary process running forever;
- guarantee one uninterrupted multi-hour Python call;
- guarantee every website is accessible;
- bypass login/paywalls;
- replay private authenticated HAR sessions;
- remember thousands of dynamic prop rows perfectly as conversational memory;
- rely on conversational prose as the authoritative database;
- guarantee a scheduled task can access the Pillars Project files;
- fabricate missing game logs because a web page failed;
- continue an unfinished simulation silently after the session stops.

Therefore the DCM MUST be:

```text
bounded
batched
checkpointed
restartable
artifact-first
hash-verifiable
fail-closed
```

Any stage that may be long must support partial completion + exact resume.

If ChatGPT cannot complete the whole run in the current execution window:

```text
RUN_STATE = INCOMPLETE_CHECKPOINTED
```

It must return:
- completed stage;
- exact row counts;
- exact pending events/players/props;
- blockers;
- checkpoint hash;
- next deterministic resume command.

It must NOT approximate the remaining rows in prose.

---

# 4. MEMORY LAW — STATIC DOCTRINE VS DYNAMIC RUN DATA

Do not use ChatGPT saved memory as the canonical database for Top 100 or full-board results.

Use **Project files + run artifacts** as persistent memory.

Static doctrine may live in:
- Project instructions;
- `00_READ_ME_FIRST.md`;
- `CHATGPT_ENTRYPOINT.md`;
- `PILLARS_DCM_V6_OPERATOR_DOCTRINE.md`.

Dynamic run state must live in:

```text
RUNS/<run_id>/
```

The complete rankings, Top 100+, evidence and settlement population must be persisted there.

This distinction is mandatory:

```text
PROJECT MEMORY / INSTRUCTIONS
    = stable operating doctrine

RUN ARTIFACTS / LEDGER
    = exact dynamic data and audit history
```

Never trust conversational recall for exact:
- probabilities;
- ranks;
- lines;
- timestamps;
- hashes;
- game logs;
- Top 100 populations.

---

# 5. CANONICAL PACKAGE DESIGN

The canonical install should retain the clean three-file identity:

```text
Pillars_DCM_v6.0.0_COMPLETE_PROJECT_SOURCE.txt
Pillars_DCM_v6.0.0_Learning_Ledger.xlsx
Pillars_DCM_v6.0.0_INSTALL_SHA256.txt
```

The COMPLETE PROJECT SOURCE must embed everything required to reconstruct:

```text
dcm/
schemas/
configs/
rules/
tests/
fixtures/
tools/
docs/
operator/
performance/
release/
```

For operator convenience, optionally also publish small noncanonical convenience sources:

```text
PILLARS_DCM_V6_CHATGPT_ENTRYPOINT.md
PILLARS_DCM_V6_CAPABILITY_SUMMARY.json
```

They must be hash-bound to the canonical source.

One exact install command must reconstruct the tree into the active sandbox.

One exact verify command must verify every embedded file.

---

# 6. PLATFORM INPUT ADAPTERS

Implement a common interface:

```text
MarketCaptureAdapter
```

with at least:

```text
PrizePicksHARAdapter
OutlierBetHARAdapter
```

Do not assume Outlier’s HAR schema is the same as PrizePicks.

Each adapter must:

1. chunk-hash input;
2. security-sanitize;
3. index only relevant endpoints;
4. normalize source-specific identities;
5. reconstruct latest-as-of market state;
6. preserve line/modifier/side/status history;
7. emit common normalized `board.json`.

If Outlier contains lines from multiple books/platforms, preserve the source book/platform identity.

Never collapse distinct source lines into one fake market.

---

# 7. HAR SECURITY

HAR files are market evidence, not authentication authority.

Never persist, print, export, reuse or replay:

```text
Authorization
Cookie
Set-Cookie
CSRF
access token
refresh token
session id
account id unless structurally required and pseudonymized
device ids
personal info
private entry history
```

Raw HAR must never enter the canonical release.

The run may store:

```text
HAR SHA-256
capture start/end
safe endpoint metadata
normalized market rows
response content hashes
change deltas
security redaction counts
```

---

# 8. COMPLETE BOARD EXTRACTION

Extraction must happen BEFORE Green Goblin elimination.

This is required for accounting.

The pipeline must report:

```text
raw_projection_rows
unique_offer_rows
standard_rows
goblin_rows
demon_rows
unknown_modifier_rows
unknown_side_rows
duplicate_rows
removed_rows
unresolved_rows
final_model_population
```

Every visible/normalized prop from the HAR gets an identity.

Then apply exclusion/eligibility.

Green Goblins:
- extract;
- identify;
- record;
- exclude from production selection;
- optionally model for analytics/audit if cheap;
- never allow into Top 25 qualified recommendations or submitted portfolios.

---

# 9. USER HALF-LINE AVOIDANCE POLICY

Create an explicit configurable policy:

```text
HalfLineAvoidancePolicy
```

The user prefers to avoid certain `.5` prop lines in markets/sports where they are frequently promotional, low-ceiling, fragile, or too tightly concentrated around common discrete outcomes.

Initial preference includes:

```text
BASEBALL:
  Hits + Runs + RBIs at 0.5:
    AVOID_BY_DEFAULT
```

Also inspect other `.5` markets for:
- Goblin association;
- promo association;
- discrete-state fragility;
- very high line elasticity;
- insufficient downside/upside cushion.

IMPORTANT:
Do not encode the false generalization that “a bigger line always gives both Higher and Lower more room.”

Line value is directional:
- increasing line generally helps a Lower;
- increasing line generally hurts a Higher;
- exact effect comes from the modeled distribution.

Therefore `.5` avoidance is a **user preference / fragility gate**, not a mathematical axiom.

The policy must be:
- configurable by Sport × League × Market;
- versioned;
- audited;
- demotion/exclusion-only;
- removable later if future evidence shows it is harmful.

Unknown or changing modifier behavior must not be inferred.

---

# 10. EVERY PROP MUST ENTER THE DCM

This is non-negotiable.

The user does not want ChatGPT to pick 25 interesting props first and model only those.

Required sequence:

```text
HAR
→ ALL normalized prop rows
→ extraction accounting
→ Goblin / hard policy exclusions
→ capability + definition checks
→ shared evidence acquisition
→ full-board fast modeling
→ quality / blocker classification
→ candidate refinement
→ complete ranking
→ Top 100+
→ Top 25
```

Bad props may be discarded from selection only after the DCM has assigned an explicit state/reason.

No silent pruning.

Every row gets one of:

```text
MODELED
UNSUPPORTED_FAIL_CLOSED
MISSING_DEFINITION
MISSING_EVIDENCE
OFFERED_SIDE_UNKNOWN
MODIFIER_UNKNOWN
GOBLIN_EXCLUDED
HALF_LINE_POLICY_EXCLUDED
STALE_EVIDENCE
EVENT_STARTED
DUPLICATE
OTHER_EXPLICIT_BLOCKER
```

---

# 11. PLAYER / TEAM / MATCHUP DISCOVERY

Once the HAR is normalized, build canonical unique sets:

```text
Sports
Leagues
Events
Teams
Players
Markets
```

Resolve each player to:
- canonical player ID;
- current team;
- opponent;
- event;
- role/position;
- league.

Do not infer team from stale memory if the HAR / current evidence contradicts it.

Create:

```text
EntityResolutionReport.json
```

Unresolved player/team/event identity fails closed for selection.

---

# 12. RESEARCH REQUIREMENT — ALL UNIQUE PLAYERS, SHARED EVIDENCE

For every unique player whose props remain in the model population, gather a reusable evidence packet.

Do NOT run one web search per prop if a player has 8 props.

Research hierarchy:

```text
Sport
→ League
→ Event
→ Team
→ Player
→ Market
```

Research once at the highest reusable scope.

## EVENT packet

Gather as applicable:
- date/time;
- venue;
- home/away;
- weather/roof for outdoor sports;
- travel/rest;
- competition/round;
- expected pace/tempo;
- event status;
- relevant officials/referees only if demonstrated useful.

## TEAM packet

Gather:
- current-season record;
- offense/defense team statistics;
- pace/possessions/plays/tempo;
- opponent-specific strengths/weaknesses;
- lineup/depth chart;
- injuries;
- suspensions;
- recent role changes;
- starting lineup;
- bullpen/rotation/depth information where relevant;
- current-season data first;
- previous-season data as a fallback when current-season sample is absent/thin.

## PLAYER packet

Gather as much trustworthy game-level historical data as reasonably accessible:
- current season game logs;
- previous season if current season is unavailable or too small;
- minutes/snaps/routes/PA/BF/opportunity;
- primitive stat results;
- starter/bench state;
- role changes;
- injury/return;
- home/away;
- opponent;
- game context.

Also gather:
- season average;
- recent 5/10/15/20 where meaningful;
- role-epoch sample;
- comparable-role sample;
- same-opponent history;
- similar-opponent history;
- current-line clears/fails.

Same-opponent samples must not be overweighted when tiny or stale.

## NEWS / SENTIMENT packet

Gather:
- official team/league status;
- reliable beat/news reporting;
- coach/player role comments;
- injury updates;
- lineup changes;
- workload limits;
- matchup narratives;
- recent performance context;
- meaningful market-moving information.

Keep sentiment separate from facts.

Store:
- source;
- published time;
- observed time;
- claim;
- reliability;
- whether confirmed/rumor/opinion;
- affected model component.

Do not allow generic positive/negative sentiment to override quantitative evidence automatically.

---

# 13. EVIDENCE SOURCE HIERARCHY

Prefer:

1. official league/team/stat providers;
2. official box scores/game logs;
3. established statistics providers;
4. reputable sports/news sources;
5. credible beat reporting;
6. broad media;
7. community/social sentiment only as low-authority contextual evidence.

If one source is unavailable, use another.

Do not fabricate a full game log from snippets.

Every quantitative feature used in Top 25 must be traceable to:
- a source/evidence record;
- a frozen parameter;
- or a deterministic transformation.

---

# 14. CURRENT VS PREVIOUS SEASON

Use current-season information first.

If no current-season data exists or sample is immature:

```text
current season
+ prior season
+ role-comparable priors
+ league/market priors
```

with hierarchical shrinkage.

Previous-season data must not be treated as equally current.

Record:
- sample count;
- age;
- team/coach/role changes;
- competition changes;
- whether prior-season carryover was used.

---

# 15. ROLE EPOCHS

Do not blindly average all historical games.

Create role epochs based on:
- starter/bench;
- minutes;
- snaps;
- routes;
- attempts;
- targets;
- carries;
- PA/BF;
- batting-order position;
- pitcher role;
- line assignment;
- special teams;
- injury return;
- team change;
- coach/system change;
- lineup change.

Old-role data becomes a shrunk prior, not equal-weight evidence.

Any detected role shift requires dated contextual evidence before production authority.

---

# 16. CURRENT-LINE HISTORICAL ANALYSIS

All hit-rate studies must evaluate historical actual stat output against **today’s HAR line**.

Do not confuse:

```text
historical prop result vs historical line
```

with:

```text
historical stat output vs today's line
```

Calculate for relevant windows:
- raw clears;
- smoothed clears;
- effective N;
- posterior interval;
- margin over/under line;
- near-line mass.

---

# 17. OPPONENT / MATCHUP MODEL

Research and model opponent context at the stat/opportunity level.

Examples:
- basketball pace, positional/role matchup, rebound/assist/shot environment;
- football pressure, coverage, rush defense, pace, expected game script;
- baseball pitcher/batter handedness, park, bullpen, lineup;
- soccer possession, shot creation/concession, role matchup;
- hockey shot/goalie environment, TOI, special teams;
- tennis serve/return matchup and surface;
- UFC style/state transition matchup;
- cricket format/opposition/venue;
- golf course/field conditions.

Do not use a generic “opponent rank” as a magic multiplier.

Model:
- opportunity effect;
- efficiency effect;
- uncertainty;
separately.

---

# 18. MODEL CAUSAL ORDER

Keep:

```text
Event environment
→ discrete regime
→ team/side opportunity
→ player role
→ player opportunity
→ conditional efficiency
→ primitive stats
→ derived stats
→ prop distribution
```

Never merge opportunity and efficiency into one opaque adjustment.

---

# 19. SHARED EVENT WORLDS / PRIMITIVE LEDGERS

Use the DCM v6 Phase B/C doctrine.

For each event:
- build shared EventWorlds once;
- derive team/player primitives;
- validate conservation;
- freeze PrimitiveStatLedger;
- derive all related markets.

Do not independently simulate:
- PRA;
- points+rebounds;
- pass+rush;
- rush+rec;
- H+R+RBI;
- fantasy score;
- other composites.

Composite = deterministic function of primitives under exact MarketDefinition.

---

# 20. SPORT COVERAGE

The workstream must be universal by plugin architecture and fail-closed support.

At minimum architect and implement support paths for:

```text
GRIDIRON
  NFL
  NFL postseason
  NFL preseason analytics
  CFB
  CFL
  UFL

BASKETBALL
  NBA
  WNBA
  NCAA M
  NCAA W
  G League
  FIBA/international

BASEBALL
  MLB
  NPB
  KBO
  CPBL
  LMB
  WBC/international

SOCCER
HOCKEY
TENNIS
CRICKET
MMA/UFC
BOXING
GOLF
ESPORTS by game
LACROSSE
HANDBALL
AFL/AFLW
RUGBY
VOLLEYBALL
MOTORSPORT
future international sports
```

A sport becomes production selectable only after:
- plugin exists;
- primitive registry exists;
- league rules exist;
- conservation exists;
- MarketDefinition exists;
- distribution exists;
- evidence requirements exist;
- platform participation rules exist;
- tests pass.

Unknown sport/market:
`UNSUPPORTED_FAIL_CLOSED`.

---

# 21. GREEN GOBLIN / DEMON LAW

Green Goblins:
- always extract/account;
- always exclude from production selection;
- never resurrect via ranking/portfolio/manual path.

Red Demons:
- require stricter:
  probability lower bound;
  edge;
  robustness;
  line tolerance;
  fragility;
  false-sign protection.

Demon policy is demotion-only until future validation.

---

# 22. OFFERED SIDES

The internal distribution may compute P(Higher), P(Lower), P(Push), but production selection may use only a side actually offered by the source.

Store:

```text
offered_higher
offered_lower
offered_side_verified
```

Unknown:
`OFFERED_SIDE_UNKNOWN`.

Never invent the other side.

---

# 23. PROBABILITY AND UNCERTAINTY OUTPUTS

Every modeled prop should record:

```text
P_Higher
P_Lower
P_Push
selected_side_probability
probability_lower_bound
model_mean
model_median
distribution_family
MCSE if simulated
aleatoric_uncertainty
epistemic_uncertainty
Reliability
DataQuality
Volatility
Fragility
OODRisk
FalseSignRisk
SelectionScore
RankStability
PortfolioUtility
```

Do not collapse these into “confidence”.

---

# 24. FULL LINE SURFACE

For serious candidates compute:
- offered-line probability;
- neighboring-line probabilities;
- break-even line;
- playable-break line;
- edge elasticity;
- robustness area;
- true unclamped tolerance;
- near-threshold mass.

Use common random numbers / same world sample for adjacent lines.

Do not clamp true tolerance for display convenience.

---

# 25. TOP 25 CONTRACT

There are two separate concepts:

## A. TOP 25 BOARD LEADERS

If at least 25 non-Goblin modeled rows exist, preserve the top 25 statistically ranked rows even if some are LEAN/PASS.

This is diagnostic ranking, not automatically a recommendation list.

## B. TOP 25 QUALIFIED

Return up to 25 rows that actually satisfy all DCM production requirements.

Do not force 25 PLAYABLES.

If only 13 pass:

```text
QUALIFIED_TOP25_COUNT = 13
```

The other 12 are not upgraded artificially.

The user-facing default should clearly distinguish:

```text
TOP 25 RANKED
vs
PLAYABLE / LEAN / PASS / TRAP
```

---

# 26. TOP 25 EXPLANATION REQUIREMENT

Every Top 25 row must include a compact but audit-grounded explanation.

Required fields:

```text
rank
sport
league
event
player
team
opponent
market
line
modifier
offered_sides
selected_direction
grade

P_Higher
P_Lower
P_Push
selected_probability
lower_bound

projection_mean
projection_median
line_edge
break_even_line
playable_break
true_line_tolerance
edge_elasticity

expected_opportunity
opportunity_range
clearing_opportunity where relevant
opportunity_clear_probability

season_sample_n
recent_sample_n
role_epoch_sample_n
same_opponent_sample_n
similar_opponent_sample_n

season_average
recent_average
current_line_clear_rate_raw
current_line_clear_rate_shrunk

opponent_context
role_status
injury_status
lineup_status
weather/travel if applicable
line_movement

Reliability
DataQuality
Volatility
Fragility
OODRisk
FalseSignRisk
SelectionScore
RankStability

top_evidence_ids
evidence_cutoff
parameter_snapshot_hash
world/ledger hash
market_definition_hash
forecast hash

primary_positive_reasons
primary_failure_paths
primary_uncertainties
why_grade
```

The explanation must distinguish:
- historical evidence;
- current matchup evidence;
- model projection;
- uncertainty;
- sentiment/context.

Do not explain a prediction with vague prose like “good matchup” without supporting features.

---

# 27. FULL POPULATION / TOP 100+ PERSISTENCE

The user wants to later inspect ranks 26–100+ if the Top 25 fail.

Therefore every run must persist:

```text
population_full.jsonl
population_full.csv or parquet if appropriate
top25_ranked.json
top25_qualified.json
top100.json
rank_frontier.json
excluded_population.jsonl
blockers.json
```

Do not store only Top 25.

If board has 3,000 props, persist all 3,000 states.

The full population is the real audit asset.

---

# 28. COMPLETE RUN DIRECTORY

Required:

```text
RUNS/<run_id>/
├── run_integrity.json
├── input_manifest.json
├── har_security_report.json
├── board.json
├── entity_resolution.json
├── event_inventory.json
├── team_inventory.json
├── player_inventory.json
├── evidence/
├── evidence_manifest.json
├── research_completeness.json
├── capability_report.json
├── parameter_snapshots/
├── parameter_snapshot_manifest.json
├── worlds/
├── world_manifest.json
├── primitive_ledgers/
├── primitive_ledger_manifest.json
├── conservation_report.json
├── market_projections/
├── probability_report.json
├── line_surfaces.json
├── population_full.jsonl
├── excluded_population.jsonl
├── grades.json
├── rank_frontier.json
├── top100.json
├── top25_ranked.json
├── top25_qualified.json
├── portfolio.json
├── card.json
├── blockers.json
├── freeze.json
├── checkpoint.json
├── hashes.txt
├── audit_trace/
└── logs/
```

---

# 29. RESEARCH COMPLETENESS GATE

Before declaring the run complete, calculate:

```text
unique_players_total
unique_players_researched
events_total
events_researched
teams_total
teams_researched
props_total
props_modeled
props_blocked
props_excluded
props_unresolved
evidence_packets_complete
evidence_packets_partial
```

A Top 25 candidate cannot be marked fully vetted if its required evidence packet is incomplete.

If the system cannot research the full board in one session:
- checkpoint;
- return incomplete;
- resume.

Never pretend the remaining rows were vetted.

---

# 30. EFFICIENT WEB RESEARCH

Large boards require aggressive evidence reuse.

Do not search the same:
- team injury;
- matchup;
- weather;
- lineup;
- player game log;
multiple times.

Create shared evidence cache keyed by:

```text
semantic_scope
entity
forecast_cutoff
source_version
TTL
```

Research batch order:

```text
all events
→ all teams
→ all players
→ market-specific unresolved questions
```

This lets one event/team/player packet support many props.

---

# 31. SOURCE FAILURE / MISSING DATA

If historical data cannot be obtained:

Do not invent.

Use explicit fallback ladder:

```text
official current season
→ trusted current season
→ official prior season
→ trusted prior season
→ role-comparable prior
→ league/market prior
→ FAIL_CLOSED if still insufficient
```

Every fallback must lower Data Quality / increase epistemic uncertainty appropriately.

---

# 32. NEWS / SENTIMENT USE

Sentiment is not a replacement for stats.

Maintain separate objects:

```text
FACT_CLAIM
STATUS_CLAIM
ROLE_CLAIM
MATCHUP_CLAIM
SENTIMENT_CLAIM
RUMOR_CLAIM
```

Only high-authority confirmed claims can directly alter availability/role state.

Broad sentiment may:
- raise a research flag;
- increase uncertainty;
- identify a possible role shift;
- provide context;
but cannot mechanically create a large probability edge.

---

# 33. RANKING

Rank after the complete modeled population exists.

Ranking must account for:
- selected-side probability;
- probability lower bound;
- material edge;
- line robustness;
- opportunity support;
- Reliability;
- Data Quality;
- Volatility;
- Fragility;
- OOD;
- False-Sign Risk;
- rank uncertainty;
- portfolio/correlation risk.

Keep `Probability` separate from `SelectionScore`.

Store posterior/rank uncertainty where supported:
- P(True Top 25)
- P(True Top 100)
- rank entropy
- regret.

---

# 34. PARLAY / PORTFOLIO LAYER

The DCM must learn about props and about multi-leg entries separately.

Do not judge a prop solely by whether a parlay containing it won.

Portfolio layer must enforce:
- unique players;
- same-event limits;
- same-player multi-market limits;
- shared QB/offense dependence;
- teammate competing opportunity;
- shared injury;
- shared weather;
- shared source;
- component/composite dependence;
- same failure path.

Track:
- individual leg model quality;
- lineup joint probability;
- payout contract;
- payout vs net-positive probability;
- correlation/failure path;
- actual lineup outcome.

Never force a 6-leg card.

---

# 35. FREEZE EVERYTHING BEFORE OUTCOMES

Freeze the COMPLETE population before any current-slate outcome is read.

The freeze must bind:
- board;
- evidence cutoff;
- evidence hashes;
- parameter snapshots;
- worlds/ledgers;
- probabilities;
- grades;
- ranks;
- Top 25;
- Top 100;
- portfolio;
- blockers.

No post-game edit to a frozen row.

---

# 36. SETTLE ALL PROPS

After official results are available:

Settle every frozen prop, not only selected legs.

This enables hidden-winner analysis.

Store for every row:

```text
actual_stat
comparison_result
administrative_state
economic_state where applicable
model_residual
probability_assigned
rank
grade
selected/not_selected
```

---

# 37. POST-SLATE AUDIT

Always compare:

```text
ranks 1–25
ranks 26–50
ranks 51–100
ranks 101+
excluded
blocked
```

Questions:

- Did Top 25 outperform 26–100?
- Did probability ordering correspond to outcomes?
- Were hidden winners concentrated in one sport/market?
- Did Lower/Higher bias appear?
- Did .5-line avoidance help/hurt?
- Did Goblin exclusion remain exact?
- Were role changes missed?
- Did same-opponent history overfit?
- Did current-season priors work?
- Did previous-season fallback cause errors?
- Did lineup/status data arrive too late?
- Did line movement after freeze matter?
- Did sentiment add useful information or noise?
- Did top-ranked failures share one mechanism?
- Did lower-ranked winners share one overlooked mechanism?
- Did portfolio correlation create common failures?

---

# 38. AUDIT METRICS

Do not use only hit rate.

Track where statistically appropriate:

```text
Brier score
log loss
CRPS
calibration curve
reliability diagram
coverage
false-sign rate
mean residual
rank correlation
Top-K inclusion performance
Top25 vs Top100 performance
directional Higher/Lower performance
sport/league/market performance
line-size bucket performance
modifier performance
role-epoch performance
DataQuality bucket performance
OOD bucket performance
```

Do not invent precision if sample size is small.

---

# 39. FUTURE-ONLY LEARNING

A losing Top 25 row does not automatically imply a model error.

Classify:

```text
NORMAL_VARIANCE
OPPORTUNITY_ERROR
EFFICIENCY_ERROR
ROLE_ERROR
STATUS_ERROR
MATCHUP_ERROR
SOURCE_ERROR
DEFINITION_ERROR
DISCRETE_STATE_ERROR
LINE_ERROR
RANKING_ERROR
PORTFOLIO_ERROR
EXTRACTION_ERROR
```

Allow soft posterior attribution when ambiguous.

New observations create:
- audit findings;
- candidate patches;
- shadow challengers.

They do not retroactively alter old forecasts.

Promotion requires future unseen evidence.

---

# 40. HIDDEN-WINNER / RANK-REPAIR PROGRAM

The full Top 100+ is specifically intended to reveal ranking defects.

For every slate:
- identify winners in ranks 26–100;
- compare them with Top 25 failures;
- calculate feature/market/role differences;
- test whether a stable pattern exists across future slates;
- create a shadow ranking challenger;
- promote only after chronological success.

Do not create a permanent rule from one hidden winner.

---

# 41. TREND PROGRAM

Persist trend features for all modeled props.

Monitor across slates:
- sport;
- market;
- line range;
- direction;
- role;
- opponent type;
- opportunity distribution;
- efficiency distribution;
- Data Quality;
- volatility;
- modifier;
- game environment;
- time to event;
- line movement.

Prevent trend mining:
record how many splits were searched.

Penalize high `TrendSearchComplexity`.

---

# 42. CHATGPT-NATIVE COMPUTE DESIGN

Full-board work may be large.

Implement:

```text
Tier 1: analytical / cheap full-board
Tier 2: fast event-world screening
Tier 3: serious candidate refinement
Tier 4: Top 100 / rank-boundary refinement
Tier 5: Top 25 / portfolio joint refinement
```

BUT:
Every row must still pass through DCM Tier 1/2 and receive an explicit state.

Deep computation may focus on contenders only after full-board screening.

This satisfies:
- all props explicitly processed;
- practical compute limits;
- no cherry-pick-first behavior.

---

# 43. CHECKPOINTING

Checkpoint at:

```text
HAR indexed
board frozen
entities resolved
event research done
team research done
player research batches
parameter snapshots
event worlds batches
primitive ledgers
full-board fast pass
Top100 frontier
Top25 refinement
ranking
freeze
settlement
audit
```

A checkpoint must include:
- completed event/player IDs;
- pending IDs;
- row counts;
- hashes;
- config;
- sources;
- blockers;
- next exact command.

---

# 44. NO STREAMING / INTERRUPTION HALLUCINATION

The system must never say:
- “all players researched”
- “all props modeled”
- “Top 25 final”
unless the relevant completion artifacts say so.

Create completion gates:

```text
BOARD_COMPLETE
RESEARCH_COMPLETE
MODEL_COMPLETE
RANK_COMPLETE
FREEZE_COMPLETE
```

Top 25 is FINAL only if all required gates are true.

Otherwise:

```text
TOP25_STATUS = PROVISIONAL_INCOMPLETE
```

or no Top 25 at all, depending on the missing stage.

---

# 45. EXACT APPLICATION API

Expose one public surface:

```python
verify_install()

ingest_har(
    path="INBOX/current.har",
    source="auto"
)

research_run(run_id)

model_run(run_id)

rank_run(run_id)

freeze_run(run_id)

run_from_har(
    path="INBOX/current.har",
    cutoff=...,
    source="auto",
    resume=True
)

resume_run(run_id)

settle_run(run_id)

audit_run(run_id)
```

`run_from_har()` orchestrates the whole path and checkpoints.

---

# 46. CHATGPT ENTRYPOINT FILE

Create `CHATGPT_ENTRYPOINT.md` containing exactly what a future ChatGPT session needs.

Example concept:

```text
WHEN USER SAYS "RUN DCM":

1. Read VERSION + INSTALL manifest.
2. Verify canonical hashes.
3. Find exactly one HAR in INBOX or current attachment.
4. Hash HAR.
5. Run verify_install().
6. Run run_from_har().
7. If checkpointed, resume until complete or tool/runtime boundary.
8. Do not answer final Top25 until MODEL_COMPLETE + RANK_COMPLETE.
9. Return:
   Run Integrity
   Top25 Qualified / Ranked
   playable card if requested
   blockers
   artifact paths
10. Preserve full population in RUNS/<run_id>.
```

---

# 47. CAPABILITY SUMMARY

`CAPABILITY_SUMMARY.json` must make it trivial for ChatGPT to answer:

“Can this market be run?”

Key:

```text
Sport
League
ProductType
Market
DefinitionVersion
PhysicsPlugin
OpportunityModel
EfficiencyModel
Distribution
Conservation
EvidenceRequirement
PlatformRule
ProductionState
BlockerCodes
```

---

# 48. RUN INTEGRITY OUTPUT

User-visible run summary:

```text
DCM version
LR
source hash
ledger hash
HAR hash
source adapter
forecast cutoff
raw rows
Goblin excluded
half-line policy excluded
modeled rows
blocked rows
unresolved rows
unique events
unique teams
unique players
research completion
model completion
rank completion
freeze hash
Top25 qualified count
Top100 artifact
full population artifact
```

---

# 49. TOP 25 PRESENTATION

Use compact tables.

For each row show at least:

```text
Rank
Player
Team/Opponent
Market
Line
Direction
Grade
Selected Probability
Lower Bound
Projection
Line Tolerance
Opportunity Support
Reliability
Data Quality
Fragility
Primary Evidence/Reason
Primary Risk
```

Then provide a concise evidence-backed note for each.

No unsupported narrative.

---

# 50. RELEASE / TEST REQUIREMENTS

Preserve WSAB baseline 46 once built.

Expand to:
- sport plugin tests;
- conservation tests;
- exact stat-definition tests;
- HAR adapter tests for PrizePicks and Outlier;
- Green Goblin tests;
- half-line policy tests;
- Demon tests;
- offered-side tests;
- research completeness tests;
- cutoff/leakage tests;
- line-surface monotonicity;
- ranking determinism;
- checkpoint/resume;
- performance regression;
- full-board accounting;
- audit/settlement.

Historical mechanism fixtures from Pillars must include:
- WNBA minute redistribution
- NFL preseason QB rotation
- CFL opportunity/weather/role lessons
- Ryan Feltner bonus flip
- UFC scaling
- KBO DNP/availability
- explosive Lower
- zero-eligibility registry bootstrap
- Goblin veto
- Demon cushion
- line movement after freeze
- source-scope mismatch
- role-epoch mismatch

---

# 51. PERFORMANCE

Use the Optimization Blueprint v2.

Do not rely on one enormous in-memory object.

Use:
- content-addressed DAG;
- bounded caches;
- event-once/markets-many;
- columnar arrays where useful;
- adaptive MC;
- common random numbers;
- sufficient stats;
- sparse dependence;
- bounded parallelism;
- ResourceGovernor;
- AdaptiveExecutionPlanner;
- token/evidence budgets;
- atomic checkpoints.

Benchmark:
- small board
- normal board
- largest known
- 2× stress
- mixed sport
- cold/warm
- repeated run
- interruption/resume
- settlement-only

No “optimized” claim without measured before/after.

---

# 52. EXPLICIT USER PREFERENCES TO FREEZE

The following are user operating preferences and should be encoded as versioned configuration rather than hidden assumptions:

```text
Green Goblins:
  NEVER SELECT

Red Demons:
  EXTRA CUSHION

Top 25:
  desired ranked research output

Top 100+:
  persist every run for hidden-winner/ranking audits

Full board:
  every prop accounted for before ranking

0.5 lines:
  user prefers avoidance in specified fragile/promotional markets,
  especially baseball H+R+RBI 0.5;
  policy is configurable and directional, not a universal theorem

Research:
  use as much trustworthy historical data as accessible;
  current season first;
  prior season fallback with shrinkage;
  role-comparable samples;
  current matchup/team/player evidence;
  injuries/lineups/news/sentiment

Audit:
  settle entire frozen population;
  compare Top25 vs 26–100 vs rest;
  learn future-only

Cards/parlays:
  no forced size;
  model correlation and shared failure paths
```

---

# 53. DO NOT DO THESE THINGS

Never:
- model only the first 25 interesting props;
- silently skip large portions of a board;
- fabricate player history;
- fabricate current team;
- fabricate injury status;
- fabricate sentiment;
- fabricate probability precision;
- fabricate line movement;
- fabricate official platform rules;
- silently use post-cutoff info;
- silently use outcomes;
- store Top100 only in conversational memory;
- return a “final” run when Research/Model/Rank gates are incomplete;
- use all historical games equally regardless of role change;
- overweight tiny head-to-head samples;
- assume previous season = current season;
- treat sentiment as truth;
- infer unknown side;
- select Goblins;
- force 25 PLAYABLES;
- assume higher numerical line helps both directions;
- simulate derived markets independently;
- use generic Normal fallback for unsupported sports;
- mutate canonical v5.4.1;
- bump LR for engineering changes;
- rewrite past forecasts after results.

---

# 54. REQUIRED PROJECT-OPERATOR DOCTRINE

Generate a stable file:

```text
PILLARS_DCM_V6_OPERATOR_DOCTRINE.md
```

This file must contain the user intent in a compact stable form so future ChatGPT sessions do not need to rediscover this conversation.

It must say:

> DCM v6 exists to take a PrizePicks or Outlier HAR, extract and account for the complete prop board, research every unique player/team/event at reusable scope, explicitly process every eligible non-Goblin prop through the DCM, rank the full population, expose the Top 25 with auditable evidence and calculations, persist Top 100+ and the full population, settle every frozen prop later, and use future-only audits to improve sport, market, ranking and portfolio models.

The operator doctrine is stable memory.

The exact Top100 from any slate is NOT stable memory; it belongs in run artifacts.

---

# 55. FIRST BUILD ACTION

Do not begin with speculative sport code.

First:

1. verify canonical v5.4.1;
2. verify/finish WSAB baseline 46;
3. freeze operator doctrine;
4. freeze HAR normalized board contract;
5. freeze EvidencePacket contract;
6. freeze Top25/Top100/full-population contracts;
7. freeze run-completion gates;
8. freeze checkpoint/resume contract;
9. build PrizePicks + Outlier adapters;
10. prove one sanitized historical HAR can go:
    HAR → board.json → full population accounting.

Then integrate DCM modeling.

---

# 56. SPRINT EXIT CRITERION FOR THE FINAL PRODUCT

DCM v6 is not accepted until a representative multi-sport HAR can demonstrate:

```text
HAR verified
board complete
Goblin accounting complete
player/team/event identities complete
research evidence complete or explicitly blocked
all props accounted
all supported props modeled
unsupported props fail closed
Top100 persisted
Top25 ranked
qualified/playable count honest
freeze complete
settlement replayable
audit trace complete
checkpoint/resume proven
no secret leakage
hashes reproducible
```

The final output may be EMPTY or fewer than 25 qualified selections.

That is not a failure.

A run that invents data or silently skips rows is a failure.

---

# 57. FINAL ACCEPTANCE PHILOSOPHY

The DCM should be able to improve for years because every slate preserves:

```text
what was offered
what was known
what was researched
what was modeled
what probability was assigned
why it ranked
what was selected
what actually happened
what failure mechanism was likely
what future-only challenger was created
```

The full-board archive—not only the winning/losing card—is the learning asset.

Build that system.

# END PROMPT
