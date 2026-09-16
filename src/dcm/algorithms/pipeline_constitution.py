"""Insights/HAR head-to-tail Pipeline Constitution gate.

Registration ≠ execution. A stage that claims ACTIVE without a real consumer
fail-closes with a typed blocker. This module evaluates REQUIRED_CORE algorithm
classes per stage via AlgorithmSelectionEngine and records activated
algorithmIds + consumers for execution receipts / capability manifests.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.algorithms.selection import AlgorithmSelectionEngine
from dcm.algorithms.telemetry import AlgorithmTelemetry, ceremonial_violations
from dcm.contracts.hashes import content_hash
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM

PIPELINE_CONSTITUTION_ID = "INSIGHTS_HAR_PIPELINE_CONSTITUTION_v1"
PIPELINE_CONSTITUTION_SCHEMA = "pillars_dcm.insights_har_pipeline_constitution.v1"

# Stage → (problem_class, required producer/consumer labels)
STAGE_REQUIRED_CORE: dict[str, tuple[str, ...]] = {
    "ACCOUNT_INDEX": ("HOT_HASH_INDEX", "CONTENT_ADDRESS", "HAR_GROUPING"),
    "CHEAP_SCREEN": ("SHRINKAGE", "TOPK_PARTIAL", "FINAL_RANK"),
    "TOP100_SCHEDULE": ("RESEARCH_SCHEDULE", "SET_COVER", "SUBMODULAR"),
    "RESEARCH": ("GRAPH_TRAVERSAL", "HOT_CACHE", "CONTENT_ADDRESS"),
    "TOP25_SELECT": ("FINAL_RANK", "TOPK_PARTIAL", "RESULT_DIVERSITY"),
    "TOP6_PORTFOLIO": ("RESULT_DIVERSITY", "CYCLE_SAFETY", "GRAPH_TRAVERSAL"),
    "ARCHIVE": ("CONTENT_ADDRESS", "MERKLE_INTEGRITY"),
}

STAGE_ORDER = (
    "ACCOUNT_INDEX",
    "CHEAP_SCREEN",
    "TOP100_SCHEDULE",
    "RESEARCH",
    "TOP25_SELECT",
    "TOP6_PORTFOLIO",
    "ARCHIVE",
)

STAGE_CONSUMERS = {
    "ACCOUNT_INDEX": "dcm.ingest.har / BoardIndexes",
    "CHEAP_SCREEN": "dcm.research.insight_queue",
    "TOP100_SCHEDULE": "dcm.research.acquisition",
    "RESEARCH": "dcm.research.source_catalog / evidence ledger",
    "TOP25_SELECT": "dcm.research.insight_queue / insights_offer_snapshots",
    "TOP6_PORTFOLIO": "dcm.chat.slate playables-or-abstain",
    "ARCHIVE": "dcm.chat.archive / content-addressed snapshots",
}


class PipelineConstitutionGate:
    """Evaluate/select REQUIRED_CORE algorithms per Insights/HAR pipeline stage."""

    def __init__(self, *, engine: AlgorithmSelectionEngine | None = None) -> None:
        self.engine = engine or AlgorithmSelectionEngine()
        self.telemetry = AlgorithmTelemetry(engine=self.engine)

    def evaluate_stage(
        self,
        stage: str,
        *,
        context: Mapping[str, Any] | None = None,
        active: bool = True,
        consumer: str | None = None,
    ) -> dict[str, Any]:
        problems = STAGE_REQUIRED_CORE.get(stage) or ()
        consumer_label = consumer or STAGE_CONSUMERS.get(stage) or f"pipeline.{stage}"
        selected: list[dict[str, Any]] = []
        blockers: list[str] = []
        for problem in problems:
            row = self.telemetry.select_and_record(
                problem,
                producer=f"PipelineConstitutionGate.{stage}",
                consumer=consumer_label,
                artifact=PIPELINE_CONSTITUTION_ID,
                context={**(context or {}), "stage": stage, "pipeline": PIPELINE_CONSTITUTION_ID},
            )
            selected.append({
                "problemClass": problem,
                "algorithmId": row.get("algorithm_id"),
                "activated": bool(row.get("activated")),
                "phase": row.get("phase"),
                "downstreamUsed": bool(row.get("downstream_used")),
            })
            if active and row.get("activated") and not row.get("downstream_used"):
                blockers.append(f"ACTIVE_WITHOUT_CONSUMER:{stage}:{row.get('algorithm_id')}")
        if active and not selected:
            blockers.append(f"STAGE_MISSING_REQUIRED_CORE:{stage}")
        status = "ACTIVE" if active and not blockers else ("INACTIVE" if not active else "BLOCKED")
        if blockers and active:
            status = "BLOCKED"
        return {
            "stage": stage,
            "status": status,
            "requiredCoreProblemClasses": list(problems),
            "selected": selected,
            "consumer": consumer_label,
            "blockers": blockers,
        }

    def evaluate_pipeline(
        self,
        *,
        context: Mapping[str, Any] | None = None,
        stages: Mapping[str, bool] | None = None,
    ) -> dict[str, Any]:
        """Evaluate every constitution stage. Fail-closed on ceremonial ACTIVE."""
        stage_flags = {name: True for name in STAGE_ORDER}
        if stages:
            stage_flags.update({str(k): bool(v) for k, v in stages.items()})
        stage_rows = [
            self.evaluate_stage(stage, context=context, active=stage_flags.get(stage, True))
            for stage in STAGE_ORDER
        ]
        snap = self.telemetry.snapshot()
        ceremonial = list(snap.get("ceremonialViolations") or []) + ceremonial_violations(snap.get("executions") or [])
        # Deduplicate ceremonial rows by algorithm/consumer/phase
        seen: set[tuple[Any, ...]] = set()
        unique_ceremonial: list[dict[str, Any]] = []
        for row in ceremonial:
            key = (row.get("algorithm_id"), row.get("consumer"), row.get("phase"), row.get("reason"))
            if key in seen:
                continue
            seen.add(key)
            unique_ceremonial.append(dict(row))
        blockers = []
        for row in stage_rows:
            blockers.extend(row.get("blockers") or [])
        if unique_ceremonial:
            blockers.append("CEREMONIAL_ALGORITHM_EXECUTION")
        valid = not blockers
        body = {
            "schema": PIPELINE_CONSTITUTION_SCHEMA,
            "constitutionId": PIPELINE_CONSTITUTION_ID,
            "law": "registration_is_not_execution; no_consumer_means_not_ACTIVE",
            "stageOrder": list(STAGE_ORDER),
            "stages": stage_rows,
            "activatedAlgorithmIds": sorted((snap.get("activatedCounts") or {}).keys()),
            "telemetry": {
                "activatedAlgorithmCount": snap.get("activatedAlgorithmCount"),
                "rowCount": snap.get("rowCount"),
                "ceremonialViolations": unique_ceremonial,
                "contentHash": snap.get("contentHash"),
            },
            "valid": valid,
            "blockers": blockers,
            "predictiveClaim": PREDICTIVE_CLAIM,
            "learningRevision": LEARNING_REVISION,
            "note": (
                "HAR extract → cheap screen → Top100 schedule → research → "
                "Insights-backed Top25 → Top6 playables-or-abstain → append-only archive."
            ),
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body


def evaluate_insights_har_pipeline(
    *,
    context: Mapping[str, Any] | None = None,
    stages: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Convenience entrypoint used by run-slate / Insights prepare."""
    return PipelineConstitutionGate().evaluate_pipeline(context=context, stages=stages)
