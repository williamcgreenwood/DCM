# CURRENT WORK HANDOFF — 2026 CFB GUARDED LAUNCH

- **Timestamp:** 2026-09-03T06:15:00Z
- **Canonical integration branch:** `integration/v6-ml-architecture-20260830`
- **Canonical integration base:** `37e78ccfeff0bda74f8592bd46fb7d26e4b158e4` (through PR #16)
- **Active branch:** `chatgpt/cfb-guarded-launch-20260902`
- **Active PR:** #17
- **Verified implementation/governance SHA:** `567feaa5946efb0f9515f63775b1383f303e96fb`
- **Verified standard CI:** GREEN — DCM v6 branch CI run #223
- **Full pytest:** 350 passed / 0 failed
- **Code inventory:** 229 modules / 1,471 symbols / 0 parse errors
- **Inventory hash:** `38b8812f389c89a1ea47ed795e967e48ae3b681353aab317f7c0c7a6c4a80672`
- **Benchmark:** PASS — 100 and 1,000 row engineering synthetic smoke; host performance remains uncertified
- **Learning revision:** `LR000000`
- **Predictive claim:** `NONE`
- **Production root:** NOT CERTIFIED

This handoff and the immutable engineering-pass record are audit-only follow-up commits after the verified SHA above. The final PR head must pass the same standard CI before merge.

## COMPLETE NOW

### Canonical ancestry

- PR #16 donor Tranche A/B is inherited through the canonical integration base.
- PR #17 is based exactly on the integration line and targets integration only.
- No merge to `main` is authorized by this handoff.

### CFB guarded-launch research and modelability

- Real CFB boards with actual partial evidence are no longer rejected solely because unrelated global research requests remain missing.
- Research completeness remains visible and auditable.
- Zero real evidence still preserves the existing `RESEARCH_REQUIRED / INCOMPLETE_CHECKPOINTED` fail-closed behavior.
- Minimum model support and strict PLAYABLE support are separate.
- Thin but defensibly parameterized CFB props may reach `MODELED_DIAGNOSTIC`.
- `MODELED_DIAGNOSTIC` is not a PLAYABLE bypass.

### CFB evidence requirements

- Opportunity-only markets require actual relevant opportunity history but do not require irrelevant yardage-efficiency evidence.
- Efficiency-dependent markets retain relevant efficiency support requirements.
- ParameterSnapshots expose current-season support, prior-season support, role-comparable effective support, minimum model support, strict production/PLAYABLE support, role state, spread/total context when available and event-regime parameters.
- Unsupported or zero-history rows remain held/fail-closed rather than receiving invented precision.

### CFB role states

Implemented explicit early-season states:

- `RETURNING_STARTER`
- `RETURNING_ROTATION`
- `PROMOTED_STARTER`
- `TRANSFER_STARTER`
- `TRANSFER_ROTATION`
- `TRUE_FRESHMAN`
- `NEW_QB`
- `NEW_COORDINATOR_SYSTEM`
- `INJURY_RETURN`
- `ROLE_UNCERTAIN`

Transfer history may inform priors, but previous-school opportunity share is not carried over 1:1. `ROLE_UNCERTAIN` blocks strict PLAYABLE support while allowing bounded diagnostic modeling when minimum evidence exists.

### ChatGPT-native CFB research

The host research plan now explicitly requests, where relevant and available:

- complete 2026 player game logs;
- complete 2025 college history;
- current team/school and opponent;
- current roster/depth/starter state;
- injury/availability;
- transfer history;
- coordinator/system changes;
- team plays/pass/rush attempts, yards and scoring context;
- opponent defensive workload/yards/sacks/pressure/turnover/red-zone/explosive context;
- event start/status/venue/home-away/surface/roof;
- weather and severe-weather risk;
- spread/game total and meaningful movement as context only;
- verified full-game market definitions and settlement semantics.

The architecture reuses the canonical ResearchStore/EvidenceGraph/host observation pipeline. No second truth store or second probability engine was introduced.

### CFB EventWorld

CFB shared-world context now represents:

- competitive;
- controlled lead;
- blowout / starter curtailment.

These states modify workload/opportunity quantities rather than directly forcing a Higher/Lower direction.

### Guarded physical markets

The guarded football market set is:

- `pass_yds`
- `pass_att`
- `pass_cmp`
- `rush_yds`
- `rush_att`
- `rec_yds`
- `receptions`
- `pass_rush_yds`
- `rush_rec_yds`

### Acceptance evidence

Dedicated fixture:

`artifacts/dcm_v6_workstream_ab/fixtures/cfb_guarded_launch_har.json`

Dedicated acceptance tests:

`artifacts/dcm_v6_workstream_ab/tests/test_cfb_guarded_launch.py`

Verified properties:

- 8 total CFB offers extracted;
- 3 subjects;
- 1 event;
- 8/8 direct fixture rows reach probability evaluation;
- `P(Higher) + P(Lower) + P(Push) = 1`;
- real-shaped non-synthetic CFB HAR plus deliberately globally incomplete evidence does not blanket-checkpoint supported rows;
- all 8 rows in that partial-evidence acceptance path reach `MODELED` or `MODELED_DIAGNOSTIC`;
- missing global research remains recorded in `research_partial.json`;
- role uncertainty and thin support cannot silently become PLAYABLE.

Additional CFB tests cover opportunity-only attempts markets, thin yardage diagnostic modeling, zero-history research holds, explicit blowout regimes and transfer/promoted role classification.

### Sanitized historical HAR

Existing August 29, 2026 sanitized PrizePicks HAR remains valid accounting evidence:

- 11,113 unique offers;
- 1,568 CFB offers;
- 1,849 Goblins;
- 8,053 Demons;
- 1,211 Standard;
- 84 events;
- 1,358 players.

This HAR is historical/sanitized acceptance evidence. It is not a current September 2/3 live forecast.

**CURRENT_LIVE_CFB_HAR_NOT_SUPPLIED**

## NOT COMPLETE

The following remain explicitly unearned or incomplete:

- prospective CFB calibration;
- historical settlement calibration sufficient for model promotion;
- learned reliability thresholds;
- expanded/exotic football markets;
- advanced opponent-efficiency fields without reliable producers;
- full 24/24 SportPlugin coverage;
- broader P380X Tranche C+;
- complete universal Research OS;
- complete all-sport production physics;
- fresh-wheel/current-HAR production acceptance;
- production-root certification;
- host performance certification;
- predictive superiority.

Do not change `LR000000` or claim learned improvement based on this fixture/CI pass.

## NEXT EXACT TRANCHE

Use an actual **current CFB HAR supplied by the user** and execute:

`HAR → complete prop accounting → ResearchPopulation → hierarchical current web research → EvidenceGraph → ParameterSnapshots → CFB EventWorld → Higher/Lower/Push probabilities → uncertainty → PLAYABLE/LEAN/PASS/TRAP grading → ranking/portfolio controls → frozen forecast`

For the live acceptance:

1. extract every offered prop before exclusions;
2. remove Green Goblins after accounting;
3. respect offered sides only;
4. preserve extra Red Demon cushion;
5. research Sport → Event → Team/Affiliation → Player/Subject → Market and reuse evidence;
6. gather 2026 history plus role-comparable 2025 history where available;
7. verify current role, depth, availability, transfer/system state and opponent;
8. model opportunity separately from efficiency;
9. keep thin-evidence rows diagnostic/non-PLAYABLE;
10. calculate true unclamped line tolerance for serious candidates;
11. freeze the forecast before later settlement;
12. start prospective settlement evidence without changing learning revision until earned.

The next tranche is **operational live-board acceptance + prospective settlement evidence**, not another architecture redesign.
