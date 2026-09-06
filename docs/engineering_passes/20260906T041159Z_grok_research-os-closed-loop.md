# Engineering pass — Research OS closed loop (grouped CFB)

- **Timestamp:** `2026-09-06T04:11:59Z`
- **Agent:** grok
- **Branch:** `task/research-os-closed-loop-20260906`
- **Base main:** `3ab948a3abd84e51387715b9f5e2921827d7ba94` (PR #36 requirement ledger)

## Intent

Finish one mergeable Research OS closed-loop slice on the live CFB path:
ResearchRequirement separate from AcquisitionAction; graphs persist; CELF/set-cover is the live selector with `downstream_used` telemetry; host observation import advances coverage and shrinks the next batch.

## Already existed (hardened, not rewritten)

- `BoardGraph` / `MarketDemandGraph` / `RequirementGraph` in `dcm.research.os_graphs` + `persist_research_os_graphs`
- `build_acquisition_actions` + `schedule_acquisition_actions` (CELF `ALG-SCHED-001`, weighted set-cover, batch pack)
- Exact-first cache cascade + evidence lookup before acquisition in `prepare_cfb_research_os`
- Source-aware `execute_source_aware_observations`: HostObservation → typed validation → EvidenceClaim → ParameterSnapshot / DAG invalidation → coverage
- Empty field coverage rejected (`EMPTY_FIELD_COVERAGE`)
- Fan-out only after semantic validation moves coverage

## Newly wired this pass

1. **`AcquisitionActionGraph`** (`build_acquisition_action_graph`) — persistable action→requirement/offer incidence with CELF/set-cover selection mirrored; written as `acquisition_action_graph.json` from `prepare_cfb_research_os` and after import.
2. **Closed-loop reschedule** inside `execute_source_aware_observations`:
   - `resolve_material_facts` → `material_facts.json` / features
   - rebuild AcquisitionActions under updated coverage
   - CELF schedule + AcquisitionActionGraph + `host_research_batch.json`
   - `closed_loop_algorithm_telemetry.json` with `ALG-SCHED-001` `downstream_used=True`
   - result fields: `actionCountBefore/After`, `unresolvedBefore/After`, `nextBatchShrunk`, `celfDownstreamUsed`
3. **Import-cycle hardening:** lazy `dcm.chat` exports + lazy observation_execute import from `evidence_import` (pre-existing cycle broken for direct imports).
4. **Tests:** `test_closed_loop_observation_reschedules_and_shrinks_next_batch`; graph assertions on Research OS prepare path.

## Not claimed

- Current live CFB HAR operational card / PLAYABLEs
- Live adapter fetch beyond fixtures (EXTERNAL / PARTIAL)
- LR promotion, predictive superiority, production-root certification
- Mixed-sport R1 completion
- EventWorld / C++ / src layout rewrites

## EXTERNAL blockers remaining for operational CFB card

- `REQ-EVID-011.02` / `REQ-FRZ-023.02` / `REQ-FINAL-042.01` — current HAR + host-acquired evidence
- `REQ-ADAPT-010.01` — live adapter fetch / licensed providers
- `REQ-SIDE-005.01` — unresolved sides on live boards
- `REQ-LEARN-026.01` / `REQ-UNC-019.01` — prospective settlements / calibration

## Validation

- Focused: `tests/test_cfb_source_aware_import.py`, Research OS graph asserts, incremental freeze-gate reuse
- Inventory regenerated via `scripts/build_code_inventory.py --write`
