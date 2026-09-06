"""Algorithmic control plane: named engines that already exist as implementations.

Does not silently rewrite constitutional semantics. Adapts execution strategy
from workload metadata using the Algorithm Registry.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.algorithms.registry import load_algorithm_registry
from dcm.algorithms.selection import AlgorithmSelectionEngine
from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.contracts.hashes import content_hash

PLAN_STATES = (
    "REGISTERED",
    "APPLICABILITY_EVALUATED",
    "SELECTED",
    "BUILT",
    "QUERIED",
    "EXECUTED",
    "FALLBACK_EVALUATED",
    "FALLBACK_EXECUTED",
    "SKIPPED_NOT_APPLICABLE",
    "FAILED",
)


class AlgorithmApplicabilityEvaluator:
    def __init__(self, engine: AlgorithmSelectionEngine | None = None) -> None:
        self.engine = engine or AlgorithmSelectionEngine()

    def evaluate(self, problem_class: str, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        sel = self.engine.select(problem_class, dict(context or {}))
        return {
            "problemClass": problem_class,
            "state": "APPLICABILITY_EVALUATED",
            "selectedAlgorithmId": sel.selected_algorithm_id,
            "activated": sel.activated,
            "reasons": list(sel.reasons),
            "evaluatedConditionals": list(sel.evaluated_conditionals),
        }


class AlgorithmFallbackResolver:
    def __init__(self, engine: AlgorithmSelectionEngine | None = None) -> None:
        self.engine = engine or AlgorithmSelectionEngine()

    def resolve(self, algorithm_id: str, problem_class: str, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        rec = self.engine.record(algorithm_id)
        fallback = rec.fallback_algorithm_id
        return {
            "algorithmId": algorithm_id,
            "state": "FALLBACK_EVALUATED",
            "fallbackAlgorithmId": fallback,
            "portable": rec.portability_class,
        }


class AlgorithmBenchmarkRegistry:
    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}
        for rec in load_algorithm_registry():
            aid = rec.algorithm_id
            self._rows[aid] = {
                "algorithmId": aid,
                "benchmarkIds": list(rec.benchmark_ids or []),
                "cpuExpectation": rec.time_complexity_expectation,
                "memoryExpectation": rec.memory_complexity_expectation,
                "lifecycle": rec.lifecycle,
            }

    def lookup(self, algorithm_id: str) -> dict[str, Any] | None:
        return self._rows.get(algorithm_id)

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": "pillars_dcm.algorithm_benchmark_registry.v1",
            "count": len(self._rows),
            "algorithms": sorted(self._rows),
        }
        body["contentHash"] = content_hash({"count": body["count"], "algorithms": body["algorithms"]})
        return body


class AlgorithmExecutionPlan:
    """Runtime plan distinct from the HAR AlgorithmExecutionPlan artifact."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, algorithm_id: str, *, state: str, problem_class: str, note: str | None = None) -> dict[str, Any]:
        if state not in PLAN_STATES:
            raise ValueError(f"UNKNOWN_PLAN_STATE:{state}")
        row = {
            "algorithmId": algorithm_id,
            "state": state,
            "problemClass": problem_class,
            "note": note,
        }
        self.rows.append(row)
        return row

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": "pillars_dcm.algorithm_execution_plan_runtime.v1",
            "rows": list(self.rows),
            "states": list(PLAN_STATES),
        }
        body["contentHash"] = content_hash({"n": len(self.rows), "states": [r["state"] for r in self.rows]})
        return body


class AlgorithmExecutionTelemetry(AlgorithmTelemetry):
    """Named telemetry type required by the constitution control plane."""


def unused_algorithm_audit(telemetry: AlgorithmTelemetry, registered: list[str] | None = None) -> dict[str, Any]:
    snap = telemetry.snapshot()
    activated = set(snap.get("activatedCounts") or {})
    registered = registered or [r.algorithm_id for r in load_algorithm_registry() if r.lifecycle == "REQUIRED_CORE"]
    unused = [aid for aid in registered if aid and aid not in activated]
    body = {
        "schema": "pillars_dcm.unused_algorithm_audit.v1",
        "activated": sorted(activated),
        "requiredCoreUnused": unused,
        "note": "Construction of an unused index is not successful algorithm execution.",
    }
    body["contentHash"] = content_hash({"activated": body["activated"], "unused": unused})
    return body
