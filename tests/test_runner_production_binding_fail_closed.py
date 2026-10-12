"""Fail-closed modeled-runner card binding tests using synthetic CFB observations."""
from __future__ import annotations

from copy import deepcopy

import pytest

from dcm.runtime.lineage_integrity import LineageHalt
from dcm.runtime.runner_freeze_bridge import bind_verified_runner_cfb_card


def _inputs():
    row = {
        "league": "CFB", "market": "pass_yds", "eventId": "EVENT-1",
        "playerId": "PLAYER-1", "projectionId": "CAPTURE-1",
        "status": "pre_game", "line": 245.5, "periodLabel": "FULL_GAME",
        "modifier": "STANDARD", "offeredHigher": True,
    }
    candidate = {
        "row": row, "selectedSide": "MORE", "calibratedP": 0.63,
        "parameterSnapshotHash": "a" * 64,
        "parameterSnapshot": {
            "parameter_snapshot_hash": "a" * 64,
            "evidence_hashes": ["b" * 64],
        },
        "evidenceHashes": ["b" * 64],
    }
    offer = {
        "state": "VALID", "productionSelectionPermitted": True,
        "eventId": "EVENT-1", "subjectId": "PLAYER-1",
        "proposition": "PASS_YDS", "line": 245.5, "direction": "HIGHER",
        "propId": "PROP:EVENT-1-PLAYER-1-PASS-YDS",
        "marketDefinitionId": "MARKETDEF:CFB-PASS-YDS-FULL_GAME",
        "settlementRuleHash": "c" * 64,
        "periodLabel": "FULL_GAME", "modifier": "STANDARD",
    }
    return dict(
        card=[candidate],
        current_offers={"CAPTURE-1": offer},
        parameter_snapshot_hashes=["a" * 64],
        feature_store_hash="d" * 64,
        evidence_graph_hash="e" * 64,
    )


def test_verified_capture_binds_model_to_canonical_ids_and_selected_side():
    params = _inputs()
    card = bind_verified_runner_cfb_card(**params)
    assert card[0]["selectedSide"] == "HIGHER"
    assert card[0]["row"]["propId"] == params["current_offers"]["CAPTURE-1"]["propId"]
    assert card[0]["row"]["settlementRuleHash"] == "c" * 64
    assert card[0]["parameterSnapshotHash"] == "a" * 64
    assert card[0]["featureStoreHash"] == "d" * 64
    assert card[0]["evidenceGraphHash"] == "e" * 64
    assert "propId" not in params["card"][0]["row"]


@pytest.mark.parametrize("scope,field,value,code", [
    ("top", "feature_store_hash", "", "PRODUCTION_FREEZE_FEATURE_STORE_REQUIRED"),
    ("top", "evidence_graph_hash", "", "PRODUCTION_FREEZE_EVIDENCE_GRAPH_REQUIRED"),
    ("top", "parameter_snapshot_hashes", [], "PRODUCTION_FREEZE_PARAMETER_INDEX_INVALID"),
    ("offer", "productionSelectionPermitted", False, "PRODUCTION_FREEZE_OFFER_NOT_AUTHORIZED"),
    ("offer", "eventId", "OTHER", "PRODUCTION_FREEZE_CAPTURE_ROW_MISMATCH"),
    ("offer", "marketDefinitionId", "", "PRODUCTION_FREEZE_CAPTURE_FIELD_MISSING"),
    ("row", "line", 250.5, "PRODUCTION_FREEZE_LINE_CHANGED"),
    ("row", "periodLabel", "FIRST_HALF", "PRODUCTION_FREEZE_CANONICAL_CONFLICT"),
    ("row", "status", "LIVE", "PRODUCTION_FREEZE_EVENT_NOT_PREGAME"),
    ("row", "offeredHigher", False, "PRODUCTION_FREEZE_SIDE_NOT_OFFERED"),
    ("candidate", "calibratedP", None, "PRODUCTION_FREEZE_CALIBRATION_REQUIRED"),
    ("candidate", "parameterSnapshotHash", "0" * 64, "PRODUCTION_FREEZE_PARAMETER_NOT_IN_RUN"),
    ("candidate", "evidenceHashes", ["0" * 64], "PRODUCTION_FREEZE_EVIDENCE_SNAPSHOT_CONFLICT"),
])
def test_runner_binder_rejects_conflicting_missing_or_unsupported_dependencies(
    scope, field, value, code,
):
    args = _inputs()
    if scope == "top":
        args[field] = value
    elif scope == "row":
        args["card"][0]["row"][field] = value
    elif scope == "candidate":
        args["card"][0][field] = value
    else:
        args["current_offers"]["CAPTURE-1"][field] = value
    with pytest.raises(LineageHalt, match=code):
        bind_verified_runner_cfb_card(**args)
