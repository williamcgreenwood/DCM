"""Adaptive evidence freshness from DCM6-ROS-EG-001 §11.

H_eff = H_base * M_event * M_volatility * M_status
Freshness = 2 ** (-age_hours / H_eff)

Unknown categories, volatility, or status fail closed.
Only verified immutable completed-event facts bypass clock expiration.
season_recent_form is a derived aggregate and is NOT an immutable fact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

BASE_HALF_LIFE_HOURS: dict[str, float] = {
    "player_history": 4320.0,
    "season_recent_form": 168.0,
    "opportunity": 18.0,
    "efficiency": 18.0,
    "team_context": 72.0,
    "opponent_context": 72.0,
    "current_status": 3.0,
    "lineup_depth_chart": 2.0,
    "teammate_availability": 3.0,
    "environment": 2.0,
    "travel_rest": 24.0,
    "external_market": 0.5,
    "sentiment": 4.0,
}

VOLATILITY_M: dict[str, float] = {
    "STABLE": 1.00,
    "MEDIUM": 0.75,
    "HIGH": 0.50,
    "CRITICAL": 0.25,
}

STATUS_M: dict[str, float] = {
    "CONFIRMED": 1.00,
    "PROBABLE": 0.75,
    "QUESTIONABLE": 0.50,
    "GAME_TIME_DECISION": 0.25,
}

# Governed aliases only. Do not invent OUT/ACTIVE multipliers here.
STATUS_ALIASES: dict[str, str] = {
    "GTD": "GAME_TIME_DECISION",
}

VOLATILE_CATEGORIES = frozenset({
    "current_status",
    "lineup_depth_chart",
    "teammate_availability",
    "environment",
    "external_market",
    "sentiment",
    "opportunity",
    "efficiency",
})

IMMUTABLE_FACT_CATEGORIES = frozenset({"player_history"})
IMMUTABLE_FACT_CLAIM_TYPES = frozenset({
    "HISTORICAL_PERFORMANCE",
    "GAME_LOGS",
    "COMPLETED_EVENT_FACT",
})

CLAIM_TYPE_TO_CATEGORY: dict[str, str] = {
    "HISTORICAL_PERFORMANCE": "player_history",
    "GAME_LOGS": "player_history",
    "COMPLETED_EVENT_FACT": "player_history",
    "SEASON_STATS": "season_recent_form",
    "SEASON_RECENT_FORM": "season_recent_form",
    "OPPORTUNITY": "opportunity",
    "EFFICIENCY": "efficiency",
    "TEAM_CONTEXT": "team_context",
    "AFFILIATION": "team_context",
    "OPPONENT_CONTEXT": "opponent_context",
    "COUNTERPARTY": "opponent_context",
    "CURRENT_STATUS": "current_status",
    "STATUS": "current_status",
    "AVAILABILITY": "teammate_availability",
    "INJURY": "current_status",
    "LINEUP": "lineup_depth_chart",
    "STARTERS": "lineup_depth_chart",
    "DEPTH_CHART": "lineup_depth_chart",
    "ENVIRONMENT": "environment",
    "WEATHER": "environment",
    "TRAVEL_REST": "travel_rest",
    "EXTERNAL_MARKET": "external_market",
    "SENTIMENT": "sentiment",
    "CURRENT_CONTEXT": "current_status",
}


class FreshnessPolicyError(ValueError):
    """Unknown freshness policy input. Fail closed."""


def normalize_status(status: str | None) -> str:
    raw = str(status or "").strip().upper()
    if not raw:
        raise FreshnessPolicyError("UNKNOWN_STATUS")
    raw = STATUS_ALIASES.get(raw, raw)
    if raw not in STATUS_M:
        raise FreshnessPolicyError(f"UNKNOWN_STATUS:{raw}")
    return raw


def normalize_volatility(volatility: str | None) -> str:
    raw = str(volatility or "").strip().upper()
    if not raw:
        raise FreshnessPolicyError("UNKNOWN_VOLATILITY")
    if raw not in VOLATILITY_M:
        raise FreshnessPolicyError(f"UNKNOWN_VOLATILITY:{raw}")
    return raw


def category_for(claim_type: str | None, explicit: str | None = None) -> str:
    if explicit:
        raw = str(explicit).strip().lower()
        if raw not in BASE_HALF_LIFE_HOURS:
            raise FreshnessPolicyError(f"UNKNOWN_FRESHNESS_CATEGORY:{raw}")
        return raw
    key = str(claim_type or "").strip().upper()
    if not key:
        raise FreshnessPolicyError("UNKNOWN_CLAIM_TYPE")
    if key not in CLAIM_TYPE_TO_CATEGORY:
        raise FreshnessPolicyError(f"UNKNOWN_CLAIM_TYPE:{key}")
    return CLAIM_TYPE_TO_CATEGORY[key]


def is_immutable_completed_fact(
    *,
    category: str,
    claim_type: str = "",
    historical_fact: bool | None = None,
) -> bool:
    if historical_fact is True:
        return True
    if historical_fact is False:
        return False
    ctype = str(claim_type or "").strip().upper()
    if ctype in IMMUTABLE_FACT_CLAIM_TYPES:
        return True
    return category in IMMUTABLE_FACT_CATEGORIES and ctype in IMMUTABLE_FACT_CLAIM_TYPES


def event_multiplier(hours_to_event: float | None) -> float:
    if hours_to_event is None:
        return 1.0
    h = float(hours_to_event)
    if h >= 24.0:
        return 1.0
    if h < 0.0:
        return 0.20
    return 0.20 + 0.80 * (h / 24.0)


def effective_half_life(
    *,
    category: str,
    hours_to_event: float | None = None,
    volatility: str = "STABLE",
    status: str = "CONFIRMED",
    historical_fact: bool | None = None,
    claim_type: str = "",
) -> float | None:
    cat = category_for(None, category) if category in BASE_HALF_LIFE_HOURS else category_for(claim_type, category)
    if is_immutable_completed_fact(category=cat, claim_type=claim_type, historical_fact=historical_fact):
        return None
    vol = normalize_volatility(volatility)
    st = normalize_status(status)
    h_base = BASE_HALF_LIFE_HOURS[cat]
    return float(h_base) * event_multiplier(hours_to_event) * VOLATILITY_M[vol] * STATUS_M[st]


def freshness_score(
    *,
    age_hours: float,
    category: str,
    hours_to_event: float | None = None,
    volatility: str = "STABLE",
    status: str = "CONFIRMED",
    historical_fact: bool | None = None,
    claim_type: str = "",
) -> float:
    h_eff = effective_half_life(
        category=category,
        hours_to_event=hours_to_event,
        volatility=volatility,
        status=status,
        historical_fact=historical_fact,
        claim_type=claim_type,
    )
    if h_eff is None:
        return 1.0
    if h_eff <= 0:
        return 0.0
    return float(2.0 ** (-max(0.0, float(age_hours)) / h_eff))


def parse_utc(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hours_between(later: datetime | None, earlier: datetime | None) -> float | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).total_seconds() / 3600.0


def derive_freshness_inputs(request: dict[str, Any], prior: dict[str, Any] | None) -> dict[str, Any]:
    extra = request.get("context") if isinstance(request.get("context"), dict) else {}
    prior = prior or {}
    cutoff = parse_utc(
        str(request.get("forecast_cutoff") or extra.get("forecast_cutoff") or extra.get("forecastCutoff") or "")
    )
    observed = parse_utc(
        str(
            prior.get("observedAt")
            or prior.get("observed_at")
            or extra.get("observed_at")
            or request.get("observed_at")
            or ""
        )
    )
    event_start = parse_utc(
        str(
            request.get("eventStart")
            or extra.get("eventStart")
            or extra.get("scheduledStart")
            or extra.get("startTime")
            or ""
        )
    )
    missing: list[str] = []
    if cutoff is None:
        missing.append("forecast_cutoff")
    age = hours_between(cutoff, observed) if cutoff and observed else None
    if age is None:
        missing.append("observed_at")
    hte = hours_between(event_start, cutoff) if event_start and cutoff else None
    if event_start is None:
        missing.append("eventStart")
    return {
        "cutoff": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ") if cutoff else None,
        "observedAt": observed.strftime("%Y-%m-%dT%H:%M:%SZ") if observed else None,
        "eventStart": event_start.strftime("%Y-%m-%dT%H:%M:%SZ") if event_start else None,
        "ageHours": age,
        "hoursToEvent": hte,
        "missing": missing,
        "inventedTimestamp": False,
    }


def evaluate_freshness(
    *,
    claim_type: str = "",
    category: str | None = None,
    age_hours: float | None = None,
    hours_to_event: float | None = None,
    volatility: str = "STABLE",
    status: str = "CONFIRMED",
    stored_freshness: float | None = None,
    stale_threshold: float = 0.35,
    historical_fact: bool | None = None,
) -> dict[str, Any]:
    try:
        cat = category_for(claim_type, category)
        historical = is_immutable_completed_fact(
            category=cat, claim_type=claim_type, historical_fact=historical_fact
        )
        h_eff = effective_half_life(
            category=cat,
            hours_to_event=hours_to_event,
            volatility=volatility,
            status=status,
            historical_fact=historical,
            claim_type=claim_type,
        )
    except FreshnessPolicyError as exc:
        return {
            "ok": False,
            "unresolved": True,
            "reason": str(exc),
            "historicalFact": False,
            "freshness": None,
            "stale": True,
            "source": "policy_error",
        }
    if age_hours is None:
        if stored_freshness is not None:
            score = float(stored_freshness)
            source = "stored"
        elif historical:
            score = 1.0
            source = "immutable_fact"
        else:
            return {
                "ok": False,
                "unresolved": True,
                "reason": "FRESHNESS_AGE_MISSING",
                "category": cat,
                "historicalFact": historical,
                "freshness": None,
                "stale": True,
                "source": "missing_age",
            }
    else:
        score = freshness_score(
            age_hours=age_hours,
            category=cat,
            hours_to_event=hours_to_event,
            volatility=volatility,
            status=status,
            historical_fact=historical,
            claim_type=claim_type,
        )
        source = "adaptive"
    return {
        "ok": True,
        "unresolved": False,
        "reason": None,
        "category": cat,
        "historicalFact": historical,
        "effectiveHalfLifeHours": h_eff,
        "ageHours": age_hours,
        "hoursToEvent": hours_to_event,
        "freshness": score,
        "stale": (not historical) and score < float(stale_threshold),
        "source": source,
        "eventMultiplier": event_multiplier(hours_to_event),
    }


def apply_adaptive_freshness(
    request: dict[str, Any],
    prior: dict[str, Any] | None,
    delta: dict[str, Any],
) -> dict[str, Any]:
    """Refine a classify_delta result using derived timestamps. Never invent times."""
    extra = request.get("context") if isinstance(request.get("context"), dict) else {}
    prior = prior or {}
    claim_type = str(request.get("claim_type") or extra.get("claim_type") or request.get("need") or "")
    explicit_cat = extra.get("freshnessCategory") or request.get("freshnessCategory")
    try:
        category = category_for(claim_type, explicit_cat)
    except FreshnessPolicyError:
        if explicit_cat:
            out = dict(delta)
            out["deltaClass"] = "REFRESH_STALE"
            out["deltaReason"] = "UNKNOWN_FRESHNESS_CATEGORY"
            out["acquire"] = True
            return out
        return delta
    derived = derive_freshness_inputs(request, prior)
    volatile = category in VOLATILE_CATEGORIES
    if volatile and derived["hoursToEvent"] is None and "eventStart" in derived["missing"]:
        out = dict(delta)
        out["deltaClass"] = "REFRESH_CURRENT_CONTEXT"
        out["deltaReason"] = "FRESHNESS_EVENT_START_MISSING"
        out["acquire"] = True
        out["freshnessInputs"] = derived
        return out
    vol = str(request.get("volatility") or extra.get("volatility") or prior.get("volatility") or "STABLE")
    status = str(request.get("status") or extra.get("status") or prior.get("status") or "CONFIRMED")
    stored = None
    if prior.get("freshness") is not None:
        try:
            stored = float(prior.get("freshness"))
        except (TypeError, ValueError):
            stored = None
    fact_flag = extra.get("immutableCompletedFact")
    if fact_flag is None:
        fact_flag = request.get("immutableCompletedFact")
    ev = evaluate_freshness(
        claim_type=claim_type,
        category=category,
        age_hours=derived["ageHours"],
        hours_to_event=derived["hoursToEvent"],
        volatility=vol,
        status=status,
        stored_freshness=stored,
        historical_fact=None if fact_flag is None else bool(fact_flag),
    )
    out = dict(delta)
    out["freshnessEvaluation"] = ev
    out["freshnessInputs"] = derived
    if ev.get("unresolved"):
        out["deltaClass"] = "REFRESH_STALE"
        out["deltaReason"] = ev.get("reason") or "FRESHNESS_UNRESOLVED"
        out["acquire"] = True
        return out
    if ev.get("historicalFact"):
        return out
    if ev.get("stale"):
        out["deltaClass"] = "REFRESH_STALE"
        out["deltaReason"] = "ADAPTIVE_FRESHNESS_BELOW_THRESHOLD"
        out["acquire"] = True
        return out
    structural = {
        "APPEND_MISSING_HISTORY",
        "TEAM_CHANGED",
        "ROLE_EPOCH_CHANGED",
        "DEFINITION_CHANGED",
        "CONTRADICTED_REVERIFY",
        "REPLACE_INVALIDATED",
        "NEW_ENTITY_FULL_RESEARCH",
        "NEW_OPPONENT_REQUIRED",
    }
    if out.get("deltaClass") not in structural:
        out["deltaClass"] = "REUSE_VALID"
        out["deltaReason"] = "ADAPTIVE_FRESHNESS_OK"
        out["acquire"] = False
    return out
