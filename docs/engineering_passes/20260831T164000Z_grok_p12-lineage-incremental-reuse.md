# Engineering pass — EvidenceGraph runtime lineage, incremental research reuse, ParticipationModel

- Agent: Grok
- Date: 2026-08-31
- Starting integration branch: `integration/v6-ml-architecture-20260830`
- Exact starting SHA: `4d887690c1f08c09630b9e5635a655c6fa1566df`
- Child branch: `grok/p7-host-native-persistent-research-20260831`
- Prior pass on this child: `docs/engineering_passes/20260831T162745Z_grok_p7-host-native-persistent-research.md` (not rewritten)
- Pull request: opened against the integration line after this commit
- Ending SHA: see Git history for this record's commit

## Objective

Populate EvidenceGraph Feature→State→Parameter→Simulation→Selection at freeze (Settlement as an append-only sidecar), make persistent research reuse actually hydrate stored blobs instead of pointer stubs, append missing game logs without replacing history, keep HIT/MISS out of research-delta decisions, and extract a real ParticipationModel consumed by opportunity.

## Files added or changed

Added:

- `artifacts/dcm_v6_workstream_ab/dcm/model/participation.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_runtime_lineage.py`
- this pass record

Changed:

- `artifacts/dcm_v6_workstream_ab/dcm/research/evidence_graph.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/research_store.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/__init__.py`
- `artifacts/dcm_v6_workstream_ab/dcm/runtime/dag.py`
- `artifacts/dcm_v6_workstream_ab/dcm/chat/research_bridge.py`
- `artifacts/dcm_v6_workstream_ab/dcm/chat/evidence_import.py`
- `artifacts/dcm_v6_workstream_ab/dcm/chat/session.py`
- `artifacts/dcm_v6_workstream_ab/dcm/runner.py`
- `artifacts/dcm_v6_workstream_ab/dcm/learning/postgame.py`
- `artifacts/dcm_v6_workstream_ab/dcm/ml/feature_store.py`
- `artifacts/dcm_v6_workstream_ab/dcm/model/parameters.py`
- `artifacts/dcm_v6_workstream_ab/dcm/model/basketball_opportunity.py`
- `artifacts/dcm_v6_workstream_ab/dcm/model/gridiron_models.py`
- `artifacts/dcm_v6_workstream_ab/dcm/sports/common/contract.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_research_store.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_sport_plugin_full_contract.py`
- `docs/PROGRAM_STATUS.md`
- `docs/PROGRAM_STATUS.json`
- `docs/UNIVERSAL_IMPLEMENTATION_MATRIX_20260831.md`

## Modules/classes/functions added or behaviorally changed

- `dcm.model.participation.ParticipationModel` — minutes/snaps independent of opportunity/efficiency
- `dcm.research.evidence_graph.attach_runtime_lineage` / `trace_runtime_lineage`
- `dcm.research.research_store.prior_fields` — classify from blob, not pointer
- `game_identity` / `merge_game_logs` / `history_gap` / `hydrate_reused_claims` / `put_outcome` / `put_game_logs`
- `Dag.invalidate_for_delta` — line changes never invalidate SUBJECT_HISTORY
- Host `next_research_batch` hydrates REUSE_VALID claims into `evidence_bundle.jsonl`
- Runner attaches runtime lineage before freeze hash
- `settle_run` writes `settlement_lineage.json` and outcome memory; does not rewrite frozen forecast

## Algorithms/contracts implemented

- Persistent evidence = prior + new since last update + current event context + current market. History is append-only; first game identity wins.
- `classify_requests` loads stored claim freshness, affiliation, opponent, role epoch, definition, history count from the blob.
- Outcome HIT/MISS is stored separately and is not an input to `classify_delta`.
- Participation is fit before opportunity. Opportunity consumes participation when supplied.

## Tests added/modified

Added: `test_runtime_lineage.py`.

