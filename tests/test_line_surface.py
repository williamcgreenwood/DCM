"""Unclamped directional line surfaces for serious (PLAYABLE/LEAN) candidates."""
from __future__ import annotations

from dcm.model.line_surface import surface


def test_tolerance_positive_when_distribution_clears_soft_line_more():
    values = [28.0 + i * 0.05 for i in range(64)]
    surf = surface(values, 20.5, side="MORE", playable_p=0.58)
    assert surf["offered_line"] == 20.5
    assert surf["true_unclamped_line_tolerance"] > 0
    assert surf["playable_break_line"] > 20.5
    assert surf["break_even_line"] > 20.5
    assert surf["robustness_area"] > 0
    assert surf["edge_elasticity"] >= 0
    for key in (
        "offered_line", "break_even_line", "playable_break_line",
        "true_unclamped_line_tolerance", "edge_elasticity", "robustness_area",
    ):
        assert key in surf


def test_tolerance_positive_when_distribution_clears_soft_line_less():
    values = [10.0 + (i % 3) * 0.2 for i in range(64)]
    surf = surface(values, 20.5, side="LESS", playable_p=0.58)
    assert surf["true_unclamped_line_tolerance"] > 0
    assert surf["playable_break_line"] < 20.5
    assert surf["robustness_area"] > 0


def test_tolerance_zero_when_worlds_do_not_clear_line():
    values = [18.0] * 32
    surf = surface(values, 20.5, side="MORE", playable_p=0.58)
    assert surf["true_unclamped_line_tolerance"] == 0.0
    assert surf["robustness_area"] == 0.0
