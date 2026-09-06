"""Explicit early-season CFB role-state resolver.

This is a descriptive role state, not a forecast probability. Missing facts
remain ROLE_UNCERTAIN and increase downstream epistemic risk rather than being
silently coerced into RETURNING_STARTER.
"""
from __future__ import annotations

from typing import Any

ROLE_STATES = frozenset({
    "RETURNING_STARTER",
    "RETURNING_ROTATION",
    "PROMOTED_STARTER",
    "TRANSFER_STARTER",
    "TRANSFER_ROTATION",
    "TRUE_FRESHMAN",
    "NEW_QB",
    "NEW_COORDINATOR_SYSTEM",
    "INJURY_RETURN",
    "ROLE_UNCERTAIN",
})


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "confirmed"}


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_cfb_role_state(player: dict[str, Any], *, role: str | None = None) -> dict[str, Any]:
    player = player if isinstance(player, dict) else {}
    role_text = str(role or player.get("role") or "").strip().upper()
    depth = str(
        player.get("depth_chart_role")
        or player.get("depthChartRole")
        or player.get("projected_role")
        or player.get("role")
        or ""
    ).strip().lower()
    current_starter = any(token in depth for token in ("starter", "wr1", "rb1", "qb1", "te1"))
    current_rotation = any(token in depth for token in ("rotation", "depth", "backup", "wr2", "wr3", "rb2", "te2"))
    prior_starts = _num(player.get("prior_season_starts") or player.get("priorStarts"))
    prior_role = str(player.get("prior_role") or player.get("priorRole") or "").strip().lower()
    transferred = _truthy(player.get("transfer")) or bool(player.get("previous_school") or player.get("previousSchool"))
    true_freshman = _truthy(player.get("true_freshman")) or str(player.get("class") or "").strip().upper() in {"FR", "TRUE FRESHMAN"}
    injury_return = _truthy(player.get("injury_return") or player.get("returning_from_injury"))
    new_system = _truthy(player.get("new_coordinator_system") or player.get("new_offensive_coordinator"))
    new_qb = role_text in {"QB", "QUARTERBACK"} and (
        _truthy(player.get("new_starting_qb"))
        or (prior_starts is not None and prior_starts <= 1 and current_starter)
    )

    flags: list[str] = []
    if new_system:
        flags.append("NEW_COORDINATOR_SYSTEM")
    if injury_return:
        flags.append("INJURY_RETURN")
    if transferred:
        flags.append("TRANSFER")
    if true_freshman:
        flags.append("TRUE_FRESHMAN")
    if new_qb:
        flags.append("NEW_QB")

    if injury_return:
        primary = "INJURY_RETURN"
    elif true_freshman:
        primary = "TRUE_FRESHMAN"
    elif transferred and current_starter:
        primary = "TRANSFER_STARTER"
    elif transferred and (current_rotation or depth):
        primary = "TRANSFER_ROTATION"
    elif new_qb:
        primary = "NEW_QB"
    elif current_starter and prior_starts is not None and prior_starts >= 5:
        primary = "RETURNING_STARTER"
    elif current_starter and ("backup" in prior_role or "rotation" in prior_role or (prior_starts is not None and prior_starts < 5)):
        primary = "PROMOTED_STARTER"
    elif current_rotation and (prior_starts is not None or prior_role):
        primary = "RETURNING_ROTATION"
    elif new_system and (current_starter or current_rotation):
        primary = "NEW_COORDINATOR_SYSTEM"
    else:
        primary = "ROLE_UNCERTAIN"

    return {
        "primary": primary,
        "flags": flags,
        "resolved": primary != "ROLE_UNCERTAIN",
        "role": role_text or None,
        "depthChartRole": depth or None,
        "priorSeasonStarts": prior_starts,
        "previousSchool": player.get("previous_school") or player.get("previousSchool"),
        "transferOpportunityCarryoverAllowed": False if transferred else None,
    }
