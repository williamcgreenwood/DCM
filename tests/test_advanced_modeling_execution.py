from __future__ import annotations

from dcm.model.advanced_execution import (
    compile_advanced_execution_dag,
    execute_advanced_modeling,
    gaussian_kde_diagnostic,
    normalized_svd_diagnostic,
    validate_advanced_execution_receipt,
)
from dcm.platform.prizepicks.payouts import DEMO_MG_TABLE_HASH


def test_kde_bandwidth_is_diagnostic_and_abstains_on_small_sample(monkeypatch):
    small = gaussian_kde_diagnostic([1.0, 2.0])
    assert small["state"] == "INACTIVE_INSUFFICIENT_DATA"
    assert small["forecastProbability"] is None
    result = gaussian_kde_diagnostic([float(i % 11) for i in range(64)])
    assert result["state"] == "SHADOW_DIAGNOSTIC"
    assert result["bandwidth"] > 0
    assert result["forecastProbability"] is None
    assert result["probabilityAuthority"] == "NONE_DIAGNOSTIC_ONLY"
    assert abs(result["gridIntegralDiagnostic"] - 1.0) < 0.04
    assert len(result["bandwidthCandidates"]) == 5
    monkeypatch.setattr("dcm.model.advanced_execution.MAX_KDE_SAMPLE", 40)
    bounded = gaussian_kde_diagnostic([float(i % 17) for i in range(80)])
    assert bounded["inputN"] == 80
    assert bounded["n"] == 40
    assert bounded["sampleReduction"] == "EVEN_SPACED_DETERMINISTIC"


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
    shuffled = normalized_svd_diagnostic(matrix, observed_at=list(reversed(timestamps)),
                                         forecast_cutoff="2026-02-01T00:00:00Z")
    assert shuffled["state"] == "BLOCKED_NONCHRONOLOGICAL_FEATURE_MATRIX"
    missing = normalized_svd_diagnostic([], forecast_cutoff="2026-02-01T00:00:00Z")
    assert missing["state"] == "BLOCKED_HISTORICAL_FEATURE_MATRIX_MISSING"
    oversized_rows = 10_001
    oversized = normalized_svd_diagnostic(
        [[float(i), float(i % 3)] for i in range(oversized_rows)],
        observed_at=["2026-01-01T00:00:00Z"] * oversized_rows,
        forecast_cutoff="2026-02-01T00:00:00Z",
    )
    assert oversized["state"] == "BLOCKED_RESOURCE_LIMIT"


def test_dag_is_registered_and_receipt_has_every_capability():
    dag = compile_advanced_execution_dag()
    assert dag["validated"] is True
    assert len(dag["nodes"]) == 7
    forecasts = [{"_worldValues": [float(i) for i in range(40)],
                  "_selectionOutcomes": bytes([i % 3 for i in range(40)]),
                  "calibrationState": "INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS"}]
    receipt = execute_advanced_modeling(
        forecasts=forecasts, portfolio=[], calibration_state={},
        forecast_cutoff="2026-10-14T07:00:00Z",
    )
    validate_advanced_execution_receipt(receipt)
    assert receipt["manifestType"] == "ModelExecutionManifest"
    assert receipt["runId"] == "UNAVAILABLE"
    assert receipt["allCapabilitiesEvaluated"] is True
    assert {r["capability"] for r in receipt["receipts"]} == {
        "ALGORITHM_GRAPH", "KDE", "SVD", "MONTE_CARLO", "CALIBRATION",
        "PORTFOLIO_CORRELATION", "PAYOUT_EV"
    }
    assert receipt["fullModelingExecution"] is False
    graph = next(r for r in receipt["receipts"] if r["capability"] == "ALGORITHM_GRAPH")
    assert graph["details"]["registryAlgorithmCount"] == 170
    assert graph["details"]["registeredDoesNotMeanExecuted"] is True
    assert graph["details"]["unrelatedRegistryAlgorithmsExecutionState"].startswith("TRACKED_BY")
    assert all("outputHash" in r and "executionDurationMs" in r for r in receipt["receipts"])
    assert all(r["runId"] == "UNAVAILABLE" for r in receipt["receipts"])
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
                "outcomeDomain": "CONTINUOUS_APPROXIMATION_VALIDATED",
                "_worldValues": [1.0], "_selectionOutcomes": bytes([2])}
    receipt = execute_advanced_modeling(
        forecasts=[forecast], portfolio=[], calibration_state={"kdeComparableSamples": historical},
        forecast_cutoff=cutoff,
    )
    kde = next(row for row in receipt["receipts"] if row["capability"] == "KDE")
    assert kde["state"] == "SHADOW_DIAGNOSTIC"
    assert kde["details"]["diagnosticRows"] == 1
    assert kde["details"]["forecastProbabilityProduced"] is False


