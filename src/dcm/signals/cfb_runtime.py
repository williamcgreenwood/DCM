"""Canonical CFB signal registry and runtime consumers.

Signals are feature/diagnostic operators only.  They can expose support and
uncertainty context to the feature store and audit graph; they cannot rewrite
probabilities or bypass status/evidence gates.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.contracts.hashes import content_hash
from dcm.ml.feature_store import signal_evaluation_feature_records
from dcm.signals.compiler import SignalCompiler
from dcm.signals.contracts import LifecycleState, SignalField, SignalOperatorSpec, SignalStage
from dcm.signals.executor import SignalEvaluation, SignalExecutor
from dcm.signals.registry import CompiledRegistry, SignalRegistry


CFB_SIGNAL_OPERATOR = "CFB_SUPPORT_CONTEXT_V1"


def build_cfb_signal_registry() -> CompiledRegistry:
    registry = SignalRegistry()
    registry.register(SignalOperatorSpec(
        operator_id=CFB_SIGNAL_OPERATOR,
        version="1.0.0",
        stage=SignalStage.FEATURE,
        family="CFB_SUPPORT_CONTEXT",
        sports=("gridiron",),
        competitions=("CFB",),
        outputs=(
            SignalField("modelSupportState", "categorical", "evidence"),
            SignalField("opportunitySupportN", "count", "opportunity"),
            SignalField("efficiencySupportN", "count", "efficiency"),
            SignalField("holdPlayable", "boolean", "eligibility"),
            SignalField("dataQuality", "ratio", "evidence"),
            SignalField("oodRisk", "ratio", "uncertainty"),
        ),
        transformation_id="dcm.signals.cfb_support_context.v1",
        lifecycle_state=LifecycleState.ACTIVE_FEATURE,
        consumers=(
            "dcm.ml.feature_store.signal_evaluation_feature_records",
            "dcm.audit.trace.signal_evaluations",
        ),
        tests=("test_cfb_signal_runtime_executes_and_consumes",),
        behavior_class="FEATURE_TRANSFORM",
        source_ref="dcm/signals/cfb_runtime.py",
        doctrine_hash=content_hash({"rule": "signals_do_not_change_probability_or_hard_gates"}),
        audit_tags=("CFB", "SUPPORT", "UNCERTAINTY", "NO_PROBABILITY_OVERRIDE"),
    ))
    return SignalCompiler().compile(registry.candidates())


def _support_context(inputs: Mapping[str, Any], _deps: Mapping[str, SignalEvaluation]) -> Mapping[str, Any]:
    snapshot = inputs.get("snapshot") if isinstance(inputs.get("snapshot"), Mapping) else {}
    support = snapshot.get("model_support") if isinstance(snapshot.get("model_support"), Mapping) else {}
    opportunity = snapshot.get("opportunity") if isinstance(snapshot.get("opportunity"), Mapping) else {}
    efficiency = snapshot.get("efficiency") if isinstance(snapshot.get("efficiency"), Mapping) else {}
    blockers = list(support.get("modelBlockers") or [])
    hold = bool(snapshot.get("blocker")) or bool(blockers) or not bool(snapshot.get("minimum_model_support", True))
    quality = float(snapshot.get("data_quality") or 0.0)
    ood = float(snapshot.get("ood_risk") or 1.0)
    return {
        "modelSupportState": "HELD" if hold else "SUPPORTED",
        "opportunitySupportN": int(opportunity.get("support_n") or 0),
        "efficiencySupportN": int(efficiency.get("support_n") or 0),
        "holdPlayable": hold,
        "dataQuality": quality,
        "oodRisk": ood,
        "_uncertaintyContribution": min(1.0, max(0.0, ood + (0.25 if hold else 0.0))),
        "_reasonCodes": tuple(sorted(str(item) for item in blockers)),
    }


def execute_cfb_signals(
    row: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    material_facts: Mapping[str, Any] | None,
    *,
    cutoff: str,
    registry: CompiledRegistry | None = None,
) -> tuple[CompiledRegistry, tuple[SignalEvaluation, ...], list[dict[str, Any]]]:
    registry = registry or build_cfb_signal_registry()
    executor = SignalExecutor(registry, {CFB_SIGNAL_OPERATOR: _support_context})
    evaluations = executor.execute({
        "row": dict(row),
        "snapshot": dict(snapshot),
        "materialFactsHash": str((material_facts or {}).get("contentHash") or ""),
        "cutoff": str(cutoff),
    })
    entity = str(row.get("playerId") or row.get("playerName") or "")
    event_id = str(row.get("eventId") or "")
    records = signal_evaluation_feature_records(
        list(evaluations),
        entity=entity,
        event_id=event_id,
        as_of=cutoff,
        source_hashes=tuple(
            str(value) for value in (snapshot.get("evidence_hashes") or []) if value
        ),
    )
    return registry, evaluations, records


__all__ = ["CFB_SIGNAL_OPERATOR", "build_cfb_signal_registry", "execute_cfb_signals"]
