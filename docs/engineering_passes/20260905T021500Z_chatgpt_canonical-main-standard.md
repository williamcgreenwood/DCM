# Engineering Pass: Canonical-main standard and runtime closure

- **Pass ID:** `20260905T021500Z_chatgpt_canonical-main-standard`
- **Base:** `chatgpt/cfb-production-closure-v2-20260904` / `ebf636e947647010a91bcd973b314465f0b236b1`
- **Target:** `main`, through a reviewable PR and required checks
- **Active branch:** `chatgpt/canonical-main-cfb-standard-20260905`
- **Remote commit:** `bf3846255c952a5d9240f67d000b84a9e9e7cc20` → follow-up
  `1462fefa8abfebaf5f3e19ddcce5195d367d40eb`; merged as
  `dd49206419c5e7de7650e75a6f3fe6fd5bc01104` through PR #22

## Implementation

- Added a permanent coding and prompt-inheritance standard covering bounded
  execution contracts, typed/time/units boundaries, Algorithmic Constitution
  telemetry, CFB opportunity/world conservation, PLAYABLE-only portfolio
  eligibility, future-only learning, privacy, checkpoints, release tests, and
  main-promotion rules.
- Added the deterministic `dcm.runtime.storage_router` and documented Drive
  hierarchy. It emits stable routes, rejects raw HAR/SQLite/credential-shaped
  objects, stages immutable safe objects, and leaves upload/read-back to the
  host connector.
- Created the verified Drive hierarchy under the existing project folder and
  uploaded the safe folder-ID registry to `00_control/2026-09`.
- Repaired package-level circular imports through lazy public exports.
- Changed the canonical runner's provider-facing research cache to use
  restart-persistent SQLite L2 storage with payload-hash verification.
- Fixed source-health routing to use the injected clock, preserving deterministic
  circuit-breaker tests.
- Added a CI policy validator and storage-router tests; regenerated the AST
  inventory.

## Validation

- Targeted runtime, signal, temporal, decision, lineage, cache, storage, and
  governance tests: pass.
- Remote CI run #253: full pytest, Constitution, policy, inventory, and
  benchmark steps all passed on the complete repository fixture.
- Local scratch validation remains supportive only because the API-backed
  mirror lacks the remote 11,113-row fixture.
- Release freshness tests: pass with temporary Git metadata, with no source
  repository mutation.
- Supplied quarantined HAR: 4,307 normalized rows, 4,248 CFB, 948 Goblins,
  3,122 missing-side rows, 14 unsupported CFB rows; fixture research issued
  zero production selections by design.
- Engineering benchmark: 100 rows / 4.12 s / ~181 MB RSS; 1,000 rows /
  89.08 s / ~1.53 GB RSS. This is synthetic engineering evidence only;
  `hostPerformanceCertified` remains false.

## Unearned or externally dependent states

`SOFTWARE_CLOSED=PASS` for the declared offline scope;
`HAR_ACCOUNTING_ACCEPTED=PASS`;
`OPERATIONAL_ACCEPTED_WITH_CURRENT_HAR=PARTIAL`;
`PREDICTIVE_CERTIFIED=DEFERRED`;
`PRODUCTION_ROOT_CERTIFIED=FAIL`.

LR remains `LR000000` and predictive claim remains `NONE`. The supplied HAR is
an offers capture, not authoritative historical/statistical/settlement
evidence. No raw HAR, SQLite database, cookie, token, or credential was
committed or uploaded.

## Next exact action

The coherent branch delta was pushed, PR #22 was checked by CI run #253,
exact head and key blob bytes were read back, and the PR was merged normally
to `main`. Continue from the merged main tree with the separately gated
current-HAR, settlement, calibration, and production-root work.
