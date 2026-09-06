"""Participation / workload model, independent of opportunity and efficiency.

Opportunity (attempts per unit of participation) and efficiency (production per
attempt) consume this output. Minutes, snaps, plate appearances and analogous
units belong here — never inside the universal core.
"""
from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.model.basketball_opportunity import league_priors as basketball_priors
from dcm.model.gridiron_models import QB_ROLES, _avg as _g_avg, _blend as _g_blend, _sd as _g_sd, league_priors as gridiron_priors

PART_VERSION = "PARTICIPATION_V1_20260831"


def _f(v: Any, default: float) -> float:
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else default
    except (TypeError, ValueError):
        return default


def _avg(logs: list[dict[str, Any]], key: str) -> tuple[float | None, int]:
    vals = []
    for row in logs:
        try:
            x = float(row[key])
            if x == x and abs(x) != float("inf"):
                vals.append(x)
        except (KeyError, TypeError, ValueError):
            pass
    return (mean(vals), len(vals)) if vals else (None, 0)


def _sd(logs: list[dict[str, Any]], key: str, fallback: float) -> float:
    vals = []
    for row in logs:
        try:
            x = float(row[key])
            if x == x and abs(x) != float("inf"):
                vals.append(x)
        except (KeyError, TypeError, ValueError):
            pass
    return pstdev(vals) if len(vals) >= 2 else fallback


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


class ParticipationModel:
    """Expected participation units from role-comparable logs.

    Basketball unit: minutes. Gridiron unit: snaps. Other sports fail closed
    unless they declare a plugin-owned unit.
    """

    definition_version = PART_VERSION

    def fit(
        self,
        comparable_logs: list[dict[str, Any]],
        *,
        family: str,
        league: str | None = None,
        shrinkage: dict[str, float] | None = None,
        role_multiplier: float = 1.0,
        support_n: int | None = None,
        season_logs: list[dict[str, Any]] | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        family_l = str(family or "").strip().lower()
        role_logs = [r for r in (comparable_logs or []) if isinstance(r, dict)]
        season = [r for r in (season_logs or role_logs) if isinstance(r, dict)]
        weights = dict(shrinkage or {})
        if not weights:
            from dcm.research.role_epoch import shrinkage_weights
            weights = shrinkage_weights(len(role_logs), len(season))
        mul = _f(role_multiplier, 1.0)

        if family_l == "basketball":
            priors = basketball_priors(league)
            minutes, mn = _avg(role_logs, "minutes")
            season_minutes, _ = _avg(season, "minutes")
            n = int(support_n) if support_n is not None else mn
            if mn >= 3 and minutes is not None:
                mean_v = minutes
                source = "LOGS"
            elif mn > 0 and minutes is not None:
                mean_v = _blend(minutes, season_minutes, priors["minutes_mean"], weights)
                source = "LOGS"
            else:
                mean_v = priors["minutes_mean"]
                source = "PRIOR"
            body = {
                "family": "basketball",
                "unit": "minutes",
                "mean": mean_v * mul,
                "sd": max(0.75, _sd(role_logs if role_logs else season, "minutes", priors["minutes_sd"])),
                "support_n": n if n else mn,
                "source": source,
                "roleMultiplier": mul,
                "shrinkage": {
                    "roleWeight": float(weights.get("roleWeight") or 0.0),
                    "seasonWeight": float(weights.get("seasonWeight") or 0.0),
                    "priorWeight": float(weights.get("priorWeight") or 0.0),
                },
                "definition_version": PART_VERSION,
            }
        elif family_l == "gridiron":
            priors = gridiron_priors(league)
            bucket = "QB" if str(role or "").upper() in QB_ROLES else "SKILL"
            snap_prior = priors["snaps_mean_qb"] if bucket == "QB" else priors["snaps_mean_wr"]
            snaps, sn = _g_avg(role_logs, "snaps")
            s_snaps, _ = _g_avg(season, "snaps")
            n = int(support_n) if support_n is not None else sn
            mean_v = _g_blend(snaps, s_snaps, snap_prior, weights)
            source = "LOGS" if sn > 0 else "PRIOR"
            body = {
                "family": "gridiron",
                "unit": "snaps",
                "mean": mean_v * mul,
                "sd": max(2.0, _g_sd(role_logs if role_logs else season, "snaps", priors["snaps_sd"])),
                "support_n": n if n else sn,
                "source": source,
                "role": str(role or ""),
                "roleMultiplier": mul,
                "shrinkage": {
                    "roleWeight": float(weights.get("roleWeight") or 0.0),
                    "seasonWeight": float(weights.get("seasonWeight") or 0.0),
                    "priorWeight": float(weights.get("priorWeight") or 0.0),
                },
                "definition_version": PART_VERSION,
            }
        else:
            raise ValueError(f"PARTICIPATION_FAMILY_UNSUPPORTED:{family_l or 'unknown'}")

        body["inputHash"] = content_hash({
            "family": body["family"],
            "unit": body["unit"],
            "logs": [{"minutes": r.get("minutes"), "snaps": r.get("snaps")} for r in role_logs],
            "league": league,
            "role": role,
            "shrinkage": body["shrinkage"],
            "version": PART_VERSION,
        })
        return body
