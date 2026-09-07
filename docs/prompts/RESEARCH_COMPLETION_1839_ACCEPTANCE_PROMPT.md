# Research-completion prompt: 1,839 subject-offer sets

Run against the latest `main` with the owner-supplied HAR as private local input. The owner supplies no research. Perform fresh, cutoff-valid web research on every run; reuse only claims whose provenance, freshness, and temporal validity pass. Never upload or echo raw HAR, cookies, response bodies, credentials, or absolute runtime paths.

## Execute to completion
1. Verify `main`, clean state, exactly one task branch/PR, CI, and the prior checkpoint. Hash the HAR and preserve its hash/configuration as the run identity.
2. Re-ingest and account every row and offered side. Reconcile the complete population: all 1,839 subject-offer sets, every eligible player, team, opponent, event, environment, market definition, and modifier. No Top-100 shortcut; Top-100 is an output after full-board processing.
3. Fan out reusable research in dependency order: event/environment → teams/opponents → players/roles → market definitions → offers. Use exact/hash indexes, temporal keys, evidence graph reuse, bounded CELF/set-cover batches, and descendant-only invalidation. One validated source observation may satisfy all dependent offers; record each dependency.
4. For every research task, obtain public authoritative evidence (official league/team/player/statistics/weather/rules sources first). Capture URL, source identity, authority, independence, published/observed/valid times, cutoff, claim hash, contradiction/freshness state, coverage contribution, and explicit failure reason. Do not infer missing facts or mark a task complete without evidence.
5. After each batch: import typed observations, recompute coverage, persist immutable claims and scheduler decisions, run the canonical engine, and write a sanitized checkpoint. Checkpoint includes completed/pending task IDs, claim hashes, counts, next batch, input/config/code hashes, and exact blockers.
6. Prove deterministic resume: interrupted and uninterrupted runs with the same HAR hash, cutoff, configuration, and evidence must produce identical claim, accounting, ranking, and freeze hashes. Freeze before settlement; settlement and learning are append-only and future-only.
7. Produce full-board terminal accounting, ranked Top-100/Top-25, genuine playables, and explicit abstentions. Promote each sport only after adapter/schema/market/failure/benchmark acceptance; unsupported or research-only sports remain fail-closed.
8. Regenerate inventories and artifacts; run format/lint/type/contract/property/integration/package tests and relevant benchmarks. Commit, push, open the single PR, wait for CI, merge normally, verify `main`, and record the final receipt.

## No-fabrication stop rule
If web access, permitted evidence, protected checks, or budget prevents completion, stop safely with `status=EXTERNAL_RESEARCH_PENDING`, preserve all completed claim hashes and the next deterministic batch, and report the exact blocker. Never claim 1,839 complete, 10/10, predictive certification, or production readiness without receipts.
