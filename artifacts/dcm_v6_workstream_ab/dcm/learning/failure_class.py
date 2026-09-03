"""Lightweight post-settlement failure classification. Heuristic. Not a permanent patch."""
from __future__ import annotations

from typing import Any

FAILURE_CLASSES = (
    "normal_variance",
    "opportunity_miss",
    "minutes_miss",
    "role_miss",
    "efficiency_miss",
    "injury_status_miss",
    "lineup_miss",
    "team_context_miss",
    "opponent_matchup_miss",
    "distribution_miss",
    "calibration_miss",
    "ranking_miss",
    "portfolio_miss",
    "source_miss",
    "definition_miss",
    "line_movement_miss",
    "unknown",
)

_INJURY = ("OUT", "INJURED", "QUESTIONABLE", "DOUBTFUL", "GTD", "INACTIVE", "PLAYER_STATUS")
_ROLE = ("ROLE", "BENCH", "STARTER", "ROTATION")
_LINEUP = ("LINEUP", "TEAMMATE_OUT", "STARTER_OUT")
_TEAM = ("PACE", "TEAM_CONTEXT", "REST")
_MATCHUP = ("MATCHUP", "OPPONENT")
_SOURCE = ("EVIDENCE_MISSING", "SOURCE_MISSING", "THIN_OPPORTUNITY", "THIN_EFFICIENCY")
_DEF = ("UNVERIFIED_MARKET", "DEFINITION")
_LINE = ("LINE_MOVE", "LINE_MOVEMENT")

def _f(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def _blob(fields: dict[str, Any]) -> str:
    parts = [
        str(fields.get("blocker") or ""),
        str(fields.get("status") or fields.get("playerStatus") or ""),
        str(fields.get("reason") or ""),
        " ".join(str(t) for t in (fields.get("dependencyTags") or [])),
        str(fields.get("calibrationState") or ""),
    ]
    return " ".join(parts).upper()

def classify_failure(
    *,
    predicted_side: str,
    outcome: str,
    snapshot_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assign one failure class. Never authorizes a permanent model patch from one result."""
    fields = snapshot_fields if isinstance(snapshot_fields, dict) else {}
    result = str(outcome or fields.get("result") or fields.get("settlement") or "").upper()
    blob = _blob(fields)
    reasons: list[str] = []
    label = "unknown"

    if result not in {"WIN", "LOSS"}:
        label = "unknown"
        reasons.append("non_binary_outcome")
    elif result == "WIN":
        label = "normal_variance"
        reasons.append("win_is_not_a_permanent_rule")
    else:
        actual_min = _f(fields.get("actualMinutes") or fields.get("minutesActual"))
        expected_min = _f(fields.get("expectedMinutes") or fields.get("minutesMean") or fields.get("opportunityMean"))
        if actual_min is not None and expected_min not in {None, 0}:
            ratio = actual_min / max(1e-9, expected_min)
            if ratio < 0.75 or ratio > 1.25 or abs(actual_min - expected_min) >= 8:
                label = "minutes_miss"
                reasons.append("minutes_residual")
        actual_opp = _f(fields.get("actualOpportunity"))
        expected_opp = _f(fields.get("opportunityMean") or fields.get("expectedOpportunity"))
        if label == "unknown" and actual_opp is not None and expected_opp not in {None, 0}:
            ratio = actual_opp / max(1e-9, expected_opp)
            if ratio < 0.75 or ratio > 1.25:
                label = "opportunity_miss"
                reasons.append("opportunity_residual")
        if label == "unknown" and any(tok in blob for tok in _INJURY):
            label = "injury_status_miss"
        elif label == "unknown" and any(tok in blob for tok in _ROLE):
            label = "role_miss"
        elif label == "unknown" and any(tok in blob for tok in _LINEUP):
            label = "lineup_miss"
        elif label == "unknown" and any(tok in blob for tok in _TEAM):
            label = "team_context_miss"
        elif label == "unknown" and any(tok in blob for tok in _MATCHUP):
            label = "opponent_matchup_miss"
        elif label == "unknown" and any(tok in blob for tok in _SOURCE):
            label = "source_miss"
        elif label == "unknown" and any(tok in blob for tok in _DEF):
            label = "definition_miss"
        elif label == "unknown" and any(tok in blob for tok in _LINE):
            label = "line_movement_miss"
        if label == "unknown":
            cal = str(fields.get("calibrationState") or "")
            p = _f(fields.get("forecastP") or fields.get("selectedP") or fields.get("calibratedP"))
            if "INACTIVE" in cal.upper() and p is not None and abs(p - 0.0) > 0.25:
                label = "calibration_miss"
                reasons.append("inactive_calibration_and_loss")
        if label == "unknown":
            p = _f(fields.get("forecastP") or fields.get("selectedP") or fields.get("calibratedP"))
            if p is not None and 0.45 <= p <= 0.55:
                label = "distribution_miss"
                reasons.append("near_coin_flip_loss")
        if label == "unknown":
            official = _f(fields.get("officialStatValue"))
            line = _f(fields.get("line"))
            actual_min = _f(fields.get("actualMinutes"))
            expected_min = _f(fields.get("opportunityMean"))
            if official is not None and line is not None:
                minutes_ok = True
                if actual_min is not None and expected_min not in {None, 0}:
                    minutes_ok = abs(actual_min / max(1e-9, expected_min) - 1.0) < 0.15
                if minutes_ok:
                    label = "efficiency_miss"
                    reasons.append("stat_miss_with_stable_minutes")
        if label == "unknown":
            if str(fields.get("grade") or "") in {"PLAYABLE"} and fields.get("rank") in {1, 2, 3}:
                label = "ranking_miss"
            elif fields.get("onCard") is True:
                label = "portfolio_miss"
        if label == "unknown":
            lower = _f(fields.get("lowerBound"))
            if lower is not None and lower < 0.55:
                label = "normal_variance"
                reasons.append("loss_inside_declared_uncertainty")
            else:
                label = "unknown"

    if label not in FAILURE_CLASSES:
        label = "unknown"
    return {
        "failureClass": label,
        "predictedSide": str(predicted_side or fields.get("direction") or ""),
        "outcome": result,
        "reasons": reasons,
        "permanentPatch": False,
        "note": "One isolated result must never become a permanent rule.",
    }
