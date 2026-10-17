# DCM multi-HAR run failure and recovery audit

Baseline: `main` at `d795084f8d2b87b002b7bc41209e2474f5165da1` (PR #114). This audit uses the user's progress transcript, the checked-out source, and the sanitized prior run receipts in the supplied Drive folder. The prior private run directory, raw HARs, and host memory logs are unavailable here. The previous run's counts and failure states are recovered from its saved receipts; they are not an independently reproduced replay.

## What happened

1. The operator retrieved 32 named inputs and reported 11 unique SHA-256 contents. Several names described different pages or leagues but held the same bytes. Filename sport labels therefore did not establish data coverage.
2. The all-sports composite exited `-9` after 1,285.6 seconds, leaving a 755,609,967-byte partial board. The prior operator described a host memory limit; `-9` establishes SIGKILL but, without cgroup/OOM logs, does not independently prove who sent it. A Python `except Exception` cannot handle SIGKILL, and the in-process slate command could not write a terminal receipt after such a kill.
3. Sport-sized CFB, NHL, and WNBA runs finished with their production gates blocked. Soccer source-level accounting completed, but its composite stopped with a 406,836,530-byte partial board and **no final DCM receipt**. The prior package counted 157,789 unique offer rows: 11,783 schedule-matched to October 16, 91,503 to October 17, 441 date-unresolved, and 54,062 outside those dates. It did not complete independent official event-level verification for all rows.
4. The seven evaluators produced per-date readiness/blocker receipts. No calibrated forecast, production Top 25, or playable was produced. No public player-level fact was imported, and settlement was deferred at the captured cutoff.
   The CFB integrated director reported `BATCH_CAP_EXCEEDED` for its first 8-task / 425-dependent-offer packet. This is a producer/consumer budget mismatch requiring a bounded batch-contract fix, independent of the memory watchdog.
5. Eleven sanitized artifacts were uploaded to the run folder, including a source inventory, cohort ledger, checkpoint, run status, gate receipts, and closeout summary. The saved task DAG distinguishes completed, partial, blocked, and deferred tasks. The folder listing confirms names and sizes; this audit has not independently read back and hashed every uploaded byte against `artifact_hashes.json`.
6. The live conversation still ran for 10h 35m without a final response and showed 0/5 tasks marked complete. That display was stale and did not reflect the saved partial closeout. Elapsed time is not evidence of completed modeling. The communication and progress accounting failed even though partial deliverables existed.

## Code evidence at the baseline

| Boundary | Observed weakness | Consequence | Treatment in this branch |
|---|---|---|---|
| `dcm.chat.cli` → `run_slate` | Ran in the same Python process, with no wall, progress, or RSS watchdog | Silent hard kill or unbounded stage | Separate parent supervisor with typed failure receipt and configurable limits |
| `dcm.chat.slate._legacy_run_slate` | Parsed each pathname separately, even when bytes matched | Repeated source work and larger union | Keep every named source record; parse each SHA once and mark aliases |
| `dcm.chat.slate` composite failure | Loaded every source claim list into memory for a fallback merge | Could repeat the failure in the process already under memory pressure | Preserve source receipts and fail the union without that merge |
| `dcm.chat.har_only_controller` | Reparsed duplicate HARs for capture time; reread duplicate claim projections during diff | Repeated large JSON loads and memory | Cache time by content hash; aliases contribute byte-duplicate relationships without repeated claims |
| `dcm.chat.slate._step` | A `valid: false` verification result was reported as `COMPLETE` | Receipt could overstate verification | Treat failed verification as a typed failed step |
| Slate operational receipt | Did not depend on all failed steps | Could call accounting accepted despite step failure | Gate operational status on phase failures |
| CLI child exit | Exit zero alone could be treated as success | Incomplete union could appear complete | Parent checks hash-bound manifest and receipt, composite ID, and failed phases |

`compose_ingest_stream` in `dcm.ingest.composite` still repeatedly reconciles all cumulative scope attempts and scans the full previous/current projection union per capture. This may have substantial CPU and artifact growth on large captures. The supplied 32-file workload is needed to profile the exact share of the ten-hour elapsed time. No benchmark claim is made from the small fixtures.

The missing forecasts and public research are separate from process failure handling. Source-level CFB/NHL/WNBA accounting succeeded, yet their `probabilityStatus` was `NONE`; no player-level public observations were imported, no sport parameter snapshots or historical feature matrix supported the blocked gates, and offer revalidation remained unavailable. A watchdog can make those states visible and finite; it cannot turn absent evidence into a valid prediction. The saved cohort summary also says official event-level schedule validation was partial and 441 rows had unresolved dates.

## Recovery contract

The parent and child must have different responsibilities. The child owns typed stage work and writes privacy-safe transitions. The parent can detect no-progress intervals, wall limits, memory growth, process death, missing receipts, and failed hashes even if the child cannot execute exception handling. A failed run returns nonzero, retains local source artifacts, writes `run_failure.json`, forbids production selection, and says `checkpointVerified: false` until a separate verifier proves otherwise. The parent stores child stdout/stderr locally with restricted permissions and never embeds their contents in the failure receipt.

Default guard: 7,200 seconds wall; 1,200 seconds without a stage transition; child RSS at 80% of the detected cgroup memory limit and total cgroup use at 90% when `--max-rss-mib` is zero. These are operational limits, not a host-performance certification. A stage can be intentionally retried with explicit larger bounds only after inspecting its partial artifacts. A hard kill of the entire container, including the parent, requires an outside orchestrator to read the last atomic progress file on restart.

Do not add `try/except` to every pure function. Put typed catches at I/O, process, stage, and transaction boundaries. A catch must classify an error, preserve its causal code without raw data, roll back or checkpoint state, and either retry only when idempotent or stop dependent work. Broad catches that turn failures into empty rows or successful receipts are defects.

## Remaining whole-system hardening matrix

The current branch repairs the multi-HAR `run-slate` path. The following boundaries still need an audited contract and adversarial tests before claiming every DCM operation is guarded:

| Boundary | Required catch / invariant | Failure output |
|---|---|---|
| Drive/source acquisition | Timeout, auth, missing bytes, size/hash mismatch; idempotent bounded retry | Source-specific `INACCESSIBLE_SOURCE` or `HASH_MISMATCH`, no fabricated coverage |
| HAR/PDF/OCR intake | Byte/entry/page limit, malformed JSON, decompression/OCR timeout, page accounting | Per-source and per-page error with source hash; all observed offers accounted |
| Identity/schedule join | Ambiguous IDs, conflicts, missing event times, wrong league/date | Quarantined unresolved row; no event-date inference from filename |
| Composite reconciliation | Incremental state and deterministic stream; bounded memory and checkpoint per partition | Exact failed partition and resume pointer, never all-source in-memory retry |
| Research | Per-source timeout/rate limit, stale or post-cutoff fact, missing host tool, import conflict | Typed acquisition failure and unchanged evidence gate |
| Feature/model/KDE/SVD/EventWorld | Resource bound, numeric/shape/seed checks, supported sport-market contract | Individual capability blocker or failure receipt; no fabricated probability |
| Ranking/portfolio/payout | Failed upstream stage, missing exact line or payout, invalid joint outcome | Per-row terminal state; no recommendation or verified EV |
| Freeze/settlement/learning | Atomic writes, hash/readback, authoritative outcome mismatch, chronology | No partial freeze promotion; append-only correction or typed block |
| Archive/Drive outbox | Local snapshot integrity, retryable upload, readback hash, publication state | Local-only checkpoint and explicit remote blocker |
| GitHub/CI/release | Required checks, inventory drift, package import, policy/privacy | No merge or operational promotion on failed gate |

## Acceptance needed for full closure

Use the exact supplied 32-file manifest, but keep raw HARs in local quarantine. Verify 32 source records, 11 unique hashes if the same bytes are available, complete offer accounting, separate October 16 and 17 event-date cohorts, 441 unresolved joins only if reproduced, and no cross-date leakage. Run fault injection for malformed input, duplicated bytes, hung parser, SIGKILL, memory threshold, disk full, corrupted checkpoint, partial research import, and remote upload failure. Compare resumed and uninterrupted hashes. Profile peak RSS, CPU, wall, I/O and artifact size on representative real inputs. Every applicable seven-gate status and final cohort state must have a receipt; zero certified plays is a valid outcome.

This branch does **not** certify that full closure. No prior private-run artifact was recovered, no real slate was rerun, and no predictive/production claim is earned. `LR000000` and predictive claim `NONE` remain unchanged.
