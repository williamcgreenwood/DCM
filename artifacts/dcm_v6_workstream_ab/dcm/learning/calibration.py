"""Chronological calibration cells and inactive-until-earned application gate."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

MIN_ACTIVE_CELL_N = 30


def cell_key(sport: str, league: str, market: str, side: str) -> str:
    return f"{sport}|{league}|{market}|{side}"


def apply_calibration(raw_p: float, *, key: str, cells: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    cell = (cells or {}).get(key)
    n = int((cell or {}).get("n", 0))
    if not cell or n < MIN_ACTIVE_CELL_N:
        return {
            "raw": raw_p,
            "calibrated": raw_p,
            "state": "INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS",
            "cell_n": n,
        }
    if str(cell.get("promotion_state") or "") != "ACTIVE_PROMOTED":
        return {
            "raw": raw_p,
            "calibrated": raw_p,
            "state": "SHADOW_NOT_PROMOTED",
            "cell_n": n,
        }
    activation_revision = str(cell.get("activation_revision") or "")
    if not activation_revision or activation_revision == "LR000000":
        return {
            "raw": raw_p,
            "calibrated": raw_p,
            "state": "INACTIVE_NO_LEARNING_REVISION_PROMOTION",
            "cell_n": n,
        }
    mean_pred = float(cell.get("mean_pred", raw_p))
    empirical = float(cell.get("empirical_rate", mean_pred))
    weight = n / (n + 50.0)
    correction = (empirical - mean_pred) * weight
    calibrated = max(0.001, min(0.999, raw_p + correction))
    return {
        "raw": raw_p,
        "calibrated": calibrated,
        "state": "ACTIVE_CHRONOLOGICAL_CELL",
        "cell_n": n,
        "activation_revision": activation_revision,
    }


def build_challenger_cells(settlements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in settlements:
        if s.get("binaryOutcome") not in {0, 1}:
            continue
        groups[str(s["calibrationKey"])].append(s)
    out: dict[str, dict[str, Any]] = {}
    for key, rows in groups.items():
        n = len(rows)
        mean_pred = sum(float(r["forecastP"]) for r in rows) / n
        empirical = sum(int(r["binaryOutcome"]) for r in rows) / n
        brier = sum((float(r["forecastP"]) - int(r["binaryOutcome"])) ** 2 for r in rows) / n
        log_loss = -sum(
            int(r["binaryOutcome"]) * math.log(max(1e-12, float(r["forecastP"])))
            + (1 - int(r["binaryOutcome"])) * math.log(max(1e-12, 1.0 - float(r["forecastP"])))
            for r in rows
        ) / n
        out[key] = {"n": n, "mean_pred": mean_pred, "empirical_rate": empirical, "brier": brier, "log_loss": log_loss,
                    "promotion_state": "SHADOW_ONLY_REQUIRES_FUTURE_WALK_FORWARD"}
    return out
