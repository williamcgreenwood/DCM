# DCM v6.0.0 — Phase A / B / C Master Engineering Blueprint

**Document ID:** DCM-V6-BLUEPRINT-2026-08-27  
**Schema freeze:** PHASE_BC_SCHEMA_V1_2026-08-25  
**Schema contract SHA-256:** `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`  
**PrizePicks rule snapshot:** PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1  
**Baseline:** Canonical DCM v5.4.1 (untouched; hashes verified against install manifest)  
**Compiled:** 2026-08-27

## Thesis

Simulate a sporting event once as a shared primitive world. Derive every market from that world under a versioned definition. Translate the world through a frozen platform contract. Fail closed on unknown state. Never guess an unresolved settlement. Never sample a composite independently of its primitives.

---

## 0. Global doctrine and inherited v5.4.1 constraints

v6 does not reopen Phase A production gates and does not replace the v5.4.1 event-first, unit-safe, versioned-definition architecture. It formalizes what v5.4.1 already required and adds an exact platform-economics layer that the earlier “6-leg parlay table” objective could not represent.

### Four universal persistence rules

1. Frozen objects are immutable after a content hash is written.
2. Derived values never overwrite primitives.
3. Unknown state is explicit — never coerced to false, zero, WIN, LOSS, or eligible.
4. Anything that can change a forecast or a settlement has its own version and hash.

Every persistent object carries `schema_version`, `created_at_utc`, `learning_revision`, `source_hashes`, `content_hash`.

### Inherited production law

- Shared event worlds.
- Conservation and cross-market identities hold in every world, not merely in expectation.
- Registry key is exactly `(Platform, League, Market, DefinitionVersion)`.
- Unresolved settlements fail closed.
- GOBLIN: analytics/settlement allowed; DCM selection forbidden.
- Primitive-stat validity ≠ PrizePicks selectability.

Sports prediction and platform settlement must not contaminate each other.

---

## 1. Phase A — BEL, Bartlett, fixed-b

Bartlett is a higher-order research refinement, not a production gate. Block-length selection is a frozen policy object, not a claimed universal optimum. Fixed-b is the main temporal-robustness challenger. Convex-hull failure is a separate problem that no Bartlett factor solves.

### Method roles (frozen)

| Method | Role |
|---|---|
| BEL_CHI2 | Diagnostic |
| BEL_BARTLETT | Higher-order small-b research only |
| BEL_FIXED_B | Main temporal robustness challenger |
| ABEL | Convex-hull robustness |
| PBEL | Block-choice robustness challenger |

Do **not** use the i.i.d. scalar EL Bartlett factor for overlapping BEL. Kitamura’s correction uses third- and fourth-order block cumulant tensors plus parameter derivatives. Test both plug-in block-moment and bootstrap Bartlett factors in the coverage tournament. High-order moment estimation is noisy in the small samples where the correction is most attractive.

Small-b and fixed-b address different approximation errors. Fixed-b holds `b = L/n → b̄ ∈ (0,1]` and uses a nonstandard but pivotal limit, not χ².

---

## 2. Block-length selection

No universal optimum exists between long-run variance and BEL coverage. Politis–White (2009-corrected) is a **candidate generator**, not a theorem that `L*` is optimal for BEL coverage.

`BlockPlan` gains:

- `block_selection_objective`
- `block_selector_version`
- `block_selector_training_hash`

Selection minimizes a preregistered training-only coverage / Type-I criterion. Hard invariants: enough valid blocks; `training_cutoff < first_evaluation_timestamp`; no block crosses `regime_id`.

---

## 3. Phase B — EventWorld and PrimitiveStatLedger

Two levels: `EventWorldSet` (run definition, seeds, evidence/parameter hashes) and `EventWorld` (indexed draw). Latents and discrete regimes are explicit. Opportunity and efficiency stay separate. Player shares obey conservation.

**Primitives are the source of truth.** Do not independently draw Points, Rebounds, Assists, PRA, Fantasy. Every market is `f(ledger_w; definition_version)`. Identities hold exactly in every world.

Hybrid path vs aggregate: path models only where ordering matters (possessions, drives, PA/base-out, fight-time). Hierarchical shrinkage lives inside the simulator. Cross-event coupling is independent by default.

---

## 4. Semantics, markets, conservation

`PRIMITIVE | DERIVED | COMPOSITE | PLATFORM_SCORE`. Simulator may not write derived values into the primitive ledger.

`MarketDefinition` key: `(Platform, League, Market, DefinitionVersion)`. No fuzzy fallback.

`ConservationRule` is a first-class object. Phase B requires `P(structural invariant failure) = 0` for deterministic identities.

---

## 5. Basketball primitive registry (LIVE)

Executable topology: Minutes, FGA, 3PA, 2PA, 3PM, 2PM, FGM, FTA, FTM, OREB, DREB, REB, AST, STL, BLK, TO, PTS, plus derived PRA, PR, PA, RA, Blocks+Steals, Fantasy.

Exact identities: `2PA = FGA − 3PA`, `FGM = 2PM + 3PM`, `REB = OREB + DREB`, `PTS = 2·2PM + 3·3PM + FTM`, combo identities, made ≤ attempts, team-minute conservation.

