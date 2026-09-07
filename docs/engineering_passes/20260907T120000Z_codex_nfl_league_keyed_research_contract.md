# Engineering pass — NFL league-keyed research contract (20260907T120000Z)

## Scope

Refresh the reviewable NFL research-contract parity increment from the live
post-DCM-6.1-contract base. The increment is limited to requirement
`DCM61-08`: explicit, typed CFB/NFL source and acquisition routing. It does
not run a private HAR, certify NFL operation, or change predictive, root, or
performance status.

## Producer and consumer

- **Producers:** football market-requirement resolution, acquisition actions,
  request graphs, and source-health routing.
- **Consumers:** NFL research scheduling and validation, which receive explicit
  NFL identity instead of inheriting CFB-only source metadata.
- **Fallback:** unknown leagues produce no market requirements and remain
  fail-closed; CFB compatibility is retained only for explicitly CFB-keyed
  requests.

## Validation

- `pytest -q tests/test_nfl_research_contract.py` — 2 passed.
- `python scripts/build_code_inventory.py --check` — passed after regeneration.
- `git diff --check` — passed.
- Full CI is required before merge; no host/HAR or prediction claim is made by
  this pass.

## Status

- Current main at the beginning of this pass: `3b80d1c1dfc5f5c1663b67735d5ed0d4a8bb0d39`.
- `LR000000`, predictive claim `NONE`, production-root certification `false`,
  and host-performance certification `false` are unchanged.
- NFL current-HAR acceptance remains `EXTERNAL_BLOCKED` pending a local private
  HAR and permitted evidence acquisition.

## Next action

Run the complete required CI on the exact PR head, review the generated
inventory and league-separation tests, merge only through the protected normal
PR mechanism, then read back the new `main` SHA.
