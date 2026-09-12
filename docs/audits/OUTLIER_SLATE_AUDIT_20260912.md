# Outlier slate audit — 2026-09-12

This is a sanitized, reproducible audit of the six supplied Outlier captures
(`091126cfb(1).har`, `091126mlb(1).har`, `091126nfl(1).har`,
`091126Soccer(1).har`, `091126wnba(1).har`, and `091126insights(1).har`).
The raw HAR bytes, cookies, response bodies, and credentials are not stored in
the repository. The hashes below are the only input identifiers published here.

## Decision

The software path is coherent and fail-closed. It does **not** produce a Top 10,
Top 100, parlay, or betting recommendation from this slate. Every market row
has `status=unknown`: Outlier's `active=true` proves only that an offer was
listed, not that the event was pre-game or that the player was available. The
legal funnel therefore returns zero selectable rows. This is the correct result
for the evidence supplied, not a missing prediction.

The run remains `LR000000` with predictive claim `NONE`. No settled labels,
verified event-status evidence, or independent holdout exist, so calibration or
model promotion would be a hallucinated claim.

## Input ledger

| Capture | SHA-256 | Adapter | Market rows | Events | Players | Evidence payloads | Legal rows |
|---|---|---:|---:|---:|---:|---:|---:|
| CFB | `9f1a9d41248381eaa40bfd42a6f85caf3deeee2e0dc9a4520fc67fa4909277c4` | OUTLIER_BET | 18,598 | 47 | 1,048 | 0 | 0 |
| MLB | `22d4e3a7cc7504c0b1e15de1473fb0d65cf00d8d56bc83970ebb34fcb9387836` | OUTLIER_BET | 9,861 | 28 | 393 | 0 | 0 |
| NFL | `42253d6f5f3cce61699f5366e62b8b49a462f2f4396a681da069ad09ef78d00c` | OUTLIER_BET | 37,690 | 18 | 645 | 0 | 0 |
| Soccer | `32af770c827562a66215c5240e278309f7212c3c1be6246f521324e59eb39cb1` | OUTLIER_BET | 103,312 | 111 | 2,967 | 0 | 0 |
| WNBA | `881758d84f1321d87afb4a41b4f8a5599e737afe9c93040f1e23ba071cb11edd` | OUTLIER_BET | 1,503 | 8 | 75 | 0 | 0 |
| Insights | `205f0a840cd08e885114ce16df905249fde12bb736c16c9b7e85aa50c2d2fa42` | INSIGHTS_EVIDENCE | 0 | 0 | 0 | 7 | 0 |

All six market captures report `status=unknown` for every row. The insights
capture is structurally indexed only; its opaque values are not converted into
player facts or probabilities.

### Offer and modifier accounting

| Capture | Standard | Demon | Green Goblin | Other / target missing | Higher only | Lower only | Target present | Target missing | Same-line rows | Collapsed duplicates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CFB | 2,355 | 2,172 | 1,157 | 12,914 | 16,031 | 2,567 | 5,684 | 12,914 | 16,341 | 2,257 |
| MLB | 570 | 2,166 | 456 | 6,669 | 6,892 | 2,969 | 3,192 | 6,669 | 8,067 | 1,794 |
| NFL | 3,594 | 4,873 | 2,655 | 26,568 | 30,909 | 6,781 | 11,122 | 26,568 | 32,216 | 5,474 |
| Soccer | 920 | 12,072 | 1,715 | 88,605 | 102,782 | 530 | 14,707 | 88,605 | 102,801 | 511 |
| WNBA | 74 | 100 | 44 | 1,285 | 1,330 | 173 | 218 | 1,285 | 1,351 | 152 |

The side counts are observed sides only. The adapter never manufactures Lower
from a Higher-only row, and never manufactures Higher from a Lower-only row.
Same-line grouping retains modifier, target provider/presence, period, and
MarketDefinition so an unavailable target offer cannot hide an available one.

