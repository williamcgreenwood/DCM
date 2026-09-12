# Universal sport research expansion audit — 2026-09-12

Base: protected `main` after PR #78, `3d2625cc1f369d6e225120e1245e4b2cd5f690d2`.

## Implementation result

- 17 canonical sport profiles are registered.
- Every profile has native research requirements and a 24-component plugin
  completion report.
- Outlier is the preferred exact captured offer source; it is not a player-
  performance or settlement authority.
- Known research-only sport rows can enter the Research OS only through the
  explicit research-shadow path. Their modeling/selection state remains
  fail-closed.
- SubjectOfferSet identity now includes sport and competition, preventing
  cross-sport provider-ID collisions.

## Deterministic multi-sport replay

The committed historical sanitized fixture was used only as an engineering
regression workload. It is not a current slate or predictive acceptance test.

| Metric | Result |
|---|---:|
| Accounted rows | 11,113 |
| Research-eligible with explicit shadow enabled | 6,578 |
| Production-path research rows | 1,656 |
| Research-only/shadow rows | 4,922 |
| Unknown-sport rows | 8 |
| Universal host tasks | 8,067 |

Research-eligible offers by family:

| Family | Offers |
|---|---:|
| Baseball | 1,695 |
| Basketball | 836 |
| Gridiron | 820 |
| Soccer | 3,227 |

Subject-level fan-out reduced those offers to 1,161 subject tasks: baseball
206, basketball 43, gridiron 372, and soccer 540. Event, affiliation,
counterparty, environment, market-definition and offer tasks remain separately
accounted in the universal dependency plan.

## Validation

- Focused multi-sport/research/source/plugin tests: 62 passed.
- Full Python suite: 609 passed, 1 skipped.
- `compileall`: passed.
- policy validation: `DCM_POLICY_VALID`.
- generated inventory write/check: passed.
- whitespace validation: passed.

## Non-claims

No new sport is production-complete from this tranche. No live-board forecast,
Top100, Top25, Playable, settlement, predictive superiority, production-root
or host-performance certification is claimed. `LR000000` and predictive claim
`NONE` remain unchanged.
