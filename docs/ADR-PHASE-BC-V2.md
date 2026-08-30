# ADR: PHASE_BC_SCHEMA_V2

- Status: Accepted as a **new working freeze**; **not** accepted as a production replacement of V1.
- Date: 2026-08-29
- Software: DCM 6.0.0
- Learning Revision: `LR000000`
- Predictive claim: `NONE`

## Context

The accepted Phase B/C V1 freeze is:

- Schema id: `PHASE_BC_SCHEMA_V1_2026-08-25`
- Expected SHA-256: `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`

The original V1 JSON bytes are **not available** in this workspace. A development inventory exists, and it is explicitly not byte-identical. Changing the expected V1 hash to match a reconstruction would be a root-of-trust violation.

## Decision

1. Leave the V1 expected hash unchanged.
2. Keep the V1 production gate closed (`productionEligible = false`) until the original bytes are recovered and hash-verified.
3. Create an explicit new freeze: `PHASE_BC_SCHEMA_V2_2026-08-29`.
4. Freeze complete V2 JSON bytes, compute SHA-256, and test that the frozen file matches that hash.
5. Do not auto-promote V2 to production. Promotion requires a later explicit acceptance record, independent of software completion.

## Consequences

- Engineering can continue against V2 as the working contract.
- Production selection remains blocked by the V1 hash gate (and by missing chronological evidence / LR000000).
- Recovering original V1 bytes later does not require rewriting V2; it re-opens the V1 gate only.

## Frozen location

- `artifacts/dcm_v6_workstream_ab/schemas/phase_bc_v2/phase_bc_schema_v2.json`
- `artifacts/dcm_v6_workstream_ab/schemas/phase_bc_v2/HASH.txt`
- `schemas/phase_bc_v2/` (same bytes)
