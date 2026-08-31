"""Adaptive evidence freshness from DCM6-ROS-EG-001 §11.

Completed historical facts do not expire by wall-clock age. Volatile
current-state claims use effective half-life as event start approaches.
"""
from __future__ import annotations

from typing import Any

BASE_HALF_LIFE_HOURS: dict[str, float] = {
    "player_history": 4320.0,
    "season_recent_form": 168.0,
    "opportunity": 18.0,
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
    "GTD": 0.25,
    "ACTIVE": 1.00,
    "OUT": 0.50,
}

HISTORICAL_CATEGORIES = frozenset({"player_history", "season_recent_form"})

CLAIM_TYPE_TO_CATEGORY: dict[str, str] = {
    "HISTORICAL_PERFORMANCE": "player_history",
    "GAME_LOGS": "player_history",
    "SEASON_STATS": "season_recent_form",
    "SEASON_RECENT_FORM": "season_recent_form",
    "OPPORTUNITY": "opportunity",
    "EFFICIENCY": "opportunity",
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
    "MARKET": "external_market",
    "SENTIMENT": "sentiment",
    "CURRENT_CONTEXT": "current_status",
}


def category_for(claim_type: str | None, explicit: str | None = None) -> str:
    if explicit:
        raw = str(explicit).strip().lower()
        if raw in BASE_HALF_LIFE_HOURS:
            return raw
    key = str(claim_type or "").strip().upper()
    return CLAIM_TYPE_TO_CATEGORY.get(key, "current_status")


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
) -> float | None:
    cat = category_for(None, category)
    if historical_fact is None:
        historical_fact = cat in HISTORICAL_CATEGORIES
    if historical_fact:
        return None
    h_base = BASE_HALF_LIFE_HOURS.get(cat, BASE_HALF_LIFE_HOURS["current_status"])
    m_event = event_multiplier(hours_to_event)
    m_vol = VOLATILITY_M.get(str(volatility or "STABLE").upper(), 1.00)
    m_status = STATUS_M.get(str(status or "CONFIRMED").upper(), 1.00)
    return float(h_base) * m_event * m_vol * m_status


def freshness_score(
    *,
    age_hours: float,
    category: str,
    hours_to_event: float | None = None,
    volatility: str = "STABLE",
    status: str = "CONFIRMED",
    historical_fact: bool | None = None,
) -> float:
    h_eff = effective_half_life(
        category=category,
        hours_to_event=hours_to_event,
        volatility=volatility,
        status=status,
        historical_fact=historical_fact,
    )
    if h_eff is None:
        return 1.0
    if h_eff <= 0:
        return 0.0
    age = max(0.0, float(age_hours))
    return float(2.0 ** (-age / h_eff))


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
) -> dict[str, Any]:
    cat = category_for(claim_type, category)
    historical = cat in HISTORICAL_CATEGORIES
    h_eff = effective_half_life(
        category=cat,
        hours_to_event=hours_to_event,
        volatility=volatility,
        status=status,
        historical_fact=historical,
    )
    if age_hours is None:
        score = float(stored_freshness) if stored_freshness is not None else (1.0 if historical else 0.0)
        source = "stored" if stored_freshness is not None else "default"
    else:
        score = freshness_score(
            age_hours=age_hours,
            category=cat,
            hours_to_event=hours_to_event,
            volatility=volatility,
            status=status,
            historical_fact=historical,
        )
        source = "adaptive"
    return {
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


def delta_from_freshness(request: dict[str, Any], prior: dict[str, Any] | None) -> dict[str, Any] | None:
    extra = request.get("context") if isinstance(request.get("context"), dict) else {}
    age = request.get("ageHours", extra.get("ageHours"))
    hours_to_event = request.get("hoursToEvent", extra.get("hoursToEvent"))
    if age is None and hours_to_event is None:
        return None
    stored = None
    if prior is not None and prior.get("freshness") is not None:
        try:
            stored = float(prior.get("freshness"))
        except (TypeError, ValueError):
            stored = None
    try:
        age_f = float(age) if age is not None else None
    except (TypeError, ValueError):
        age_f = None
    try:
        hte = float(hours_to_event) if hours_to_event is not None else None
    except (TypeError, ValueError):
        hte = None
    ev = evaluate_freshness(
        claim_type=str(request.get("need") or request.get("claim_type") or ""),
        category=str(request.get("freshnessCategory") or extra.get("freshnessCategory") or "") or None,
        age_hours=age_f,
        hours_to_event=hte,
        volatility=str(request.get("volatility") or extra.get("volatility") or "STABLE"),
        status=str(request.get("status") or extra.get("status") or "CONFIRMED"),
        stored_freshness=stored,
    )
    if ev["historicalFact"]:
        return None
    if ev["stale"]:
        return {
            "deltaClass": "REFRESH_STALE",
            "reason": "ADAPTIVE_FRESHNESS_BELOW_THRESHOLD",
            "acquire": True,
            "freshness": ev["freshness"],
            "effectiveHalfLifeHours": ev["effectiveHalfLifeHours"],
        }
    return None
