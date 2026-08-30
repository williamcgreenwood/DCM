# ENGINEERING_AUDIT — DCM v6 live HAR production (LR000000)

Date: 2026-08-29 (PT) / 2026-08-30 UTC
Branch: `grok/v6-live-har-production` from `chatgpt/v6-production-completion-20260828` @ `795e545`
Canonical tree: `/workspace/DCM-repo`
Canonical engine: `artifacts/dcm_v6_workstream_ab/dcm` (Python). Not `/workspace/pillars-dcm`.

Learning Revision: **LR000000** (not promoted)
Predictive claim: **NONE**
This is **not** optimized DCM 6.0. Host performance is **not certified**.

## Scores (honest; not a marketing grade)

| Area | Score | Why |
|---|---|---|
| Parser / HAR ingest | 8/10 | PrizePicks JSON:API certified on sanitized live capture; player IDs from HAR only; goblin/demon/standard + sides accounted. |
| Board accounting | 8/10 | 11113 unique rows; league/status/modifier/side/event/player counts match capture. As-of uses `account_capture` so a post-cutoff HAR is still fully counted. |
| Plugin / sport gates | 7/10 | NBA/WNBA/NFL/CFB production-capable in software; MLB SHADOW; soccer/EPL/KBO/NPB/CFL/OTD fail closed after accounting. Not a new sport model. |
| Research / BundleProvider | 7/10 | MARKET_DEFINITION vs OFFER split; BundleProvider JSONL with FileProvider validation. No live web research in this sandbox. Fixture claims never production-eligible. |
| Schema / root of trust | 5/10 | V1 expected hash unchanged and **closed**. V2 frozen (`12b25060…`) and **not** auto-promoted. |
| Runner / CLI | 8/10 | `python -m dcm.runner` and `python -m pillars_dcm.runner` after `pip install -e .`. Compact HAR full path; full HAR `--account-only`. |
| Tests | 8/10 | Existing WSAB suite plus live-HAR, BundleProvider, V2 hash tests. |
| Production selection | 2/10 | Gate closed: missing v5.4.1 mount, missing V1 bytes, no chronological production evidence, LR000000. |
| Predictive / host | 0/10 | NONE / not certified. |

Overall engineering completeness for this pass: **software pipeline operable, production selection not earned**.

## Live HAR board (sanitized 2026-08-29 capture)

Unique projections: **11113** (24 HAR entries, 11 successful nonempty JSON:API bodies)

| League | n | Sport family | Production path |
|---|---:|---|---|
| MLB | 4480 | baseball | SHADOW; never PLAYABLE |
| SOCCER | 3104 | soccer | fail closed after accounting |
| CFB | 1568 | gridiron | production-capable markets only |
| WNBA | 1238 | basketball | production-capable markets only |
| EPL | 580 | soccer | fail closed after accounting |
| KBO | 81 | baseball | fail closed after accounting |
| NPB | 44 | baseball | fail closed after accounting |
| CFL | 10 | gridiron | fail closed after accounting |
| OTD | 8 | unknown | fail closed after accounting |

Modifiers: goblin **1849** (extracted then excluded), demon **8053**, standard **1211**

Raw `allowed_wager_types`: over **6868**, under_or_over **2290**, missing **1955** (fail closed). After goblin default MORE, missing-sides fail-closed ≈ **1614**.

Status: pre_game **10836**, in_progress **259**, suspended **18**. 84 games, 1358 players.

Live/in_progress/suspended are not production-selected.

Account-only classification (CLI): EXCLUDED_GOBLIN 1849, MODELED 2414 (MLB shadow 1805 of those), UNRESOLVED 1634, UNSUPPORTED 5216. Tests: **116 passed** (pytest, DCM_FAST_WORLDS=64). Compact CLI: EMPTY_CARD_COMPLETE, 127 rows, 23 modeled, 0 playable.


## Schema

- V1 expected SHA-256 (immutable): `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`
- V1 bytes: **ABSENT**. Reconstruction inventory is not canonical.
- V2 freeze id: `PHASE_BC_SCHEMA_V2_2026-08-29`
- V2 SHA-256: `6edbc92e94c734ead8c94edcfa8b112c2fb33ec3fb4610a89199b84993df6521` (field-level expansion; productionEligible false)
- V2 `productionEligible`: **false**. ADR: `docs/ADR-PHASE-BC-V2.md`

## Remaining blockers (do not paper over)

1. Hash-verified v5.4.1 canonical source bytes ABSENT (`bd1fb433…`).
2. Phase B/C V1 original bytes ABSENT; production hash gate closed.
3. V2 frozen but not accepted for production.
4. No live web research / real game logs in this sandbox — do not fabricate.
5. MLB PA engine remains SHADOW.
6. Soccer/EPL/KBO/NPB/CFL/OTD remain UNSUPPORTED_FAIL_CLOSED.
7. Host performance not certified.
8. LR000000 / predictive NONE.
9. TypeScript operator console is out of scope; Python remains the single canonical DCM.
10. Capture startedDateTime is 2026-08-30T00:36Z; requested evidence cutoff 2026-08-29T16:00:00Z is before capture. Accounting uses `account_capture`; evidence/production still firewall at cutoff.

## What this pass is not

Not a certified production selector. Not an optimized 6.0. Not a second Python engine. Not a reconstructed V1 schema labeled canonical.
