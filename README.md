# Pillars DCM

Canonical Python engine for Pillars Distribution Cushion Model v6.

Software: `6.0.0+WSAB.E2E.PRODUCTION_PIPELINE.LR000000`  
Learning Revision: **LR000000** (not promoted)  
Predictive claim: **NONE**  
This is **not** an “optimized DCM 6.0”. Host performance is **not certified**.  
Phase B/C V1 expected SHA-256 `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22` — original bytes unavailable; production hash gate remains closed. Working freeze: `PHASE_BC_SCHEMA_V2_2026-08-29` (not auto-promoted).

Python is the single canonical DCM. The TypeScript operator console must not implement a second model.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

After install, `pillars-dcm`, `python -m dcm`, and `python -m pillars_dcm` work without `PYTHONPATH`. Identity is `VERSION.json`.

Without install (legacy):

```bash
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runner --help
```

## Tests

```bash
pytest -q
# or
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m pytest -q artifacts/dcm_v6_workstream_ab/tests
```

CI uses `DCM_FAST_WORLDS=64` (and related caps) so Monte Carlo stays bounded.

## CLI

Synthetic smoke:

```bash
python -m dcm --synthetic --research fixture --cutoff-from-capture --out dcm_v6/RUNS
```

Compact sanitized live HAR (full model path; fixture research is synthetic/test-only):

```bash
python -m dcm.runner \
  --input artifacts/dcm_v6_workstream_ab/fixtures/sanitized_live_har/prizepicks_compact.har \
  --version 6.0.0 \
  --cutoff 2026-08-29T16:00:00Z \  # required; or --cutoff-from-capture
  --research fixture \
  --output dcm_v6/RUNS
```

Full sanitized live HAR (account every row; do not fabricate logs; skip MC):

```bash
python -m dcm.runner \
  --input artifacts/dcm_v6_workstream_ab/fixtures/sanitized_live_har/prizepicks_20260829.sanitized.har \
  --version 6.0.0 \
  --cutoff 2026-08-29T16:00:00Z \  # required; or --cutoff-from-capture
  --account-only \
  --output dcm_v6/RUNS
```

Resume:

```bash
python -m dcm.runner --resume dcm_v6/RUNS/<run_id>/checkpoint.json
```

`--output` is an alias of `--out`. `--research file` (default) checkpoints at `INCOMPLETE_CHECKPOINTED` until validated `evidence/` files exist. `--research bundle` reads `evidence_bundle.jsonl`.

Expected `RUN_STATE` ∈ `{COMPLETE_FROZEN, INCOMPLETE_CHECKPOINTED, COMPLETE_WITH_UNSUPPORTED_ROWS, EMPTY_CARD_COMPLETE}`.

## Live HAR contract (2026-08-29 sanitized capture)

Unique projections: **11113**  
MLB 4480, SOCCER 3104, CFB 1568, WNBA 1238, EPL 580, KBO 81, NPB 44, OTD 8, CFL 10  
goblin 1849, demon 8053, standard 1211  
raw `allowed_wager_types`: over 6868, under_or_over 2290, missing 1955 (fail closed)  
status: pre_game 10836, in_progress 259, suspended 18  
84 games, 1358 players  

Goblins are extracted/accounted then excluded from selection. Demons get extra cushion. MLB is SHADOW (no production PLAYABLE). Soccer/EPL/KBO/NPB/CFL/OTD fail closed after accounting. Live/in_progress/suspended are not production-selected. Player IDs come from HAR `new_player` ids only.

## Cutoff and version

`--cutoff` is required unless `--cutoff-from-capture` or `--resume`. There is no hardcoded default (the old 2026-08-28T00:00:00Z default is gone). `--version` must match VERSION.json software or softwareShort. `--research-shadow` (default OFF) is required to deep-research MLB. Host research plans are bundle-oriented.

## Releases

Do not load a committed artifacts ZIP. Build with `python -m pillars_dcm.release` or `scripts/build_portable.py`.

## Honest blockers

- Hash-verified v5.4.1 canonical source bytes ABSENT (`bd1fb433…`)
- Phase B/C V1 original bytes ABSENT (`6e78dacc…`); V2 frozen but not production-accepted
- Host performance not certified
- MLB PA engine shadow only
- No live web research in this sandbox (do not fabricate game logs)
- LR000000 / predictive NONE
