"""Execute only the compact, compiled, non-duplicate operator DAG."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from dcm.signals.contracts import EXECUTABLE_STATES
from dcm.signals.registry import CompiledRegistry


OperatorHandler = Callable[[Mapping[str, Any], Mapping[str, "SignalEvaluation"]], Mapping[str, Any]]


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SignalEvaluation:
    operator_id: str
    version: str
    lifecycle_state: str
    input_hashes: tuple[str, ...]
    dependency_evaluation_hashes: tuple[str, ...]
    outputs: Mapping[str, Any]
    applicability_state: str
    uncertainty_contribution: float
    reason_codes: tuple[str, ...]
    consumers: tuple[str, ...]
    execution_micros: int
    output_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operatorId": self.operator_id,
            "version": self.version,
            "lifecycleState": self.lifecycle_state,
            "inputHashes": list(self.input_hashes),
            "dependencyEvaluationHashes": list(self.dependency_evaluation_hashes),
            "outputs": dict(self.outputs),
            "applicabilityState": self.applicability_state,
            "uncertaintyContribution": self.uncertainty_contribution,
            "reasonCodes": list(self.reason_codes),
            "consumers": list(self.consumers),
            "executionMicros": self.execution_micros,
            "outputHash": self.output_hash,
            "canChangeProbabilityDirectly": False,
            "canOverrideHardGate": False,
        }


class SignalExecutor:
    def __init__(self, registry: CompiledRegistry, handlers: Mapping[str, OperatorHandler]):
        self.registry = registry
        self.handlers = dict(handlers)

    def execute(self, inputs: Mapping[str, Any]) -> tuple[SignalEvaluation, ...]:
        by_id = self.registry.by_id()
        evaluations: dict[str, SignalEvaluation] = {}
        input_hash = _hash(inputs)
        for operator_id in self.registry.execution_order:
            compiled = by_id[operator_id]
            if compiled.lifecycle_state not in EXECUTABLE_STATES:
                continue
            handler = self.handlers.get(operator_id)
            if handler is None:
                raise RuntimeError(f"SIGNAL_HANDLER_MISSING:{operator_id}")
            deps = {key: evaluations[key] for key in compiled.spec.dependencies if key in evaluations}
            started = time.perf_counter_ns()
            output = dict(handler(inputs, deps))
            elapsed = max(0, (time.perf_counter_ns() - started) // 1000)
            dependency_hashes = tuple(evaluations[key].output_hash for key in sorted(deps))
            semantic = {
                "operatorId": operator_id,
                "version": compiled.spec.version,
                "inputHash": input_hash,
                "dependencyHashes": dependency_hashes,
                "outputs": output,
            }
            evaluation = SignalEvaluation(
                operator_id=operator_id,
                version=compiled.spec.version,
                lifecycle_state=compiled.lifecycle_state.value,
                input_hashes=(input_hash,),
                dependency_evaluation_hashes=dependency_hashes,
                outputs=output,
                applicability_state="APPLICABLE",
                uncertainty_contribution=float(output.pop("_uncertaintyContribution", 0.0)),
                reason_codes=tuple(output.pop("_reasonCodes", ())),
                consumers=compiled.spec.consumers,
                execution_micros=int(elapsed),
                output_hash=_hash(semantic),
            )
            evaluations[operator_id] = evaluation
        return tuple(evaluations[key] for key in self.registry.execution_order if key in evaluations)
