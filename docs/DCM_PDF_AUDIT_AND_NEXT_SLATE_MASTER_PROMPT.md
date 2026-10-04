# DCM PDF Audit, Research, Forecasting & Evidence Archive Protocol

## Invocation

Audit the attached PDF `Photo(6).pdf` (133 pages) and then, as a **separate forward-looking run**, research the football slate for `TARGET_DATE` in `America/Los_Angeles`.  Use the **Research, Forecasting & Evidence Archive Protocol** below.  Use the connected Google Drive as the durable research store and `williamcgreenwood/DCM` on GitHub for code, schemas, tests, registries, and compact immutable pointers only.

**Run parameters**

```text
INPUT_PDF = Photo(6).pdf
SPORT = NFL unless the extracted board says otherwise
TARGET_DATE = next scheduled slate after this run, America/Los_Angeles
RESEARCH_MIN_SECONDS = 300
MAX_FINAL_LEGS = 6
NO_OUTCOME_LEAKAGE = true
DRIVE_ROOT = DCM/ResearchRuns
GITHUB_REPO = williamcgreenwood/DCM
GITHUB_BASE = integration/v6-ml-architecture-20260830
```

Do not rush or return a preliminary card. Start a live research timer and do not release forecasts until at least 300 seconds have elapsed **and** the coverage gates pass.  The timer is not a sleep: persist the acquisition log, source timestamps, outstanding requirements, and coverage progress during those five minutes.  If a gate fails, return fewer than six picks or no picks.  Never fabricate a line, player, availability, stat, opener, result, source, price, or model output.

If sub-models are used for extraction, classification, or cross-checks, only use GPT-5.5-or-stronger models for final entity/offer linking and final adjudication.  Never let an uncalibrated sub-model finalize a pick.

---

## Non-negotiable separation of time and purpose

Create two bitemporal tracks and never mix them:

| Track | Cutoff | May contain | Must not contain |
|---|---|---|---|
| `AUDIT_SETTLEMENT` | the original forecast freeze time | original board, pre-cutoff evidence, final official outcomes, settlement and attribution | post-cutoff facts presented as original knowledge |
| `TARGET_FORECAST` | current timestamp for `TARGET_DATE` | current verified odds, lineup/injury/news, weather, role data, research evidence | outcomes of target games; stale screenshot prices treated as live |

Classify every audit fact as exactly one of: `KNOWN_AND_USED`, `KNOWN_NOT_ACQUIRED`, `ACQUIRED_NOT_CONSUMED`, `NOT_AVAILABLE_AT_CUTOFF`, or `POST_CUTOFF_ONLY`.  A postgame fact may settle a bet or inspire a later controlled experiment, but it may never rewrite the original forecast’s evidence set.

---

## Stage 0 — integrity, extraction, and complete board accounting

1. Hash the original PDF (SHA-256), record byte size/page count, retain immutable source identity, and render/OCR each page. Preserve original page and crop references.
2. Extract **every visible offer**, not just every player. Normalize the exact event, kickoff time/timezone, league, home/away, market, period, player/team, direction (Higher/Lower), line, price, platform, and screenshot page/crop.
3. Build stable IDs: `run_id`, `source_id`, `event_id`, `team_id`, `player_id`, `market_id`, `offer_id`, `evidence_id`, and `forecast_id`. Use canonical aliases; do not silently merge ambiguous names.
4. Deduplicate using exact canonical keys first, then MinHash/SimHash only as a review candidate. Mark superseded lines; never overwrite an observation.
5. Publish a `ResearchPopulationManifest` with counts for `pages`, `offers_visible`, `offers_extracted`, `deduped`, `ambiguous`, `current_verified`, `unsupported`, `settled`, and `unresolved`. Each unsupported offer gets a terminal reason such as `NO_CURRENT_LINE`, `ENTITY_AMBIGUOUS`, `STATUS_UNCERTAIN`, `MISSING_REQUIRED_FACT`, `OUT_OF_SCOPE`, or `DATA_CONFLICT`.

The screenshots are the source of truth for availability at the time captured. They are **not** proof that a price/line remains available for `TARGET_DATE`.

---

## Stage 1 — frozen-card audit

For each original leg found in the PDF, make a row containing:

```text
exact screenshot selection | event | market | line/price | platform | original timestamp if known |
official final/stat result | win/loss/push/void | pre-cutoff evidence used |
evidence class | decision-quality grade | attribution tags | counterfactual conclusion
```

