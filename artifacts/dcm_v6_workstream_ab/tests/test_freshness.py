"""Adaptive freshness equations from DCM6-ROS-EG-001 §11."""
import pytest

from dcm.research.freshness import (
    BASE_HALF_LIFE_HOURS,
    FreshnessPolicyError,
    category_for,
    effective_half_life,
    evaluate_freshness,
    event_multiplier,
    freshness_score,
    is_immutable_completed_fact,
    normalize_status,
)


def test_completed_game_facts_do_not_expire():
    ev = evaluate_freshness(
        claim_type="HISTORICAL_PERFORMANCE",
        age_hours=10_000.0,
        hours_to_event=1.0,
        volatility="CRITICAL",
        status="GAME_TIME_DECISION",
    )
    assert ev["ok"] is True
    assert ev["historicalFact"] is True
    assert ev["effectiveHalfLifeHours"] is None
    assert ev["freshness"] == 1.0
    assert ev["stale"] is False


def test_season_recent_form_is_not_an_immutable_fact():
    assert is_immutable_completed_fact(category="season_recent_form", claim_type="SEASON_RECENT_FORM") is False
    ev = evaluate_freshness(
        claim_type="SEASON_RECENT_FORM",
        age_hours=400.0,
        hours_to_event=48.0,
        volatility="STABLE",
        status="CONFIRMED",
    )
    assert ev["historicalFact"] is False
    assert ev["stale"] is True


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
        claim_type="STATUS",
    )
    near = freshness_score(
        age_hours=3.0,
        category="current_status",
        hours_to_event=2.0,
        volatility="STABLE",
        status="CONFIRMED",
        claim_type="STATUS",
    )
    gtd = freshness_score(
        age_hours=3.0,
        category="current_status",
        hours_to_event=2.0,
        volatility="CRITICAL",
        status="GAME_TIME_DECISION",
        claim_type="STATUS",
    )
    assert far > near > gtd
    assert far > 0.4
    assert gtd < 0.1


def test_gtd_is_governed_alias_for_game_time_decision():
    assert normalize_status("GTD") == "GAME_TIME_DECISION"
    a = effective_half_life(category="current_status", status="GTD", volatility="STABLE")
    b = effective_half_life(category="current_status", status="GAME_TIME_DECISION", volatility="STABLE")
    assert a == b


def test_unknown_inputs_fail_closed():
    with pytest.raises(FreshnessPolicyError):
        normalize_status("OUT")
    with pytest.raises(FreshnessPolicyError):
        category_for("NOT_A_REAL_CLAIM")
    ev = evaluate_freshness(claim_type="NOPE", age_hours=1.0, volatility="STABLE", status="CONFIRMED")
    assert ev["ok"] is False
    assert ev["unresolved"] is True


def test_efficiency_is_not_mapped_to_opportunity_category():
    assert category_for("EFFICIENCY") == "efficiency"
    assert category_for("OPPORTUNITY") == "opportunity"


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
