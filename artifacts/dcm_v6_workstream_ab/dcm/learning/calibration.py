"""Chronological calibration cells and inactive-until-earned application gate.

INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS is the default apply_calibration
state until a cell has n >= MIN_ACTIVE_CELL_N *and* an LR promotion other than
LR000000. evaluate_calibration_readiness reports whether N/ECE gates could be
considered; it never flips LEARNING_REVISION or predictiveClaim.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

MIN_ACTIVE_CELL_N = 30
MIN_CALIBRATION_READY_N = 200
MAX_CALIBRATION_READY_ECE = 0.08
INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS = "INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS"


def cell_key(sport: str, league: str, market: str, side: str) -> str:
    return f"{sport}|{league}|{market}|{side}"


def apply_calibration(raw_p: float, *, key: str, cells: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    cell = (cells or {}).get(key)
    n = int((cell or {}).get("n", 0))
    if not cell or n < MIN_ACTIVE_CELL_N:
        return {
            "raw": raw_p,
            "calibrated": raw_p,
            "state": INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS,
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


def _clip_p(raw: Any) -> float | None:
    try:
        p = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(p):
        return None
    return min(1.0, max(0.0, p))

def expected_calibration_error(preds: list[float], y: list[int], *, n_bins: int = 10) -> float | None:
    n = len(preds)
    if n == 0:
        return None
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, yi in zip(preds, y):
        idx = min(n_bins - 1, max(0, int(p * n_bins)))
        bins[idx].append((p, yi))
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        mean_y = sum(yi for _, yi in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(mean_p - mean_y)
    return ece

def evaluate_calibration_readiness(settlements: list[dict[str, Any]]) -> dict[str, Any]:
    """Readiness report only. Does not activate cells or advance LR000000."""
    preds: list[float] = []
    y: list[int] = []
    for rec in settlements or []:
        if rec.get("binaryOutcome") not in {0, 1}:
            continue
        p = _clip_p(rec.get("forecastP") or rec.get("calibratedP") or rec.get("selectedP"))
        if p is None:
            continue
        preds.append(p)
        y.append(int(rec["binaryOutcome"]))
    n = len(preds)
    ece = expected_calibration_error(preds, y)
    reasons: list[str] = []
    if n < MIN_CALIBRATION_READY_N:
        reasons.append(f"INSUFFICIENT_N:{n}<{MIN_CALIBRATION_READY_N}")
        reasons.append(INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS)
    if ece is None:
        reasons.append("ECE_UNDEFINED")
    elif ece > MAX_CALIBRATION_READY_ECE:
        reasons.append(f"ECE_ABOVE_THRESHOLD:{ece:.4f}>{MAX_CALIBRATION_READY_ECE}")
    reasons.append("LR000000_UNCHANGED")
    ready = n >= MIN_CALIBRATION_READY_N and ece is not None and ece <= MAX_CALIBRATION_READY_ECE
    return {
        "ready": False if not ready else True,
        "reasons": reasons if not ready else ["READY_TO_REPORT_ONLY_DOES_NOT_FLIP_LR"],
        "n": n,
        "ece": ece,
        "minN": MIN_CALIBRATION_READY_N,
        "maxEce": MAX_CALIBRATION_READY_ECE,
        "state": INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS if n < MIN_CALIBRATION_READY_N else "READINESS_REPORTED_NOT_PROMOTED",
        "learningRevisionUnchanged": "LR000000",
        "predictiveClaimUnchanged": "NONE",
        "activatesCalibration": False,
    }
