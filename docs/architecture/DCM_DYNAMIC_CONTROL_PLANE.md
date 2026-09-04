# DCM dynamic control plane

The control plane is dynamic and graph-driven, but bounded by deterministic
contracts. It is not an uncontrolled self-modifying optimizer.

## State machine

PREPARED → RESEARCHABLE → RESEARCHED → MODELED → RANKED →
FRONTIER_CHECKPOINT or FROZEN → SETTLED.

FRONTIER_CHECKPOINT is not a forecast freeze. It has no frozen forecast hash,
frozen hash sidecar, FrozenForecast ledger record, or settlement eligibility.
A host may import the missing, cutoff-safe evidence and resume from the
checkpoint. Only a terminal Top25 frontier result can enter FROZEN.

## Pre-research gate

Every HAR emits an AlgorithmExecutionPlan before collection. The plan selects
the cheapest appropriate exact, indexed, graph, schedule, cache, and modeling
algorithms and records fallbacks, resource expectations, and audit lineage.
Research cannot begin until identity, scope, requirement, dependency, and
cycle checks validate.

## Lawful pre-freeze feedback

MaterialFact changes invalidate only dependent Features, ParameterSnapshots,
EventWorlds, evaluations, ranks, and portfolio nodes. Line-only changes reuse
worlds. Frontier passes increment only when a downstream semantic hash changes.
The full board remains accounted for while Top100/Top25 are derived views.

## Post-freeze firewall

Settlement reads the immutable frozen forecast and full modeled population.
Results append Settlement, Audit, CalibrationChallenger, and future-only
PatchProposal records. No outcome can enter production calibration or modify
LR000000 without chronological unseen evidence and an explicit promotion gate.
