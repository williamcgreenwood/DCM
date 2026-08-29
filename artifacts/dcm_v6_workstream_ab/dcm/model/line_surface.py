"""Directional empirical line surface from shared worlds.

Tolerance is side-specific and derived from the empirical order statistics;
there is no arbitrary +/- display clamp.
"""
from __future__ import annotations

import bisect
import math


def _probs(xs: list[float], line: float) -> dict[str, float]:
    n = len(xs)
    if n == 0:
        return {"pHigher": 0.0, "pLower": 0.0, "pPush": 1.0, "mean": 0.0, "n": 0}
    lower = bisect.bisect_left(xs, line - 1e-9)
    higher = n - bisect.bisect_right(xs, line + 1e-9)
    push = n - higher - lower
    return {"pHigher": higher / n, "pLower": lower / n, "pPush": push / n, "mean": sum(xs) / n, "n": n}


def _side_p(probs: dict[str, float], side: str) -> float:
    return probs["pHigher"] if side == "MORE" else probs["pLower"]


def _order_break(xs: list[float], side: str, required_p: float) -> float:
    n = len(xs)
    if not n:
        return math.nan
    k = max(1, min(n, int(math.ceil(required_p * n))))
    if side == "MORE":
        return xs[n - k]
    return xs[k - 1]


def surface(values: list[float], offered_line: float, *, side: str = "MORE", playable_p: float = 0.58, step: float = 0.5) -> dict:
    if side not in {"MORE", "LESS"}:
        raise ValueError("SIDE_REQUIRED_FOR_LINE_SURFACE")
    xs = sorted(float(v) for v in values)
    offered = _probs(xs, offered_line)
    offered_p = _side_p(offered, side)
    playable_break = _order_break(xs, side, playable_p)
    break_even = _order_break(xs, side, 0.50)
    if not xs or math.isnan(playable_break):
        tolerance = 0.0
    elif side == "MORE":
        tolerance = max(0.0, playable_break - offered_line)
    else:
        tolerance = max(0.0, offered_line - playable_break)
    adverse_line = offered_line + step if side == "MORE" else offered_line - step
    adverse_p = _side_p(_probs(xs, adverse_line), side)
    elasticity = abs(adverse_p - offered_p) / max(1e-9, step)
    area = 0.0
    if tolerance > 0:
        intervals = max(1, int(math.ceil(tolerance / step)))
        for i in range(intervals):
            line = offered_line + i * step if side == "MORE" else offered_line - i * step
            p = _side_p(_probs(xs, line), side)
            area += max(0.0, p - playable_p) * step
    return {
        "side": side,
        "offered_line": offered_line,
        "offered_probability": offered_p,
        "break_even_line": break_even,
        "playable_break_line": playable_break,
        "true_unclamped_line_tolerance": tolerance,
        "edge_elasticity": elasticity,
        "robustness_area": area,
        "pHigher": offered["pHigher"], "pLower": offered["pLower"],
        "pPush": offered["pPush"], "mean": offered["mean"], "n": offered["n"],
    }
