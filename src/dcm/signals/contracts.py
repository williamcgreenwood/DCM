"""Immutable contracts for stage-bound deterministic signal operators."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SignalStage(str, Enum):
    RESEARCH_TRUTH = "RESEARCH_TRUTH"
    FEATURE = "FEATURE"
    DIAGNOSTIC = "DIAGNOSTIC"
    HARD_GATE = "HARD_GATE"
    PORTFOLIO = "PORTFOLIO"
    LEARNING = "LEARNING"


class LifecycleState(str, Enum):
    CANDIDATE = "CANDIDATE"
    SHADOW_DIAGNOSTIC = "SHADOW_DIAGNOSTIC"
    ACTIVE_FEATURE = "ACTIVE_FEATURE"
    ACTIVE_HARD_GATE = "ACTIVE_HARD_GATE"
    DEFERRED = "DEFERRED"
    REJECTED_INVALID = "REJECTED_INVALID"
    REJECTED_DUPLICATE = "REJECTED_DUPLICATE"


ACTIVE_STATES = frozenset({LifecycleState.ACTIVE_FEATURE, LifecycleState.ACTIVE_HARD_GATE})
EXECUTABLE_STATES = frozenset({*ACTIVE_STATES, LifecycleState.SHADOW_DIAGNOSTIC})


@dataclass(frozen=True)
class SignalField:
    name: str
    unit: str
    dimension: str
    temporal_class: str = "PRE_CUTOFF"
    normalized: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("SIGNAL_FIELD_NAME_REQUIRED")
        if not self.unit.strip():
            raise ValueError(f"SIGNAL_FIELD_UNIT_REQUIRED:{self.name}")
        if not self.dimension.strip():
            raise ValueError(f"SIGNAL_FIELD_DIMENSION_REQUIRED:{self.name}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SignalField":
        return cls(
            name=str(value.get("name") or ""),
            unit=str(value.get("unit") or ""),
            dimension=str(value.get("dimension") or ""),
            temporal_class=str(value.get("temporal_class") or value.get("temporalClass") or "PRE_CUTOFF"),
            normalized=bool(value.get("normalized", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "dimension": self.dimension,
            "temporalClass": self.temporal_class,
            "normalized": self.normalized,
        }


@dataclass(frozen=True)
class EvidenceRequirement:
    claim_type: str
    freshness_policy: str
    required: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceRequirement":
        return cls(
            claim_type=str(value.get("claim_type") or value.get("claimType") or ""),
            freshness_policy=str(value.get("freshness_policy") or value.get("freshnessPolicy") or ""),
            required=bool(value.get("required", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "claimType": self.claim_type,
            "freshnessPolicy": self.freshness_policy,
            "required": self.required,
        }


@dataclass(frozen=True)
class SignalOperatorSpec:
    operator_id: str
    version: str
    stage: SignalStage
    family: str
    sports: tuple[str, ...]
    competitions: tuple[str, ...] = ()
    market_definitions: tuple[str, ...] = ()
    semantic_scopes: tuple[str, ...] = ()
    required_inputs: tuple[SignalField, ...] = ()
    outputs: tuple[SignalField, ...] = ()
    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    dependencies: tuple[str, ...] = ()
    overlap_group: str = ""
    transformation_id: str = ""
    execution_cost_class: str = "LOW"
    lifecycle_state: LifecycleState = LifecycleState.CANDIDATE
    consumers: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    behavior_class: str = "FEATURE_TRANSFORM"
    source_ref: str = ""
    doctrine_hash: str = ""
    can_change_probability_directly: bool = False
    can_override_hard_gate: bool = False
    hard_gate_authorization: str = ""
    audit_tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("operator_id", "version", "family", "transformation_id"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"SIGNAL_OPERATOR_{name.upper()}_REQUIRED")
        for name in (
            "sports", "competitions", "market_definitions", "semantic_scopes",
            "required_inputs", "outputs", "evidence_requirements", "dependencies",
            "consumers", "tests", "audit_tags",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.can_change_probability_directly:
            raise ValueError("SIGNAL_OPERATOR_DIRECT_PROBABILITY_CHANGE_FORBIDDEN")
        if self.can_override_hard_gate:
            raise ValueError("SIGNAL_OPERATOR_HARD_GATE_OVERRIDE_FORBIDDEN")

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> "SignalOperatorSpec":
        """Parse without mutating or destructively canonicalizing source JSON."""
        value = deepcopy(dict(source))
        return cls(
            operator_id=str(value.get("operator_id") or value.get("operatorId") or ""),
            version=str(value.get("version") or ""),
            stage=SignalStage(str(value.get("stage") or "FEATURE")),
            family=str(value.get("family") or ""),
            sports=tuple(str(v).lower() for v in value.get("sports", ())),
            competitions=tuple(str(v).upper() for v in value.get("competitions", ())),
            market_definitions=tuple(str(v) for v in value.get("market_definitions", value.get("marketDefinitions", ()))),
            semantic_scopes=tuple(str(v) for v in value.get("semantic_scopes", value.get("semanticScopes", ()))),
            required_inputs=tuple(SignalField.from_mapping(v) for v in value.get("required_inputs", value.get("requiredInputs", ()))),
            outputs=tuple(SignalField.from_mapping(v) for v in value.get("outputs", ())),
            evidence_requirements=tuple(EvidenceRequirement.from_mapping(v) for v in value.get("evidence_requirements", value.get("evidenceRequirements", ()))),
            dependencies=tuple(str(v) for v in value.get("dependencies", ())),
            overlap_group=str(value.get("overlap_group") or value.get("overlapGroup") or ""),
            transformation_id=str(value.get("transformation_id") or value.get("transformationId") or ""),
            execution_cost_class=str(value.get("execution_cost_class") or value.get("executionCostClass") or "LOW"),
            lifecycle_state=LifecycleState(str(value.get("lifecycle_state") or value.get("lifecycleState") or "CANDIDATE")),
            consumers=tuple(str(v) for v in value.get("consumers", ())),
            tests=tuple(str(v) for v in value.get("tests", ())),
            behavior_class=str(value.get("behavior_class") or value.get("behaviorClass") or "FEATURE_TRANSFORM"),
            source_ref=str(value.get("source_ref") or value.get("sourceRef") or ""),
            doctrine_hash=str(value.get("doctrine_hash") or value.get("doctrineHash") or ""),
            can_change_probability_directly=bool(value.get("can_change_probability_directly", value.get("canChangeProbabilityDirectly", False))),
            can_override_hard_gate=bool(value.get("can_override_hard_gate", value.get("canOverrideHardGate", False))),
            hard_gate_authorization=str(value.get("hard_gate_authorization") or value.get("hardGateAuthorization") or ""),
            audit_tags=tuple(str(v) for v in value.get("audit_tags", value.get("auditTags", ()))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operatorId": self.operator_id,
            "version": self.version,
            "stage": self.stage.value,
            "family": self.family,
            "sports": list(self.sports),
            "competitions": list(self.competitions),
            "marketDefinitions": list(self.market_definitions),
            "semanticScopes": list(self.semantic_scopes),
            "requiredInputs": [v.to_dict() for v in self.required_inputs],
            "outputs": [v.to_dict() for v in self.outputs],
            "evidenceRequirements": [v.to_dict() for v in self.evidence_requirements],
            "dependencies": list(self.dependencies),
            "overlapGroup": self.overlap_group,
            "transformationId": self.transformation_id,
            "executionCostClass": self.execution_cost_class,
            "lifecycleState": self.lifecycle_state.value,
            "consumers": list(self.consumers),
            "tests": list(self.tests),
            "behaviorClass": self.behavior_class,
            "sourceRef": self.source_ref,
            "doctrineHash": self.doctrine_hash,
            "canChangeProbabilityDirectly": False,
            "canOverrideHardGate": False,
            "hardGateAuthorization": self.hard_gate_authorization,
            "auditTags": list(self.audit_tags),
        }
