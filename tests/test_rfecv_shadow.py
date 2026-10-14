from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sklearn")

from dcm.learning.rfecv_shadow import evaluate_rfecv_shadow
from dcm.learning.walkforward import run_walkforward


def _fixture_rows():
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(36):
        cutoff = origin + timedelta(days=i)
        for duplicate, y in enumerate((0, 1)):
            rows.append({
                "eventId": f"event-{i}-{duplicate}",
                "decisionCutoff": cutoff.isoformat().replace("+00:00", "Z"),
                "labelAvailableAt": (cutoff + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                "result": "WIN" if y else "LOSS",
                "features": {"signal": float(y * 2 - 1), "noise": float((i * 13 + duplicate) % 11)},
            })
    return rows


def test_rfecv_shadow_uses_nested_event_disjoint_chronological_folds():
    rows = _fixture_rows()
    result = evaluate_rfecv_shadow(rows, ["signal", "noise"], min_train_rows=20)
    assert result["status"] == "SHADOW_ONLY"
    assert result["outerTrainN"] == 70
    assert result["outerTestN"] == 2
    assert result["eventDisjoint"] is True
    assert result["innerFoldCount"] >= 2
    assert result["featureCount"] >= 1
    assert result["outerTestLogLoss"] >= 0
    assert result["allFeatureBaselineLogLoss"] >= 0
    assert result["logLossDifferenceVsAllFeatureBaseline"] == pytest.approx(
        result["outerTestLogLoss"] - result["allFeatureBaselineLogLoss"]
    )
    assert result["productionProbabilityAuthority"] is False
    assert result["predictiveClaim"] == "NONE"
    wired_rows = [{**row, "numericFeatures": row["features"], "selectedP": 0.5} for row in rows]
    report = run_walkforward(wired_rows)
    assert report["rfecvShadowChallenger"]["algorithmId"] == "ALG-ML-FS-001"
    assert report["rfecvShadowChallenger"]["status"] == "SHADOW_ONLY"
    assert report["rfecvShadowChallenger"]["trainingOrProductionSelection"] is False


def test_rfecv_blocks_missing_event_identity():
    rows = _fixture_rows()
    rows[0]["eventId"] = ""
    with pytest.raises(ValueError, match="RFECV_EVENT_ID_REQUIRED"):
        evaluate_rfecv_shadow(rows, ["signal", "noise"])


def test_canonical_walkforward_records_rfecv_missing_matrix_blocker():
    report = run_walkforward(_fixture_rows())
    assert report["rfecvShadowChallenger"]["status"] == "BLOCKED_MISSING_CUTOFF_SAFE_NUMERIC_FEATURE_MATRIX"
