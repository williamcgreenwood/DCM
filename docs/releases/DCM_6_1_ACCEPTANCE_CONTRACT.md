# DCM 6.1 CFB/NFL acceptance contract

- **Release:** `6.1.0` (CFB and NFL operational scope)
- **Base:** `main` at `90d9e65dad3ba7e7e3c64ebcff0cfe1c7eb0afee`
- **Constitution:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`
- **Status:** in implementation; this document is not a release certificate.

## The release boundary

DCM 6.1 is one installable Python engine under `src/dcm`. It accepts a
private, local HAR through a typed host runner, accounts for every offer, and
either emits a traceable CFB/NFL result or a typed fail-closed receipt. It does
not certify prediction, profitability, production root, or a card merely
because software paths exist. `LR000000` and predictive claim `NONE` remain
unchanged until prospective gates are independently earned.

Only CFB and NFL are release leagues. Every other sport/league/market must
return an explicit unsupported state; it may not silently reuse CFB or NFL
logic. Raw HARs, cookies, credentials, response bodies, and private run
databases stay in local quarantine and are never committed or published.

## Acceptance states

| State | Meaning | Evidence required |
|---|---|---|
| `SOFTWARE_CLOSED` | Clean install, typed runner, ledger, and deterministic tests work. | PR CI plus fresh-install smoke. |
| `HAR_ACCOUNTING_ACCEPTED` | A current private HAR has a terminal disposition for every offer. | Local redacted receipt and accounting counts. |
| `OPERATIONAL_ACCEPTED_WITH_CURRENT_HAR` | Current-HAR CFB or NFL route has obtained sufficient typed evidence or has honestly held all ineligible offers. | Redacted run receipt, evidence manifest, freeze/hold disposition. |
| `PREDICTIVE_CERTIFIED` | Prospective, chronological, independently reviewed predictive gates passed. | Separate future-only evidence. |
| `PRODUCTION_ROOT_CERTIFIED` | Release provenance/root-of-trust gates passed. | Release manifest and protected promotion evidence. |

The first three states are separately reported per league. The latter two are
not implied by 6.1 software closure.

## Non-negotiable gates

1. Full-board accounting occurs before Goblin/exclusion handling. Missing
   offered side, identity collision, stale/conflicting evidence, or unsupported
   market produces a terminal hold/unsupported disposition, never a guess.
2. HAR/platform-derived offer metadata is owned by the local HAR or platform
   authority. Research adapters must not substitute weather or generic sources
   for offer line, side, status, or market definition.
3. External research is routed by league, market, source health, cutoff,
   authority, and reusable `Subject + Event / OfferSet` identity. Each claim
   carries source URL/key, retrieval time, cutoff evaluation, hash, and failure
   state.
4. A run is resumable and content-addressed. Reused evidence is visible in its
   receipt; a failed acquisition cannot become a passing claim on restart.
5. All predictive output remains traceable to a conserved event world,
   parameters, evidence bundle, algorithm execution plan, and immutable
   forecast/freeze receipt. No selection is forced.
6. Settlement and learning are append-only and future-only. They do not alter
   a frozen output or promote `LR000000` / `NONE` without their own gates.

## Delivery sequence

| PR | Increment | Exit evidence |
|---|---|---|
| 1 | Release contract, 6.1 ledger, native-runtime ADR, execution prompt | Governance tests and reviewable contract. |
| 2 | NFL research-contract parity | League-keyed route/source tests and clean rebase. |
| 3 | Self-contained package/runtime | Fresh temporary-directory install and `dcm-host doctor`. |
| 4 | Typed run receipt, accounting, HAR authority | CFB/NFL synthetic and failure-path tests. |
| 5 | Evidence routing, persistence, reuse, resume | Restart/idempotency and provenance tests. |
| 6 | CFB current-HAR operational acceptance | Private redacted local receipt; no HAR committed. |
| 7 | NFL current-HAR operational acceptance | Private redacted local receipt; no HAR committed. |
| 8 | Freeze, settlement boundary, release automation | CI evidence and versioned `6.1.0` release manifest. |

PRs are small, independently testable, and merged only through normal review
and required checks. A failed external gate is recorded as such, not retried as
a synthetic success.

## Release exit

`6.1.0` may be tagged only after all `DCM61-*` software gates in
[`DCM_6_1_REQUIREMENT_LEDGER.json`](../requirements/DCM_6_1_REQUIREMENT_LEDGER.json)
are verified, both league acceptance records exist, and the release receipt
states the exact status of operational, predictive, and production-root gates.
