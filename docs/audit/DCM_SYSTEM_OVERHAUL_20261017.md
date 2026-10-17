# DCM system overhaul audit and execution contract

Baseline: `d795084f8d2b87b002b7bc41209e2474f5165da1`. This document distinguishes inspected code, saved run receipts, local generated benchmarks, and work still requiring the supplied captured bytes. The static inventory in `FAILURE_BOUNDARY_INVENTORY.json` covers every `src/dcm` Python module. Its call-site counts identify review candidates, not proven bugs or proof of safety.

## Evidence and current status

The supplied folder contains the October 16/17 capture set and prior sanitized run receipts. The saved receipts report 32 named files and 11 unique byte contents. Different labels on identical bytes cannot establish independent prop, schedule, injury, league, or ranking coverage. The attempted combined run exited `-9` after 1,285.6 seconds; SIGKILL is established, while the exact kernel/host cause remains unverified here. The completed sport cohorts and partial Soccer composite are described in `RUN_FAILURE_AND_RECOVERY_20261017.md`. This checkout has no private HAR run state. The sanitized receipts are not a substitute for a new byte-verified replay.

The October 15 subset also includes a 180 MB screenshots PDF. Its page extraction, hashes, and offer reconciliation remain separate unclosed input gates. No modeling, research, settlement, calibration, or production selection is certified by this code audit.

## Static boundary scan

The generated inventory found 272 Python modules, 1,927 function definitions, 325 exception-handler sites (32 catching `Exception`, `BaseException`, or bare), and 697 calls matching the scan's I/O/process operation names. Of those calls, 527 have no `try` directly around them. These numbers are **not** 527 confirmed missing catches: a caller, transaction context, or process supervisor can own the failure boundary, and method names such as `run` can be unrelated to external I/O. Review each flagged site by its actual call graph, transaction, and receipt. An indiscriminate `except Exception: pass` would make the system less trustworthy.

## Stage contracts and measured bottlenecks

| Stage | Failure and resource contract | Correctness receipt | Preferred implementation |
|---|---|---|---|
| Source acquisition and manifest | Bounded transfer/retry, expected size and SHA-256, aliases by bytes, private storage; one failed file cannot claim coverage | Named source state and hash, byte alias map | Python orchestration and streaming `hashlib` |
| HAR/PDF parser | Entry/page size and decompression limits; per-entry/page parse failure; no filename-derived facts; OCR timeout | Every source/page accounted; redacted provenance | Python parser with streaming JSON where compatible; OCR process isolated |
| Canonical offer and schedule join | Exact IDs first, conflicts/date ambiguity quarantined; no inferred side or line | Row-level disposition and unresolved join reason | SQLite indexes for large joins, Python domain contracts |
| Composite reconciliation | Incremental affected-scope updates; bounded lineage output; preserve all attempts for as-of replay; no memory fallback after OOM | Final hash parity, changed timeline, failed refreshes | Python plus SQLite spill only when measured memory requires it |
| Research acquisition and cache | Source timeout/rate limits, cutoff/rights/authority, transactional import, no made-up observations | Fact hash and source, freshness, conflicting evidence | Python host bridge and SQLite durable index |
| Feature/model/event worlds | Supported sport × market, numeric shape/units, deterministic seed, finite resources; unsupported state is explicit | Per-offer model or exact blocker; seven-gate applicability/execution | Python dispatch, NumPy numerical kernels; Rust only after parity and representative profiling |
| Rank/portfolio/payout | Full-board terminal disposition, top-k views after baseline modeling, correlation and payout gates | Direction separated from certification, immutable lineage | Python policy and indexed top-k; vectorized kernels only for measurable hot loops |
| Freeze/settlement/learning | Hash-verified atomic freeze; FINAL authoritative label; append-only corrections and future-only promotion | Freeze, settlement, chronology, and learning receipts | Python transactions, SQLite local index and verified outbox |
| Publish/CI/operations | Per-stage wall/stall/RSS and process death, local-only logs, upload readback, clean branch and required checks | Typed terminal receipt even after child kill; CI and remote hash | Python parent supervisor, external job watchdog for container death |

