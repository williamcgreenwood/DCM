# ADR: INSIGHTS_HAR_PIPELINE_CONSTITUTION_v1

**Status:** Accepted  
**Date:** 2026-09-16  
**Constitution inheritance:** MANDATORY / CI-GATED  
**Related:** `docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md`, `docs/engineering/ALGORITHM_CONSUMPTION_LAW.md`

## Context

Insights-only HAR captures (`boardOfferCount=0`) still require a durable
head-to-tail algorithmic path:

HAR extract → full-universe cheap analysis → Top100 research priority → host
research → Insights-backed Top25 → Top6 Playables-or-abstain → append-only archive.

Registration of algorithms in `configs/algorithm_registry.json` is not
execution. A stage that claims ACTIVE without a real consumer is illegal.

## Decision

1. Adopt pipeline constitution id `INSIGHTS_HAR_PIPELINE_CONSTITUTION_v1`.
2. Runtime `PipelineConstitutionGate` (`dcm.algorithms.pipeline_constitution`)
   evaluates REQUIRED_CORE problem classes per stage via
   `AlgorithmSelectionEngine`, records activated algorithmIds + consumers, and
   fail-closes with typed blockers when ACTIVE lacks a consumer.
3. Insights claims with exact line + HIGHER/LOWER are `INSIGHTS_OFFER_BACKED`
   research candidates (`InsightsOfferSnapshot`). Missing side fail-closes.
   BoardOffer gates remain intact for real board captures. Playables may still
   be 0 without a production model; Insights Top25 must still populate.
4. Acquisition/source catalog routing is sport-correct (MLB→baseball, NFL→football,
   NCAAFB/CFB→gridiron, WNBA→basketball, SOCCER→soccer). `CFB_WEATHER` is never
   primary for non-CFB subjects.

## Stage map (REQUIRED_CORE problem classes)

| Stage | REQUIRED_CORE classes |
|---|---|
| ACCOUNT_INDEX | HOT_HASH_INDEX, CONTENT_ADDRESS, HAR_GROUPING |
| CHEAP_SCREEN | SHRINKAGE (Wilson/BetaBin; never p=hitRate), TOPK_PARTIAL, FINAL_RANK |
| TOP100_SCHEDULE | RESEARCH_SCHEDULE (CELF), SET_COVER, SUBMODULAR |
| RESEARCH | GRAPH_TRAVERSAL, HOT_CACHE, CONTENT_ADDRESS |
| TOP25_SELECT | FINAL_RANK, TOPK_PARTIAL, RESULT_DIVERSITY |
| TOP6_PORTFOLIO | RESULT_DIVERSITY, CYCLE_SAFETY, GRAPH_TRAVERSAL (allow 0; no padding) |
| ARCHIVE | CONTENT_ADDRESS, MERKLE_INTEGRITY |

## Law

**registration ≠ execution; no consumer = not ACTIVE.**

## Consequences

- `run_slate` / Insights prepare invoke the gate and persist the receipt in
  `execution_receipt` / `capability_manifest` surfaces.
- Predictive claim remains `NONE`; learning revision remains `LR000000`.
- Supersession requires a later ADR + benchmarks.
