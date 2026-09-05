# Engineering Pass: CFB host scope regression correction

- **Pass ID:** `20260905T065000Z_cfb-host-scope-boundary-regression-fix`
- **Base:** `main` @ `07cd18c750cd5399b67d6abe3c146b3d50ae8809`
- **Task branch:** `chatgpt/cfb-host-scope-boundary-20260905`
- **Implementation commit:** `5f13dc3286d1edae3dcd2521ffc18f47f7401464`
- **Regression correction commit:** `74d2737884ba31ec270687b0c391dcf7f68dadfd`
- **Target:** `main` through PR #24

## Exact-head failure reproduced

PR #24 run #257 executed the complete test step and failed only in the newly added
host-native regression assertion. The planner's existing contract initializes
counts from emitted tasks and then adds supplied unique-scope counts; the test
expected `SUBJECT=1`, while the preserved behavior correctly emitted `SUBJECT=2`.
The defect under test was still reproduced: no legacy `PLAYER` key escaped the
host-facing plan.

## Correction

- Changed the regression expectation to the established combined count `2`.
- Kept the producer normalization and canonical `uniqueScopes` key invariant.
- Regenerated the JSON and Markdown code inventory; inventory hash is
  `1445f85564d95fbdf1aa1019add2ca9125e14e0a6170a374de3ba50a285f070b`.
- Kept `ROS-HOST-SCOPE-001`, `LR000000`, predictive claim `NONE`, and
  production-root/host-performance gates unchanged.
- No HAR, secret, SQLite database, or private runtime artifact was added.

## Validation

- Changed Python source compiles in the isolated check: PASS.
- Exact-head CI run #257: FAILED at the original regression expectation; all
  setup, install, CLI, and synthetic-smoke steps passed.
- PR #24 retry at exact head `74d2737884ba31ec270687b0c391dcf7f68dadfd`: PENDING.
- Current-HAR operational acceptance remains EXTERNAL/PENDING.

The task remains unmerged until exact-head retry checks and normal review state pass.
