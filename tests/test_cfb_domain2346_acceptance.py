from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dcm.cfb.event_worlds import simulate_joint_cfb_event_worlds
from dcm.cfb.opportunity_state import STATE_VERSION, state_opportunity
from dcm.model.hierarchical_distribution import (
    effective_sample_size,
    fit_hierarchical_distribution,
    uncertainty_interval,
)
from dcm.model.uncertainty import probability_bundle
from dcm.validation.predictive_acceptance import (
    domain2_cfb_predictive_acceptance,
    domain3_distribution_calibration_acceptance,
    domain4_covariance_portfolio_acceptance,
    domain6_model_promotion_acceptance,
    predictive_superiority_claim,
)


def test_cfb_state_opportunity_is_bounded_and_trailing_raises_pass_rate() -> None:
    neutral = state_opportunity(
        base_pass_rate=0.54,
        state_probabilities={"NEUTRAL": 1.0},
        support_n=20,
    )
    trailing = state_opportunity(
        base_pass_rate=0.54,
        state_probabilities={"TRAIL": 1.0},
        support_n=20,
    )
    blowout = state_opportunity(
        base_pass_rate=0.54,
        state_probabilities={"BLOWOUT_LEAD": 1.0},
        support_n=20,
    )
    assert 0.18 <= blowout.expected_pass_rate < neutral.expected_pass_rate < trailing.expected_pass_rate <= 0.85
    assert blowout.starter_participation < neutral.starter_participation
    assert abs(sum(trailing.state_probabilities.values()) - 1.0) < 1e-12


def test_shared_cfb_eventworld_consumes_state_opportunity() -> None:
    specs = [{
        "row": {"eventId": "E1", "playerId": "QB1", "teamId": "T1", "role": "QB"},
        "snapshot": {
            "parameters": {
                "role": "QB",
                "pass_att_mean": 30.0,
                "rush_att_mean": 5.0,
                "completion_rate": 0.62,
                "pass_ypa": 7.5,
                "rush_ypa": 4.5,
                "pass_td_rate": 0.05,
                "int_rate": 0.025,
            }
        },
    }]
    out = simulate_joint_cfb_event_worlds(
        specs,
        n=8,
        seed="state-consumer-test",
        event_contexts=[{
            "pass_rate": 0.54,
            "scoreStateProbabilities": {"TRAIL": 1.0},
            "stateSupportN": 10,
        }],
        backend="reference",
    )
    assert out["meta"]["stateOpportunityVersion"] == STATE_VERSION
    assert len(out["worlds"]["QB1"]) == 8
    assert all(float(w["team_pass_att"]) >= 0 for w in out["worlds"]["QB1"])


def test_hierarchical_distribution_uses_ess_shrinkage_and_overdispersion() -> None:
    values = [0, 1, 2, 8, 0, 7, 1, 9, 0, 6]
    ess = effective_sample_size([1.0] * len(values), len(values))
    fit = fit_hierarchical_distribution(
        values,
        prior_mean=3.0,
        prior_strength=8.0,
        count_like=True,
        low_volume=False,
    )
    lo, hi = uncertainty_interval(fit)
    assert ess == len(values)
    assert fit.family in {"NEGATIVE_BINOMIAL", "HURDLE_COUNT", "EMPIRICAL_COUNT"}
    assert 0.0 < fit.posterior_mean < max(values)
    assert lo < fit.posterior_mean < hi


def test_hierarchical_epistemic_uncertainty_only_widens_risk() -> None:
    base = probability_bundle(
        raw_selected_p=0.70,
        n_worlds=1000,
        support_n=12,
        data_quality=0.9,
        ood_risk=0.1,
        volatility=0.2,
        synthetic=False,
    )
    widened = probability_bundle(
        raw_selected_p=0.70,
        n_worlds=1000,
        support_n=12,
        data_quality=0.9,
        ood_risk=0.1,
        volatility=0.2,
        synthetic=False,
        hierarchical_epistemic_sd=5.0,
    )
    assert widened["raw_probability"] == base["raw_probability"]
    assert widened["evidence_safe_probability"] == base["evidence_safe_probability"]
    assert float(widened["epistemic_uncertainty"]) >= float(base["epistemic_uncertainty"])


def _prediction_rows(n: int, *, p: float, outcome_rate: float, start: datetime) -> list[dict]:
    rows = []
    wins = int(round(n * outcome_rate))
    for i in range(n):
        ts = start + timedelta(days=i // 8)
        rows.append({
            "eventId": f"E{i}",
            "eventGroupId": f"G{i // 4}",
            "league": "CFB",
            "result": "WIN" if i < wins else "LOSS",
            "calibratedP": p,
            "decisionCutoff": ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
    return rows


def test_acceptance_ladder_refuses_predictive_superiority_without_evidence() -> None:
    d2 = domain2_cfb_predictive_acceptance([], baseline_mae=None, model_mae=None)
    d3 = domain3_distribution_calibration_acceptance([], baseline_brier=None)
    d4 = domain4_covariance_portfolio_acceptance([])
    d6 = domain6_model_promotion_acceptance([], [])
    claim = predictive_superiority_claim(d2, d3, d4, d6)
    assert d2.status == "INSUFFICIENT_EVIDENCE"
    assert d3.status == "INSUFFICIENT_EVIDENCE"
    assert d4.status == "INSUFFICIENT_EVIDENCE"
    assert d6.status == "INSUFFICIENT_EVIDENCE"
    assert claim["predictiveSuperiority"] == "NONE"
    assert claim["status"] == "NOT_EARNED"


def test_acceptance_ladder_can_report_pass_when_predeclared_evidence_is_supplied() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = _prediction_rows(520, p=0.60, outcome_rate=0.60, start=start)
    baseline_brier = 0.26
    d2 = domain2_cfb_predictive_acceptance(
        rows,
        baseline_mae=6.0,
        model_mae=4.8,
    )
    d3 = domain3_distribution_calibration_acceptance(
        rows,
        baseline_brier=baseline_brier,
    )
    portfolios = [{
        "freezeId": f"F{i}",
        "jointWorldCount": 1000,
        "dependencyGraphHash": f"H{i}",
        "lineageFault": False,
    } for i in range(200)]
    d4 = domain4_covariance_portfolio_acceptance(portfolios)

    challenger = _prediction_rows(240, p=0.60, outcome_rate=0.60, start=start)
    champion = _prediction_rows(240, p=0.50, outcome_rate=0.60, start=start)
    d6 = domain6_model_promotion_acceptance(challenger, champion)

    assert d2.status == "PASS"
    assert d3.status == "PASS"
    assert d4.status == "PASS"
    assert d6.status == "PASS"
    claim = predictive_superiority_claim(d2, d3, d4, d6)
    assert claim["predictiveSuperiority"] == "EARNED"