Extended: `test_research_store.py` (blob hydration, history gap, game-log append, outcome isolation, indexes), `test_sport_plugin_full_contract.py` (ParticipationModel no longer PARTIAL).

## Validation

```
python3 -m compileall -q artifacts/dcm_v6_workstream_ab/dcm artifacts/dcm_v6_workstream_ab/tests
PYTHONPATH=artifacts/dcm_v6_workstream_ab DCM_FAST_WORLDS=64 DCM_SERIOUS_WORLDS=128 pytest -q
python3 -m dcm.chat doctor
python3 scripts/build_code_inventory.py --write
python3 scripts/build_code_inventory.py --check
```

Result: compileall clean; full pytest suite green (100%); doctor LR000000 / predictive NONE / hostComputesProbabilities false / hostPerformanceCertified false.

## Workstream status changes

| ID | Before this pass | After | Why |
|---|---:|---:|---|
| P2 | 8 | 9 | Separate ParticipationModel wired into basketball/gridiron snapshots |
| P12 | 6 | 7 | Blob hydration, indexes, append-only logs, outcome isolation, DAG invalidation |

P3 stays 6: Participation binding closed for basketball/gridiron, but FeatureSchema/Environment/ValidationSuite remain PARTIAL and `productionCompleteSports=[]`.
P5 stays 8: runtime lineage exists; fresh-wheel HAR acceptance does not.
P7 stays 7.

Not 10/10 anywhere newly claimed.

## Requirements completed in this pass

- EvidenceGraph runtime Feature/Role/Participation/Opportunity/Efficiency/Parameter/Simulation/PropEvaluation/Selection/Forecast population at freeze
- Settlement/LearningObservation sidecar that cannot rewrite freeze bytes
- ResearchStore classifies from stored blobs, not latest-pointer stubs
- Incremental game-log identity + append-only merge
- Entity/source/as-of indexes
- Hydrate REUSE_VALID claims into the run bundle before forecast
- Outcome memory that cannot decide research reuse
- DAG invalidation by delta class; line changes preserve subject history
- ParticipationModel extracted and import-validated as IMPLEMENTED for basketball/gridiron

## Requirements still partial or missing

### CODE

- Fresh-host wheel+HAR acceptance is not an end-to-end CI test
- PLAYER/TEAM remain lookup aliases in packets/parameters/coverage
- No sport is 24/24 production-complete (FeatureSchema, EnvironmentModel, ValidationSuite, basketball MarketDefinitionRegistry still PARTIAL)
- Pass B / quarter-state / MLB SHADOW unchanged
- Live `DCM_LIVE_FETCH` remains opt-in
- High-volume queryable research DB/object store still future

### ENVIRONMENT

- ChatGPT still needs an explicit exact wheel mount; GitHub read ≠ importability

### DATA / EXTERNAL

- Authenticated/paid sources remain optional; secrets stay out of Git

### VALIDATION

- Chronological unseen settlements remain insufficient for LR/predictive promotion

### GOVERNANCE

- Production root remains closed
- This child PR targets integration only; do not merge integration to main

## Compatibility shims introduced or retired

Kept: PLAYER/TEAM claim lookup aliases, entity_graph teams/players projections, player/team/opponent packet files.

No new predictive/LR claim.

## Root-of-trust / LR / predictive / performance claims

Unchanged:

- Learning Revision: `LR000000`
- Predictive claim: `NONE`
- Production root: CLOSED / not certified
- Host performance: not certified
- V1 hash `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22` not rewritten

## Ordered next pass

1. Exact-wheel fresh-ChatGPT HAR acceptance through `dcm-host` with no source checkout.
2. Retire remaining PLAYER/TEAM lookup aliases so they exist only inside source/sport adapters.
3. Close remaining PARTIAL SportPlugin 24-component bindings sport-by-sport.
4. High-volume research store (queryable artifact/DB) referenced by hashes.
5. Measured CPU/RSS/token benchmarks before any host-performance claim.
6. Chronological unseen settlements before any LR/predictive promotion.