## CFB terminal accounting

The CFB account-only replay completed with:

| Receipt | Value |
|---|---:|
| Raw rows | 18,598 |
| Green Goblin rows | 1,157 |
| Exact permanent-denylist matches | 75 |
| Permanent matches with a non-Goblin terminal blocker | 71 |
| Permanent matches overlapping Goblin | 4 |
| CFB active-market rows before permanent exclusion | 10,628 |
| CFB active-market rows after permanent exclusion | 10,575 |
| Unsupported rows in the CFB market-accounting receipt | 6,813 |
| Shared terminal `MODELED` rows | 3,517 |
| Shared terminal `UNRESOLVED` rows | 12,930 |
| Shared terminal `UNSUPPORTED` rows | 994 |
| Production card / strict card | 0 / 0 |

The CFB market-accounting receipt and the shared terminal receipt answer
different questions: the former asks whether a row uses one of the 19 CFB
research market definitions; the latter applies the full cross-sport structural
classifier (modifier, identity, market, side, and provider gates). They are not
added together and do not represent duplicate rows.

## Permanent exclusions

The exclusion policy is now enforced at every downstream boundary:

- Green Goblin is counted first and then terminally excluded from research,
  modeling, ranking, cards, production contracts, and independent learning.
- Brennan Parachek and C.J. Carr are exact configured subject exclusions. The
  code accepts their stable IDs or punctuation-normalized full names only.
- The policy does not fuzzy-match `Carr`, does not exclude other players with a
  similar surname, and does not infer a missing identity.
- Excluded rows remain in accounting, and overlapping Goblin rows retain the
  Goblin terminal state while still appearing in the denylist-match count.

## Algorithm execution receipt

The CFB replay constructed and consumed the native DCM algorithm path. The
receipt recorded 19 activated algorithm IDs, 56 execution records, and zero
ceremonial violations. Representative live consumers included:

- exact-first hash lookup over 18,598 offers;
- bitmap eligibility and requirement reverse indexes;
- composite-key grouping, DSU/connected components, SCC cycle safety;
- CSR and hypergraph incidence indexes;
- Kahn dependency ordering and topological sorting;
- exact evidence lookup;
- weighted set cover, CELF lazy-greedy scheduling, submodular selection, and
  deterministic batch packing.

The BoardIndexes receipt reports 18,598 exact identities/offers, 5,637
composite keys, 1,048 subjects, `identityFirst=true`, and fuzzy lookup skipped
for all 18,598 rows. Archive/hash receipts were written locally and reconciled;
raw private inputs were not archived.

Machine-learning components remain correctly bounded. There are no settled
observations in this slate, so empirical calibration, isotonic/conformal
promotion, and champion replacement are not activated. The run stays at
`LR000000` / `NONE`; challenger analysis may be appended only after future
settlement and chronological holdout.

## Validation

- Full repository pytest: **pass** (one pre-existing skip).
- Focused Outlier, HAR, CFB Research OS, entry-contract, card-layer, and
  governance tests: **pass**.
- `compileall` for `src` and `tests`: **pass**.
- `scripts/validate_dcm_policy.py`: **`DCM_POLICY_VALID`**.
- Generated code inventory write/check: **pass**.
- Account-only CFB replay: **pass**, archive integrity certified, no
  hallucination flag, production selection not certified.

## Remaining blockers

These are evidence blockers, not software defects:

1. The supplied Outlier market responses do not expose a trusted explicit
   pre-game/live/suspended event-state field.
2. 12,914 CFB rows, and comparable proportions in the other captures, lack the
   configured target-book offer. They cannot be selected or used to invent an
   inverse side.
3. No authoritative player availability, role/matchup evidence, settlement
   labels, or chronological holdout is attached. Research must be requested only
   for unresolved candidates after a future evidence bundle is supplied.

Until those blockers are resolved, the only logical slate result is abstention:
no Top 10, Top 100, parlay, or bet recommendation.
