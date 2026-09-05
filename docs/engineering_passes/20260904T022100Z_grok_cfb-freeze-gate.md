# Engineering Pass — CFB freeze-gate / incremental-runtime closure

- **Timestamp:** 2026-09-04T02:41:00Z
- **START_SHA:** `0e5e2275742246211cb20ba4e5d17b7908106ab2` (PR #19 HEAD at pass start)
- **INTEGRATION_SHA:** `59ea12487ad2e747a15427ba6bb9babd1b9f5907`
- **BRANCH:** `grok/cfb-guarded-launch-today-20260903`
- **TARGET:** `integration/v6-ml-architecture-20260830` only. Do not merge to `main`.
- **CONSTITUTION:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`
- **CONSTITUTION_DOCUMENT_SHA256:** `d35da146d021f7caae959f18c4838ad3a7ac58cba2c681fdd2c6ef437766df68`
- **CONSTITUTION_LINEAGE_HASH:** `bba7b082bf67e12d87e675ac58d5b6f96d9cbad9b6a487a0aa157bf7cef9e599`
- **ALGORITHM_REGISTRY_SHA256:** `9327ec9884e7a55a7854f27d85fd062d6b959794197670db14b7932428e885ca`
- **CODE_INVENTORY:** 272 modules / 1,945 symbols / 0 parse errors
- **INVENTORY_HASH:** `d25db58371c5acd9cb85d377373ff71c08616f20e91dea82ab77c31193375686`
- **FULL_PYTEST:** 435 passed / 0 failed
- **LEARNING_REVISION:** `LR000000`
- **PREDICTIVE_CLAIM:** `NONE`
- **PRODUCTION_ROOT_CERTIFIED:** false

## Objective

Close remaining ChatGPT-audit semantic defects so CFB can freeze only after Top25 FINAL. Not an expansion pass.

## What this pass implemented

1. MaterialFacts overlay player/team/event packets **before** RoleEpoch / opportunity / efficiency fit. Snapshot hash includes `materialFactHashes`.
2. Material refresh returns rebuild keys; runner rebuilds ParameterSnapshots + shared EventWorlds, then `recompute_full_bundle` + rerank. Line-only reuses worlds. `simulate_player_worlds` is not called inside refresh. Cached snapshots are invalidated before rebuild.
3. Shared CFB EventWorlds run when `eventId` is present, including a lone board player. Residuals remain. Kickers stay isolated.
4. `OpportunityShareEstimate` is evidence-driven (role-epoch logs → thin sample → archetype prior → static cap last). Starter QB is not blindly capped at 92%.
5. Freeze gate: `forecastFrozen=false` and `runState=AWAITING_FRONTIER_RESEARCH` when Top25 is not FINAL or stop reason is `EXTERNAL_HOST_REQUIRED`. Fixture/bundle still freeze when frontier is terminal.
6. `FrontierPassState` persisted with before/after snapshot, world, feature, fact, probability, ranking, Top25 hashes. Pass increments only on material downstream change.
7. Requirement completion uses `evaluate_request`. Scope-level EvidenceIndex hits are candidates only. STATUS does not satisfy GAME_HISTORY.
8. Exact projectionId path is hash lookup only. Bloom/composite/SQLite are not queried for known IDs.
9. L5 semantic index `(scope, scope_id, claim_type)` → content hashes → exact identify. No false L5 if Drive catalog is absent.
10. Source health persists across `prepare_cfb_research_os`. `historicalSuccessProbability` 0.0 stays 0.0. HALF_OPEN is one trial. CELF `expectedGain` uses routed source pSuccess/authority/cost.
11. Market execution matrix proves championProducer / ParameterSnapshot / EventWorldPrimitive from runtime contracts. Rows participate in the content hash. 19/19 ACTIVE complete after gridiron-ledger alias preference for `fg_made`.
12. Incremental Research OS: static BoardGraph/RequirementGraph/indexes reused when HAR fingerprint matches; facts/catalog/cache reused when claims fingerprint matches; acquisition rebuilt only when frontier fingerprint changes. Requirement bitmaps cover the full request set.
13. Stage telemetry: HAR / RESEARCH / MODEL / RANK / FREEZE written under `performance/stages.json`. Host-performance remains uncertified.

## Performance (engineering synthetic; not certified)

| size | original wall/RSS | prior freeze-gate wall/RSS | this pass wall/RSS |
|---|---:|---:|---:|
| 100 | ~4 s / ~127 MB | 8.19 s / 179 MB | 8.05 s / 170 MB |
| 1000 | ~96 s / ~932 MB | 142.8 s / 1518 MB | 131.6 s / 1446 MB |

Repeated static Research OS rebuilds are skipped on matching HAR fingerprint. Matching claims skip catalog/cache rebuilds. Matching frontier skips acquisition rebuild. ParameterSnapshots are cached by projectionId and invalidated on material refresh. Wall/RSS improved vs the uncommitted freeze-gate snapshot but remain worse than the pre-freeze-gate engineering numbers because semantic work (joint worlds, full-requirement bitmaps, fact overlay, CELF health) is now real. Host-performance remains uncertified.

## Verdict

`CFB_REFERENCE_IMPLEMENTATION_SOFTWARE_COMPLETE` for the declared CFB software path, pending exact-head CI. Current-HAR operational acceptance remains external. Do not merge to main.
