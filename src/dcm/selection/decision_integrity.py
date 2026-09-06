"""Non-overriding decision audits for directional probability outputs.

These checks observe the model output and may reject a row.  They never repair
or overwrite a probability, reverse a side, or rescue a rejected candidate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash


def _hashed(body: dict[str, Any]) -> dict[str, Any]:
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def probability_sanity_diagnostic(
    *,
    p_higher: Any,
    p_lower: Any,
    p_push: Any,
    tolerance: float = 1e-9,
) -> dict[str, Any]:
    values = {"pHigher": p_higher, "pLower": p_lower, "pPush": p_push}
    blockers: list[str] = []
    parsed: dict[str, float] = {}
    for name, value in values.items():
        try:
            parsed[name] = float(value)
        except (TypeError, ValueError):
            blockers.append(f"{name.upper()}_NOT_FINITE")
            continue
        if not math.isfinite(parsed[name]) or not 0.0 <= parsed[name] <= 1.0:
            blockers.append(f"{name.upper()}_OUT_OF_RANGE")
    total = sum(parsed.values()) if len(parsed) == 3 else None
    if total is not None and abs(total - 1.0) > float(tolerance):
        blockers.append("PROBABILITY_SUM_NOT_ONE")
    return _hashed({
        "schema": "pillars_dcm.probability_sanity.v1",
        "values": parsed,
        "sum": total,
        "tolerance": float(tolerance),
        "valid": not blockers,
        "blockers": blockers,
    })


def inverse_consistency_audit(
    row: Mapping[str, Any],
    evaluations: Mapping[str, Mapping[str, Any]],
    selected_side: str | None,
) -> dict[str, Any]:
    offered = []
    if bool(row.get("offeredHigher")):
        offered.append("MORE")
    if bool(row.get("offeredLower")):
        offered.append("LESS")
    evaluated = sorted(str(side) for side in evaluations)
    blockers: list[str] = []
    if not offered:
        blockers.append("OFFERED_SIDE_UNKNOWN")
    if selected_side not in offered:
        blockers.append("SELECTED_SIDE_NOT_OFFERED")
    if set(evaluated) != set(offered):
        blockers.append("EVALUATED_SIDES_DO_NOT_MATCH_OFFER")
    for side in evaluated:
        record = evaluations.get(side) or {}
        for key in ("rawP", "calibratedP", "evidenceSafeP", "lowerBound"):
            if key not in record:
                continue
            try:
                value = float(record[key])
            except (TypeError, ValueError):
                blockers.append(f"{side}_{key}_NOT_FINITE")
                continue
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                blockers.append(f"{side}_{key}_OUT_OF_RANGE")
    return _hashed({
        "schema": "pillars_dcm.inverse_consistency_audit.v1",
        "projectionId": str(row.get("projectionId") or ""),
        "offeredSides": offered,
        "evaluatedSides": evaluated,
        "selectedSide": selected_side,
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "rule": "audit_only_reject_on_failure_no_probability_or_side_overwrite",
    })


@dataclass
class SurvivorState:
    """One-way survivor ledger; a rejected projection cannot re-enter ranking."""

    rejected: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def reject(self, projection_id: str, *reasons: str) -> None:
        pid = str(projection_id or "")
        if not pid:
            return
        prior = set(self.rejected.get(pid, ()))
        prior.update(str(reason) for reason in reasons if reason)
        self.rejected[pid] = tuple(sorted(prior))

    def accept(self, projection_id: str) -> bool:
        return str(projection_id or "") not in self.rejected

    def snapshot(self) -> dict[str, Any]:
        return _hashed({
            "schema": "pillars_dcm.survivor_state.v1",
            "rejected": {key: list(value) for key, value in sorted(self.rejected.items())},
            "irreversible": True,
        })


__all__ = ["SurvivorState", "inverse_consistency_audit", "probability_sanity_diagnostic"]
