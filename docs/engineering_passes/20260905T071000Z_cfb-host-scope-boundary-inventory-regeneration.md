# Engineering Pass: CFB host scope inventory regeneration

- **Pass ID:** `20260905T071000Z_cfb-host-scope-boundary-inventory-regeneration`
- **Base:** `main` @ `07cd18c750cd5399b67d6abe3c146b3d50ae8809`
- **Task branch:** `chatgpt/cfb-host-scope-boundary-20260905`
- **Implementation commit:** `5f13dc3286d1edae3dcd2521ffc18f47f7401464`
- **Regression correction:** `74d2737884ba31ec270687b0c391dcf7f68dadfd`
- **Inventory correction:** `6ec832774d72877ef46f3635b9a6d17681cb2b48`
- **Target:** `main` through PR #24

## Exact-head validation evidence

PR #24 run #259 passed the complete test step, Algorithmic Constitution gates,
and permanent coding/prompt policy. The generated-inventory gate then failed with
`CODE_INVENTORY_STALE:docs/generated/CODE_INVENTORY.json`.

The semantic inventory hash and Markdown inventory hash were already correct.
The JSON retained literal Unicode from the earlier manual update, while
`scripts/build_code_inventory.py` uses Python's default ASCII-escaped
`json.dumps` serialization.

## Correction

- Regenerated `docs/generated/CODE_INVENTORY.json` with canonical Python-compatible
  ASCII escaping.
- Kept the source producer/consumer and regression test unchanged.
- Inventory semantic hash remains `1445f85564d95fbdf1aa1019add2ca9125e14e0a6170a374de3ba50a285f070b`.
- No HAR, secret, SQLite database, or private runtime artifact was added.

## Validation

- Run #259 tests and policy gates: PASS.
- Run #259 generated-inventory gate: FAILED on JSON serialization only.
- PR #24 retry-2 at exact head `6ec832774d72877ef46f3635b9a6d17681cb2b48`: PENDING.
- Current-HAR operational acceptance remains EXTERNAL/PENDING; LR remains
  `LR000000`, predictive claim `NONE`, and production/host-performance
  certification remain false.

The task remains unmerged until exact-head retry-2 checks and normal review state pass.
