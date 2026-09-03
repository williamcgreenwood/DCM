# Engineering pass — P7 host-native CLI, universal scopes, persistent research

- Agent: Grok
- Date: 2026-08-31
- Starting integration branch: `integration/v6-ml-architecture-20260830`
- Exact starting SHA: `4d887690c1f08c09630b9e5635a655c6fa1566df`
- Child branch: `grok/p7-host-native-persistent-research-20260831`
- Pull request: opened against the integration line after this commit
- Ending SHA: see Git history for this record's commit

## Objective

Implement the ChatGPT-native host interface over the existing Python runner (no second engine), migrate canonical research/provider semantics from PLAYER/TEAM to Subject/Affiliation/Counterparty/Event/Environment, add universal packet wrappers, a versioned source catalog, event-first research batching, simple host-observation import, a content-addressed research store with delta classification, and the first committed AST code inventory with CI `--check`.

## Files added or changed

Added:

- `artifacts/dcm_v6_workstream_ab/dcm/chat/` (`__init__.py`, `__main__.py`, `cli.py`, `session.py`, `contracts.py`, `state.py`, `research_bridge.py`, `evidence_import.py`, `report.py`, `archive.py`)
- `artifacts/dcm_v6_workstream_ab/dcm/research/scopes.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/source_catalog.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/research_store.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/batch.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/universal_packets.py`
- `artifacts/dcm_v6_workstream_ab/dcm/data/source_catalog.json`
- `artifacts/dcm_v6_workstream_ab/tests/test_host_native.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_universal_scopes.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_research_store.py`
- `artifacts/dcm_v6_workstream_ab/tests/test_source_catalog.py`
- `docs/generated/CODE_INVENTORY.json`
- `docs/generated/CODE_INVENTORY.md`
- this pass record

Changed:

- `artifacts/dcm_v6_workstream_ab/dcm/research/requests.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/provider.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/coverage.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/host_plan.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/entity_packets.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/player_packet.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/population.py`
- `artifacts/dcm_v6_workstream_ab/dcm/research/emit.py`
- `artifacts/dcm_v6_workstream_ab/dcm/model/parameters.py`
- `artifacts/dcm_v6_workstream_ab/dcm/ml/feature_store.py`
- `artifacts/dcm_v6_workstream_ab/dcm/runtime/github_archive.py`
- `pyproject.toml`
- `.github/workflows/dcm-v6-ci.yml`
- `scripts/build_code_inventory.py`
- `docs/PROGRAM_STATUS.md`
- `docs/PROGRAM_STATUS.json`
- `docs/UNIVERSAL_IMPLEMENTATION_MATRIX_20260831.md`
- `docs/generated/README.md`
- tests: `test_research_efficiency.py`, `test_entity_packets.py`, `test_bundle_e2e_resume.py`

## Modules/classes/functions added or behaviorally changed

- `dcm.chat.HostSession` — prepare / next_research_batch / import_evidence / coverage / forecast / report / resume / audit / archive / settle wrapping `run_dcm` and existing settle/archive
- `dcm.chat.cli.main` — `dcm-host` and `python -m dcm.chat`
- `dcm.chat.doctor`
- `dcm.research.scopes` — canonical scopes + PLAYER/TEAM lookup aliases
- `dcm.research.requests.plan_research` — emits universal scopes only
- `dcm.research.provider.FixtureProvider.resolve` — SUBJECT/AFFILIATION/COUNTERPARTY/ENVIRONMENT/COMPETITION + PLAYER/TEAM aliases
- `dcm.research.coverage.evaluate_request` — universal scopes + SportResearchSchema extras
- `dcm.research.batch.build_next_research_batch` — event-first scheduler
- `dcm.research.research_store.ResearchStore` / `classify_delta`
- `dcm.research.source_catalog.load_source_catalog` / `sources_for`
- `dcm.research.universal_packets.build_universal_packets`
- `dcm.chat.evidence_import.observation_to_claim` / `import_observations`
- `dcm.model.parameters.build_parameter_snapshot` — alias lookups + `layers`
- `dcm.ml.feature_store.FEATURE_FAMILIES` — universal families

## Algorithms/contracts implemented

Scheduler score (runtime, not just spec):

`fanout × information_importance × freshness_need × uncertainty_reduction / estimated_acquisition_cost`

