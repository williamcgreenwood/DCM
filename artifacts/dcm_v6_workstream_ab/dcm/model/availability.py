"""Availability-state mixtures for PROBABLE/QUESTIONABLE.

QUESTIONABLE/DOUBTFUL remain PLAYABLE-hard-excluded (Bonner / P0): mixture
entropy is treated as excessive. PROBABLE is mixed but may stay PLAYABLE
when P(play) is high. The mixture is always recorded so later learning can
see the availability path that was taken.
"""
from __future__ import annotations

import math
from typing import Any

from dcm.contracts.hashes import content_hash


PLAY_PRIORS = {
    "ACTIVE": 0.99,
    "AVAILABLE": 0.99,
    "EXPECTED_ACTIVE": 0.97,
    "PROBABLE": 0.85,
    "QUESTIONABLE": 0.55,
    "GTD": 0.50,
    "GAME_TIME_DECISION": 0.50,
    "LIMITED": 0.60,
    "DOUBTFUL": 0.20,
    "OUT": 0.02,
    "INACTIVE": 0.01,
    "SUSPENDED": 0.00,
    "UNKNOWN": 0.50,
}
# PLAYABLE is forbidden when mixture entropy or sit-probability is too high.
EXCESSIVE_SIT_P = 0.25
EXCESSIVE_ENTROPY = 0.70


def _entropy(p_play: float) -> float:
    p = min(1.0 - 1e-9, max(1e-9, p_play))
    q = 1.0 - p
    return float(-(p * math.log2(p) + q * math.log2(q)))


def availability_mixture(status: str | None) -> dict[str, Any]:
    label = str(status or "UNKNOWN").strip().upper() or "UNKNOWN"
    p_play = float(PLAY_PRIORS.get(label, PLAY_PRIORS["UNKNOWN"]))
    p_sit = 1.0 - p_play
    entropy = _entropy(p_play)
    excessive = p_sit >= EXCESSIVE_SIT_P or entropy >= EXCESSIVE_ENTROPY or label in {
        "QUESTIONABLE", "GTD", "GAME_TIME_DECISION", "DOUBTFUL", "LIMITED", "OUT",
        "INACTIVE", "SUSPENDED", "UNKNOWN",
    }
    body = {
        "schema": "pillars_dcm.availability_mixture.v1",
        "status": label,
        "pPlay": p_play,
        "pSit": p_sit,
        "entropyBits": entropy,
        "minutesScaleIfSit": 0.0,
        "excessiveUncertainty": excessive,
        "playableBlockedByMixture": excessive,
        "components": [
            {"state": "PLAY", "weight": p_play},
            {"state": "SIT", "weight": p_sit},
        ],
        "note": "QUESTIONABLE/DOUBTFUL stay PLAYABLE-excluded; mixture is recorded for audit/learning.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
