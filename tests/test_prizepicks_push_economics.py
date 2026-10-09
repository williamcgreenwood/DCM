from __future__ import annotations

import pytest

from dcm.platform.prizepicks.economics import (
    LegOutcomeProbabilities,
    PayoutPricingError,
    expected_return_from_worlds,
    expected_return_independent,
)
from dcm.platform.prizepicks.payouts import register_minimum_guarantee_table


def _table() -> str:
    # Test-only captured return table. A push removes a pick from the payout
    # tier: two wins use the 2-pick row; one win + one push uses the 1-pick row.
    return register_minimum_guarantee_table(
        {
            (2, 2): 3.0,
            (2, 1): 1.5,
            (2, 0): 0.0,
            (1, 1): 1.0,
            (1, 0): 0.0,
            (0, 0): 1.0,
        },
        label="P0_PUSH_ECONOMICS_TEST",
    )


def test_push_degrades_payout_tier_in_exact_independent_pricer() -> None:
    table_hash = _table()
    all_wins = expected_return_independent(
        table_hash=table_hash,
        legs=[
            LegOutcomeProbabilities(win=1.0, loss=0.0, push=0.0),
            LegOutcomeProbabilities(win=1.0, loss=0.0, push=0.0),
        ],
        stake=1.0,
    )
    one_push = expected_return_independent(
        table_hash=table_hash,
        legs=[
            LegOutcomeProbabilities(win=1.0, loss=0.0, push=0.0),
            LegOutcomeProbabilities(win=0.0, loss=0.0, push=1.0),
        ],
        stake=1.0,
    )
    assert all_wins["expectedReturn"] == 3.0
    assert one_push["expectedReturn"] == 1.0
    assert one_push["expectedValue"] == 0.0


def test_joint_world_pricer_uses_aligned_wlp_states_without_independence() -> None:
    table_hash = _table()
    priced = expected_return_from_worlds(
        table_hash=table_hash,
        worlds=[
            ["WIN", "WIN"],
            ["WIN", "PUSH"],
            ["LOSS", "LOSS"],
            ["WIN", "LOSS"],
        ],
        stake=1.0,
    )
    assert priced["worldCount"] == 4
    assert priced["expectedReturn"] == pytest.approx((3.0 + 1.0 + 0.0 + 1.5) / 4.0)


def test_unknown_payout_state_fails_closed() -> None:
    table_hash = register_minimum_guarantee_table(
        {(2, 2): 3.0},
        label="INCOMPLETE_TEST_TABLE",
    )
    with pytest.raises(PayoutPricingError, match="UNKNOWN_PAYOUT_STATE"):
        expected_return_independent(
            table_hash=table_hash,
            legs=[
                LegOutcomeProbabilities(win=1.0, loss=0.0, push=0.0),
                LegOutcomeProbabilities(win=0.0, loss=0.0, push=1.0),
            ],
        )
