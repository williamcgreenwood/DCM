# ADR-ALG-CONST-001 — Adopt the Permanent Algorithmic Constitution (R0)

- **Status:** Accepted
- **Date:** 2026-09-03
- **Constitution version:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`
- **Supersedes:** none
- **Affects:** HAR intake, Research OS, ranking, release manifests, CI, future DCM versions

## Context

The v3 master prompt made Searching, Indexing, Sorting, Grouping, Graph/Hypergraph, Scheduling, Caching, ML, Calibration, and Uncertainty a permanent inherited architecture law. Before R0 the live DCM had substantial forecasting, EvidenceGraph, StatePack, and P380X signal governance, but no machine-readable algorithm registry, selection engine, HAR AlgorithmExecutionPlan, or CI gate preventing silent algorithm omission.

## Decision

1. Adopt `docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md` as the permanent inherited constitution.
2. Treat `dcm.algorithms.catalog` as the editable source of truth and `configs/algorithm_registry.json` as the committed canonical bytes.
3. Hash the committed registry bytes; do not hard-code a registry hash in source.
4. Treat the v3 prompt-declared constitution SHA-256 `bba7b082…` as lineage only. The committed file SHA-256 is computed from exact repository bytes.
5. Implement ChatGPT-native stdlib CORE algorithms and keep optional packages (HNSW, Leiden, CP-SAT, XGBoost, TabPFN, DiskANN, GNNs) as REQUIRED_CONDITIONAL or PERMANENT_CHALLENGER with deterministic fallbacks.
6. Emit `algorithm_execution_plan.json` from the canonical runner before research. Do not add constitution fields to `forecast_hash_payload` `_CONTEXT_FIELDS`.
7. Require an ADR plus benchmark evidence before any algorithm retirement or silent demotion.
8. Leave BoardGraph / MarketDemandGraph / RequirementGraph / live AcquisitionAction packing as the next Research OS tranche (R1). R0 does not claim them complete.

## Consequences

CI fails if a required algorithm, fallback, test, trace, or release hash disappears. Future DCM versions inherit this constitution unless a newer constitution is adopted under a superseding ADR. LR remains `LR000000`. Predictive claim remains `NONE`. Production root remains closed. Host performance remains uncertified.
