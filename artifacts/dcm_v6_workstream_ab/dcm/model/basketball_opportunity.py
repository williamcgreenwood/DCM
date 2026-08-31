"""Basketball opportunity model: minutes and per-minute usage from role-comparable logs.

Hierarchical shrink toward league priors with explicit weights. No pickled models.
Deterministic hashes of inputs only. Efficiency stays out of this module.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from dcm.contracts.hashes import content_hash

OPP_VERSION = "BASKETBALL_OPP_V1_2026-08-30"

LEAGUE_PRIORS: dict[str, dict[str, float]] = {
    "NBA": {
        "minutes_mean": 34.0,
        "minutes_sd": 4.5,
        "fga_per_min": 0.55,
        "three_pa_share": 0.42,
        "fta_per_min": 0.18,
        "reb_per_min": 0.23,
        "ast_per_min": 0.14,
        "stl_per_min": 0.03,
        "blk_per_min": 0.025,
        "tov_per_min": 0.08,
    },
    "WNBA": {
        "minutes_mean": 31.0,
        "minutes_sd": 4.5,
        "fga_per_min": 0.55,
        "three_pa_share": 0.42,
        "fta_per_min": 0.18,
        "reb_per_min": 0.23,
        "ast_per_min": 0.14,
        "stl_per_min": 0.03,
        "blk_per_min": 0.025,
        "tov_per_min": 0.08,
    },
}
_DEFAULT_PRIORS = LEAGUE_PRIORS["WNBA"]


def _f(v: Any, default: float) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _avg(logs: list[dict[str, Any]], key: str) -> tuple[float | None, int]:
    vals = []
    for row in logs:
        try:
            x = float(row[key])
            if math.isfinite(x):
                vals.append(x)
        except (KeyError, TypeError, ValueError):
            pass
    return (mean(vals), len(vals)) if vals else (None, 0)


def _sd(logs: list[dict[str, Any]], key: str, fallback: float) -> float:
    vals = []
    for row in logs:
        try:
            x = float(row[key])
            if math.isfinite(x):
                vals.append(x)
        except (KeyError, TypeError, ValueError):
            pass
    return pstdev(vals) if len(vals) >= 2 else fallback


def _shrink(sample: float | None, n: int, prior: float, prior_n: float = 5.0) -> float:
    if sample is None or n <= 0:
        return prior
    return (sample * n + prior * prior_n) / (n + prior_n)


def _blend(role_val: float | None, season_val: float | None, prior: float, weights: dict[str, float]) -> float:
    rw = float(weights.get("roleWeight") or 0.0)
    sw = float(weights.get("seasonWeight") or 0.0)
    pw = float(weights.get("priorWeight") or 0.0)
    parts: list[tuple[float, float]] = []
    if role_val is not None:
        parts.append((rw, role_val))
    if season_val is not None and (role_val is None or abs(season_val - role_val) > 1e-12):
        parts.append((sw, season_val))
    parts.append((pw if pw > 0 else 1.0, prior))
    wsum = sum(w for w, _ in parts)
    if wsum <= 0:
        return prior
    return sum(w * v for w, v in parts) / wsum


def league_priors(league: str | None) -> dict[str, float]:
    key = str(league or "").strip().upper()
    return dict(LEAGUE_PRIORS.get(key) or _DEFAULT_PRIORS)


class OpportunityModel:
    """Minutes + per-minute opportunity from role-comparable logs and pace."""

    definition_version = OPP_VERSION

    def fit(
        self,
        comparable_logs: list[dict[str, Any]],
        *,
        season_logs: list[dict[str, Any]] | None = None,
        pace: float = 1.0,
        shrinkage: dict[str, float] | None = None,
        league: str | None = None,
        role_multiplier: float = 1.0,
        support_n: int | None = None,
    ) -> dict[str, Any]:
        role_logs = [r for r in (comparable_logs or []) if isinstance(r, dict)]
        season = [r for r in (season_logs or role_logs) if isinstance(r, dict)]
        priors = league_priors(league)
        role_n = int(support_n) if support_n is not None else len(role_logs)
        weights = dict(shrinkage or {})
        if not weights:
            from dcm.research.role_epoch import shrinkage_weights
            weights = shrinkage_weights(role_n, len(season))

        minutes, mn = _avg(role_logs, "minutes")
        season_minutes, _ = _avg(season, "minutes")
        fga, fn = _avg(role_logs, "fga")
        tpa, tn = _avg(role_logs, "tpa")
        fta, ftan = _avg(role_logs, "fta")
        reb, rn = _avg(role_logs, "reb")
        ast, an = _avg(role_logs, "ast")
        s_fga, _ = _avg(season, "fga")
        s_tpa, _ = _avg(season, "tpa")
        s_fta, _ = _avg(season, "fta")
        s_reb, _ = _avg(season, "reb")
        s_ast, _ = _avg(season, "ast")

        prior_minutes = priors["minutes_mean"]
        if mn >= 3 and minutes is not None:
            observed_minutes = minutes
        elif mn > 0 and minutes is not None:
            observed_minutes = _blend(minutes, season_minutes, prior_minutes, weights)
        else:
            observed_minutes = prior_minutes

        def _rate(num: float | None, den: float | None) -> float | None:
            if num is None or den is None or den == 0:
                return None
            return num / den

        role_fga_pm = _rate(fga, minutes)
        role_tpa_share = _rate(tpa, fga)
        role_fta_pm = _rate(fta, minutes)
        role_reb_pm = _rate(reb, minutes)
        role_ast_pm = _rate(ast, minutes)
        season_fga_pm = _rate(s_fga, season_minutes)
        season_tpa_share = _rate(s_tpa, s_fga)
        season_fta_pm = _rate(s_fta, season_minutes)
        season_reb_pm = _rate(s_reb, season_minutes)
        season_ast_pm = _rate(s_ast, season_minutes)

        # Hierarchical blend of rates; missing sample → prior. Then apply pace.
        fga_pm = _blend(role_fga_pm, season_fga_pm, priors["fga_per_min"], weights) if role_fga_pm is not None or season_fga_pm is not None else priors["fga_per_min"]
        tpa_share = _blend(role_tpa_share, season_tpa_share, priors["three_pa_share"], weights) if role_tpa_share is not None or season_tpa_share is not None else priors["three_pa_share"]
        fta_pm = _blend(role_fta_pm, season_fta_pm, priors["fta_per_min"], weights) if role_fta_pm is not None or season_fta_pm is not None else priors["fta_per_min"]
        reb_pm = _blend(role_reb_pm, season_reb_pm, priors["reb_per_min"], weights) if role_reb_pm is not None or season_reb_pm is not None else priors["reb_per_min"]
        ast_pm = _blend(role_ast_pm, season_ast_pm, priors["ast_per_min"], weights) if role_ast_pm is not None or season_ast_pm is not None else priors["ast_per_min"]

        pace_m = _f(pace, 1.0)
        body = {
            "minutes_mean": observed_minutes * _f(role_multiplier, 1.0),
            "minutes_sd": max(0.75, _sd(role_logs if role_logs else season, "minutes", priors["minutes_sd"])),
            "fga_per_min": max(0.01, fga_pm * pace_m),
            "three_pa_share": max(0.0, min(1.0, tpa_share)),
            "fta_per_min": max(0.0, fta_pm * pace_m),
            "reb_per_min": max(0.0, reb_pm * pace_m),
            "ast_per_min": max(0.0, ast_pm * pace_m),
            "stl_per_min": max(0.0, priors["stl_per_min"] * pace_m),
            "blk_per_min": max(0.0, priors["blk_per_min"] * pace_m),
            "tov_per_min": max(0.0, priors["tov_per_min"] * pace_m),
            "support_n": mn,
            "shrinkage": {
                "roleWeight": float(weights.get("roleWeight") or 0.0),
                "seasonWeight": float(weights.get("seasonWeight") or 0.0),
                "priorWeight": float(weights.get("priorWeight") or 0.0),
            },
            "definition_version": OPP_VERSION,
        }
        body["inputHash"] = content_hash({
            "logs": [{"minutes": r.get("minutes"), "fga": r.get("fga"), "tpa": r.get("tpa"), "fta": r.get("fta"), "reb": r.get("reb"), "ast": r.get("ast")} for r in role_logs],
            "pace": pace_m,
            "league": league,
            "shrinkage": body["shrinkage"],
            "version": OPP_VERSION,
        })
        return body
