"""Evidence completeness contracts for production research."""
from __future__ import annotations

from typing import Any


def _values_for(request: dict[str, Any], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for claim in claims:
        if (
            str(claim.get("semantic_scope")) == str(request.get("scope"))
            and str(claim.get("scope_id")) == str(request.get("scope_id"))
            and isinstance(claim.get("claim_value"), dict)
        ):
            out.append(dict(claim["claim_value"]))
    return out


def _merge(values: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        merged.update(value)
    return merged


def evaluate_request(request: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    scope = str(request.get("scope") or "")
    values = _values_for(request, claims)
    merged = _merge(values)
    missing: list[str] = []

    if not values:
        missing.append("EVIDENCE_CLAIM")
    elif scope == "PLAYER":
        status = str(merged.get("status") or "").strip().upper()
        if not status:
            missing.append("PLAYER_STATUS")
        role = str(merged.get("role") or "").strip()
        if not role:
            missing.append("PLAYER_ROLE")
        logs = merged.get("role_epoch_logs") or merged.get("game_logs")
        if not isinstance(logs, list) or len([x for x in logs if isinstance(x, dict)]) < 3:
            missing.append("ROLE_COMPARABLE_GAME_LOGS_MIN_3")
        opportunity = merged.get("opportunity")
        if not isinstance(opportunity, dict):
            missing.append("OPPORTUNITY_EVIDENCE")
        efficiency = merged.get("efficiency")
        if not isinstance(efficiency, dict):
            missing.append("EFFICIENCY_EVIDENCE")
    elif scope in {"MARKET", "MARKET_DEFINITION"}:
        if merged.get("definition_verified") is not True:
            missing.append("VERIFIED_MARKET_DEFINITION")
    elif scope == "OFFER":
        if not merged:
            missing.append("OFFER_CONTEXT")
    elif scope in {"SPORT", "EVENT", "TEAM"}:
        if not merged:
            missing.append(f"{scope}_CONTEXT")

    return {
        "requestId": request.get("request_id"),
        "scope": scope,
        "scopeId": request.get("scope_id"),
        "need": request.get("need"),
        "complete": not missing,
        "missing": missing,
        "claimCount": len(values),
    }


def coverage_report(requests: list[dict[str, Any]], claims: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [evaluate_request(req, claims) for req in requests]
    incomplete = [row for row in rows if not row["complete"]]
    return {
        "complete": not incomplete,
        "requested": len(rows),
        "completeRequests": len(rows) - len(incomplete),
        "incompleteRequests": len(incomplete),
        "missingRequirementCount": sum(len(row["missing"]) for row in incomplete),
        "requests": rows,
    }
