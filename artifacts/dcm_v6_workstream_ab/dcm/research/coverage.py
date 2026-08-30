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



def _league_family(request: dict[str, Any]) -> tuple[str, str]:
    extra = request if isinstance(request, dict) else {}
    league = str(extra.get("league") or extra.get("League") or "").upper()
    family = str(extra.get("sportFamily") or extra.get("sport_family") or "").lower()
    if not family:
        if league in {"NBA", "WNBA"}:
            family = "basketball"
        elif league in {"NFL", "CFB"}:
            family = "gridiron"
    return family, league


def _event_missing(request: dict[str, Any], merged: dict[str, Any], values: list[dict[str, Any]]) -> list[str]:
    if not values:
        return ["EVENT_CONTEXT"]
    family, _ = _league_family(request)
    missing: list[str] = []
    if not merged:
        missing.append("EVENT_CONTEXT")
        return missing
    # Fail closed on sport-specific required fields when the family is known.
    if family == "basketball":
        if not (merged.get("event_context") or merged.get("starters_known") or merged.get("scheduled_start") or merged.get("environment")):
            missing.append("BASKETBALL_EVENT_CONTEXT")
        if not (merged.get("scheduled_start") or merged.get("start") or merged.get("starters_known") or merged.get("venue") or merged.get("environment")):
            missing.append("BASKETBALL_EVENT_START_OR_VENUE")
    elif family in {"gridiron", "football"}:
        if not (merged.get("event_context") or merged.get("scheduled_start") or merged.get("environment") or merged.get("starters_known")):
            missing.append("FOOTBALL_EVENT_CONTEXT")
        if not (merged.get("surface") or merged.get("weather") or merged.get("environment") or merged.get("venue")):
            missing.append("FOOTBALL_EVENT_SURFACE_OR_WEATHER")
    return missing


def _team_missing(request: dict[str, Any], merged: dict[str, Any], values: list[dict[str, Any]]) -> list[str]:
    if not values:
        return ["TEAM_CONTEXT"]
    family, _ = _league_family(request)
    missing: list[str] = []
    if not merged:
        missing.append("TEAM_CONTEXT")
        return missing
    if family == "basketball":
        if not (merged.get("team_context") or merged.get("pace_multiplier") or merged.get("pace") or merged.get("possessions")):
            missing.append("BASKETBALL_TEAM_PACE")
    elif family in {"gridiron", "football"}:
        if not (merged.get("team_context") or merged.get("injury_cluster") is not None or merged.get("depth") or merged.get("matchup_efficiency_multiplier")):
            missing.append("FOOTBALL_TEAM_INJURY_OR_DEPTH")
        if not (merged.get("plays") or merged.get("pace") or merged.get("pace_multiplier") or merged.get("matchup_efficiency_multiplier")):
            missing.append("FOOTBALL_TEAM_PLAYS_OR_PACE")
    return missing


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
    elif scope == "MARKET_DEFINITION":
        if merged.get("definition_verified") is not True:
            missing.append("VERIFIED_MARKET_DEFINITION")
    elif scope == "MARKET":
        # Legacy fallback only — validated if a leftover MARKET request exists.
        if merged.get("definition_verified") is not True:
            missing.append("VERIFIED_MARKET_DEFINITION")
    elif scope == "OFFER":
        if not merged:
            missing.append("OFFER_CONTEXT")
        elif merged.get("offer_recorded") is False:
            missing.append("OFFER_CONTEXT")
    elif scope == "SPORT":
        if not merged:
            missing.append("SPORT_CONTEXT")
    elif scope == "EVENT":
        missing.extend(_event_missing(request, merged, values))
    elif scope == "TEAM":
        missing.extend(_team_missing(request, merged, values))

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
