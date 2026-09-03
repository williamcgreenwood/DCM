"""Live algorithm execution telemetry. A named algorithm with no consumer does not count."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from dcm.algorithms.selection import AlgorithmSelectionEngine
from dcm.contracts.hashes import content_hash


class AlgorithmTelemetry:
    """Records constitution algorithm executions on the live HAR path."""

    def __init__(self, *, engine: AlgorithmSelectionEngine | None = None) -> None:
        self.engine = engine or AlgorithmSelectionEngine()
        self._rows: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []

    def record(
        self,
        algorithm_id: str,
        *,
        problem_class: str,
        producer: str,
        consumer: str,
        artifact: str | None = None,
        fallback: str | None = None,
        activated: bool = True,
        applicability: str = "APPLICABLE",
        count: int = 1,
        note: str | None = None,
    ) -> dict[str, Any]:
        key = f"{algorithm_id}|{consumer}|{producer}"
        row = self._rows.get(key)
        if row is None:
            rec = self.engine.record(algorithm_id)
            row = {
                "algorithm_id": algorithm_id,
                "canonical_name": rec.canonical_name,
                "lifecycle": rec.lifecycle,
                "problem_class": problem_class,
                "applicability_decision": applicability,
                "producer": producer,
                "consumer": consumer,
                "fallback": fallback or rec.fallback_algorithm_id,
                "activated": bool(activated),
                "execution_count": 0,
                "artifact": artifact,
                "note": note,
            }
            self._rows[key] = row
            self._order.append(key)
        row["execution_count"] = int(row["execution_count"]) + int(count)
        if artifact and not row.get("artifact"):
            row["artifact"] = artifact
        return row

    def select_and_record(
        self,
        problem_class: str,
        *,
        producer: str,
        consumer: str,
        artifact: str | None = None,
        context: Mapping[str, Any] | None = None,
        count: int = 1,
    ) -> dict[str, Any]:
        sel = self.engine.select(problem_class, {**(context or {}), "consumer": consumer})
        return self.record(
            sel.selected_algorithm_id,
            problem_class=problem_class,
            producer=producer,
            consumer=consumer,
            artifact=artifact,
            fallback=sel.fallback_algorithm_id,
            activated=sel.activated,
            applicability="APPLICABLE" if sel.activated else "CONDITIONAL_NOT_ACTIVATED",
            count=count,
            note=";".join(sel.reasons[:4]),
        )

    def snapshot(self) -> dict[str, Any]:
        executions = [self._rows[k] for k in self._order]
        by_id: dict[str, int] = defaultdict(int)
        for row in executions:
            if row.get("activated"):
                by_id[str(row["algorithm_id"])] += int(row["execution_count"])
        body = {
            "schema": "pillars_dcm.algorithm_execution_telemetry.v1",
            "executions": executions,
            "activatedCounts": dict(sorted(by_id.items())),
            "activatedAlgorithmCount": len(by_id),
            "rowCount": len(executions),
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body
