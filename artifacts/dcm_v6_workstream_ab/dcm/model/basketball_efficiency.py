"""Basketball efficiency model: shooting rates from made/attempted on comparable logs.

Shrinks with support. Does not invent opportunity. No pickled models.
"""
from __future__ import annotations

import math
from typing import Any

from dcm.contracts.hashes import content_hash

EFF_VERSION = "BASKETBALL_EFF_V1_2026-08-30"

LEAGUE_PRIORS: dict[str, dict[str, float]] = {
    "NBA": {"two_fg_pct": 0.52, "three_fg_pct": 0.36, "ft_pct": 0.78},
    "WNBA": {"two_fg_pct": 0.52, "three_fg_pct": 0.36, "ft_pct": 0.78},
}
_DEFAULT = LEAGUE_PRIORS["WNBA"]


def _f(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _sum_pair(logs: list[dict[str, Any]], made_key: str, att_key: str) -> tuple[float | None, int, float, float]:
    made = 0.0
    att = 0.0
    n = 0
    for row in logs:
        m = _f(row.get(made_key))
        a = _f(row.get(att_key))
        if m is None or a is None or a <= 0:
            continue
        made += m
        att += a
        n += 1
    if n <= 0 or att <= 0:
        return (None, 0, 0.0, 0.0)
    return (made / att, n, made, att)


def _two_point_rate(logs: list[dict[str, Any]]) -> tuple[float | None, int]:
    made = 0.0
    att = 0.0
    n = 0
    for row in logs:
        fgm = _f(row.get("fgm"))
        fga = _f(row.get("fga"))
        tpm = _f(row.get("tpm"))
        tpa = _f(row.get("tpa"))
        if fgm is None or fga is None:
            continue
        twom = fgm - (tpm if tpm is not None else 0.0)
        twoa = fga - (tpa if tpa is not None else 0.0)
        if twoa <= 0:
            continue
        made += max(0.0, twom)
        att += twoa
        n += 1
    if n <= 0 or att <= 0:
        return (None, 0)
    return (made / att, n)


def _blend(sample: float | None, n: int, prior: float, weights: dict[str, float]) -> float:
    if sample is None or n <= 0:
        return prior
    rw = float(weights.get("roleWeight") or 0.0)
    pw = float(weights.get("priorWeight") or 0.0)
    if rw + pw <= 0:
        # classical shrink when weights were not supplied
        prior_n = 5.0
        return (sample * n + prior * prior_n) / (n + prior_n)
    return (rw * sample + pw * prior) / (rw + pw)


def league_priors(league: str | None) -> dict[str, float]:
    key = str(league or "").strip().upper()
    return dict(LEAGUE_PRIORS.get(key) or _DEFAULT)


class EfficiencyModel:
    definition_version = EFF_VERSION

    def fit(
        self,
        comparable_logs: list[dict[str, Any]],
        *,
        matchup: float = 1.0,
        shrinkage: dict[str, float] | None = None,
        league: str | None = None,
    ) -> dict[str, Any]:
        logs = [r for r in (comparable_logs or []) if isinstance(r, dict)]
        priors = league_priors(league)
        weights = dict(shrinkage or {})
        two, two_n = _two_point_rate(logs)
        three, three_n, _, _ = _sum_pair(logs, "tpm", "tpa")
        ft, ft_n, _, _ = _sum_pair(logs, "ftm", "fta")
        match = matchup if math.isfinite(float(matchup or 1.0)) else 1.0
        try:
            match = float(matchup)
        except (TypeError, ValueError):
            match = 1.0
        two_pct = _blend(two, two_n, priors["two_fg_pct"], weights) * match
        three_pct = _blend(three, three_n, priors["three_fg_pct"], weights) * match
        ft_pct = _blend(ft, ft_n, priors["ft_pct"], weights)
        body = {
            "two_fg_pct": max(0.05, min(0.95, two_pct)),
            "three_fg_pct": max(0.05, min(0.80, three_pct)),
            "ft_pct": max(0.2, min(1.0, ft_pct)),
            "support_n": max(two_n, three_n, ft_n, len(logs)),
            "makesAttemptedSupport": {"two_n": two_n, "three_n": three_n, "ft_n": ft_n},
            "shrinkage": {
                "roleWeight": float(weights.get("roleWeight") or 0.0),
                "seasonWeight": float(weights.get("seasonWeight") or 0.0),
                "priorWeight": float(weights.get("priorWeight") or 0.0),
            },
            "definition_version": EFF_VERSION,
        }
        body["inputHash"] = content_hash({
            "logs": [{"fgm": r.get("fgm"), "fga": r.get("fga"), "tpm": r.get("tpm"), "tpa": r.get("tpa"), "ftm": r.get("ftm"), "fta": r.get("fta")} for r in logs],
            "matchup": match,
            "league": league,
            "shrinkage": body["shrinkage"],
            "version": EFF_VERSION,
        })
        return body
