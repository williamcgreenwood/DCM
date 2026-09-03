# CURRENT WORK HANDOFF — R0 ALGORITHMIC CONSTITUTION

- **Timestamp:** 2026-09-03T19:50:00Z
- **Canonical integration branch:** `integration/v6-ml-architecture-20260830`
- **Canonical integration HEAD:** `cdb428f6a05406184fe265b0a1e81abec92cd1f9` (PR #17 CFB guarded launch merged)
- **Active branch:** `grok/r0-algorithmic-constitution-20260903`
- **Target branch:** `integration/v6-ml-architecture-20260830` only. Do not merge to `main`.
- **Constitution version:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`
- **Learning revision:** `LR000000`
- **Predictive claim:** `NONE`
- **Production root:** NOT CERTIFIED
- **Host performance:** uncertified

Do not continue stale Grok branches targeting `main` or superseded ChatGPT branches. Base every new pass on the current integration HEAD.

## COMPLETE NOW — R0

- Permanent constitution document, inheritance receipt, and ADR-ALG-CONST-001.
- Machine-readable algorithm registry generated from `dcm.algorithms.catalog` to `configs/algorithm_registry.json`. Hash is computed from those exact bytes.
- `AlgorithmRequirement.schema.json`, trace matrix, selection engine, HAR AlgorithmExecutionPlan.
- Canonical runner emits `algorithm_execution_plan.json` before research.
- Host doctor/release manifests carry constitution and registry hashes.
- Ranking consumes Timsort + heap Top-K. Research batch consumes set-cover telemetry + heap event ordering.
- Governance tests under `tests/governance/` and CI `export_algorithm_registry.py --check`.
- ChatGPT-native CORE primitives with deterministic fallbacks for HNSW/Leiden/CP-SAT/TabPFN/etc. challengers.
- No second EvidenceGraph, ResearchStore, probability, ranking, SportPlugin, or persistence engine.

R0 does **not** close BoardGraph / MarketDemandGraph / RequirementGraph / live AcquisitionAction packing. Those remain R1.

## NOT COMPLETE

- R1 Universal Adaptive Research OS core (graphs + AcquisitionAction scheduler on live HAR).
- R2 CFB research fan-out completion on a current user HAR.
- Drive-first indexed retrieval replacing folder scans (storage law exists; existing store unchanged).
- Full 24/24 SportPlugin coverage.
- Prospective settlement / LR promotion.
- Production-root certification.
- Predictive superiority.

## NEXT EXACT TRANCHE

**R1 — Universal Adaptive Research OS core**, still on a child of current integration HEAD:

1. Canonical BoardGraph / MarketDemandGraph / RequirementGraph before browsing.
2. Distinct `ResearchRequest` vs `AcquisitionAction` with fan-out bitmaps.
3. Adaptive lazy-greedy / weighted set-cover scheduler as the live batch selector (not telemetry-only).
4. Source health/circuit breaker/co-extraction harvest policy.
5. Per-prop modelable vs playable coverage independent of global completion.
6. Reuse existing ResearchStore / EvidenceGraph / host observation pipeline.
7. Prove on the mixed-sport HAR fixture even if some sports remain unsupported downstream.

Do not start R2 live-CFB HAR research until R1 graphs exist. Do not change `LR000000`.
