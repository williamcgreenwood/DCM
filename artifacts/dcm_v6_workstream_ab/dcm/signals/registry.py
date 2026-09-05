"""Candidate and compiled signal registries with explicit lifecycle state."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from dcm.signals.contracts import LifecycleState, SignalOperatorSpec


@dataclass(frozen=True)
class CompiledOperator:
    spec: SignalOperatorSpec
    lifecycle_state: LifecycleState
    semantic_signature: str
    overlap_group: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "spec": self.spec.to_dict(),
            "compiledLifecycleState": self.lifecycle_state.value,
            "semanticSignature": self.semantic_signature,
            "overlapGroup": self.overlap_group,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class CompiledRegistry:
    operators: tuple[CompiledOperator, ...]
    execution_order: tuple[str, ...]
    registry_hash: str

    def by_id(self) -> dict[str, CompiledOperator]:
        return {item.spec.operator_id: item for item in self.operators}

    def counts(self) -> dict[str, int]:
        counts = {state.value: 0 for state in LifecycleState}
        for item in self.operators:
            counts[item.lifecycle_state.value] += 1
        counts["CANDIDATE_TOTAL"] = len(self.operators)
        counts["EXECUTION_TOTAL"] = len(self.execution_order)
        counts["OVERLAP_GROUPS"] = len({v.overlap_group for v in self.operators if v.overlap_group})
        return counts

    @classmethod
    def build(cls, operators: Iterable[CompiledOperator], execution_order: Iterable[str]) -> "CompiledRegistry":
        ordered = tuple(sorted(operators, key=lambda item: item.spec.operator_id))
        order = tuple(execution_order)
        payload = {
            "schema": "pillars_dcm.compiled_signal_registry.v1",
            "operators": [item.to_dict() for item in ordered],
            "executionOrder": list(order),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        return cls(ordered, order, hashlib.sha256(raw).hexdigest())


class SignalRegistry:
    def __init__(self) -> None:
        self._items: dict[str, SignalOperatorSpec] = {}

    def register(self, spec: SignalOperatorSpec) -> None:
        if spec.operator_id in self._items:
            raise ValueError(f"SIGNAL_OPERATOR_ID_DUPLICATE:{spec.operator_id}")
        self._items[spec.operator_id] = spec

    def extend(self, specs: Iterable[SignalOperatorSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def candidates(self) -> tuple[SignalOperatorSpec, ...]:
        return tuple(self._items[key] for key in sorted(self._items))
