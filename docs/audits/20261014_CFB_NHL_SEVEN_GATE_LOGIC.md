# 10/14/26 CFB + NHL: seven-gate logic and input audit

## Purpose

The seven gate evaluators now complete on every canonical run, including an
empty run. Missing inputs are recorded separately from gate completion so an
input issue cannot stop the run from reaching the remaining gates. A completed
gate evaluation does not mean its scientific computation ran or that a
recommendation is eligible.

The machine-readable empty-input diagnostic is
[`20261014_CFB_NHL_SEVEN_GATE_INPUT_DIAGNOSTIC.json`](20261014_CFB_NHL_SEVEN_GATE_INPUT_DIAGNOSTIC.json).
It is deliberately labeled as a gate-readiness diagnostic, not a forecast.

## Run scope and source boundary

The requested date has scheduled CFB events Kennesaw State at Missouri State
and Western Kentucky at Sam Houston, and NHL event Dallas at Colorado. The
Missouri State game center lists Kennesaw State for Oct. 14 at 6:30 p.m.; the
NHL's schedule update lists Dallas at Colorado for Oct. 14 at 6:30 p.m. local
after a start-time change. Sources:

- https://missouristatebears.com/game-center/7864
- https://ksuowls.com/calendar/event/kennesaw-state-university-football-at-missouri-state-5004
- https://gobearkats.com/sports/football/schedule
- https://wkusports.com/sports/football/schedule
- https://www.nhl.com/news/nhl-announces-the-following-start-time-changes-for-the-2026-27-regular-season-schedule
- https://www.nhl.com/stars/news/topic/press-releases/dallas-stars-announce-2026-27-regular-season-schedule-071626

The available Oct. 14 Outlier PDF is a research/screenshot export (SHA-256
`e037a8d76f330af37f9a0acb90ce7d23525fee803f282a3ea22c355654c05563`). Its
trend claims do not establish an active offer, exact line/side, capture
timezone, or forecast cutoff. No verified CFB/NHL offer board, entry contract,
stake, or complete dated payout table is present in the run input. The official
game schedules establish event identity and time only.

## Why each gate had an input problem

| Gate | Logic and observed gap | Work completed | Input producer still needed for a real computation |
|---|---|---|---|
| KDE | A KDE needs comparable, cutoff-safe continuous outcomes. Most player prop outcomes here are discrete counts; smoothing them creates mass at impossible fractional counts. The prior runner also had no modeled market rows or historical distribution samples. | Discrete markets now use a registered empirical point-mass fallback when at least 30 exact-key, cutoff-safe samples exist. KDE remains diagnostic-only. Empty runs produce a readiness receipt instead of `NOT_APPLICABLE`. | Acquire comparable player/stat history with units, role, market definition, observed time, label-available time, and cutoff. Obtain an observed offer before evaluating a line-specific market. |
| SVD | SVD is defined over a numeric feature matrix. The run had no historical role/opponent matrix, so there was no valid input to decompose. An identity or made-up matrix would create a fake signal. | The runner now builds a matrix from frozen `numericFeatures` in cutoff-safe chronological training rows when available, records excluded future/invalid rows, and runs the existing rank-checked SVD. | Retain the frozen numeric feature snapshots in canonical run history. The current 10/14 diagnostic has no eligible feature rows to use. |
| Shared-event Monte Carlo | CFB has a shared football EventWorld backend, but this research-only input had no modeled CFB rows or parameter snapshots. DCM has no hockey EventWorld backend; using basketball/football primitives for hockey would be invalid. | The gate is always evaluated. The blocker receipt lists the needed parameter snapshots and sport-specific backend. | Run the CFB backend on real resolved player/market inputs. Implement and validate a hockey primitive ledger/EventWorld before claiming NHL simulation. |
| Algorithm graph | Registry validation and dependency ordering ran. Registry membership is not execution of every algorithm, and 173 registered algorithms is not 173 applicable operators on these two slates. | The graph gate remains an executed registry/DAG validation with candidate/execution counts kept distinct. | Add sport-specific operators only with typed units, stage contracts, valid producers/consumers, tests, and benchmark evidence. |
| Calibration | Calibration consumes DCM's own frozen pregame forecasts joined to authoritative later settlements. There are zero eligible chronological pairs in this run. Public game outcomes without original frozen predictions cannot calibrate these forecasts. | The readiness estimator runs and reports zero eligible pairs; `LR000000` and predictive claim `NONE` remain. | Continue autonomous settle/join over genuine frozen DCM runs; only then run event-disjoint chronological evaluation. |
| Portfolio dependence | The final card had no selected entries. The old implementation skipped the gate in this case. | The gate now analyzes aligned modeled candidates when a final card is empty. If there are no candidates, it emits an executed empty-portfolio diagnostic with a null joint probability instead of a skipped/NA result. | Produce at least two eligible forecasts with aligned shared-world outcome rows. Do not force a card to make this gate nonempty. |
| Payout EV | EV is conditional on an observed multi-selection entry contract, stake, complete dated payout rules, settlement/reversion rules, and calibrated joint outcomes. None were supplied by the research screenshots. | The gate evaluates every run and returns `EV_UNVERIFIED` with exact missing inputs; no expected return is made up. | Resolve the actual platform entry, captured stake/legs, complete payout table, push/void/reboot treatment, and validated joint outcomes. |

## Run-through contract

`capabilityRunThrough` reports `COMPLETED` for all seven gate evaluations and
`runContinuesOnInputIssues=true`. Each gate also carries its computation state,
input issues, required inputs, producer needed, and output hash. Thus the
controller proceeds through the gate sequence without treating missing data
as a fatal process error. Scientific and production eligibility remain
separate: this empty-input run has no forecasts, probabilities, selected
portfolio, or EV result.

## Acceptance boundary

The new tests prove that (a) all seven gate evaluators complete with missing
inputs, (b) the discrete fallback preserves point mass and emits no forecast
probability, (c) an empty portfolio is diagnosed rather than skipped, and (d)
candidate dependence is analyzed when there is no selected card but aligned
shared outcomes exist. These are software proofs. They do not satisfy the
missing real CFB/NHL data, NHL backend, calibration labels, or payout contract.
