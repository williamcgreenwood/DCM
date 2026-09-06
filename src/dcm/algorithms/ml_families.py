"""Stdlib-only ML primitives used as constitution CORE/conditional fallbacks.

These are ChatGPT-native implementations. Optional packages (XGBoost, HNSW,
Leiden, TabPFN, etc.) remain permanent challengers and MUST NOT become
production dependencies.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

from dcm.algorithms.contracts import AlgorithmNotProductionActive


def ewma(values: Sequence[float], *, alpha: float = 0.3) -> list[float]:
    if not values:
        return []
    out = [float(values[0])]
    a = max(0.0, min(1.0, float(alpha)))
    for v in values[1:]:
        out.append(a * float(v) + (1.0 - a) * out[-1])
    return out


def cusum(values: Sequence[float], *, threshold: float = 5.0, drift: float = 0.5) -> list[int]:
    """Return indexes where a mean shift is detected."""
    if not values:
        return []
    gp = gn = 0.0
    mean0 = float(values[0])
    hits: list[int] = []
    for i, raw in enumerate(values):
        x = float(raw) - mean0
        gp = max(0.0, gp + x - drift)
        gn = min(0.0, gn + x + drift)
        if gp > threshold or gn < -threshold:
            hits.append(i)
            gp = gn = 0.0
            mean0 = float(raw)
    return hits


def page_hinkley(values: Sequence[float], *, delta: float = 0.005, lam: float = 50.0) -> list[int]:
    hits: list[int] = []
    mean = 0.0
    m_t = 0.0
    min_m = 0.0
    n = 0
    for i, raw in enumerate(values):
        n += 1
        x = float(raw)
        mean += (x - mean) / n
        m_t += x - mean - delta
        min_m = min(min_m, m_t)
        if m_t - min_m > lam:
            hits.append(i)
            mean = x
            m_t = 0.0
            min_m = 0.0
            n = 1
    return hits


def empirical_bayes_shrink(x: float, n: float, prior_mean: float, prior_n: float) -> float:
    total = max(0.0, float(n)) + max(0.0, float(prior_n))
    if total <= 0:
        return float(prior_mean)
    return (float(n) * float(x) + float(prior_n) * float(prior_mean)) / total


def isotonic_regression(xs: Sequence[float], ys: Sequence[float]) -> list[float]:
    """Pool-adjacent-violators; xs used only for pairing/order."""
    if len(xs) != len(ys):
        raise ValueError("ISOTONIC_LENGTH_MISMATCH")
    paired = sorted(zip(xs, ys), key=lambda p: p[0])
    values = [float(y) for _, y in paired]
    weights = [1.0] * len(values)
    i = 0
    while i < len(values) - 1:
        if values[i] <= values[i + 1] + 1e-15:
            i += 1
            continue
        w = weights[i] + weights[i + 1]
        v = (values[i] * weights[i] + values[i + 1] * weights[i + 1]) / w
        values[i] = v
        weights[i] = w
        del values[i + 1]
        del weights[i + 1]
        if i:
            i -= 1
    # Expand pooled blocks back. Reconstruct by a second PAV on original order.
    # Simpler reconstruct: run PAV keeping block sizes then expand.
    return _pav_expand([float(y) for _, y in paired])


def _pav_expand(y: list[float]) -> list[float]:
    n = len(y)
    if n == 0:
        return []
    v = [float(x) for x in y]
    w = [1.0] * n
    i = 0
    blocks = [[0]]
    vals = [v[0]]
    weights = [1.0]
    for j in range(1, n):
        blocks.append([j])
        vals.append(v[j])
        weights.append(1.0)
        while len(vals) >= 2 and vals[-2] > vals[-1]:
            wsum = weights[-2] + weights[-1]
            vmerge = (vals[-2] * weights[-2] + vals[-1] * weights[-1]) / wsum
            blocks[-2] = blocks[-2] + blocks[-1]
            vals[-2] = vmerge
            weights[-2] = wsum
            blocks.pop()
            vals.pop()
            weights.pop()
    out = [0.0] * n
    for block, val in zip(blocks, vals):
        for idx in block:
            out[idx] = val
    return out


def platt_scale(scores: Sequence[float], labels: Sequence[int], *, lr: float = 0.1, steps: int = 200) -> tuple[float, float]:
    if len(scores) != len(labels) or not scores:
        return (1.0, 0.0)
    a, b = 1.0, 0.0
    for _ in range(steps):
        ga = gb = 0.0
        for s, y in zip(scores, labels):
            z = a * float(s) + b
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            err = p - float(y)
            ga += err * float(s)
            gb += err
        a -= lr * ga / len(scores)
        b -= lr * gb / len(scores)
    return (a, b)


def split_conformal(residuals: Sequence[float], *, alpha: float = 0.1) -> float:
    if not residuals:
        return 0.0
    q = min(1.0, math.ceil((len(residuals) + 1) * (1.0 - alpha)) / len(residuals))
    ordered = sorted(abs(float(r)) for r in residuals)
    idx = min(len(ordered) - 1, max(0, int(math.ceil(q * len(ordered)) - 1)))
    return ordered[idx]


def empirical_quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    qq = max(0.0, min(1.0, q))
    idx = min(len(ordered) - 1, max(0, int(round(qq * (len(ordered) - 1)))))
    return ordered[idx]


def zscore_ood(value: float, population: Sequence[float]) -> float:
    if len(population) < 2:
        return 0.0
    mean = sum(population) / len(population)
    var = sum((x - mean) ** 2 for x in population) / (len(population) - 1)
    sd = math.sqrt(var) or 1e-12
    return abs(float(value) - mean) / sd


def ridge_closed_form(xs: Sequence[Sequence[float]], ys: Sequence[float], *, l2: float = 1.0) -> list[float]:
    """Tiny-matrix ridge using Gaussian elimination (stdlib)."""
    n = len(xs)
    if n == 0:
        return []
    d = len(xs[0])
    xtx = [[0.0 for _ in range(d)] for _ in range(d)]
    xty = [0.0] * d
    for row, y in zip(xs, ys):
        for i in range(d):
            xty[i] += row[i] * y
            for j in range(d):
                xtx[i][j] += row[i] * row[j]
    for i in range(d):
        xtx[i][i] += l2
    return _solve(xtx, xty)


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(n):
        pivot = max(range(i, n), key=lambda r: abs(m[r][i]))
        m[i], m[pivot] = m[pivot], m[i]
        diag = m[i][i] or 1e-12
        for j in range(i, n + 1):
            m[i][j] /= diag
        for r in range(n):
            if r == i:
                continue
            factor = m[r][i]
            for j in range(i, n + 1):
                m[r][j] -= factor * m[i][j]
    return [m[i][n] for i in range(n)]


def not_active_challenger(*_args: Iterable[object], **_kwargs: object) -> None:
    raise AlgorithmNotProductionActive("PERMANENT_CHALLENGER_NOT_PRODUCTION_ACTIVE")