Capability registry now sources market family from the versioned registry (closes the old `COUNT_MARKETS` gap). Connected via `phase_bc_conservation_rules()`, `phase_bc_primitive_values()`, `build_phase_bc_primitive_ledger()`.

Reported verification: targeted 23/23; v5.x regressions 96 OK + 1 skip; runnable suite 316 OK + 1 skip. External HAR FileNotFoundError is pre-existing.

---

## 6. Next sports

| Sport | Path unit | Status |
|---|---|---|
| Basketball | Possession / stint | LIVE |
| Football | Drive / play | NEXT |
| Baseball | PA / base-out | PLANNED |
| UFC | Round / fight-time | PLANNED |

New sports must not invent new ledger / world / settlement schemas.

---

## 7–9. Phase C — PrizePicks 2026 contract

Freeze `EntryContract` including `payout_display_hash`. Never infer L from card size.

Three pick dimensions: `AdministrativeState`, `ComparisonState`, `EconomicState`. Two card counts: payout-tier vs eligibility population. Ties stay in eligibility; DNP/Reboot do not.

Reboot snapshot `PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1` is sport-specific (NBA/WNBA 1H-leave; NFL offensive + K/P special case, defense excluded; CFB requires explicit player registry; MLB batter ≤2 PA). Unknown stat eligibility → `UNRESOLVED`. LESS is not Rebooted.

Same-team after administrative removal → refund. Sport-stat revisions after platform settle are not automatically forecast errors.

Leaderboard weights: Demon 1.05, Standard 1.00, Goblin/Discounted/Stack 0.95; same-player stack wins 0.95. Ties split L. Final payout = `max(R_LB, R_MG)`.

Production reporting:

```
MINIMUM_GUARANTEE_RETURN:   MODELED
LEADERBOARD_RETURN:         UNMODELED_UNLESS_GROUP_DISTRIBUTION_AVAILABLE
TOTAL_PLATFORM_EV:          LOWER_BOUND_OR_PARTIAL
```

`expected_leaderboard_return_iid` is RESEARCH_ONLY. Closed form:

`E[R_LB | s] = L * ((q+p)^n − q^n) / (n p)` when `p>0`, else `L * q^{n-1}`.

`P(payout>0)` ≠ `P(net>0)`.

---

## 10. Schema freeze and lineage

Deep-frozen dataclasses + `schemas/Phase_BC_Immutable_Contracts.json` + introspection test.

Lineage (no skipped stages, no silent hash replacement):

EvidenceGraphHash → ParameterSnapshotHash → EventWorldSetHash → PrimitiveLedgerHash → MarketDefinitionHash → WorldProjectionHash → EntryContractHash → SettlementRuleHash → WorldLineupOutcomeHash

Failure codes (integrity, not probability knobs):  
`EVENT_WORLD_INVALID`, `PRIMITIVE_CONSERVATION_FAILURE`, `DERIVED_IDENTITY_FAILURE`, `UNVERIFIED_MARKET_DEFINITION`, `UNIT_MISMATCH`, `UNKNOWN_PLATFORM_RULE`, `UNKNOWN_REBOOT_RULE`, `UNKNOWN_PARTICIPATION_RULE`, `ENTRY_CONTRACT_INCOMPLETE`, `PLATFORM_SETTLEMENT_UNRESOLVED`, `LEADERBOARD_EV_UNIDENTIFIED`, `SPORT_STAT_REVISION_AFTER_SETTLEMENT`.

Accounting: `active + void/DNP + reboot = contract pick count`; `wins + losses + pushes = active picks`.

---

## 11. Research challengers

**DPMM residuals** sit on top of the structural hierarchy, not in place of it. Shadow challenger. Posterior predictive only. No cluster-as-rule. Freeze a sample bank for replay.

**Bayesian GP-LVM + ARD** (dims 2–5 vs PCA / PPCA / none) is a role/context latent challenger, not a Higher/Lower generator. Hard production veto. GPDM deferred until ordinary GPLVM shows sequential value.

Promotion for both: future-only CRPS / LogS / Brier / ES-VS / subgroup safety / slate stability.

---

## 12. Build order

1. Lock BEL formulas + BlockPlan selector; Bartlett RESEARCH_ONLY.
2. EventWorld → ledger → deriver with conservation (basketball LIVE).
3. Football registry, then baseball and UFC.
4. EntryContract + PlatformSettlementAdapter.
5. Optimizer around true return function; keep `P(K=k)` and `P(Π>0)` as explicit, non-substitutable metrics.

Do not modify the canonical v5.4.1 installation.

---

## 13. Chain

```
FrozenEvidence → EventWorldSet → EventWorld → PrimitiveStatLedger
  → MarketDefinition → WorldProjectionResult

EntryContract + PlatformRuleVersion + WorldProjectionResult
  → RebootRuleRegistry → WorldPickState → WorldLineupOutcome
  → max(Leaderboard, Minimum Guarantee) under frozen display

After games:
OfficialSportStat + PlatformSettlementEvidence → PickSettlement → LineupSettlement
```

---

End of blueprint. Canonical v5.4.1 untouched.
