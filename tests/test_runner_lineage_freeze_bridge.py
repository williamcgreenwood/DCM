"""Synthetic supported-CFB pregame freeze contract, not live predictive validation."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3

import pytest

from dcm.runtime.lineage_integrity import LineageHalt, line_snapshot_id
from dcm.runtime.runner_freeze_bridge import freeze_supported_cfb_card


def _supported() -> tuple[dict, dict]:
    row = {
        "league": "CFB", "market": "pass_yds", "projectionId": "CAPTURE-ONE",
        "propId": "PROP:CFB-EVENT-SUBJECT-PASS-YDS-FULL-GAME",
        "marketDefinitionId": "MARKETDEF:CFB-PASS-YDS-FULL-GAME",
        "eventId": "CFB-EVENT-ONE", "playerId": "CFB-SUBJECT-ONE",
        "periodLabel": "FULL_GAME", "line": 245.5, "modifier": "STANDARD",
        "offeredHigher": True, "offeredLower": True,
        "settlementRuleHash": "a" * 64, "status": "pre_game",
    }
    selected = {
        "row": row, "selectedSide": "HIGHER", "parameterSnapshotHash": "b" * 64,
        "evidenceHashes": ["c" * 64], "evidenceSafeP": 0.62,
        "grade": "PLAYABLE", "blocker": None, "productionSelectable": True,
        "survivorStateAccepted": True,
    }
    offer = {
        "state": "VALID", "offerBacking": "CURRENT_OFFER_REVALIDATED",
        "productionSelectionPermitted": True,
        "projectionId": "CAPTURE-ONE", "claimId": "CAPTURE-ONE",
        "propId": row["propId"], "marketDefinitionId": row["marketDefinitionId"],
        "eventId": row["eventId"], "subjectId": row["playerId"],
        "proposition": "PASS_YDS", "periodLabel": "FULL_GAME",
        "line": 245.5, "direction": "HIGHER", "modifier": "STANDARD",
        "settlementRuleHash": "a" * 64, "eventStatus": "PRE_GAME",
        "scheduledTime": "2026-10-18T21:00:00Z",
        "retrievedAt": "2026-10-18T19:59:00Z",
        "validUntilUtc": "2026-10-18T20:03:00Z",
        "sourceHash": "d" * 64,
    }
    offer["lineSnapshotId"] = line_snapshot_id(offer)
    return selected, offer


def _args(tmp_path: Path) -> dict:
    selected, offer = _supported()
    return {
        "dest": tmp_path, "run_id": "SYNTHETIC-CFB-20261018",
        "frozen_at_utc": "2026-10-18T20:00:00Z",
        "board_hash": "e" * 64, "prompt_hash": "f" * 64,
        "model_snapshot_id": "MODEL:SYNTHETIC-CFB-ONE",
        "card": [selected], "current_offers": {"CAPTURE-ONE": offer},
        "root_accepted": True,
    }


def test_supported_pregame_bridge_freezes_and_replays_deterministically(tmp_path: Path) -> None:
    args = _args(tmp_path)
    first = freeze_supported_cfb_card(**args)
    assert first["productionLineageFrozen"] is True
    assert first["memberCount"] == 1
    assert first["freezeId"].startswith("FREEZE:")
    assert first["predictiveClaim"] == "NONE"
    assert freeze_supported_cfb_card(**args) == first
    with sqlite3.connect(tmp_path / "lineage.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM line_snapshots").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM freezes").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM freeze_members").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM freeze_members")


@pytest.mark.parametrize("mutation,code", [
    (("root_accepted", False), "PRODUCTION_ROOT_NOT_ACCEPTED"),
    (("prompt_hash", ""), "PRODUCTION_FREEZE_PROMPT_HASH_REQUIRED"),
    (("current_offers", {}), "OFFER_REVALIDATION_UNAVAILABLE"),
])
def test_missing_global_dependency_rejects_without_freeze(tmp_path: Path, mutation: tuple, code: str) -> None:
    args = _args(tmp_path)
    args[mutation[0]] = mutation[1]
    with pytest.raises(LineageHalt, match=code):
        freeze_supported_cfb_card(**args)
    assert not (tmp_path / "lineage.sqlite3").exists()


@pytest.mark.parametrize("field,value,code", [
    ("propId", "", "PRODUCTION_FREEZE_CANONICAL_IDENTITY_REQUIRED"),
    ("marketDefinitionId", "", "PRODUCTION_FREEZE_CANONICAL_IDENTITY_REQUIRED"),
    ("settlementRuleHash", "", "PRODUCTION_FREEZE_SETTLEMENT_RULE_MISSING"),
    ("market", "longest_reception", "PRODUCTION_FREEZE_MARKET_UNSUPPORTED"),
    ("status", "live", "PRODUCTION_FREEZE_EVENT_NOT_PREGAME"),
    ("line", 246.5, "PRODUCTION_FREEZE_LINE_CHANGED"),
    ("offeredHigher", False, "PRODUCTION_FREEZE_SIDE_NOT_OFFERED"),
])
def test_missing_row_dependency_fails_closed(tmp_path: Path, field: str, value: object, code: str) -> None:
    args = _args(tmp_path)
    args["card"][0]["row"][field] = value
    with pytest.raises(LineageHalt, match=code):
        freeze_supported_cfb_card(**args)
    assert not (tmp_path / "lineage.sqlite3").exists()


@pytest.mark.parametrize("field,value,code", [
    ("productionSelectionPermitted", False, "PRODUCTION_FREEZE_OFFER_NOT_AUTHORIZED"),
    ("eventStatus", "LIVE", "PRODUCTION_FREEZE_EVENT_NOT_PREGAME"),
    ("validUntilUtc", "2026-10-18T19:59:30Z", "OFFER_REVALIDATION_STALE"),
    ("scheduledTime", "2026-10-18T19:59:00Z", "PRODUCTION_FREEZE_EVENT_STARTED"),
    ("sourceHash", "", "PRODUCTION_FREEZE_OFFER_SOURCE_HASH_REQUIRED"),
    ("lineSnapshotId", "LINE:FAKE", "PRODUCTION_FREEZE_LINE_SNAPSHOT_ID_MISMATCH"),
])
def test_unverified_current_offer_fails_closed(tmp_path: Path, field: str, value: object, code: str) -> None:
    args = _args(tmp_path)
    args["current_offers"]["CAPTURE-ONE"][field] = value
    with pytest.raises(LineageHalt, match=code):
        freeze_supported_cfb_card(**args)
    assert not (tmp_path / "lineage.sqlite3").exists()


@pytest.mark.parametrize("field,value,code", [
    ("parameterSnapshotHash", "", "PRODUCTION_FREEZE_MODEL_HASH_REQUIRED"),
    ("evidenceHashes", [], "PRODUCTION_FREEZE_EVIDENCE_REQUIRED"),
    ("evidenceSafeP", float("nan"), "PRODUCTION_FREEZE_PROBABILITY_INVALID"),
    ("grade", "LEAN", "PRODUCTION_FREEZE_CANDIDATE_NOT_CERTIFIED"),
    ("productionSelectable", False, "PRODUCTION_FREEZE_CANDIDATE_NOT_CERTIFIED"),
])
def test_model_evidence_and_selection_missing_reject(tmp_path: Path, field: str, value: object, code: str) -> None:
    args = _args(tmp_path)
    args["card"][0][field] = value
    with pytest.raises(LineageHalt, match=code):
        freeze_supported_cfb_card(**args)
    assert not (tmp_path / "lineage.sqlite3").exists()
