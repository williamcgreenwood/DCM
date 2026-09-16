# Engineering contract: INSIGHTS_HAR_PIPELINE_CONSTITUTION_v1

Runtime module: `dcm.algorithms.pipeline_constitution`  
ADR: `docs/architecture/ADR-INSIGHTS_HAR_PIPELINE_CONSTITUTION_v1.md`

## REQUIRED_CORE per stage

See ADR stage map. Consumers must be real module paths / artifact writers.

## Fail-closed blockers

- `ACTIVE_WITHOUT_CONSUMER:<stage>:<algorithmId>`
- `STAGE_MISSING_REQUIRED_CORE:<stage>`
- `CEREMONIAL_ALGORITHM_EXECUTION`

## Insights offer-equivalent

- Line + HIGHER/LOWER → `INSIGHTS_OFFER_BACKED` / `RESEARCH_CANDIDATE`
- Missing side → fail-closed (no invented opposite side)
- Board offers unchanged; playables may remain 0
