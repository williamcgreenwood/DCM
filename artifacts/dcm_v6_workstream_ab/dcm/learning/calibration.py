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
    if not cell or int(cell.get("n", 0)) < MIN_ACTIVE_CELL_N:
        return {"raw": raw_p, "calibrated": raw_p, "state": "INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS", "cell_n": int((cell or {}).get("n", 0))}
    n = int(cell["n"])
    mean_pred = float(cell.get("mean_pred", raw_p))
    empirical = float(cell.get("empirical_rate", mean_pred))
    weight = n / (n + 50.0)
    correction = (empirical - mean_pred) * weight
    calibrated = max(0.001, min(0.999, raw_p + correction))
    return {"raw": raw_p, "calibrated": calibrated, "state": "ACTIVE_CHRONOLOGICAL_CELL", "cell_n": n}


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
