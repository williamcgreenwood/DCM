"""Offered-side probabilities. P(H)+P(L)+P(P)=1. Lower is not 1-P(Higher) when pushes exist."""

from __future__ import annotations


def from_worlds(values: list[float], line: float) -> dict[str, float]:
    if not values:
        return {"pHigher": 0.0, "pLower": 0.0, "pPush": 1.0, "mean": 0.0}
    n = len(values)
    higher = sum(1 for v in values if v > line + 1e-9)
    lower = sum(1 for v in values if v < line - 1e-9)
    push = n - higher - lower
    pH, pL, pP = higher / n, lower / n, push / n
    s = pH + pL + pP
    if abs(s - 1.0) > 1e-9:
        pH, pL, pP = pH / s, pL / s, pP / s
    mean = sum(values) / n
    return {"pHigher": pH, "pLower": pL, "pPush": pP, "mean": mean, "n": n}