def test_kde_abstains_for_discrete_market_even_with_history():
    history = [{"comparableKey": "gridiron|CFB|receptions|MORE", "value": float(i),
                "observedAt": "2026-10-10T00:00:00Z", "labelAvailableAt": "2026-10-11T00:00:00Z"}
               for i in range(40)]
    row = {"row": {"sportFamily": "gridiron", "league": "CFB", "market": "receptions"},
           "selectedSide": "MORE", "state": "MODELED", "outcomeDomain": "DISCRETE"}
    receipt = execute_advanced_modeling(
        forecasts=[row], portfolio=[], calibration_state={"kdeComparableSamples": history},
        forecast_cutoff="2026-10-14T07:00:00Z",
    )
    kde = next(item for item in receipt["receipts"] if item["capability"] == "KDE")
    assert kde["state"] == "NOT_APPLICABLE"
    assert kde["details"]["unsupportedDiscreteRows"] == 1


def test_manual_shadow_mode_never_claims_canonical_full_execution():
    receipt = execute_advanced_modeling(
        forecasts=[], portfolio=[], calibration_state={}, forecast_cutoff="",
        run_id="shadow-101426-test", execution_mode="MANUAL_SHADOW_ANALYSIS",
    )
    validate_advanced_execution_receipt(receipt)
    assert receipt["mode"] == "MANUAL_SHADOW_ANALYSIS"
    assert receipt["runId"] == "shadow-101426-test"
    assert receipt["fullModelingExecution"] is False


def test_calibration_uses_only_labels_available_by_forecast_cutoff():
    cutoff = "2026-10-14T07:00:00Z"
    valid = {
        "decisionCutoff": "2026-10-12T12:00:00Z", "labelAvailableAt": "2026-10-12T23:00:00Z",
        "forecastP": 0.6, "binaryOutcome": 1, "result": "WIN",
    }
    future = {
        "decisionCutoff": "2026-10-13T12:00:00Z", "labelAvailableAt": "2026-10-14T08:00:00Z",
        "forecastP": 0.9, "binaryOutcome": 0, "result": "LOSS",
    }
    walkforward_rows = [
        {"decisionCutoff": valid["decisionCutoff"], "labelAvailableAt": valid["labelAvailableAt"],
         "forecastP": 0.6, "binaryOutcome": 1, "result": "WIN", "labelSplit": "supervised"},
        {"decisionCutoff": future["decisionCutoff"], "labelAvailableAt": future["labelAvailableAt"],
         "forecastP": 0.9, "binaryOutcome": 0, "result": "LOSS", "labelSplit": "supervised"},
    ]
    receipt = execute_advanced_modeling(
        forecasts=[], portfolio=[], calibration_state={
            "settlements": [valid, future], "walkforwardRows": walkforward_rows,
        }, forecast_cutoff=cutoff,
    )
    cal = next(r for r in receipt["receipts"] if r["capability"] == "CALIBRATION")
    assert cal["details"]["historicalSettlementRows"] == 1
    assert cal["details"]["outOfSampleMetricsProduced"] is False
    assert cal["details"]["walkForward"]["status"] == "INSUFFICIENT_CHRONOLOGICAL_CUTOFFS"


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
                   "binaryOutcome": 1, "decisionCutoff": "2026-10-12T07:00:00Z",
                   "labelAvailableAt": "2026-10-12T20:00:00Z"} for _ in range(200)]
    receipt = execute_advanced_modeling(
        forecasts=forecasts, portfolio=forecasts, calibration_state={"settlements": historical},
        forecast_cutoff="2026-10-14T07:00:00Z", payout_table_hash=DEMO_MG_TABLE_HASH, stake=1.0,
    )
    ev = next(row for row in receipt["receipts"] if row["capability"] == "PAYOUT_EV")
    assert ev["details"]["expectedValue"] == 0.5
    assert ev["state"] == "SHADOW_DIAGNOSTIC_ENTRY_RULES_UNVERIFIED"
    assert "CAPTURED_ENTRY_CONTRACT_AND_COMPLETE_SETTLEMENT_ADAPTER_MISSING" in ev["blockers"]
