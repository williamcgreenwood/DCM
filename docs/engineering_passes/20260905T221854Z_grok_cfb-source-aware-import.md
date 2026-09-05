# Engineering Pass: CFB source-aware observation import loop

- **Pass ID:** `20260905T221854Z_grok_cfb-source-aware-import`
- **Starting branch/SHA:** `main` @ `24007ef5bd6af38d44f6f004eb19300bb0fc07ab` (PR #33 merged)
- **Ending branch:** `task/cfb-grouped-research-20260905`
- **Objective:** close the gap between source-aware host research tasks and a
  typed import → coverage → ParameterSnapshot consumer loop.

## Implementation

- Added `dcm.research.observation_execute` as the canonical closed loop for
  host observations that carry `actionId`, source family/candidates, and
  timestamped typed claims.
- Routed `dcm.chat.evidence_import` into that loop when observations include
  action/source-aware fields.
- Extended claim hashing to optionally retain `parser_version`, `actionId`,
  and `sourceFamily` for provenance without weakening identity.
- Rejects `EMPTY_FIELD_COVERAGE` (network success without valid fields does
  not count). Idempotent bundle dedupe preserved.
- One EVENT-scope observation fans out across dependent offers; ParameterSnapshot
  content hashes change when contracts close.

## Validation

- `pytest -q tests/test_cfb_source_aware_import.py tests/test_research_store.py tests/test_cfb_research_os.py tests/test_host_native.py` — **28 passed**.

## Honest state and next work

Next: run the same `evidence-import` path against a current live CFB HAR host
batch with permitted public observations, then close remaining
AFFILIATION/COUNTERPARTY/SUBJECT contracts before any freeze claim. No
LR000000, predictive, or root-certification claim is earned by this pass.
No private HAR contents are committed.
