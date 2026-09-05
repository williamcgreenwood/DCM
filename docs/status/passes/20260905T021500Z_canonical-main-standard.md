# Status pass: canonical-main standard

This immutable pass records the 2026-09-05 standard/runtime tranche. It is
based on remote v2 head `ebf636e947647010a91bcd973b314465f0b236b1`, was
validated by CI run #253 on commit `1462fefa8abfebaf5f3e19ddcce5195d367d40eb`,
and merged to `main` through PR #22 as
`dd49206419c5e7de7650e75a6f3fe6fd5bc01104`.

- Permanent coding/prompt inheritance standard added and CI-gated.
- Deterministic privacy-aware Drive routing added; the verified project folder
  now has `00_control` through `09_engineering` with CFB/month/run children.
- Runner research cache now persists exact-first claims in SQLite with
  payload-hash validation across restart; source-health routing honors the
  injected clock.
- Lazy package exports remove a clean-install circular import.
- Supplied HAR remains quarantined: 4,307 normalized rows, 4,248 CFB, 948
  Goblins, 3,122 missing-side rows, 14 unsupported CFB rows.

Local targeted tests, policy validation, inventory check, release tests with
temporary Git metadata, and benchmark smoke passed. The local mirror lacks
the remote 11,113-row sanitized fixture; remote CI run #253 passed the
complete unfiltered suite and remains authoritative. LR is `LR000000`,
predictive claim is `NONE`, and no production card was issued from fixture
evidence.
