"""Regression tests: unsupported inverses, future leakage and joint EV."""
from __future__ import annotations

import pytest

from dcm.model.inverse_gate import HistoricalObservation, audit_direction
from dcm.model.joint_value import WorldSelection, evaluate_shared_world_portfolio

CUTOFF = "2026-10-13T23:59:00+00:00"


def observations(values):
    return [
        HistoricalObservation(f"event-{i}", f"2026-09-{i+1:02d}T20:00:00+00:00", float(v))
        for i, v in enumerate(values)
    ]


def test_anderson_inversion_requires_independent_evidence():
    # Four of five prior scores were OVER 14.5; one dramatic low is not a regime.
    result = audit_direction(
        side="LOWER", line=14.5,
        observations=observations([16.7, 27.7, 21.9, 14.8, 2.9]),
        cutoff_utc=CUTOFF, exact_offer_verified=True,
    )
    assert result.status == "BLOCKED_UNSUPPORTED_INVERSE"
    assert result.successes == 1
    assert result.beta22_diagnostic == pytest.approx(3 / 9)


def test_legitimate_high_base_rate_does_not_certify_prediction():
    result = audit_direction(
        side="HIGHER", line=12.5,
        observations=observations([10, 13, 19, 14, 16]),
        cutoff_utc=CUTOFF, exact_offer_verified=True,
    )
    assert result.status == "SHADOW_DIRECTION_ONLY"
    assert result.beta22_diagnostic == pytest.approx(6 / 9)


def test_rejects_future_results_and_duplicate_games():
    future = [HistoricalObservation("post", "2026-10-14T01:00:00Z", 33.8)]
    with pytest.raises(ValueError, match="POST_CUTOFF"):
        audit_direction(
            side="LOWER", line=14.5, observations=future,
            cutoff_utc=CUTOFF, exact_offer_verified=True,
        )
    with pytest.raises(ValueError, match="DUPLICATE"):
        audit_direction(
            side="LOWER", line=14.5,
            observations=observations([1, 2]) + observations([3]),
            cutoff_utc=CUTOFF, exact_offer_verified=True,
        )


def test_joint_worlds_do_not_multiply_independent_marginals():
    picks = [
        WorldSelection("p1", "e", "a", "yards", 10.5, "HIGHER"),
        WorldSelection("p2", "e", "b", "yards", 10.5, "HIGHER"),
    ]
    # Perfect correlation: both win together, not marginal 0.5 * 0.5.
    worlds = [
        {"a": {"yards": 20}, "b": {"yards": 20}},
        {"a": {"yards": 20}, "b": {"yards": 20}},
        {"a": {"yards": 0}, "b": {"yards": 0}},
        {"a": {"yards": 0}, "b": {"yards": 0}},
    ]
    r = evaluate_shared_world_portfolio(
        event_id="e", worlds=worlds, selections=picks,
        gross_multipliers_by_wins={0: 0.0, 1: 0.0, 2: 3.0},
        stake=20.0, payout_rules_verified=True, joint_model_calibrated=False,
    )
    assert r.exact_win_count_probabilities[2] == 0.5
    assert r.exact_win_count_probabilities[1] == 0.0
    assert r.estimated_net_ev == pytest.approx(10.0)
    assert r.ev_certified is False


def test_pushes_block_ev_until_reversion_rules_verified():
    picks = [WorldSelection("p1", "e", "a", "pass_att", 29.0, "LOWER")]
    r = evaluate_shared_world_portfolio(
        event_id="e", worlds=[{"a": {"pass_att": 29}}],
        selections=picks, gross_multipliers_by_wins={0: 0, 1: 1.5},
        stake=20.0, payout_rules_verified=True, joint_model_calibrated=True,
    )
    assert "PUSH_REVERSION_ADAPTER_REQUIRED" in r.blockers
    assert r.estimated_net_ev is None
    assert not r.ev_certified


def test_missing_offer_cannot_authorize_inverse():
    r = audit_direction(
        side="LOWER", line=14.5, observations=observations([2, 15, 20, 3, 12]),
        cutoff_utc=CUTOFF, exact_offer_verified=False,
    )
    assert r.status == "BLOCKED_UNVERIFIED_OFFER"
