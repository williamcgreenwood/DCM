"""Hierarchical distribution contracts for DCM predictive modeling.

The goal is not to force one family onto every market.  These functions expose
auditable moments, effective sample size, shrinkage, and a conservative family
recommendation that downstream EventWorld sampling may consume.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean, pvariance
from typing import Iterable, Sequence

from dcm.algorithms.ml_families import empirical_bayes_shrink
from dcm.contracts.hashes import content_hash

DIST_VERSION = "DCM_HIERARCHICAL_DISTRIBUTION_V1_2026-10-09"


@dataclass(frozen=True)
class HierarchicalFit:
    family: str
    observed_mean: float
    observed_variance: float
    posterior_mean: float
    prior_mean: float
    effective_n: float
    zero_rate: float
    dispersion: float | None
    epistemic_sd: float
    version: str = DIST_VERSION

    def to_dict(self) -> dict[str, object]:
        body: dict[str, object] = {
            "family": self.family,
            "observedMean": self.observed_mean,
            "observedVariance": self.observed_variance,
            "posteriorMean": self.posterior_mean,
            "priorMean": self.prior_mean,
            "effectiveN": self.effective_n,
            "zeroRate": self.zero_rate,
            "dispersion": self.dispersion,
            "epistemicSd": self.epistemic_sd,
            "version": self.version,
        }
        body["contentHash"] = content_hash(body)
        return body


def effective_sample_size(weights: Sequence[float] | None, n: int) -> float:
    if n <= 0:
        return 0.0
    if not weights:
        return float(n)
    vals = [max(0.0, float(w)) for w in weights[:n]]
    if len(vals) < n:
        vals.extend([1.0] * (n - len(vals)))
    total = sum(vals)
    sq = sum(w * w for w in vals)
    if total <= 0.0 or sq <= 0.0:
        return 0.0
    return min(float(n), total * total / sq)


def _finite(values: Iterable[float]) -> list[float]:
    out: list[float] = []
    for value in values:
        try:
            x = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            out.append(x)
    return out


def fit_hierarchical_distribution(
    values: Sequence[float],
    *,
    prior_mean: float,
    prior_strength: float = 8.0,
    weights: Sequence[float] | None = None,
    count_like: bool = True,
    low_volume: bool = False,
) -> HierarchicalFit:
    vals = _finite(values)
    if not vals:
        return HierarchicalFit(
            family="PRIOR_ONLY",
            observed_mean=float(prior_mean),
            observed_variance=0.0,
            posterior_mean=float(prior_mean),
            prior_mean=float(prior_mean),
            effective_n=0.0,
            zero_rate=0.0,
            dispersion=None,
            epistemic_sd=float("inf"),
        )

    obs_mean = mean(vals)
    obs_var = pvariance(vals) if len(vals) >= 2 else max(abs(obs_mean), 1.0)
    ess = effective_sample_size(weights, len(vals))
    posterior = empirical_bayes_shrink(
        float(obs_mean), max(ess, 1e-9), float(prior_mean), max(float(prior_strength), 1e-9)
    )
    zero_rate = sum(abs(v) <= 1e-12 for v in vals) / len(vals)

    dispersion: float | None = None
    if count_like and obs_mean > 1e-9 and obs_var > obs_mean:
        # NB2: Var(Y)=mu+alpha*mu^2
        dispersion = max(0.0, (obs_var - obs_mean) / (obs_mean * obs_mean))

    poisson_variance_gap = abs(obs_var - max(obs_mean, 0.0)) / max(1.0, abs(obs_mean))
    expected_zero_poisson = math.exp(-max(obs_mean, 0.0)) if count_like else 0.0
    excess_zero = zero_rate - expected_zero_poisson

    if low_volume and count_like and excess_zero > 0.10:
        family = "HURDLE_COUNT"
    elif count_like and dispersion is not None and dispersion > 0.05:
        family = "NEGATIVE_BINOMIAL"
    elif count_like and poisson_variance_gap <= 0.25:
        family = "POISSON"
    elif count_like:
        family = "EMPIRICAL_COUNT"
    else:
        family = "EMPIRICAL_CONTINUOUS"

    posterior_var = max(obs_var, 1e-9) / max(ess, 1.0)
    prior_var = max(abs(float(prior_mean)), 1.0) / max(float(prior_strength), 1.0)
    epistemic_sd = math.sqrt(1.0 / (1.0 / posterior_var + 1.0 / prior_var))

    return HierarchicalFit(
        family=family,
        observed_mean=float(obs_mean),
        observed_variance=float(obs_var),
        posterior_mean=float(posterior),
        prior_mean=float(prior_mean),
        effective_n=float(ess),
        zero_rate=float(zero_rate),
        dispersion=None if dispersion is None else float(dispersion),
        epistemic_sd=float(epistemic_sd),
    )


def uncertainty_interval(
    fit: HierarchicalFit,
    *,
    z: float = 1.6448536269514722,
) -> tuple[float, float]:
    if not math.isfinite(fit.epistemic_sd):
        return (float("-inf"), float("inf"))
    half = abs(float(z)) * fit.epistemic_sd
    return fit.posterior_mean - half, fit.posterior_mean + half


__all__ = [
    "DIST_VERSION",
    "HierarchicalFit",
    "effective_sample_size",
    "fit_hierarchical_distribution",
    "uncertainty_interval",
]
