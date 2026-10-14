"""Joint portfolio payout analysis from *shared* simulated EventWorlds.

Never estimates a joint probability by multiplying independent marginals.
The caller is responsible for providing calibrated, cutoff-safe EventWorlds
and the exact verified provider payout rules before EV can be certified.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal, Mapping, Sequence

Side = Literal["HIGHER", "LOWER"]


@dataclass(frozen=True)
class WorldSelection:
    selection_id: str
    event_id: str
    subject_id: str
    statistic: str
    line: float
    side: Side


@dataclass(frozen=True)
class JointValueResult:
    state: str
    n_worlds: int
    exact_win_count_probabilities: dict[int, float]
    push_worlds: int
    estimated_net_ev: float | None
    estimated_roi: float | None
    ev_certified: bool
    blockers: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_shared_world_portfolio(
    *,
    event_id: str,
    worlds: Sequence[Mapping[str, Mapping[str, float]]],
    selections: Sequence[WorldSelection],
    gross_multipliers_by_wins: Mapping[int, float],
    stake: float,
    payout_rules_verified: bool,
    joint_model_calibrated: bool,
) -> JointValueResult:
    """Evaluate correlated outcomes; block certification if inputs lack proof.

    Each world must contain all players and statistics for the *same* event.
    Pushes require an explicit reversion-rule adapter (not present here).
    """
    if not event_id or not selections:
        raise ValueError("EVENT_AND_SELECTIONS_REQUIRED")
    if not isfinite(stake) or stake <= 0:
        raise ValueError("INVALID_STAKE")
    if any(s.event_id != event_id for s in selections):
        raise ValueError("CROSS_EVENT_WORLD_NOT_SUPPORTED")
    if len({s.selection_id for s in selections}) != len(selections):
        raise ValueError("DUPLICATE_SELECTION_ID")
    if len({s.subject_id for s in selections}) != len(selections):
        # The same subject can carry multiple props, but this implementation
        # currently enforces the user's unique-player constraint.
        raise ValueError("DUPLICATE_SUBJECT_ID")
    if not worlds:
        return JointValueResult("BLOCKED_NO_EVENT_WORLDS", 0, {}, 0, None, None, False, ("NO_WORLD_SAMPLES",))
    counts = {i: 0 for i in range(len(selections) + 1)}
    pushes = 0
    for world in worlds:
        wins = 0
        has_push = False
        for sel in selections:
            if sel.side not in {"HIGHER", "LOWER"} or not isfinite(sel.line):
                raise ValueError("INVALID_SELECTION")
            if sel.subject_id not in world or sel.statistic not in world[sel.subject_id]:
                raise ValueError("INCOMPLETE_EVENT_WORLD")
            actual = float(world[sel.subject_id][sel.statistic])
            if not isfinite(actual):
                raise ValueError("INVALID_WORLD_VALUE")
            if actual == sel.line:
                has_push = True
            elif (actual > sel.line) == (sel.side == "HIGHER"):
                wins += 1
        if has_push:
            pushes += 1
        else:
            counts[wins] += 1
    n = len(worlds)
    dist = {k: v / n for k, v in counts.items()}
    blockers: list[str] = []
    if pushes:
        blockers.append("PUSH_REVERSION_ADAPTER_REQUIRED")
    if not payout_rules_verified:
        blockers.append("PAYOUT_RULES_UNVERIFIED")
    if not joint_model_calibrated:
        blockers.append("JOINT_MODEL_UNCALIBRATED")
    if not gross_multipliers_by_wins or any(
        k not in gross_multipliers_by_wins or
        not isfinite(float(gross_multipliers_by_wins[k])) or
        gross_multipliers_by_wins[k] < 0 for k in counts
    ):
        blockers.append("PAYOUT_TABLE_INCOMPLETE")
    # No fabricated EV when settlement or payout rules are unavailable.
    if pushes or not payout_rules_verified or "PAYOUT_TABLE_INCOMPLETE" in blockers:
        return JointValueResult(
            "EV_BLOCKED", n, dist, pushes, None, None, False, tuple(blockers)
        )
    gross = sum(
        dist[k] * stake * float(gross_multipliers_by_wins[k])
        for k in counts
    )
    net = gross - stake
    certified = joint_model_calibrated
    return JointValueResult(
        "EV_CERTIFIED" if certified else "EV_DIAGNOSTIC_ONLY",
        n, dist, 0, net, net / stake, certified, tuple(blockers),
    )
