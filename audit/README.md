# DCM GitHub run archive

Every production-shaped DCM run can be independently verified from this
directory: the run actually finished, research happened WITH evidence
(URLs, timestamps, claim hashes) BEFORE ranking, and every lock cites
that evidence. No hallucinations, no half-runs treated as cards, no
ranking without research.

Packs live at `audit/runs/<runId>/`. The append-only ledger is
`audit/INDEX.jsonl`. Packs never include HARs, sqlite indexes, full
population dumps, worlds, cookies, tokens, or authorization material.

## What a pack proves

| File | Role |
| --- | --- |
| `RUN_AUDIT.md` | Human review: identity, BEFORE/AFTER counts, each lock, failures |
| `pick_evidence.json` | Machine review: `locksCertified`, `hallucinationRisk`, covering claim hashes |
| `evidence_bundle.jsonl` | The evidence itself (URL, observed_at, claim_hash, claim_value) |
| `research_requests.json` | What research was demanded before ranking |
| `strict_card.json` | The locks. Each must point at covering hashes in the bundle |
| `frozen_forecast.json` / `hashes.json` | Run identity: runState, cutoff, board/forecast hashes |
| `checkpoint.json` | completedStages must include RESEARCH and FREEZE |

**Do not trust a card unless `pick_evidence.json` has `locksCertified: true`
and each lock has `coveringClaimHashes` pointing at `evidence_bundle.jsonl`
rows with real `http(s)` URLs.** Fixture research on a live HAR fails the
gate. An empty card (`cardSize: 0`) may be `locksCertified` only as an
engineering empty-card, and only if research actually ran.

Learning revision stays **LR000000**. Predictive claim stays **NONE**.
Phase B/C V1 hash `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`
is not changed by this archive.

## How to produce a pack

From a live HAR (research must be a real bundle, not fixture):

```
python -m dcm --input <har> --version 6.0.0 --cutoff-from-capture --research bundle --archive-github
```

`--archive-github` writes `audit/runs/<runId>/`, appends `INDEX.jsonl`,
commits, and pushes. Pass `--no-archive-push` to write the pack without
pushing.

From an existing run dest:

```
python -m dcm.archive --dest dcm_v6/RUNS/<id> --push
```

Omit `--push` to copy+commit locally only.

Every run still writes `dest/audit/RUN_AUDIT.md` locally even without
`--archive-github`.
