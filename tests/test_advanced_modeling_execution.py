from __future__ import annotations

from dcm.model.advanced_execution import (
    compile_advanced_execution_dag,
    execute_advanced_modeling,
    gaussian_kde_diagnostic,
    normalized_svd_diagnostic,
    validate_advanced_execution_receipt,
)
from dcm.platform.prizepicks.payouts import DEMO_MG_TABLE_HASH


def test_kde_bandwidth_is_diagnostic_and_abstains_on_small_sample():
    small = gaussian_kde_diagnostic([1.0, 2.0])
    assert small["state"] == "INACTIVE_INSUFFICIENT_DATA"
    assert small["forecastProbability"] is None
    result = gaussian_kde_diagnostic([float(i % 11) for i in range(64)])
    assert result["state"] == "SHADOW_DIAGNOSTIC"
    assert result["bandwidth"] > 0
    assert result["forecastProbability"] is None
    assert result["probabilityAuthority"] == "NONE_DIAGNOSTIC_ONLY"


def test_svd_normalizes_and_rejects_post_cutoff_rows():
    matrix = [[float(i), float(i % 3)] for i in range(10)]
    timestamps = [f"2026-01-{i + 1:02d}T00:00:00Z" for i in range(10)]
    result = normalized_svd_diagnostic(matrix, observed_at=timestamps,
                                       forecast_cutoff="2026-02-01T00:00:00Z")
    assert result["state"] == "SHADOW_DIAGNOSTIC"
    assert result["normalization"] == "COLUMN_ZSCORE"
    assert result["rank"] > 0
    assert result["forecastProbability"] is None
    leaked = normalized_svd_diagnostic(matrix, observed_at=timestamps,
                                       forecast_cutoff="2026-01-09T00:00:00Z")
    assert leaked["state"] == "BLOCKED_POST_CUTOFF_FEATURE"
    missing = normalized_svd_diagnostic([], forecast_cutoff="2026-02-01T00:00:00Z")
    assert missing["state"] == "BLOCKED_HISTORICAL_FEATURE_MATRIX_MISSING"


def test_dag_is_registered_and_receipt_has_every_capability():
    dag = compile_advanced_execution_dag()
    assert dag["validated"] is True
    assert len(dag["nodes"]) == 6
    forecasts = [{"_worldValues": [float(i) for i in range(40)],
                  "_selectionOutcomes": bytes([i % 3 for i in range(40)]),
                  "calibrationState": "INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS"}]
    receipt = execute_advanced_modeling(
        forecasts=forecasts, portfolio=[], calibration_state={},
        forecast_cutoff="2026-10-14T07:00:00Z",
    )
    validate_advanced_execution_receipt(receipt)
    assert receipt["allCapabilitiesEvaluated"] is True
    assert {r["capability"] for r in receipt["receipts"]} == {
        "KDE", "SVD", "MONTE_CARLO", "CALIBRATION", "PORTFOLIO_CORRELATION", "PAYOUT_EV"
    }
    assert receipt["certification"]["learningRevision"] == "LR000000"
    assert receipt["certification"]["predictiveClaim"] == "NONE"
    assert next(r for r in receipt["receipts"] if r["capability"] == "PAYOUT_EV")["state"] == "BLOCKED_MISSING_ENTRY_CONTRACT"


def test_kde_only_consumes_exact_key_cutoff_safe_history():
    cutoff = "2026-10-14T07:00:00Z"
    historical = [{
        "comparableKey": "gridiron|CFB|pass_yds|MORE",
        "value": float(i % 9),
        "observedAt": "2026-10-10T00:00:00Z",
        "labelAvailableAt": "2026-10-11T00:00:00Z",
    } for i in range(30)]
    historical.append({
        "comparableKey": "gridiron|CFB|pass_yds|MORE", "value": 1000.0,
        "observedAt": "2026-10-15T00:00:00Z", "labelAvailableAt": "2026-10-16T00:00:00Z",
    })
    forecast = {"row": {"sportFamily": "gridiron", "league": "CFB", "market": "pass_yds"},
                "selectedSide": "MORE", "state": "MODELED",
                "_worldValues": [1.0], "_selectionOutcomes": bytes([2])}
    receipt = execute_advanced_modeling(
        forecasts=[forecast], portfolio=[], calibration_state={"kdeComparableSamples": historical},
        forecast_cutoff=cutoff,
    )
    kde = next(row for row in receipt["receipts"] if row["capability"] == "KDE")
    assert kde["state"] == "SHADOW_DIAGNOSTIC"
    assert kde["details"]["diagnosticRows"] == 1
    assert kde["details"]["forecastProbabilityProduced"] is False


def test_joint_world_payout_ev_matches_independent_fixture():
    # The aligned worlds contain exactly one win per world, so the captured
    # two-pick payout table returns 1.5 in every joint world.
    forecasts = [
        {"_worldValues": list(range(40)), "_selectionOutcomes": bytes([2] * 20 + [0] * 20), "calibrationState": "SHADOW"},
        {"_worldValues": list(range(40)), "_selectionOutcomes": bytes([0] * 20 + [2] * 20), "calibrationState": "SHADOW"},
    ]
    receipt = execute_advanced_modeling(
        forecasts=forecasts, portfolio=forecasts, calibration_state={},
        forecast_cutoff="2026-10-14T07:00:00Z", payout_table_hash=DEMO_MG_TABLE_HASH, stake=1.0,
    )
    ev = next(row for row in receipt["receipts"] if row["capability"] == "PAYOUT_EV")
    assert ev["state"] == "SHADOW_DIAGNOSTIC_UNCALIBRATED"
    assert ev["details"]["method"] == "EMPIRICAL_JOINT_WLP_WORLDS"
    assert ev["details"]["expectedReturn"] == 1.5
    assert ev["details"]["expectedValue"] == 0.5
    assert "CALIBRATED_JOINT_PROBABILITIES_MISSING" in ev["blockers"]


def test_payout_ev_stays_uncertified_without_complete_entry_adapter():
    forecasts = [
        {"_worldValues": list(range(40)), "_selectionOutcomes": bytes([2] * 20 + [0] * 20), "calibrationState": "ACTIVE_CHRONOLOGICAL_CELL"},
        {"_worldValues": list(range(40)), "_selectionOutcomes": bytes([0] * 20 + [2] * 20), "calibrationState": "ACTIVE_CHRONOLOGICAL_CELL"},
    ]
    historical = [{"calibrationKey": "CFB|CFB|pass_yds|MORE", "forecastP": 0.95,
                   "binaryOutcome": 1} for _ in range(200)]
    receipt = execute_advanced_modeling(
        forecasts=forecasts, portfolio=forecasts, calibration_state={"settlements": historical},
        forecast_cutoff="2026-10-14T07:00:00Z", payout_table_hash=DEMO_MG_TABLE_HASH, stake=1.0,
    )
    ev = next(row for row in receipt["receipts"] if row["capability"] == "PAYOUT_EV")
    assert ev["details"]["expectedValue"] == 0.5
    assert ev["state"] == "SHADOW_DIAGNOSTIC_ENTRY_RULES_UNVERIFIED"
    assert "CAPTURED_ENTRY_CONTRACT_AND_COMPLETE_SETTLEMENT_ADAPTER_MISSING" in ev["blockers"]
