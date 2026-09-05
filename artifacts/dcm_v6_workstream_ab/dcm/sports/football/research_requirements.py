"""Market-specific evidence support for NFL/CFB.

Model support and PLAYABLE support are deliberately distinct. A market may be
simulated with a small, real player sample plus shrinkage while remaining
ineligible for selection until stronger role/context support exists.
"""
from __future__ import annotations

from typing import Any

from dcm.cfb.markets import ACTIVE_CFB_MARKETS, MARKET_CONTRACTS

ACTIVE = {"ACTIVE", "AVAILABLE", "PROBABLE", "EXPECTED_ACTIVE"}
INACTIVE = {"OUT", "DNP", "INACTIVE", "SUSPENDED", "IR", "PUP"}

MARKET_REQUIREMENTS: dict[str, dict[str, tuple[str, ...] | bool]] = {
    key: {
        "opportunity": spec["opportunity"],
        "efficiency": spec["efficiency"],
        "needs_pass_defense": spec["needs_pass_defense"],
        "needs_rush_defense": spec["needs_rush_defense"],
    }
    for key, spec in MARKET_CONTRACTS.items()
    if key in ACTIVE_CFB_MARKETS
}


def _row_has(row: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return all(row.get(field) is not None for field in fields)


def support_count(logs: list[dict[str, Any]], fields: tuple[str, ...]) -> int:
    if not fields:
        return len(logs)
    return sum(1 for row in logs if isinstance(row, dict) and _row_has(row, fields))


def assess_football_support(
    *,
    market: str,
    role: str,
    status: str,
    logs: list[dict[str, Any]],
    definition_verified: bool,
    team_event: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return independent minimum-model and PLAYABLE support states.

    Minimum modeling support requires at least one real market-relevant game
    plus a resolved role and a verified physical market definition. PLAYABLE
    support requires >=3 relevant games, active status, and the market-specific
    team/opponent context. Missing efficiency never blocks a pure opportunity
    market such as pass attempts or rush attempts.
    """
    req = MARKET_REQUIREMENTS.get(str(market or "").lower())
    if req is None:
        return {
            "modelable": False,
            "playableSupport": False,
            "modelBlockers": ["UNSUPPORTED_CFB_MARKET_REQUIREMENTS"],
            "playableBlockers": ["UNSUPPORTED_CFB_MARKET_REQUIREMENTS"],
            "opportunitySupportN": 0,
            "efficiencySupportN": 0,
        }
    role_ok = bool(str(role or "").strip()) and str(role or "").upper() not in {"UNKNOWN", "UNRESOLVED"}
    opp_fields = tuple(req["opportunity"])
    eff_fields = tuple(req["efficiency"])
    opp_n = support_count(logs, opp_fields)
    eff_n = support_count(logs, eff_fields) if eff_fields else opp_n
    model_blockers: list[str] = []
    if not definition_verified:
        model_blockers.append("UNVERIFIED_MARKET_DEFINITION")
    if not role_ok:
        model_blockers.append("PLAYER_ROLE_UNRESOLVED")
    if str(status or "").upper() in INACTIVE:
        model_blockers.append("PLAYER_NOT_ACTIVE")
    if opp_n < 1:
        model_blockers.append("MINIMUM_OPPORTUNITY_SUPPORT_MISSING")
    if eff_fields and eff_n < 1:
        model_blockers.append("MINIMUM_EFFICIENCY_SUPPORT_MISSING")

    playable_blockers = list(model_blockers)
    if str(status or "").upper() not in ACTIVE:
        playable_blockers.append("PLAYER_STATUS_NOT_CONFIRMED_ACTIVE")
    if opp_n < 3:
        playable_blockers.append("PLAYABLE_OPPORTUNITY_SUPPORT_LT3")
    if eff_fields and eff_n < 3:
        playable_blockers.append("PLAYABLE_EFFICIENCY_SUPPORT_LT3")
    team_event = team_event if isinstance(team_event, dict) else {}
    if not team_event.get("playsObserved") and not team_event.get("paceObserved"):
        playable_blockers.append("FOOTBALL_TEAM_PLAYS_OR_PACE")
    if bool(req["needs_pass_defense"]) and team_event.get("pass_defense") is None:
        playable_blockers.append("OPPONENT_PASS_DEFENSE")
    if bool(req["needs_rush_defense"]) and team_event.get("rush_defense") is None:
        playable_blockers.append("OPPONENT_RUSH_DEFENSE")

    return {
        "modelable": not model_blockers,
        "playableSupport": not playable_blockers,
        "modelBlockers": list(dict.fromkeys(model_blockers)),
        "playableBlockers": list(dict.fromkeys(playable_blockers)),
        "opportunitySupportN": opp_n,
        "efficiencySupportN": eff_n,
        "opportunityFields": list(opp_fields),
        "efficiencyFields": list(eff_fields),
    }
