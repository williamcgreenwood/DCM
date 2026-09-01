# Engineering pass — corrective StatePack integrity / freshness / gap resolver

- Agent: Grok
- Date: 2026-08-31
- Child branch: `grok/p12-statepack-queryable-store-20260831`
- Original PR #15 head: `56baa7a8ed9be55753eaec670e340a14936c0d46`
- Base: `integration/v6-ml-architecture-20260830` @ `88f7c3aec45eba9499cca5c4b679afe491c9d73d`
- Do not rewrite the prior pass record `20260831T194500Z_grok_p12-statepack-queryable-store.md`.
- Do not merge this child to `main`.

## Original CI failure

- Workflow: `python-dcm` on PR #15
- Run URL: https://github.com/williamcgreenwood/DCM/actions/runs/33433022880/job/99622716026
- Conclusion: failure
- Known failing test: `tests/test_statepack.py::test_corrupt_export_fails_closed`
- Root cause: `integrity_ok()` hashed a reconstructed SQLite object instead of the actual `deterministic_export.json.gz` bytes.

## Canonical baseline

`dcm_v6/canonical_mount/MOUNT_STATE.json` at integration `88f7c3ae`:

- state: `ABSENT_IN_THIS_WORKSPACE`
- observed_source_sha256: null
- observed_ledger_sha256: null
- expected source: `bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474`
- expected ledger: `a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a`

This environment does not contain `Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt` or `Pillars_DCM_v5.4.1_Learning_Ledger.xlsx`.

**CANONICAL_V541_BLOCKED: exact source bytes unavailable.**

Phase 0 migration/reconstruction is stopped. WSAB/integration is not treated as canonical v5.4.1.

## Files repaired or added

Repaired:

- `artifacts/dcm_v6_workstream_ab/dcm/research/freshness.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/statepack.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_freshness.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_statepack.py`

Added:

- `artifacts/dcm_v6_workstream_ab/dcm/research/historical_gap.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/classify_runtime.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_historical_gap.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_freshness_classify.py`
- `docs/DCM6_ROS_REQUIREMENT_TRACE.json`
- `docs/PHASE0_CANONICAL_AUTHENTICATION.md`
- this corrective pass record

## Status honesty

This pass does **not** complete Phase 1 of the full §36 database.
This pass does **not** authenticate v5.4.1.
P12 is not 10/10. No predictive claim. LR remains LR000000.

## Next

1. Supply canonical v5.4.1 source + ledger bytes into the mount path and hash-verify.
2. Keep PR #15 off integration until CI is green on the repaired head.
3. Continue Phase 1 remaining tables only with full doctrine→audit evidence.
