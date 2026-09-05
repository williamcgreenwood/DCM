# Engineering Pass: Canonical-main standard and runtime closure

- **Pass ID:** `20260905T021500Z_chatgpt_canonical-main-standard`
- **Base:** `chatgpt/cfb-production-closure-v2-20260904` / `ebf636e947647010a91bcd973b314465f0b236b1`
- **Target:** `main`, through a reviewable PR and required checks
- **Active branch:** `chatgpt/canonical-main-cfb-standard-20260905`
- **Remote commit:** pending at pass creation; updated after GitHub read-back

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
- Local unfiltered suite before final rerun: 447 passed, 7 blocked by the
  absent local copy of the remote 11,113-row sanitized fixture and absent Git
  metadata. The `.gitignore` blocker is fixed and will be rechecked.
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

Push the coherent branch delta, create the PR against `main`, run remote CI
against the complete repository fixture and release environment, verify exact
head/checks/blob read-back, then merge only if the normal required checks pass.
