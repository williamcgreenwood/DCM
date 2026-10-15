# Research funnel and host acquisition checkpoint — 2026-10-15

**Checkpoint updated:** `2026-10-15T21:14:30Z`

## Repository baseline

- Repository: `williamcgreenwood/DCM`
- Verified `main`: `2f8f53015da6c56ec2fe7f76e610748159fac144` (`Record merged seven-gate run-through checkpoint (#111)`).
- PR #107: closed and merged to `main` as `98cb698cf000b963e24ca47b3c1e4e18722bda96`.
- PR #112: merged as `607d03b01f857b1b67b0cd1e2fbfe937d0239bb5`; this is the verified latest repository commit after merge.
- Exact PR head: `1376cfa7b1771db10fc310a4083e8c9a80121ce8`; required workflow run `38807835854` passed all 8 jobs.
- Work branch: `fix/insights-research-funnel-20261015` (based directly on verified `main`); implementation is merged.
- No source HAR, PDF, private player data, or generated run outputs are added to the repository.

## Problem found and code change

The production selector correctly requires exact current-offer evidence, complete research, a frozen model prediction, and production certification. The research presentation was incorrectly coupled to that selector: its routine output stopped at Top 100 / Top 25, so users saw only 25 rows even when thousands of captured claims were available. The host acquisition handoff also lacked concrete instructions to search fallback sources and continue independent requests.

The research path now emits `insights_research_funnel.json` independently of the production card. It ranks every queueable captured player prop, preserves line/side-missing rows with typed blockers, and prioritizes exact captured line/side rows. It exposes the full ranked population once, with claim-ID frontiers at Top 2000, 1000, 500, 250, 100, 50, 25, 12, and 6. Global results are partitioned by league and by event date in an explicit IANA timezone. These are deterministic research-attention rankings, not win probabilities, picks, model predictions, or certification.

Claims excluded from candidate ranking (for example game lines or incomplete/non-player claims) remain in a hashed `excludedRows` diagnostic with their disposition and typed blockers; they are not silently discarded from input accounting.

`dcm-host run-slate --event-timezone <IANA-name>` supplies the event-date scope. The ChatGPT research contract now directs the host to use the user's HAR/screenshots as the chat-ignition line/side snapshot, avoid asking for another board HAR, search official/approved sources for missing player/event/team/opponent/environment/rules facts, reuse entity research, record source/time provenance, attempt fallbacks, and continue independent tasks. It prohibits inventing lines, probabilities, outcomes, payouts, calibration, or dependence.

The old bounded `research_queue_top100.json` remains as a compatibility/model handoff. The production selector continues to fail closed when actual production prerequisites are not earned; missing certification does not erase the research funnel.

## 10/15 full-input smoke findings

The provided run folder contains 16 HAR files, 9 unique contents, and one 82-page PDF. The full HAR replay completed accounting and union reconciliation:

- 6,819 canonical claims, including 6,602 player-prop candidates and 217 game-line claims.
- 6,602 queueable research candidates; 6,669 exact Insights line/side snapshots are retained in the separate offer-equivalent audit.
- The funnel was rebuilt over all 6,819 canonical claims in `America/Los_Angeles`: **0.365 seconds** in the local benchmark.
- All 6,602 candidates remain in the full cross-date research funnel; its tiers contain 2,000 / 1,000 / 500 / 250 / 100 / 50 / 25 / 12 / 6 rows.
- The Oct. 15 local-event bucket contains **1,376** candidates: NHL 976, NFL 319, NCAAFB 81. Its Top 2000 contains all 1,376; the smaller frontiers are 1000 / 500 / 250 / 100 / 50 / 25 / 12 / 6.
- Research OS readiness evaluated true using the Insights-only research graph. The first batch waited for host observations, as designed; no observation response or source acquisition is claimed by this code smoke test.

The PDF OCR receipt reports 78 of 82 pages with text. The screenshots were matchup, game-line, standing/ranking, and injury material; no individual player-prop cards were identified. PDF metadata creation is `2026-10-15T10:36:32Z`, later than the HAR-derived cutoff `2026-10-15T10:20:30.882Z`; the screenshot capture time is unverified. It is therefore audit-only for this historical replay and does not create current player offers.

## Seven capability gates: evaluation versus computation

The seven-gate evaluator completed all seven gates. Their computation states remain distinct from evaluator completion:

| Gate | Computation status | Missing input / issue |
|---|---|---|
| KDE | Readiness only | No modeled comparable market history and no resolved market definition. The 4–19 Outlier samples are below the 30-observation discrete fallback minimum. |
| SVD | Blocked | No frozen, cutoff-safe chronological numeric feature matrix. |
| Shared-event Monte Carlo | Blocked | No sport parameter snapshots or supported shared EventWorld outputs; event groupings are not simulations. |
| Algorithm graph | Executed | Registry/DAG validation ran; the registry entry count is not the number of applicable/executed algorithms. |
| Calibration | Readiness only | Zero eligible frozen-forecast/authoritative-settlement pairs; ECE undefined, N=0, learning revision `LR000000`. |
| Portfolio dependence | Empty diagnostic | No selected portfolio or aligned modeled outcomes; no dependence statistic was claimed. |
| Payout EV | `EV_UNVERIFIED` | No verified entry contract/stake, complete dated payout rules, or calibrated joint outcomes. |

Those missing data remain honest computation limits; the design correction is that they no longer suppress the independently useful ranked research funnel. No output claims production probabilities, calibration, dependence, EV, or a certified card.

## Verification and resume

- Focused selectors, run-director, insight-closure, host-contract, funnel, and slate tests pass after the current code changes.
- Full `uv run --extra dev pytest -q` passed on the current tree (one optional test skip); the timezone CLI, research funnel, date partition, and run artifacts are covered.
- Algorithm registry consistency, DCM policy, generated inventory, algorithm-frontier smoke, and baseline-profile smoke passed.
- Synthetic DCM package/CLI run completed with archive, evidence, temporal, model-run, and selection integrity checks true; predictive validation and production-root certification remain false.
- Synthetic throughput benchmark: 100 rows in 6.92 s (263 MB peak RSS); 1,000 rows in 83.16 s (2.04 GB peak RSS). Performance remains explicitly uncertified because these are synthetic workloads.
- GitHub CI run `38807835854` completed successfully on the exact PR head: all 8 jobs passed (Package/CLI, benchmark/profile, generated inventory, RFECV chronology, full test suite, algorithm/policy/governance, durable batch-search, and python-dcm).
- Queue benchmark: 6,819 claims -> 6,602 candidates and all ranked tiers in ~365 ms.
- PR #112 merge commit: `607d03b01f857b1b67b0cd1e2fbfe937d0239bb5`. The merge is verified; GitHub exposed no separate post-merge workflow run for the merge commit.
- No duplicate implementation work is pending. Resume by reading PR #112 and this checkpoint, verifying `main` is at or descends from the merge commit, and only then handling any new run or newly available evidence.
- Next run command should include the active session timezone, for example `dcm-host run-slate ... --cutoff-from-capture --event-timezone America/Los_Angeles`.
