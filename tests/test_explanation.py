"""PropExplanation contract: required keys, encoded drivers, no invented prose."""
from __future__ import annotations

from dcm.model.explanation import (
    REQUIRED_EXPLANATION_KEYS,
    build_prop_explanation,
    render_prop_explanation_text,
)
from dcm.model.line_surface import surface
from dcm.model.uncertainty import PROBABILITY_CONTRACT_KEYS


def _row():
    return {
        "projectionId": "pts-more-1",
        "playerId": "TATUM",
        "playerName": "Jayson Tatum",
        "team": "BOS",
        "opponent": "NYK",
        "eventId": "NBA_BOS_NYK",
        "market": "pts",
        "line": 27.5,
        "side": "MORE",
        "league": "NBA",
        "sportFamily": "basketball",
    }


def _snapshot():
    return {
        "parameter_snapshot_hash": "snap-hash-pts",
        "data_quality": 0.72,
        "ood_risk": 0.12,
        "reliability": 0.61,
        "synthetic": True,
        "status": "ACTIVE",
        "blocker": "SYNTHETIC_EVIDENCE_NOT_SELECTABLE",
        "evidence_hashes": ["ev-1", "ev-2"],
        "opportunity": {"support_n": 8, "minutes_mean": 36.4},
        "efficiency": {"support_n": 8},
        "parameters": {
            "minutes_mean": 36.4,
            "fga_per_min": 0.70,
            "fta_per_min": 0.22,
            "reb_per_min": 0.21,
            "ast_per_min": 0.13,
            "stl_per_min": 0.03,
            "blk_per_min": 0.025,
            "three_pa_share": 0.40,
            "tov_per_min": 0.08,
            "two_fg_pct": 0.55,
            "three_fg_pct": 0.37,
            "ft_pct": 0.84,
        },
    }


def _side_eval(values, line=27.5):
    surf = surface(values, line, side="MORE", playable_p=0.58)
    return {
        "side": "MORE",
        "rawP": 0.78,
        "evidenceSafeP": 0.62,
        "lowerBound": 0.55,
        "reliability": 0.61,
        "volatility": 0.22,
        "fragility": 0.18,
        "falseSignRisk": 0.12,
        "monteCarloSE": 0.04,
        "epistemicUncertainty": 0.11,
        "lineSurface": surf,
    }


def test_explanation_contains_required_keys_for_points_more():
    values = [32.0 + i * 0.1 for i in range(48)]
    obj = build_prop_explanation(
        _row(),
        _snapshot(),
        {
            "mean": sum(values) / len(values),
            "median": sorted(values)[len(values) // 2],
            "pMore": 0.92,
            "pLess": 0.06,
            "pPush": 0.02,
            "n": len(values),
        },
        _side_eval(values),
        ["feat-a", "feat-b"],
        ["ev-1", "ev-2"],
    )
    for key in REQUIRED_EXPLANATION_KEYS:
        assert key in obj, key
    assert obj["player"] == "Jayson Tatum"
    assert obj["team"] == "BOS"
    assert obj["opponent"] == "NYK"
    assert obj["market"] == "pts"
    assert obj["line"] == 27.5
    assert obj["direction"] == "MORE"
    assert isinstance(obj["topPositiveDrivers"], list)
    assert isinstance(obj["topNegativeDrivers"], list)
    assert isinstance(obj["primaryFailurePaths"], list)
    assert isinstance(obj["featureHashes"], list)
    assert obj["featureHashes"] == ["feat-a", "feat-b"]
    assert obj["evidenceHashes"] == ["ev-1", "ev-2"]
    assert obj["parameterSnapshotHash"] == "snap-hash-pts"
    assert obj["modelIds"]
    assert obj["simulationHash"]
    assert "minutes_mean" in obj["projectedOpportunity"]
    assert obj["projectionMean"] is not None
    assert obj["projectionMedian"] is not None
    # Encoded minutes vs NBA prior 34.0 → positive driver for MORE, never invented prose.
    pos_features = {d["feature"] for d in obj["topPositiveDrivers"]}
    assert "minutes_mean" in pos_features
    assert all("because" not in str(d).lower() for d in obj["topPositiveDrivers"])
    text = render_prop_explanation_text(obj)
    assert "Jayson Tatum" in text
    assert "pts" in text
    assert "MORE" in text


def test_drivers_empty_list_ok_when_no_delta():
    row = _row()
    snap = _snapshot()
    # Match NBA priors exactly so opportunity/efficiency deltas vanish.
    snap["parameters"] = {
        "minutes_mean": 34.0,
        "fga_per_min": 0.55,
        "fta_per_min": 0.18,
        "reb_per_min": 0.23,
        "ast_per_min": 0.14,
        "stl_per_min": 0.03,
        "blk_per_min": 0.025,
        "three_pa_share": 0.42,
        "tov_per_min": 0.08,
        "two_fg_pct": 0.52,
        "three_fg_pct": 0.36,
        "ft_pct": 0.78,
    }
    snap["opportunity"]["minutes_mean"] = 34.0
    obj = build_prop_explanation(
        row, snap,
        {"mean": 27.5, "median": 27.5, "pMore": 0.5, "pLess": 0.5, "pPush": 0.0, "n": 8},
        _side_eval([27.0, 28.0] * 8, 27.5),
        [],
        [],
    )
    assert "topPositiveDrivers" in obj
    assert "topNegativeDrivers" in obj
    assert isinstance(obj["topPositiveDrivers"], list)
    assert isinstance(obj["topNegativeDrivers"], list)


def test_probability_contract_keys_are_separate():
    assert "reliability" in PROBABILITY_CONTRACT_KEYS
    assert "selectedP" in PROBABILITY_CONTRACT_KEYS
    assert PROBABILITY_CONTRACT_KEYS[0] == "selectedP"
    assert "reliability" != "selectedP"
