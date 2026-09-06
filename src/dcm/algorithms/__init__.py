"""Permanent Algorithmic Constitution runtime.

This package is the executable constitution surface. It does not replace
EvidenceGraph, ResearchStore, ranking, SportPlugin, or probability engines.
"""

from dcm.algorithms.constitution import (
    ALGORITHM_CONSTITUTION_VERSION,
    constitution_identity,
    constitution_sha256,
    load_constitution_text,
    prompt_declared_constitution_sha256,
)
from dcm.algorithms.contracts import (
    ALGORITHM_SELECTED,
    AlgorithmNotProductionActive,
    AlgorithmRecord,
    AlgorithmSelection,
    HarAlgorithmExecutionPlan,
)
from dcm.algorithms.execution_plan import (
    build_har_algorithm_execution_plan,
    constitution_run_hashes,
    persist_har_algorithm_execution_plan,
)
from dcm.algorithms.registry import (
    algorithm_registry_sha256,
    load_algorithm_registry,
    require_algorithm,
)
from dcm.algorithms.selection import AlgorithmSelectionEngine

__all__ = [
    "ALGORITHM_CONSTITUTION_VERSION",
    "ALGORITHM_SELECTED",
    "AlgorithmNotProductionActive",
    "AlgorithmRecord",
    "AlgorithmSelection",
    "AlgorithmSelectionEngine",
    "HarAlgorithmExecutionPlan",
    "algorithm_registry_sha256",
    "build_har_algorithm_execution_plan",
    "constitution_identity",
    "constitution_run_hashes",
    "constitution_sha256",
    "load_algorithm_registry",
    "load_constitution_text",
    "persist_har_algorithm_execution_plan",
    "prompt_declared_constitution_sha256",
    "require_algorithm",
]
