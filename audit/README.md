# DCM GitHub run archive

Every production-shaped DCM run can be independently verified from this
directory: the run actually finished, research happened WITH evidence
(URLs, timestamps, claim hashes) BEFORE ranking, and every card pick cites
that evidence. No hallucinations, no half-runs treated as cards, no
ranking without research.

Packs live at `audit/runs/<runId>/`. The append-only ledger is
`audit/INDEX.jsonl`. Packs never include HARs, sqlite indexes, full
population dumps, worlds, cookies, tokens, or authorization material.

**Never trust a card as a DCM pick unless `modelRunCertified` is true.**
`locksCertified` is a derived compatibility alias only
(`modelRunCertified AND selectionCertified AND evidenceCoverageCertified`).
A manual researched card MUST have `locksCertified: false` even when
`evidenceCoverageCertified` is true.

## Certification flags

| Flag | Meaning |
| --- | --- |
| `archiveIntegrityCertified` | Pack has hashes and no HAR/sqlite/secrets were copied |
| `evidenceCoverageCertified` | Every card pick has complete PLAYER+EVENT+MARKET_DEFINITION/OFFER coverage via `dcm.research.coverage`. Empty card: true only if research ran |
| `evidenceTemporalCertified` | Every claim `observed_at` and `published_at` are present and not after `forecastDecisionCutoff`. Observation after board capture is OK if still before cutoff. Backdated `observed_at` before HAR capture while research ran after is false (see `evidenceTemporalNote`) |
| `modelRunCertified` | `runState` in {COMPLETE_FROZEN, COMPLETE_WITH_UNSUPPORTED_ROWS, EMPTY_CARD_COMPLETE} AND stages include RESEARCH+MODEL+RANK+FREEZE (or `softwareE2eComplete` with `frozenForecastHash`) AND evidenceMode is not fixture-on-live-HAR and not `manual_research`. MANUAL_RESEARCH_CARD / softwareFreeze false / hashCertifiedPythonFreeze false => always false |
| `selectionCertified` | True only if `modelRunCertified` AND the card rows were produced by the Python portfolio (`strict_card.json` from the runner), not a hand-built list |
| `productionRootCertified` | True only if `productionSelectionReady`/`systemCertified` from `production_readiness.json` (v5 mount + V1 hash). Currently false on live HARs because V1 bytes are absent |
| `predictiveValidationEarned` | Always false while LEARNING_REVISION is LR000000 / PREDICTIVE_CLAIM NONE |
| `locksCertified` | Derived alias only. Do not treat this as "the engine certified this card" by itself |

New machine-state field names do not use the word "lock".

## What a pack proves

| File | Role |
| --- | --- |
| `RUN_AUDIT.md` | Human review: identity, BEFORE/AFTER counts, each card pick, failures |
| `pick_evidence.json` | Machine review: split certification flags, covering claim hashes |
| `evidence_bundle.jsonl` | The evidence itself (URL, observed_at, claim_hash, claim_value) |
| `research_requests.json` | What research was demanded before ranking |
| `strict_card.json` | The card. Each pick must point at covering hashes in the bundle |
| `frozen_forecast.json` / `hashes.json` | Run identity: runState, cutoff, board/forecast hashes |
| `checkpoint.json` | completedStages must include RESEARCH, MODEL, RANK, and FREEZE for `modelRunCertified` |
| `prop_explanations.jsonl` | Machine-readable PropExplanations for top25 + card (copied when present) |
| `evidence_graph.json` | EvidenceGraph snapshot (copied when present) |
| `feature_store_manifest.json` / `feature_store.jsonl` | Cutoff-immutable features (copied when present) |

Fixture research on a live HAR fails `modelRunCertified`. An empty card
(`cardSize: 0`) may still have `evidenceCoverageCertified` if research ran,
and `emptyCardReason` records why the card is empty.

Learning revision stays **LR000000**. Predictive claim stays **NONE**.
Phase B/C V1 hash `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`
is not changed by this archive.

## How to produce a pack

From a live HAR (research must be a real bundle, not fixture):

```
python -m dcm --input <har> --version 6.0.0 --cutoff-from-capture --research bundle --archive-github
```

`--archive-github` writes `audit/runs/<runId>/` and appends `INDEX.jsonl`.
Git commit is optional: the local pack is written even if git identity is
missing or `git commit` fails (the DCM run still succeeds). Pass
`--no-archive-push` to write the pack without pushing. Git does not require
`git config user.name`; archive commits use `GIT_AUTHOR_*` if set, otherwise
`dcm-archive <dcm-archive@users.noreply.github.com>`.

From an existing run dest:

```
python -m dcm.archive --dest dcm_v6/RUNS/<id> --push
```

Omit `--push` to copy+commit locally only.

Every run still writes `dest/audit/RUN_AUDIT.md` locally even without
`--archive-github`.

## Example pack

`audit/runs/2026-08-30-har0830-manual/` is the 08/30 WNBA researched card
(6 STANDARD candidates) with Basketball-Reference and ESPN claim hashes.
It is **not** a Python `COMPLETE_FROZEN` freeze. `modelRunCertified` is
false, `selectionCertified` is false, `locksCertified` is false. These six
are researched candidates, not PLAYABLE outputs of EventWorlds / grading /
ranking / portfolio. Read `pick_evidence.json` and `evidence_bundle.jsonl`
before treating them as DCM picks.
