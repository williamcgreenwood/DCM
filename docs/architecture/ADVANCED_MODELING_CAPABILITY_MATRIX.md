# Advanced Modeling Execution Layer — Capability Matrix

**Scope:** canonical `src/dcm` runtime based on protected `main` SHA `2fd1ec7dd14285872307a68597262a327e17d649`
**Learning revision:** `LR000000`
**Predictive claim:** `NONE`
**Production certification:** not earned

The run receipt `advanced_modeling_execution.json` is written by
`dcm.runner.run_dcm`, hash-validated, and bound into `freeze.json` and
`hashes.json`. Registration alone never counts as execution. Each row below
distinguishes code presence from runtime use and scientific/production status.

| Capability | Registry | Implemented | Runtime consumer | Tests | Calibrated | Production certified |
|---|---|---|---|---|---|---|
| Versioned model DAG (`ALG-CTRL-001`) | Yes | Yes | Canonical runner validates its dependency order and records every capability receipt | DAG and receipt contract tests | N/A | No |
| KDE (`ALG-ML-PROB-009`) | Conditional | Yes; deterministic Gaussian KDE with leave-one-out bandwidth selection and bounded normalized density snapshots | Canonical runner stores each density diagnostic, exact comparable key, input hash, snapshot hash, and consumer in the run receipt; cannot emit or mutate forecast probability | Sample sufficiency, bandwidth, normalization, no-probability, timestamp tests | No | No; live run blocks when comparable historical labels are unavailable |
| SVD (`ALG-ML-TABULAR-013`) | Conditional | Yes; column normalization, rank selection, timestamp leakage guard | Diagnostic feature consumer when a validated historical role/opponent matrix exists | Normalization, rank, cutoff leakage tests | No; chronological stability folds remain unrun | No; live run blocks on missing historical feature matrix |
| Shared EventWorld Monte Carlo (`ALG-MC-001`) | Core | Yes; Python and NumPy CFB backends retain fixed-seed bitwise parity; player receiving yards and touchdowns reconcile to shared QB pass totals with explicit unmodeled residuals | Canonical model path supplies outcomes to empirical probabilities and advanced receipts | Shared-world conservation, exact ledger identities, backend parity, fixed-seed, composites, and convergence tests | Calibration is separately gated | No |
| Calibration (`ALG-CAL-001`) | Core | Yes; chronological readiness/application gate plus event-disjoint expanding-window isotonic challenger fitting and Brier, log-loss, ECE, and reliability metrics | Per-forecast probability path plus OOS challenger report in the canonical run receipt; challenger never self-promotes | Calibration readiness, cutoff leakage, event-disjoint folds, isotonic OOS metrics and receipt-consumer tests | Not earned at `LR000000`; no automatic promotion | No |
| Portfolio dependence (`ALG-PORT-001`) | Core | Yes; existing portfolio filters plus aligned shared-world pairwise dependence, joint W/L/P state counts, win-count distribution and tail diagnostics | `build_card`, shared-world portfolio receipt and EV diagnostics | Portfolio constraints, alignment/hash, joint-state count, payout-fixture tests | Depends on calibrated joint outcomes; not earned | No |
| Payout EV (`ALG-EV-001`) | Conditional | Yes; existing hash-keyed payout calculator prices joint W/L/P worlds | Diagnostic calculation with a supplied payout hash; canonical forecast runs currently block on absent captured entry contract, stake, and promoted calibrated joint outcomes | Independent payout fixtures, push-aware and joint-world tests | No | No |

The registry contains 170 algorithm records at this base. This layer adds six
explicit modeling/control declarations; it does not treat a target count such
as 200 as a number of active algorithms. Conditional operators report
`INACTIVE_*`, `SHADOW_DIAGNOSTIC`, or `BLOCKED_*` when their evidence gates are
not met. Receipt hashes bind the producer, consumer, algorithm ID, state,
blockers, and bounded diagnostics. Manual host analysis is labeled
`MANUAL_SHADOW_ANALYSIS` unless canonical execution evidence is attached.

Before card construction, the canonical runner compares optional
`directionalResearchEvidence` with the selected side only when the producer
attests identity, exact market comparability, hard-gate eligibility, and a
cutoff-safe timestamp. Contradictory evidence blocks that candidate for review;
the system never automatically flips the side. Screenshot ordering without an
absolute timezone is accepted only in an explicitly labeled manual shadow
analysis and cannot satisfy the production cutoff gate.

## Remaining certification work

- Supply a validated, cutoff-safe historical role/opponent feature matrix and
  chronological SVD stability folds.
- Continue collecting cutoff-safe labels and compare the event-disjoint
  isotonic challenger against the frozen baseline. The implementation reports
  out-of-sample metrics but does not promote; maintain `LR000000` until governed
  promotion criteria pass.
- Supply the exact captured provider entry contract, payout/reversion rules,
  stake, and calibrated joint probabilities before certifying expected value.
- Validate the complete live end-to-end path against real authorized evidence
  and required CI/branch protection. Synthetic tests prove software behavior,
  not predictive superiority, host performance, or production eligibility.
