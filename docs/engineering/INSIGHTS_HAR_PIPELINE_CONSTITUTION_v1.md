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
- Insights HARs with line+side *are* the current platform capture; do not
  require a second board HAR
- `CURRENT_OFFER_MISSING` is informational only when Insights line+side is
  also absent; it is never a required operator ask
- Optional board HAR must not block Top100/Top25 or autonomous closure

## HAR-only autonomous closure

`run-slate --autonomous` (default on) advances typed phases without human
prompts for another HAR:

1. cutoff-from-capture (HAR capture time is the decision context)
2. host research scheduling + evidence-import path
3. coverage↑ when observations are available
4. settle the whole Insights/modeled population when events are FINAL and
   outcomes can be fetched/joined; else schedule deferred `insight_settle`
5. append future-only training examples when settlement exists
6. train/calibrate only if labels are sufficient; else leave `LR000000`
7. Playables 0–6 only after gates; Insights-backed Top25 still fills