The project standard requires Python as the canonical orchestration and probability engine. Language migrations to SQL/DuckDB/Polars or Rust need a representative bottleneck, fallback, semantic parity, and operational evidence. A blanket rewrite into another language would enlarge the unverified surface and cannot solve missing observations or a killed process by itself.

### Changes in this branch

The slate parent supervisor writes an atomic progress/failure receipt, limits wall time, stall time, RSS, and cgroup use, and refuses a zero-exit child without valid terminal hashes. Source capture aliases are byte deduplicated while every named file remains in the manifest. In-process all-source fallback after composite failure was removed.

The runner now uses compact incremental reconciliation on multi-HAR inputs. The final canonical reconciliation still replays all attempts and asserts equality with the incremental board; scope attempts and row history remain intact for cutoff replay. The composite timeline records additions, removals, and changes instead of every unchanged projection in every capture. `board.json` is streamed to an atomic temporary file instead of building a second full JSON string in memory. A malformed acquisition-action accounting file now fails with `ACQUISITION_ACTION_ACCOUNTING_INVALID` instead of silently recording zero outstanding actions.

Generated 48,000-row/four-capture complementary-scope benchmark: full timeline 120,000 transitions, 6.80 seconds, 108.2 MiB traced peak; compact timeline 48,000 transitions, 3.20 seconds, 96.5 MiB traced peak. Both final reconciliation hashes matched. This workload is synthetic and does **not** establish a peak RSS or timing claim for the user's 32 files. The large-run output contract now carries `timelineMode=BOARD_CHANGES_ONLY`; consumers requiring a repeated per-capture retained-state event must request the legacy full mode. The saved per-scope attempts still support as-of replay.

## Remaining work required before full closure

1. Reacquire and SHA-256 all named source bytes in a private quarantine. Replay the date cohorts with bounded stage budgets. Compare accounting with saved receipts, classify source mismatches, and produce real CPU, wall, RSS, I/O, and artifact-size profiles. Do not silently reuse the previous operator's numbers.
2. Replace whole-file HAR JSON loads and duplicated parsed structures on large captures with a bounded parser/spill design, and verify parity for schedule, offer, and Insights claim semantics. Test malformed and compressed bodies, aliases, truncation, disk full, and resume.
3. Convert the 2,700-line `runner.py` sequence into named stage transactions with explicit input/output hashes, idempotency keys, timeout/resource budgets, checkpoint commits, and typed error propagation. Keep one canonical producer/consumer graph and prevent partial promotion.
4. Apply the inventory to each active research, sport, model, ranking, freeze, settlement, cache, and archive boundary. For each catch, define whether it retries, abstains, rolls back, or fails the run. Add fault injection at the boundary; pure functions generally propagate typed errors instead of swallowing them.
5. Close the observed CFB research batch cap mismatch, import actual cutoff-safe observations with host tools, and implement unsupported sport/market backends only with explicit outcome definitions and evidence. Run all seven applicable gate evaluators without equating a readiness receipt to execution or certification.
6. Verify remote artifact readback hashes and an external watcher for total container loss. A child/parent process guard cannot write a failure receipt if the entire host disappears.
7. Push through the one protected branch/PR, run full CI, review actual performance and recovery evidence, merge only when the increment's claims pass, and verify `main`. Full-system certification and predictive claims remain open until the separate operational evidence exists.

Acceptance for the complete overhaul requires every observed offer to have an exact terminal state, no date leakage, byte alias accounting, reproducible cutoff replay, every stage either complete or typed blocked, fault-injected recovery, bounded memory and time on the actual capture set, and the same final hashes after resume as an uninterrupted run. `LR000000`, predictive claim `NONE`, and zero certified playables are the honest current states.
