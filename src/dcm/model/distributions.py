"""Offered-side probabilities. P(H)+P(L)+P(P)=1. Lower is not 1-P(Higher) when pushes exist."""

from __future__ import annotations

from typing import Sequence


def from_worlds(values: list[float] | Sequence[float], line: float) -> dict[str, float]:
    """Empirical P(Higher)/P(Lower)/P(Push) from world samples.

    Uses NumPy when available for contiguous reductions; results match the
    pure-Python path (same counts / means) within float summation tolerance.
    """
    if not values:
        return {"pHigher": 0.0, "pLower": 0.0, "pPush": 1.0, "mean": 0.0}
    try:
        import numpy as np

        arr = np.asarray(values, dtype=np.float64)
        n = int(arr.size)
        if n == 0:
            return {"pHigher": 0.0, "pLower": 0.0, "pPush": 1.0, "mean": 0.0}
        higher = int(np.count_nonzero(arr > line + 1e-9))
        lower = int(np.count_nonzero(arr < line - 1e-9))
        push = n - higher - lower
        pH, pL, pP = higher / n, lower / n, push / n
        s = pH + pL + pP
        if abs(s - 1.0) > 1e-9:
            pH, pL, pP = pH / s, pL / s, pP / s
        mean = float(arr.mean())
        return {"pHigher": pH, "pLower": pL, "pPush": pP, "mean": mean, "n": n}
    except ImportError:
        return from_worlds_reference(list(values), line)


def from_worlds_reference(values: list[float], line: float) -> dict[str, float]:
    """Pure-Python fallback used by parity tests."""
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
