"""Adaptive freshness equations from DCM6-ROS-EG-001 §11."""
from dcm.research.freshness import (
    BASE_HALF_LIFE_HOURS,
    effective_half_life,
    evaluate_freshness,
    event_multiplier,
    freshness_score,
)


def test_historical_facts_do_not_expire():
    ev = evaluate_freshness(
        claim_type="HISTORICAL_PERFORMANCE",
        age_hours=10_000.0,
        hours_to_event=1.0,
        volatility="CRITICAL",
        status="GAME_TIME_DECISION",
    )
    assert ev["historicalFact"] is True
    assert ev["effectiveHalfLifeHours"] is None
    assert ev["freshness"] == 1.0
    assert ev["stale"] is False


def test_event_multiplier_piecewise():
    assert event_multiplier(48) == 1.0
    assert event_multiplier(24) == 1.0
    assert abs(event_multiplier(12) - (0.20 + 0.80 * 0.5)) < 1e-12
    assert event_multiplier(-1) == 0.20


def test_status_claim_decays_near_tipoff():
    far = freshness_score(
        age_hours=3.0,
        category="current_status",
        hours_to_event=48.0,
        volatility="STABLE",
        status="CONFIRMED",
    )
    near = freshness_score(
        age_hours=3.0,
        category="current_status",
        hours_to_event=2.0,
        volatility="STABLE",
        status="CONFIRMED",
    )
    gtd = freshness_score(
        age_hours=3.0,
        category="current_status",
        hours_to_event=2.0,
        volatility="CRITICAL",
        status="GAME_TIME_DECISION",
    )
    assert far > near > gtd
    assert far > 0.4
    assert gtd < 0.1


def test_effective_half_life_matches_spec_defaults():
    h = effective_half_life(category="lineup_depth_chart", hours_to_event=48.0)
    assert h == BASE_HALF_LIFE_HOURS["lineup_depth_chart"]
    compressed = effective_half_life(
        category="lineup_depth_chart",
        hours_to_event=0.0,
        volatility="HIGH",
        status="QUESTIONABLE",
    )
    assert compressed is not None
    assert compressed < h * 0.2


def test_evaluate_falls_back_to_stored_when_age_missing():
    ev = evaluate_freshness(claim_type="STATUS", stored_freshness=0.2)
    assert ev["source"] == "stored"
    assert ev["stale"] is True
    assert ev["freshness"] == 0.2
