"""Probability, reliability and uncertainty remain separate quantities."""
from __future__ import annotations

import math

# Reliability is not a probability. Slim/freeze rows keep these as separate keys.
PROBABILITY_CONTRACT_KEYS = (
    "selectedP",
    "evidenceSafeP",
    "lowerBound",
    "reliability",
    "dataQuality",
    "volatility",
    "fragility",
    "oodRisk",
    "falseSignRisk",
    "monteCarloSE",
    "epistemicUncertainty",
)
RELIABILITY_IS_NOT_PROBABILITY = True



def evidence_safe_probability(raw_p: float, *, support_n: int, data_quality: float, ood_risk: float, synthetic: bool) -> float:
    if synthetic:
        return 0.5 + (raw_p - 0.5) * 0.10
    support = min(1.0, max(0.0, support_n / 12.0))
    quality = math.sqrt(max(0.0, min(1.0, data_quality)))
    ood = 1.0 - 0.70 * max(0.0, min(1.0, ood_risk))
    g = max(0.05, min(1.0, support * quality * ood))
    return 0.5 + (raw_p - 0.5) * g


def wilson_lower_bound(successes: float, n: int, z: float = 1.6448536269514722) -> float:
    if n <= 0:
        return 0.0
    phat = max(0.0, min(1.0, successes / n))
    denom = 1.0 + z * z / n
    center = phat + z * z / (2.0 * n)
    rad = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n)
    return max(0.0, min(1.0, (center - rad) / denom))


def probability_bundle(
    *, raw_selected_p: float, n_worlds: int, support_n: int, data_quality: float,
    ood_risk: float, volatility: float, synthetic: bool,
) -> dict[str, float | str]:
    safe = evidence_safe_probability(
        raw_selected_p, support_n=support_n, data_quality=data_quality,
        ood_risk=ood_risk, synthetic=synthetic,
    )
    mc_se = math.sqrt(max(0.0, raw_selected_p * (1.0 - raw_selected_p)) / max(1, n_worlds))
    epistemic = min(0.45, (1.0 - min(1.0, support_n / 12.0)) * 0.20 + (1.0 - data_quality) * 0.15 + ood_risk * 0.15)
    aleatoric = min(1.0, max(0.0, volatility))
    successes = safe * max(1, n_worlds)
    lcb = wilson_lower_bound(successes, max(1, n_worlds))
    lcb = max(0.01, lcb - epistemic * 0.35)
    reliability = max(0.0, min(1.0, data_quality * (1.0 - ood_risk * 0.5) * min(1.0, support_n / 8.0)))
    false_sign = max(0.0, min(0.5, 0.5 - abs(safe - 0.5) + epistemic * 0.25))
    return {
        "raw_probability": raw_selected_p,
        "evidence_safe_probability": safe,
        "lower_bound": lcb,
        "monte_carlo_se": mc_se,
        "epistemic_uncertainty": epistemic,
        "aleatoric_uncertainty": aleatoric,
        "reliability": reliability,
        "false_sign_risk": false_sign,
        "calibration_state": "INACTIVE_ZERO_ELIGIBLE_SETTLEMENTS",
    }
