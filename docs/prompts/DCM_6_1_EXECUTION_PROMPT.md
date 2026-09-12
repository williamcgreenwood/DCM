# Pillars DCM 6.1 CFB/NFL release execution prompt

## Objective

Ship the DCM `6.1.0` CFB/NFL operational release from the live canonical
repository. Make working, tested increments; do not substitute a narrative or
a fabricated forecast for implementation.

## Execution contract

- **Repository/base:** `williamcgreenwood/DCM`, base `main` at the SHA observed
  when the task begins. Reconcile live `main`, branch state, and dirty work
  before edits; preserve unrelated changes.
- **Scope:** CFB and NFL only. Other leagues remain explicitly unsupported and
  fail closed. One canonical Python engine lives under `src/dcm`; do not build
  a parallel runtime, analytics engine, or copied donor package.
- **Inputs/privacy:** Raw HARs, cookies, tokens, credentials, response bodies, and
  private run stores are local-only quarantine. Never commit, upload, quote, or
  use them as fixtures. Publish only redacted typed counts/hashes/receipts.
- **Time:** declare the forecast cutoff and timezone in every run. Reject
  post-cutoff, stale, conflicting, or unverified-rule evidence for selection.
- **Capabilities:** use the host only for explicit acquisition actions. Treat a
  blocked source as typed failure, not as permission to infer its contents.
- **Constitution:** obey
  `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`,
  `docs/engineering/DCM_CODING_AND_PROMPT_STANDARD.md`, and `AGENTS.md`.
  Maintain `LR000000` and predictive claim `NONE` unless independent future
  gates actually change them.

## Required delivery order

1. Read `AGENTS.md`, the coding/prompt standard, algorithmic constitution,
   `REQUIREMENT_LEDGER.v1.json`, this prompt, the 6.1 acceptance contract, and
   the 6.0-to-6.1 crosswalk. Inspect repository truth and establish a release
   branch matrix.
2. Complete the smallest unblocked PR from the DCM61 ledger. Each PR has a
   single acceptance target, tests for success and abstention/failure, and a
   concise handoff with exact commands/results.
3. Implement the self-contained native 6.1 runtime. Preserve exact-v5.4.1
   validation only for requested legacy replays; absent legacy bytes must emit
   `LEGACY_RUNTIME_UNAVAILABLE`, never silently run native code as history.
4. Implement `dcm-host run --har <local-private-file> --league CFB|NFL
   --run-root <local-private-dir>` to emit a schema-versioned typed RunReceipt.
   It must account for every offer before exclusions and fail closed without a
   usable evidence bundle.
5. Ensure offer line, side, market definition, and platform status are owned by
   local HAR/platform evidence. Route external research only for its proper
   CFB/NFL purpose, keyed by league/market/source health/cutoff and reusable
   Subject + Event / OfferSet identity.
6. Apply the permanent denylist after full accounting and before every
   downstream stage: Green Goblin rows, Brennan Parachek, and C.J. Carr are
   never research candidates, modeled rows, ranked rows, card legs, or learning
   observations. Match Brennan/Carr only by their configured exact subject IDs
   or punctuation-normalized full names; never fuzzy-match a surname, infer a
   missing identity, or create an inverse side. Keep the excluded rows in the
   accounting receipt and expose a typed exclusion blocker.
7. Add content-addressed evidence reuse, idempotent restart, source lineage,
   cutoff evaluation, conflict/absence states, conserved event-world links,
   immutable freeze, and append-only future-only settlement boundaries.
8. Run targeted tests, failure/temporal/determinism/restart tests, full suite,
   policy check, inventory check, fresh-install smoke, and representative
   benchmark. Record exact results and unresolved external gates.
9. Use normal branch → PR → required checks → review → merge. Never write or
   force-push `main`, bypass protections, or claim an unverified external gate
   as complete. Verify published commit/CI/readback before advancing state.

## Artifacts and checkpoint states

For each increment emit only safe repository artifacts: code, tests, schemas,
redacted example receipt, requirement-ledger update, benchmark note, and
handoff. Report one of `SOFTWARE_CLOSED`, `HAR_ACCOUNTING_ACCEPTED`,
`OPERATIONAL_ACCEPTED_WITH_CURRENT_HAR`, `PREDICTIVE_CERTIFIED`, or
`PRODUCTION_ROOT_CERTIFIED`, separately by league where applicable. Do not
report a numerical completion percentage.

## Completion condition

Finish only when all DCM61 software gates are verified, CFB and NFL each have
their own current-HAR operational record or honest external block, CI is green,
and a `6.1.0` release receipt distinguishes software, operational, predictive,
and production-root status. Start with the smallest unblocked ledger item and
make the implementation; do not return a prose plan in place of the work.
