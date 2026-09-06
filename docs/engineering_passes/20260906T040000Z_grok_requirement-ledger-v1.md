# Engineering pass — Canonical requirement ledger v1

- **UTC:** 2026-09-06T04:00:00Z
- **PT:** 2026-09-05 ~9:00 PM PT
- **Branch:** `task/requirement-ledger-20260906`
- **Base:** `main` @ `c01724382f478ddb4221a098e37e98f55fcd9ffe` (PR #35 `src/dcm` relocate)
- **Agent:** Grok Bot

## Intent

Canonicalize the 2026-09-05 handoff ZIP seed (`REQUIREMENT_LEDGER.json` HANDOFF-001…042) into an in-repo machine ledger + human crosswalk so agents can resume CFB closure without inventing a parallel ontology or installing quarry code into the runtime package.

## Done

- `docs/requirements/REQUIREMENT_LEDGER.v1.json` — expanded atomic `REQ-*` records with producer/consumer/fallback, tests, telemetry, honest status vs live `src/dcm`, CFB-critical flags, P380X catalog policy.
- `docs/requirements/REQUIREMENT_CROSSWALK.md` — counts by status + top CFB blockers (HAR→evidence→model→card).
- Thin loader `src/dcm/governance/requirement_ledger.py` + `tests/governance/test_requirement_ledger.py`.
- PROGRAM_STATUS updated for #35 merge @ c017243 and this ledger pass.
- CODE_INVENTORY regenerated after governance package add.

## Deliberately NOT copied from ZIP

- P380X 1500+ engines (catalog + compile-to-active-DAG only)
- `original_sources` binaries / donor ZIPs as runtime
- Wholesale `source_text` into `src/dcm`
- Any HAR bytes
- Embedded executable handoff/donor code

## Not earned

- CFB current-HAR operational acceptance
- Predictive / LR promotion
- Host-performance certification
- Mixed-sport R1
