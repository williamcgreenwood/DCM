"""Measured backpressure and adaptive Monte Carlo admission.

Never skip props or lower evidentiary gates to save resources. Resource pressure
may checkpoint work, but serious candidates receive additional worlds when
classification uncertainty remains material.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass
class Governor:
    fast_worlds: int = 256
    serious_worlds: int = 2048
    ceiling_worlds: int = 8192
    mc_se_target: float = 0.008
    deadline_blocked: bool = False

    @property
    def max_worlds(self) -> int:
        """Backwards-compatible name for the initial/fast world count."""
        return self.fast_worlds

    def monte_carlo_se(self, probability: float, n: int) -> float:
        p = max(0.0, min(1.0, float(probability)))
        return sqrt(max(0.0, p * (1.0 - p)) / max(1, int(n)))

    def next_world_count(
        self,
        *,
        current: int,
        selected_probability: float,
        decision_threshold: float,
        production_selectable: bool,
    ) -> int:
        if self.deadline_blocked or not production_selectable:
            return current
        se = self.monte_carlo_se(selected_probability, current)
        distance = abs(float(selected_probability) - float(decision_threshold))

        if current < self.serious_worlds and (
            selected_probability >= 0.52 or distance <= max(0.06, 3.0 * se)
        ):
            return self.serious_worlds

        if (
            current < self.ceiling_worlds
            and se > self.mc_se_target
            and distance <= max(0.035, 2.5 * se)
        ):
            return min(self.ceiling_worlds, max(current * 2, self.serious_worlds))

        return current

    def pressure_steps(self) -> list[str]:
        return [
            "stop_new_admission",
            "finish_active_atomic_batches",
            "evict_safe_caches",
            "release_completed_objects",
            "lower_concurrency",
            "compress_noncritical_diagnostics",
            "spill_eligible_immutable",
            "checkpoint",
            "resume_bounded_batches",
            "deadline_block_explicitly",
        ]
