"""Exact push-aware minimum-guarantee economics.

The payout table is authoritative. This module never reconstructs a PrizePicks
payout from a card-size label and never treats a push as a win. A push removes
one pick from the payout tier; correlated portfolios should use the aligned
world-outcome evaluator rather than independent marginals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from dcm.platform.prizepicks.payouts import minimum_guarantee_return


class PayoutPricingError(RuntimeError):
    pass


@dataclass(frozen=True)
class LegOutcomeProbabilities:
    win: float
    loss: float
    push: float = 0.0

    def __post_init__(self) -> None:
        values = (float(self.win), float(self.loss), float(self.push))
        if any(value < 0.0 or value > 1.0 for value in values):
            raise PayoutPricingError("OUTCOME_PROBABILITY_OUT_OF_RANGE")
        if abs(sum(values) - 1.0) > 1e-9:
            raise PayoutPricingError("OUTCOME_PROBABILITY_SIMPLEX_FAILURE")


def _return_for_state(table_hash: str, *, non_push_count: int, win_count: int) -> float:
    value = minimum_guarantee_return(table_hash, non_push_count, win_count)
    if value is None:
        raise PayoutPricingError(
            f"UNKNOWN_PAYOUT_STATE:tier={non_push_count}:wins={win_count}:hash={table_hash[:12]}"
        )
    return float(value)


def independent_state_distribution(
    legs: Sequence[LegOutcomeProbabilities],
) -> dict[tuple[int, int], float]:
    """Return P(non-push tier count, wins) under independent marginals."""
    states: dict[tuple[int, int], float] = {(0, 0): 1.0}
    for leg in legs:
        nxt: dict[tuple[int, int], float] = {}
        for (tier, wins), probability in states.items():
            for key, mass in (
                ((tier + 1, wins + 1), leg.win),
                ((tier + 1, wins), leg.loss),
                ((tier, wins), leg.push),
            ):
                if mass <= 0.0:
                    continue
                nxt[key] = nxt.get(key, 0.0) + probability * mass
        states = nxt
    total = sum(states.values())
    if abs(total - 1.0) > 1e-9:
        raise PayoutPricingError("OUTCOME_STATE_MASS_FAILURE")
    return states


def expected_return_independent(
    *,
    table_hash: str,
    legs: Sequence[LegOutcomeProbabilities],
    stake: float = 1.0,
) -> dict[str, float | int | str]:
    """Exact expected table return for independent W/L/P marginals.

    The table stores return amounts in its own captured units. The stake is used
    only for net EV = expected return - stake; callers must ensure the captured
    table and stake use the same unit convention.
    """
    if not legs:
        raise PayoutPricingError("LEGS_REQUIRED")
    if stake < 0:
        raise PayoutPricingError("STAKE_NEGATIVE")
    states = independent_state_distribution(legs)
    gross = 0.0
    for (tier, wins), probability in states.items():
        gross += probability * _return_for_state(
            table_hash,
            non_push_count=tier,
            win_count=wins,
        )
    return {
        "method": "EXACT_INDEPENDENT_WLP_ENUMERATION",
        "legCount": len(legs),
        "expectedReturn": gross,
        "stake": float(stake),
        "expectedValue": gross - float(stake),
        "stateCount": len(states),
    }


def expected_return_from_worlds(
    *,
    table_hash: str,
    worlds: Iterable[Sequence[str]],
    stake: float = 1.0,
) -> dict[str, float | int | str]:
    """Price aligned joint W/L/P worlds without an independence assumption."""
    count = 0
    gross = 0.0
    leg_count: int | None = None
    for raw_world in worlds:
        world = [str(value).upper() for value in raw_world]
        if leg_count is None:
            leg_count = len(world)
        elif len(world) != leg_count:
            raise PayoutPricingError("WORLD_LEG_COUNT_MISMATCH")
        if not world:
            raise PayoutPricingError("WORLD_EMPTY")
        if any(value not in {"WIN", "LOSS", "PUSH"} for value in world):
            raise PayoutPricingError("WORLD_OUTCOME_INVALID")
        wins = sum(value == "WIN" for value in world)
        non_push = sum(value != "PUSH" for value in world)
        gross += _return_for_state(
            table_hash,
            non_push_count=non_push,
            win_count=wins,
        )
        count += 1
    if count == 0 or leg_count is None:
        raise PayoutPricingError("WORLDS_REQUIRED")
    mean_return = gross / count
    return {
        "method": "EMPIRICAL_JOINT_WLP_WORLDS",
        "legCount": leg_count,
        "worldCount": count,
        "expectedReturn": mean_return,
        "stake": float(stake),
        "expectedValue": mean_return - float(stake),
    }


def probabilities_from_mapping(row: Mapping[str, float]) -> LegOutcomeProbabilities:
    win = float(row.get("win", row.get("pWin", 0.0)))
    push = float(row.get("push", row.get("pPush", 0.0)))
    loss_raw = row.get("loss", row.get("pLoss"))
    loss = float(loss_raw) if loss_raw is not None else 1.0 - win - push
    return LegOutcomeProbabilities(win=win, loss=loss, push=push)


__all__ = [
    "LegOutcomeProbabilities",
    "PayoutPricingError",
    "expected_return_from_worlds",
    "expected_return_independent",
    "independent_state_distribution",
    "probabilities_from_mapping",
]
