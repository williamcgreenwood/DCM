"""True unclamped line surface from shared sorted worlds. Do not re-simulate per line."""

from __future__ import annotations

import bisect


def _probs(xs: list[float], line: float) -> dict[str, float]:
    n = len(xs)
    if n == 0:
        return {"pHigher": 0.0, "pLower": 0.0, "pPush": 1.0, "mean": 0.0, "n": 0}
    lower = bisect.bisect_left(xs, line - 1e-9)
    higher = n - bisect.bisect_right(xs, line + 1e-9)
    push = n - higher - lower
    pH, pL, pP = higher / n, lower / n, push / n
    mean = sum(xs) / n
    return {"pHigher": pH, "pLower": pL, "pPush": pP, "mean": mean, "n": n}


def surface(values: list[float], offered_line: float, *, playable_p: float = 0.58) -> dict:
    xs = sorted(float(v) for v in values)
    offered = _probs(xs, offered_line)
    step = 0.5
    tol_up = 0.0
    line = offered_line
    while line < offered_line + 40:
        nxt = _probs(xs, line + step)
        if nxt["pHigher"] < playable_p:
            break
        line += step
        tol_up += step
    tol_down = 0.0
    line = offered_line
    while line > offered_line - 40:
        nxt = _probs(xs, line - step)
        if nxt["pLower"] < playable_p:
            break
        line -= step
        tol_down += step
    lo, hi = offered_line - 20.0, offered_line + 20.0
    be = offered_line
    best = abs(offered["pHigher"] - 0.5)
    for _ in range(24):
        mid = (lo + hi) / 2
        p = _probs(xs, mid)["pHigher"]
        err = abs(p - 0.5)
        if err < best:
            best, be = err, mid
        if p > 0.5:
            lo = mid
        else:
            hi = mid
    elasticity = abs(_probs(xs, offered_line + 0.5)["pHigher"] - offered["pHigher"]) / 0.5
    area = 0.0
    for i in range(-12, 13):
        if _probs(xs, offered_line + i * 0.5)["pHigher"] >= playable_p:
            area += 0.5
    return {
        "offered_line": offered_line,
        "offered_probability": offered["pHigher"],
        "break_even_line": be,
        "true_unclamped_line_tolerance": max(tol_up, tol_down),
        "edge_elasticity": elasticity,
        "robustness_area": area,
        "pHigher": offered["pHigher"],
        "pLower": offered["pLower"],
        "pPush": offered["pPush"],
        "mean": offered["mean"],
    }
