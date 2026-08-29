"""Measured backpressure. Never skip props or drop uncertainty to save resources."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Governor:
    max_worlds: int = 64
    serious_worlds: int = 256
    deadline_blocked: bool = False

    def worlds_for_tier(self, tier: int) -> int:
        if self.deadline_blocked:
            return min(32, self.max_worlds)
        if tier <= 2:
            return self.max_worlds
        if tier == 3:
            return self.serious_worlds
        return self.serious_worlds

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
