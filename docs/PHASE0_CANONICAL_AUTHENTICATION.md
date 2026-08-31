# Phase 0 — canonical v5.4.1 authentication

Status: **BLOCKED**

## Required bytes

| Artifact | Expected SHA-256 | Observed in this workspace |
|---|---|---|
| Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt | `bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474` | NOT PRESENT |
| Pillars_DCM_v5.4.1_Learning_Ledger.xlsx | `a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a` | NOT PRESENT |

## Repository mount record

Path: `dcm_v6/canonical_mount/MOUNT_STATE.json`  
Ref: `integration/v6-ml-architecture-20260830` @ `88f7c3aec45eba9499cca5c4b679afe491c9d73d`

```
state: ABSENT_IN_THIS_WORKSPACE
copied: false
observed_source_sha256: null
observed_ledger_sha256: null
har_decoder: NOT_MOUNTED
```

`dcm_v6/canonical_mount/v5.4.1_copy/` contains only `.gitkeep`.

## Actions not taken

- Did not fabricate or reconstruct missing canonical bytes.
- Did not run inherited v5.4.1 tests (package absent).
- Did not treat WSAB (`artifacts/dcm_v6_workstream_ab`) as a verified v5.4.1 patch.

## Files that must be supplied

1. `Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt`
2. `Pillars_DCM_v5.4.1_Learning_Ledger.xlsx`

Place them where `MOUNT_STATE.json` can observe and hash them. Re-run Phase 0 only after observed hashes match expected hashes.
