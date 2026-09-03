"""Governed deterministic signal operators for the canonical DCM pipeline."""

from dcm.signals.compiler import SignalCompiler
from dcm.signals.contracts import (
    EvidenceRequirement,
    LifecycleState,
    SignalField,
    SignalOperatorSpec,
    SignalStage,
)
from dcm.signals.executor import SignalEvaluation, SignalExecutor
from dcm.signals.integration_gate import BindingCatalog, SignalIntegrationGate
from dcm.signals.registry import CompiledRegistry, SignalRegistry

__all__ = [
    "BindingCatalog",
    "CompiledRegistry",
    "EvidenceRequirement",
    "LifecycleState",
    "SignalCompiler",
    "SignalEvaluation",
    "SignalExecutor",
    "SignalField",
    "SignalIntegrationGate",
    "SignalOperatorSpec",
    "SignalRegistry",
    "SignalStage",
]
