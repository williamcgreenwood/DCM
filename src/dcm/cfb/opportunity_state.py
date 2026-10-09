"""CFB score-state opportunity priors consumed by the shared EventWorld.

This module models opportunity, not outcome efficiency.  State probabilities are
priors/inputs, never forecast probabilities.  All modifiers are bounded and
auditable; no weather or spread threshold is allowed to hard-overwrite play
calling.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from dcm.contracts.hashes import content_hash

STATE_VERSION = "CFB_SCORE_STATE_OPPORTUNITY_V1_2026-10-09"
STATES = ("LEAD", "NEUTRAL", "TRAIL", "BLOWOUT_LEAD")


@dataclass(frozen=True)
class CFBStateOpportunity:
    state_probabilities: dict[str, float]
    expected_pass_rate: float
    starter_participation: float
    epistemic_uncertainty: float
    version: str = STATE_VERSION

    def to_dict(self) -> dict[str, object]:
        body: dict[str, object] = {
            "stateProbabilities": dict(self.state_probabilities),
            "expectedPassRate": self.expected_pass_rate,
            "starterParticipation": self.starter_participation,
            "epistemicUncertainty": self.epistemic_uncertainty,
            "version": self.version,
        }
        body["contentHash"] = content_hash(body)
        return body


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def normalize_state_probabilities(values: Mapping[str, float] | None) -> dict[str, float]:
    raw = {state: max(0.0, float((values or {}).get(state, 0.0))) for state in STATES}
    total = sum(raw.values())
    if total <= 0.0:
        return {"LEAD": 0.20, "NEUTRAL": 0.50, "TRAIL": 0.20, "BLOWOUT_LEAD": 0.10}
    return {key: value / total for key, value in raw.items()}


def spread_state_prior(spread: float | None) -> dict[str, float]:
    """Smooth pregame script prior from team-perspective spread.

    Negative spread means favored.  This is only a prior over game states; the
    EventWorld may replace it with stronger pre-cutoff state evidence.
    """
    if spread is None or not math.isfinite(float(spread)):
        return normalize_state_probabilities(None)
    s = float(spread)
    favorite = 1.0 / (1.0 + math.exp(s / 6.5))
    underdog = 1.0 - favorite
    blowout = _clip((favorite - 0.5) * 0.55, 0.0, 0.30)
    lead = _clip(0.12 + favorite * 0.30, 0.08, 0.42)
    trail = _clip(0.12 + underdog * 0.32, 0.08, 0.44)
    neutral = max(0.10, 1.0 - lead - trail - blowout)
    return normalize_state_probabilities(
        {"LEAD": lead, "NEUTRAL": neutral, "TRAIL": trail, "BLOWOUT_LEAD": blowout}
    )


def state_opportunity(
    *,
    base_pass_rate: float,
    state_probabilities: Mapping[str, float] | None = None,
    spread: float | None = None,
    opponent_rush_defense_z: float = 0.0,
    time_remaining_fraction: float = 0.5,
    wind_mph: float | None = None,
    support_n: int = 0,
) -> CFBStateOpportunity:
    probs = normalize_state_probabilities(
        state_probabilities if state_probabilities is not None else spread_state_prior(spread)
    )
    base = _clip(base_pass_rate, 0.20, 0.82)
    rush_def = _clip(opponent_rush_defense_z, -3.0, 3.0)
    time_left = _clip(time_remaining_fraction, 0.0, 1.0)

    # Bounded state-conditioned deltas.  These are transparent priors and must
    # be prospectively validated before any predictive-promotion claim.
    state_rate = {
        "LEAD": base - 0.055,
        "NEUTRAL": base,
        "TRAIL": base + 0.105,
        "BLOWOUT_LEAD": base - 0.145,
    }
    expected = sum(probs[s] * state_rate[s] for s in STATES)
    expected += 0.015 * rush_def
    expected += 0.025 * (0.5 - time_left)

    # Weather is continuous and bounded, never a threshold override.
    if wind_mph is not None and math.isfinite(float(wind_mph)):
        wind = _clip(float(wind_mph), 0.0, 40.0)
        expected -= min(0.08, 0.0025 * max(0.0, wind - 8.0))

    starter_participation = 1.0 - 0.55 * probs["BLOWOUT_LEAD"]
    support = _clip(float(support_n) / 20.0, 0.0, 1.0)
    entropy = -sum(p * math.log(max(p, 1e-12)) for p in probs.values()) / math.log(len(STATES))
    epistemic = _clip((1.0 - support) * 0.22 + entropy * 0.08, 0.02, 0.35)

    return CFBStateOpportunity(
        state_probabilities=probs,
        expected_pass_rate=_clip(expected, 0.18, 0.85),
        starter_participation=_clip(starter_participation, 0.40, 1.0),
        epistemic_uncertainty=epistemic,
    )


__all__ = [
    "CFBStateOpportunity",
    "STATE_VERSION",
    "STATES",
    "normalize_state_probabilities",
    "spread_state_prior",
    "state_opportunity",
]
