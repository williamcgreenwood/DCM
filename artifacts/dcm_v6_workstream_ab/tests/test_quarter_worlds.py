"""Quarter worlds: shares sum to game totals; threshold counts; fail closed if incomplete."""
from __future__ import annotations

import random

import pytest

from dcm.model.market_derive import derive_market
from dcm.model.quarter_worlds import (
    QuarterPluginIncomplete,
    attach_quarter_state,
    count_quarters_at_least,
    split_game_to_quarters,
)
from dcm.model.worlds import sample_basketball, simulate_player_worlds, value_from_stats


def test_quarter_shares_sum_to_game_points_and_minutes():
    rng = random.Random(21)
    for pts in (0, 7, 18, 27, 41):
        for minutes in (0.0, 12.5, 28.0, 39.4):
            q = split_game_to_quarters(rng, pts=pts, minutes=minutes)
            assert sum(q["pts"]) == pts
            assert abs(sum(q["minutes"]) - minutes) < 1e-9
            assert len(q["pts"]) == 4
            assert len(q["minutes"]) == 4
            assert abs(sum(q["pts_shares"]) - 1.0) < 1e-9


def test_threshold_counts_quarters_with_3plus_pts():
    q = {"pts": [8, 2, 5, 1], "minutes": [10, 10, 10, 10]}
    assert count_quarters_at_least(q, "pts", 3) == 2
    assert count_quarters_at_least(q, "pts", 6) == 1
    rng = random.Random(9)
    world = sample_basketball(rng, 34.0)
    attach_quarter_state(world, random.Random(10))
    n = derive_market(world, "qtrs_w_3plus_pts")
    assert 0 <= n <= 4
    assert n == count_quarters_at_least(world["_quarters"], "pts", 3)


def test_do_not_infer_quarters_from_full_game_gaussian_alone():
    rng = random.Random(3)
    world = sample_basketball(rng, 30.0)
    world.pop("_quarters", None)
    with pytest.raises(QuarterPluginIncomplete):
        derive_market(world, "qtrs_w_3plus_pts")
    with pytest.raises(QuarterPluginIncomplete):
        derive_market(world, "pts", board_id="1H")


def test_half_and_quarter_pts_sum_to_game():
    rng = random.Random(14)
    world = sample_basketball(rng, 36.0)
    attach_quarter_state(world, random.Random(15))
    q1 = derive_market(world, "pts", board_id="Q1")
    q2 = derive_market(world, "pts", board_id="Q2")
    q3 = derive_market(world, "pts", board_id="Q3")
    q4 = derive_market(world, "pts", board_id="Q4")
    assert abs((q1 + q2 + q3 + q4) - world["pts"]) < 1e-9
    assert abs(derive_market(world, "pts", board_id="1H") - (q1 + q2)) < 1e-9
    assert abs(derive_market(world, "pts", board_id="2H") - (q3 + q4)) < 1e-9


def test_quarter_reb_board_fails_closed():
    rng = random.Random(6)
    world = sample_basketball(rng, 30.0)
    attach_quarter_state(world, random.Random(7))
    with pytest.raises(QuarterPluginIncomplete):
        derive_market(world, "reb", board_id="Q1")


def test_simulate_player_worlds_attaches_quarters():
    row = {
        "playerId": "P", "eventId": "E", "sportFamily": "basketball",
        "league": "WNBA", "teamId": "DAL",
    }
    worlds = simulate_player_worlds(row, n=8, seed="q-attach")
    for w in worlds:
        assert "_quarters" in w
        assert sum(w["_quarters"]["pts"]) == int(round(w["pts"]))
        assert abs(value_from_stats("qtrs_w_3plus_pts", w) - count_quarters_at_least(w["_quarters"], "pts", 3)) < 1e-9
