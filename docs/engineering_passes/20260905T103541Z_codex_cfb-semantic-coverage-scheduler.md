# Engineering Pass: CFB semantic coverage scheduler

- **Pass ID:** `20260905T103541Z_codex_cfb-semantic-coverage-scheduler`
- **Starting branch/SHA:** `main` @ `3267c6312dbac0844203b48abf81e1733025b7c0`
- **Ending branch:** `codex/cfb-coverage-complete-scheduler-20260905` (commit pending)
- **Objective:** prevent a newly imported, semantically complete current-run CFB research request from being acquired again before cross-run cache hydration.

## Reproduction and implementation

Using the quarantined current CFB HAR on a wheel built from this branch, a valid
official event observation changed the coverage record to `complete=true`, but
the next host batch still selected the same request because the batch scheduler
also required the separate cache classifier to report `REUSE_VALID`.

`build_next_research_batch` now treats `coverage.complete` as the authoritative
semantic completion signal. `REUSE_VALID` remains an independent cache-reuse
route. The producer is `dcm.research.batch.build_next_research_batch`; the
runtime consumer is `dcm.chat.research_bridge.next_research_batch` through
`dcm-host next-research`.

## Files and contracts changed

- `artifacts/dcm_v6_workstream_ab/dcm/research/batch.py`: corrected completion
  predicate; no algorithm, formula, market, or compatibility shim added.
- `artifacts/dcm_v6_workstream_ab/tests/test_research_store.py`: regression for
  a coverage-complete request without cache reuse classification.
- Program status and finish-line ledger: recorded the partial current-HAR
  readback and remaining gates.

## Validation

- `PYTHONPATH=artifacts/dcm_v6_workstream_ab /tmp/dcm_public_cfb_venv/bin/pytest -q artifacts/dcm_v6_workstream_ab/tests/test_research_store.py artifacts/dcm_v6_workstream_ab/tests/test_host_native.py artifacts/dcm_v6_workstream_ab/tests/test_cfb_research_os.py` — **24 passed**.
- `python -m compileall -q artifacts/dcm_v6_workstream_ab/dcm artifacts/dcm_v6_workstream_ab/tests` — **PASS**.
- Fresh wheel, quarantined HAR, cutoff `2026-09-05T12:00:00Z`: one official
  observation imported (`imported=1`, `rejected=0`); unresolved requests moved
  from `552` to `551`; the completed event was absent from the subsequent batch.
- `python scripts/build_code_inventory.py && python scripts/build_code_inventory.py --check` — **PASS**; generated inventory was refreshed through the repository generator.
- Exact-head repository CI is pending PR creation.

## Honest completion state

This closes one scheduler defect and proves a current-HAR producer/consumer
transition. It does not complete the other 551 research requests, create a
final forecast/freeze, produce Top100/Top25, certify a production root or host
performance, or change `LR000000` / predictive claim `NONE`.

## Blockers and next tasks

1. **VALIDATION:** regenerate and verify the official code inventory, then
   complete exact-head PR checks and merge only when required checks/review pass.
2. **EXTERNAL/DATA:** acquire and import permitted temporal evidence for the
   remaining current-HAR requests.
3. **CODE + VALIDATION:** re-run coverage and forecast; publish Top100/Top25
   only from a final, evidence-complete (or truthfully gated) run.
4. **EXTERNAL:** settle frozen forecasts chronologically before calibration,
   learning, or predictive claims.
