# Engineering Pass: CFB host research scope boundary

- **Pass ID:** `20260905T063645Z_cfb-host-scope-boundary`
- **Base:** `main` @ `07cd18c750cd5399b67d6abe3c146b3d50ae8809`
- **Task branch:** `chatgpt/cfb-host-scope-boundary-20260905`
- **Implementation commit:** `5f13dc3286d1edae3dcd2521ffc18f47f7401464`
- **Checkpoint commit:** `db64c0ad0e81596ab2dfb89c086ba3f16c483007`
- **Target:** `main` through PR #24

## Defect reproduced

The canonical research request planner emits universal scopes, but the host-facing
`build_host_research_plan` accepted legacy adapter scopes from resumed or
adapter-provided request state and propagated them into host tasks, bundle keys,
CFB research instructions, and scope counts.

## Implementation

- Canonicalized request scopes with `dcm.research.scopes.canonical_scope`.
- Canonicalized supplied `unique_scopes` keys before host counts are emitted.
- Added regression coverage to the existing host-native integration test.
- Regenerated `docs/generated/CODE_INVENTORY.json`.
- Added `ROS-HOST-SCOPE-001` to the requirement trace and recorded the
  producer/consumer/checkpoint linkage.
- No HAR, secret, SQLite database, or private runtime artifact was added.

## Validation

- Isolated compilation of the changed planner and host-native test: PASS.
- PR #24 exact-head repository CI: PENDING.
- Current-HAR operational acceptance: EXTERNAL/PENDING; no current HAR was
  supplied in this execution cycle.
- LR remains `LR000000`; predictive claim remains `NONE`; production root
  and host-performance certification remain false.

## Promotion state

PR #24 is open against `main` at exact head `db64c0ad0e81596ab2dfb89c086ba3f16c483007`. This pass is not MERGED_VERIFIED until exact
head checks/review and main readback pass.
