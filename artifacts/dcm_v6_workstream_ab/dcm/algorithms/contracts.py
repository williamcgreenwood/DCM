"""Immutable algorithm contracts used by the constitution registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


ALGORITHM_SELECTED = "ALGORITHM_SELECTED"

LIFECYCLES = frozenset(
    {"REQUIRED_CORE", "REQUIRED_CONDITIONAL", "PERMANENT_CHALLENGER"}
)
FAMILIES = frozenset(
    {
        "SEARCH",
        "INDEX",
        "SORT",
        "GROUP",
        "GRAPH",
        "SCHED",
        "CACHE",
        "ML_TABULAR",
        "ML_TIME",
        "ML_CAUSAL",
        "ML_PROB",
        "CAL",
        "UNCERTAINTY",
        "FM",
    }
)


class AlgorithmNotProductionActive(RuntimeError):
    """Raised when a permanent challenger is invoked as a production algorithm."""


def _tuple_of(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


@dataclass(frozen=True)
class AlgorithmRecord:
    algorithm_id: str
    canonical_name: str
    algorithm_family: str
    lifecycle: str
    applicability_contract: str
    input_contract: str
    output_contract: str
    semantic_scope: str
    implementation_module: str
    implementation_symbol: str
    runtime_producer: str
    runtime_consumer: str
    fallback_algorithm_id: str | None = None
    dependency_requirements: tuple[str, ...] = ()
    determinism_class: str = "DETERMINISTIC"
    time_complexity_expectation: str = "O(n)"
    memory_complexity_expectation: str = "O(n)"
    token_cost_expectation: str = "NONE"
    storage_cost_expectation: str = "LOW"
    portability_class: str = "STDLIB"
    benchmark_ids: tuple[str, ...] = ()
    test_ids: tuple[str, ...] = ()
    audit_event_types: tuple[str, ...] = (ALGORITHM_SELECTED,)
    requirement_trace_ids: tuple[str, ...] = ()
    introduced_version: str = "DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903"
    superseding_adr: str | None = None
    retired_version: str | None = None
    registry_record_hash: str = ""

    def __post_init__(self) -> None:
        if not self.algorithm_id.strip():
            raise ValueError("ALGORITHM_ID_REQUIRED")
        if not self.canonical_name.strip():
            raise ValueError(f"ALGORITHM_NAME_REQUIRED:{self.algorithm_id}")
        if self.algorithm_family not in FAMILIES:
            raise ValueError(f"ALGORITHM_FAMILY_UNKNOWN:{self.algorithm_id}:{self.algorithm_family}")
        if self.lifecycle not in LIFECYCLES:
            raise ValueError(f"ALGORITHM_LIFECYCLE_UNKNOWN:{self.algorithm_id}:{self.lifecycle}")
        if self.retired_version and not self.superseding_adr:
            raise ValueError(f"ALGORITHM_RETIREMENT_REQUIRES_ADR:{self.algorithm_id}")
        object.__setattr__(self, "dependency_requirements", _tuple_of(self.dependency_requirements))
        object.__setattr__(self, "benchmark_ids", _tuple_of(self.benchmark_ids))
        object.__setattr__(self, "test_ids", _tuple_of(self.test_ids))
        object.__setattr__(self, "audit_event_types", _tuple_of(self.audit_event_types) or (ALGORITHM_SELECTED,))
        object.__setattr__(self, "requirement_trace_ids", _tuple_of(self.requirement_trace_ids))

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> "AlgorithmRecord":
        return cls(
            algorithm_id=str(source.get("algorithm_id") or source.get("algorithmId") or ""),
            canonical_name=str(source.get("canonical_name") or source.get("canonicalName") or ""),
            algorithm_family=str(source.get("algorithm_family") or source.get("algorithmFamily") or ""),
            lifecycle=str(source.get("lifecycle") or ""),
            applicability_contract=str(source.get("applicability_contract") or source.get("applicabilityContract") or ""),
            input_contract=str(source.get("input_contract") or source.get("inputContract") or ""),
            output_contract=str(source.get("output_contract") or source.get("outputContract") or ""),
            semantic_scope=str(source.get("semantic_scope") or source.get("semanticScope") or ""),
            implementation_module=str(source.get("implementation_module") or source.get("implementationModule") or ""),
            implementation_symbol=str(source.get("implementation_symbol") or source.get("implementationSymbol") or ""),
            runtime_producer=str(source.get("runtime_producer") or source.get("runtimeProducer") or ""),
            runtime_consumer=str(source.get("runtime_consumer") or source.get("runtimeConsumer") or ""),
            fallback_algorithm_id=source.get("fallback_algorithm_id") or source.get("fallbackAlgorithmId"),
            dependency_requirements=_tuple_of(source.get("dependency_requirements") or source.get("dependencyRequirements")),
            determinism_class=str(source.get("determinism_class") or source.get("determinismClass") or "DETERMINISTIC"),
            time_complexity_expectation=str(source.get("time_complexity_expectation") or source.get("timeComplexityExpectation") or "O(n)"),
            memory_complexity_expectation=str(source.get("memory_complexity_expectation") or source.get("memoryComplexityExpectation") or "O(n)"),
            token_cost_expectation=str(source.get("token_cost_expectation") or source.get("tokenCostExpectation") or "NONE"),
            storage_cost_expectation=str(source.get("storage_cost_expectation") or source.get("storageCostExpectation") or "LOW"),
            portability_class=str(source.get("portability_class") or source.get("portabilityClass") or "STDLIB"),
            benchmark_ids=_tuple_of(source.get("benchmark_ids") or source.get("benchmarkIds")),
            test_ids=_tuple_of(source.get("test_ids") or source.get("testIds")),
            audit_event_types=_tuple_of(source.get("audit_event_types") or source.get("auditEventTypes")) or (ALGORITHM_SELECTED,),
            requirement_trace_ids=_tuple_of(source.get("requirement_trace_ids") or source.get("requirementTraceIds")),
            introduced_version=str(source.get("introduced_version") or source.get("introducedVersion") or "DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903"),
            superseding_adr=source.get("superseding_adr") or source.get("supersedingAdr"),
            retired_version=source.get("retired_version") or source.get("retiredVersion"),
            registry_record_hash=str(source.get("registry_record_hash") or source.get("registryRecordHash") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm_id": self.algorithm_id,
            "canonical_name": self.canonical_name,
            "algorithm_family": self.algorithm_family,
            "lifecycle": self.lifecycle,
            "applicability_contract": self.applicability_contract,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "semantic_scope": self.semantic_scope,
            "implementation_module": self.implementation_module,
            "implementation_symbol": self.implementation_symbol,
            "runtime_producer": self.runtime_producer,
            "runtime_consumer": self.runtime_consumer,
            "fallback_algorithm_id": self.fallback_algorithm_id,
            "dependency_requirements": list(self.dependency_requirements),
            "determinism_class": self.determinism_class,
            "time_complexity_expectation": self.time_complexity_expectation,
            "memory_complexity_expectation": self.memory_complexity_expectation,
            "token_cost_expectation": self.token_cost_expectation,
            "storage_cost_expectation": self.storage_cost_expectation,
            "portability_class": self.portability_class,
            "benchmark_ids": list(self.benchmark_ids),
            "test_ids": list(self.test_ids),
            "audit_event_types": list(self.audit_event_types),
            "requirement_trace_ids": list(self.requirement_trace_ids),
            "introduced_version": self.introduced_version,
            "superseding_adr": self.superseding_adr,
            "retired_version": self.retired_version,
            "registry_record_hash": self.registry_record_hash,
        }

    def payload_for_hash(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("registry_record_hash", None)
        return payload


@dataclass(frozen=True)
class AlgorithmSelection:
    problem_class: str
    selected_algorithm_id: str
    candidates: tuple[str, ...]
    reasons: tuple[str, ...]
    fallback_algorithm_id: str | None
    benchmark_threshold: str
    consumer: str
    activated: bool
    evaluated_conditionals: tuple[str, ...] = ()
    event_type: str = ALGORITHM_SELECTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventType": self.event_type,
            "problemClass": self.problem_class,
            "selectedAlgorithmId": self.selected_algorithm_id,
            "candidates": list(self.candidates),
            "reasons": list(self.reasons),
            "fallbackAlgorithmId": self.fallback_algorithm_id,
            "benchmarkThreshold": self.benchmark_threshold,
            "consumer": self.consumer,
            "activated": self.activated,
            "evaluatedConditionals": list(self.evaluated_conditionals),
        }


@dataclass(frozen=True)
class HarAlgorithmExecutionPlan:
    schema: str
    constitution_version: str
    constitution_sha256: str
    registry_sha256: str
    phases: tuple[dict[str, Any], ...]
    selections: tuple[AlgorithmSelection, ...]
    evaluated_conditionals: tuple[str, ...]
    plan_hash: str
    research_may_begin: bool
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "constitutionVersion": self.constitution_version,
            "constitutionSha256": self.constitution_sha256,
            "algorithmRegistrySha256": self.registry_sha256,
            "phases": [dict(p) for p in self.phases],
            "selections": [s.to_dict() for s in self.selections],
            "evaluatedConditionals": list(self.evaluated_conditionals),
            "planHash": self.plan_hash,
            "researchMayBegin": self.research_may_begin,
            "notes": list(self.notes),
        }
