# Engineering pass — NFL research-contract parity

- **Base:** `90d9e65dad3ba7e7e3c64ebcff0cfe1c7eb0afee` (`main`)
- **Branch:** `codex/nfl-research-contract-parity-20260907`
- **Scope:** first workbook NFL-01 tranche; no HAR, forecast, selection, or predictive claim.

## Problem

The football primitive ledger, EventWorlds, MarketDefinitions, and game-log
adapter already accepted NFL, but the evidence-support contract and research
acquisition path imported the CFB active market view and always routed sources
as `CFB`. NFL could therefore be physically modeled while lacking a
league-keyed research/scheduling proof.

## Change

1. Added league-keyed football market requirements for exactly `CFB` and `NFL`.
   Unknown leagues receive no requirements and fail closed.
2. Preserved the existing `MARKET_REQUIREMENTS` as the CFB compatibility view;
   CFB artifacts and tests retain their declared contract.
3. Added `league` and `sportFamily` to OFFER research requests so no producer
   drops the routing identity used by AcquisitionActions.
4. Routed market-demand and acquisition support through the action league.
5. Added catalog-backed NFL source health (`NFL_OFFICIAL`,
   `NFL_PRO_FOOTBALL_REFERENCE`, `CFB_STATUS` only where the catalog declares
   NFL support). CFB sources are not candidates for an NFL action.
6. Added NFL parity tests covering support, demand graph, acquisition routing,
   and fail-closed source separation.

## Validation

- `python -m compileall -q src/dcm tests` — passed.
- `python scripts/build_code_inventory.py --write` — passed; generated
  inventory updated.
- Targeted: `python -m pytest -q tests/test_nfl_research_contract.py tests/test_gridiron_plugin.py tests/test_cfb_research_os.py tests/test_source_catalog.py` — **36 passed**.
- Full: `DCM_FAST_WORLDS=64 DCM_SERIOUS_WORLDS=128 python -m pytest -q` — **passed**, one existing skip, zero failures.

## Claims unchanged

- `LR000000`; predictive claim `NONE`.
- No live NFL HAR accepted, no NFL forecast frozen, and no recommendation
  eligibility gained.
- CFB active run state is unchanged; its absent local checkpoint is a recovery
  blocker in this environment, not a reason to restart or soften gates.

## Ordered next pass

1. Add NFL board accounting and execution matrix parity using the same
   league-keyed requirements.
2. Run a fresh private NFL HAR through full accounting → evidence frontier →
   recomputation → deterministic freeze, preserving offered-side fail-closed
   behavior.
3. Restore or formally retire the missing historical CFB checkpoint; use the
   next CFB HAR as a new guarded run rather than fabricating continuity.