Use official gamebooks, league/team reports, and authoritative box scores for settlement. For player props, settle the exact stat definition used by the sportsbook; flag any rule mismatch. For spreads/totals, use the final score and the exact listed line. For moneylines, use the official winner.

Audit both winners and losers. Attribute outcome and process separately using one or more of:

```text
PRICE_OR_LINE_MOVEMENT, AVAILABILITY_OR_INJURY, ROLE_OR_OPPORTUNITY,
MATCHUP_EFFICIENCY, GAME_SCRIPT, WEATHER, TURNOVERS_OR_SPECIAL_TEAMS,
EXTRA_TIME_OR_GARBAGE_TIME, DATA_EXTRACTION_OR_IDENTITY, MODEL_CALIBRATION,
CORRELATION, MARKET_CONSTRAINT, USER_CHANGE, or INSUFFICIENT_EVIDENCE.
```

For each loss and each passed winner, answer: “Would an evidence item that existed strictly before the original freeze have changed eligibility or rank?” Give a cited yes/no answer, not hindsight. Recommend only future-control changes supported by repeated or material failures.

---

## Stage 2 — retrieve reusable DCM and fantasy-football context

Before forecasting, inspect the live DCM repository and use only components that have an identified producer, consumer, test/contract, and version lineage. Do not invent a parallel engine or claim an inactive component is functional.

Load the user’s Fantasy Football project folder and the current `NFL Watch Schedule` task. Create a source manifest listing every artifact actually retrieved, timestamp, field-level allowed use, and failures. Use fantasy material only as context signals when traceable to primary/credible reporting:

* expected starter/backup and late availability;
* snap share, routes, target share, carries, red-zone usage, role changes;
* OL/DL and secondary availability; and
* schedule/rest/travel and game-time weather.

Do **not** use rankings, start/sit opinion, postgame recaps, or unverifiable social claims as predictive facts. If the folder/task or a source cannot be retrieved, state `MISSING` and continue without pretending it was used.

---

## Stage 3 — current-board research and evidence queue

Record the current time in `America/Los_Angeles` for every odds, starter/injury, weather, and result pull. Obtain current prices independently; report screenshot line and current line separately. For each visible event, research all eligible markets:

* favorite and underdog moneyline;
* favorite spread and underdog-to-stay-within-the-spread;
* game Higher and Lower;
* first-half market only when currently offered and demonstrably safer;
* every player prop in the PDF, with exact direction/line where available.

For each game/prop, obtain or explicitly mark `MISSING`:

```text
current ML/spread/total/prop line and price, opener, movement, consensus, best price,
platform availability, confirmed starting QB, game-day injuries and practice status,
weather (wind/rain/temperature/field/kickoff change), EPA/play, success rate,
explosiveness, havoc, sack/pressure, turnover, red-zone, pace/projected possessions,
travel/rest/time-zone, rivalry/lookahead/sandwich, role/usage and opponent matchup.
```

Use authoritative and first-party sources where possible. Public-versus-sharp claims are allowed only when independently verifiable; otherwise mark `MISSING`. Group research by game/team/gamebook rather than repeating player-by-player searches.

Build a requirement graph and select research actions with a reproducible marginal-value score, for example:

\[
Priority(a)=\frac{\Delta Coverage(a)\times Authority(a)\times Freshness(a)\times ExpectedVOI(a)\times Fanout(a)}{Cost(a)+Latency(a)+FailureRisk(a)}
\]

Use a local canonical index (SQLite B-tree + FTS/BM25), content hashes, aliases, graph reuse, and deterministic keys before web retrieval. Use a Bloom filter only as a negative-cache optimization, never as proof of absence. Store raw evidence and normalized claims separately with source, observed time, valid time, cutoff, extraction confidence, and parents.

---

## Stage 4 — models, probability, and selection

Keep distinct probabilities for winning, covering, staying within a spread, Higher, Lower, and each player-prop direction. Do not infer one from another.

1. Convert American odds to implied probability where applicable:

\[
p_{imp}=\begin{cases}
\frac{|o|}{|o|+100}, & o<0\\
\frac{100}{o+100}, & o>0
\end{cases}
\]

For two-sided markets, remove vig only when both comparable prices are available; otherwise label the probability `raw implied`.

2. Estimate a model probability only when evidence coverage and data freshness satisfy the market’s requirements. Use a calibrated ensemble with a market baseline, interpretable rating/feature model, and approved DCM components. Weight challengers by strictly chronological out-of-sample calibration—not in-sample accuracy.
3. Use reliability as a separate penalty for missing/old/conflicting data. A leg with a large apparent edge but unresolved starter/injury or identity ambiguity is ineligible.
4. For candidate ranking, use a transparent reliability-adjusted edge, e.g.:

