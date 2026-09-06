"""PLAYABLE / LEAN / PASS / TRAP. Demon is demotion-only."""

from __future__ import annotations


def grade(
    *,
    selected_p: float,
    lower_bound: float,
    demon: bool,
    fragility: float,
    robustness_area: float = 0.0,
    elasticity: float = 0.0,
    false_sign: float = 0.0,
) -> str:
    if demon:
        # Stricter multi-dimension gate. Never promote PASS → PLAYABLE because Demon.
        if (
            selected_p >= 0.63
            and lower_bound >= 0.56
            and robustness_area >= 1.0
            and elasticity <= 0.25
            and false_sign <= 0.22
            and fragility <= 0.4
        ):
            return "PLAYABLE"
        if selected_p >= 0.56:
            return "LEAN"
        if selected_p < 0.46:
            return "TRAP"
        return "PASS"
    if fragility > 0.55:
        return "LEAN" if selected_p > 0.55 else "TRAP"
    if selected_p >= 0.58 and lower_bound >= 0.52:
        return "PLAYABLE"
    if selected_p >= 0.54:
        return "LEAN"
    if selected_p < 0.46:
        return "TRAP"
    return "PASS"