Delta classes: REUSE_VALID, REFRESH_STALE, APPEND_MISSING_HISTORY, REFRESH_CURRENT_CONTEXT, NEW_OPPONENT_REQUIRED, ROLE_EPOCH_CHANGED, TEAM_CHANGED, DEFINITION_CHANGED, CONTRADICTED_REVERIFY, REPLACE_INVALIDATED, NEW_ENTITY_FULL_RESEARCH, RESEARCH_NEW, NOT_APPLICABLE.

Host observations are simple source/entity/data records. DCM computes source_hash, claim_hash, reliability, freshness. Host-supplied hashes are ignored.

## Tests added/modified

Added: `test_host_native.py`, `test_universal_scopes.py`, `test_research_store.py`, `test_source_catalog.py`.

Modified: research-efficiency canonical scopes, opponent fan-out as COUNTERPARTY, bundle resume frozen-claim scopes.

## Validation

```
python3 -m compileall -q artifacts/dcm_v6_workstream_ab/dcm artifacts/dcm_v6_workstream_ab/tests
PYTHONPATH=artifacts/dcm_v6_workstream_ab DCM_FAST_WORLDS=64 DCM_SERIOUS_WORLDS=128 pytest -q
python3 -m dcm.chat doctor
python3 -m dcm.chat --help
python3 scripts/build_code_inventory.py --write
python3 scripts/build_code_inventory.py --check
```

Result: compileall clean; full pytest suite green (100%); `python -m dcm.chat doctor` returns LR000000 / predictive NONE / hostComputesProbabilities false; inventory 208 modules / 1282 symbols / 0 parse errors.

No host-performance certification is inferred.

## Workstream status changes

| ID | Before | After | Why |
|---|---:|---:|---|
| P1 | 7 | 8 | Canonical planner/provider/packets/catalog/import executable |
| P2 | 7 | 8 | Universal feature families + ParameterSnapshot layers |
| P5 | 7 | 8 | `dcm.chat` / `dcm-host` runtime exists |
| P7 | 2 | 7 | Host command family implemented and tested over the runner |
| P8 | 4 | 6 | Source catalog + event-first batches + schema extras |
| P9 | 8 | 9 | Planner no longer emits PLAYER/TEAM |
| P12 | 3 | 6 | Content-addressed store + delta classes |
| P13 | 5 | 6 | Scheduler formula is runtime-wired |
| P14 | 4 | 5 | doctor / run_manifest / host_state |

Not 10/10 anywhere newly claimed. Fresh-wheel ChatGPT HAR acceptance, live fetch, full 24/24 sport plugins, and chronological predictive promotion remain open.

## Requirements completed in this pass

- AST code inventory snapshot generated and CI `--check` enabled
- `dcm-host` / `python -m dcm.chat` / `HostSession`
- Canonical request/provider scopes migrated to universal entities
- Universal research packet containers + compatibility projections
- Versioned SourceCatalog
- Event-first iterative research batching
- Simple host-observation evidence import (engine hashes)
- SportResearchSchema consulted for universal coverage extras
- FeatureStore families universalized
- ParameterSnapshot layered containers
- Persistent content-addressed research store + delta classification

## Requirements still partial or missing

### CODE

- Fresh-host wheel+HAR acceptance is not an end-to-end CI test
- PLAYER/TEAM remain lookup aliases in packets/parameters/coverage
- EvidenceGraph Feature→State→Parameter→Simulation→Selection→Settlement lineage still incomplete
- No sport is 24/24 production-complete
- Pass B / quarter-state / MLB SHADOW unchanged
- Live `DCM_LIVE_FETCH` remains opt-in

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

Introduced/kept:

- PLAYER ↔ SUBJECT and TEAM ↔ AFFILIATION/COUNTERPARTY claim lookup aliases
- `entity_graph.teams` / `entity_graph.players` projections from affiliations/subjects
- player/team/opponent packet files remain compatibility artifacts

Retired as canonical:

- `plan_research` PLAYER/TEAM request emission

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
3. Populate EvidenceGraph Feature→State→ParameterSnapshot→Simulation→Evaluation→Selection→Settlement→Learning lineage.
4. Close PARTIAL SportPlugin 24-component bindings sport-by-sport.
5. High-volume research store (queryable artifact/DB) referenced by hashes.
6. Measured CPU/RSS/token benchmarks before any host-performance claim.
7. Chronological unseen settlements before any LR/predictive promotion.