\[
Score_i=(p_{model,i}-p_{market,i})\times Reliability_i-\lambda\,UnresolvedRisk_i
\]

This is a ranking aid, not a promise of value.
5. Test win, cover, total, and prop outcomes separately. Penalize favorites for backdoor/garbage-time exposure, slow pace, red-zone failure, opponent late scoring, rivalry/lookahead, weather, and late-QB uncertainty. Do not choose a spread when a materially safer ML has no clearly inferior evidence-backed edge.
6. Create shared-event/game-script dependencies. For a final card, choose at most one outcome per game/event and optimize realistic hit probability with correlation penalties; do not multiply leg probabilities as though they are independent.

For all models, preserve version, configuration hash, feature snapshot, training cutoff, calibration statistics (Brier, log loss, calibration slope/intercept, ECE), and out-of-distribution flag. New learning is a proposed versioned change only: train/validate/test chronologically, shadow it prospectively, and require promotion approval. Never auto-modify production logic from a single result.

---

## Stage 5 — forecast output and quality gates

Run a final current-odds/injury/weather refresh immediately before freeze. Freeze the board, evidence IDs, lines, times, model/config hashes, and ranked candidates. Do not force six picks.

Only after all gates pass, provide a **Final Card (0–6 legs)** from unique games, ordered by confidence. If six credible legs exist, it must include at least two moneyline/win legs, at least one spread/dog-cover leg, and at least one Higher/Lower. A required market type may be omitted only when no evidence-qualified current offer exists; name the limitation and the least-bad candidate without recommending it.

For every final leg include:

1. exact selection, screenshot line (if applicable), current confirmed line/price, platform, and timestamp;
2. market type and event/kickoff time;
3. estimated true-probability range and raw/no-vig market-implied probability;
4. evidence lineage and why this market is safer than alternatives in the same game;
5. three concrete failure paths;
6. exact no-play threshold (line/price/status change);
7. confidence `A`, `B`, `C`, or `Avoid`;
8. correlation/shared-failure conflicts with other selected legs.

Then include: ranked complete candidate table; no-play list; safer 3-pick subset only if its members independently pass; two most fragile legs with one validated replacement each; and combined low/mid/high sweep probability using a dependency-aware simulation/range. State that it is not a guarantee and do not recommend a stake size.

---

## Stage 6 — Drive archive, GitHub boundary, and receipts

Create and maintain this Drive run hierarchy:

```text
DCM/ResearchRuns/YYYY-MM-DD/<run_id>/
  00_source/ 01_board/ 02_evidence/ 03_features/ 04_forecasts/
  05_freeze/ 06_settlement/ 07_audit/ 08_learning/ manifests/
```

For every artifact persist: SHA-256, byte size, semantic type, source URL/identity, observed_at, valid_from, valid_to, cutoff time, producer version/commit, parent hashes, and retention tier. Maintain `drive_catalog.sqlite`/manifest with exact Drive IDs and content-hash mapping. A Drive object becomes canonical only after upload and metadata/readback verification. Write an immutable `ArchiveReceipt` stating `PRIMARY_COMMITTED`, partial, or failed; do not claim success if a large raw PDF cannot upload.

Use GitHub only for versioned code, schemas, tests, migrations, registries, ADRs, and compact content-addressed pointers. Never commit raw PDFs, screenshot packets, HAR files, account data, mutable odds dumps, or private research. If code changes are needed, branch from `integration/v6-ml-architecture-20260830`, run relevant tests, and open a **draft** PR with hashes and receipt references. Do not merge or alter main. If this run is audit-only, do not create code churn.

---

## Required final report

Return these sections in this exact order:

1. `Run integrity and coverage` — timing proof, artifact hash, extraction totals, missing data.
2. `Audit settlement` — every original leg, result, evidence-classification, and process attribution.
3. `What went right / wrong / change next` — only evidence-supported conclusions.
4. `Current research board` — every candidate market separately graded; terminal reasons included.
5. `Final Card` — 0–6 evidence-qualified unique-event selections, not forced.
6. `Archive and reproducibility` — Drive receipt/link, GitHub branch/PR if applicable, model/config/freeze hashes.

If any requirement cannot be satisfied, stop at the relevant stage, mark the affected output `MISSING` or `INELIGIBLE`, and explain exactly what is needed. Never replace missing evidence with confidence.
