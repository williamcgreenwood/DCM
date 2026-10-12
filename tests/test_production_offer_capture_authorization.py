"""Synthetic canonical CFB authorization-to-freeze tests; no live acceptance claim."""
from __future__ import annotations

from copy import deepcopy
import sqlite3

import pytest

from dcm.contracts.hashes import content_hash
from dcm.research.offer_revalidation import validate_offer_revalidation
from dcm.runtime.lineage_integrity import LineageHalt
from dcm.runtime.runner_freeze_bridge import (
    bind_verified_runner_cfb_card, freeze_supported_cfb_card,
)


CUTOFF = "2026-10-18T20:00:00Z"


def _fixture():
    captured = {
        "schema": "pillars_dcm.insights_offer_snapshot.v1",
        "sourceAdapter": "INSIGHTS_EVIDENCE",
        "harIdentityState": "VERIFIED_HAR_LOCAL",
        "claimId": "CAPTURE-ONE",
        "projectionId": "CAPTURE-ONE",
        "league": "CFB",
        "eventId": "CFB-EVENT-ONE",
        "subjectId": "CFB-SUBJECT-ONE",
        "proposition": "PASS_YDS",
        "market": "pass_yds",
        "periodLabel": "FULL_GAME",
        "modifier": "STANDARD",
        "line": 245.5,
        "direction": "HIGHER",
        "eventStatus": "PRE_GAME",
        "status": "pre_game",
        "scheduledTime": "2026-10-18T21:00:00Z",
        "sourceSnapshotTime": "2026-10-18T19:58:00Z",
        "sourceHarSha256": "b" * 64,
        "sourceBodyHash": "a" * 64,
        "platformRulesSourceHash": "d" * 64,
        "platformRulesVerified": True,
        "propId": "PROP:CFB-EVENT-SUBJECT-PASS-YDS-FULL-GAME",
        "marketDefinitionId": "MARKETDEF:CFB-PASS-YDS-FULL-GAME",
        "settlementRuleHash": "c" * 64,
    }
    captured["contentHash"] = content_hash(captured)
    raw = {
        "claimId": captured["claimId"],
        "projectionId": captured["projectionId"],
        "eventId": captured["eventId"],
        "subjectId": captured["subjectId"],
        "proposition": captured["proposition"],
        "periodLabel": captured["periodLabel"],
        "modifier": captured["modifier"],
        "line": captured["line"],
        "direction": captured["direction"],
        "sourceUrl": "https://api.prizepicks.com/projections",
        "sourceId": "HAR:" + captured["sourceHarSha256"],
        "sourceHash": captured["sourceBodyHash"],
        "retrievedAt": "2026-10-18T19:59:00Z",
        "authority": "PLATFORM_CAPTURE",
        "eventStatus": "PRE_GAME",
        "scheduledTime": captured["scheduledTime"],
        "propId": captured["propId"],
        "marketDefinitionId": captured["marketDefinitionId"],
        "settlementRuleHash": captured["settlementRuleHash"],
        "marketActive": True,
        "current": True,
    }
    return raw, captured


def test_exact_capture_can_authorize_synthetic_pregame_freeze_and_replay(tmp_path):
    raw, captured = _fixture()
    offer = validate_offer_revalidation(raw, snapshots={raw["claimId"]: captured}, cutoff=CUTOFF)
    assert offer["productionSelectionPermitted"] is True
    assert offer["propId"] == captured["propId"]
    selected = {
        "row": {
            "league": "CFB",
            "market": "pass_yds",
            "projectionId": raw["projectionId"],
            "propId": offer["propId"],
            "marketDefinitionId": offer["marketDefinitionId"],
            "eventId": offer["eventId"],
            "playerId": offer["subjectId"],
            "periodLabel": offer["periodLabel"],
            "line": offer["line"],
            "modifier": offer["modifier"],
            "offeredHigher": True,
            "offeredLower": False,
            "settlementRuleHash": offer["settlementRuleHash"],
            "status": "pre_game",
        },
        "selectedSide": "HIGHER",
        "parameterSnapshotHash": "e" * 64,
        "parameterSnapshot": {"parameter_snapshot_hash": "e" * 64, "evidence_hashes": ["f" * 64]},
        "calibratedP": 0.63,
        "evidenceHashes": ["f" * 64],
        "evidenceSafeP": 0.62,
        "grade": "PLAYABLE",
        "blocker": None,
        "productionSelectable": True,
        "survivorStateAccepted": True,
    }
    bound = bind_verified_runner_cfb_card(
        [selected], current_offers={raw["claimId"]: offer},
        parameter_snapshot_hashes=["e" * 64], feature_store_hash="2" * 64,
        evidence_graph_hash="3" * 64,
    )
    assert bound[0]["row"]["propId"] == offer["propId"]
    assert bound[0]["featureStoreHash"] == "2" * 64
    args = {
        "dest": tmp_path,
        "run_id": "SYNTHETIC-PREGAME-CFB",
        "frozen_at_utc": CUTOFF,
        "board_hash": "0" * 64,
        "prompt_hash": "1" * 64,
        "model_snapshot_id": "MODEL:SYNTHETIC-CFB",
        "card": bound,
        "current_offers": {raw["claimId"]: offer},
        "root_accepted": True,
    }
    first = freeze_supported_cfb_card(**args)
    assert first["state"] == "FROZEN"
    assert first == freeze_supported_cfb_card(**args)
    with sqlite3.connect(tmp_path / "lineage.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM freezes").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM freeze_members").fetchone()[0] == 1


@pytest.mark.parametrize("change", [
    ("raw", "current", False),
    ("raw", "marketActive", None),
    ("raw", "propId", "PROP:OTHER"),
    ("raw", "marketDefinitionId", "MARKETDEF:OTHER"),
    ("raw", "settlementRuleHash", "0" * 64),
    ("raw", "sourceHash", "0" * 64),
    ("raw", "retrievedAt", "2026-10-18T20:30:00Z"),
    ("raw", "direction", "LOWER"),
    ("raw", "line", 246.5),
    ("raw", "periodLabel", "FIRST_HALF"),
    ("raw", "eventStatus", "LIVE"),
    ("captured", "league", "NFL"),
    ("captured", "market", "longest_reception"),
    ("captured", "harIdentityState", "HAR_ALIAS_CACHED_UNVERIFIED"),
    ("captured", "sourceSnapshotTime", "2026-10-18T20:01:00Z"),
    ("captured", "sourceBodyHash", ""),
    ("captured", "sourceHarSha256", ""),
    ("captured", "platformRulesVerified", False),
    ("captured", "platformRulesSourceHash", ""),
    ("captured", "settlementRuleHash", ""),
    ("captured", "contentHash", "0" * 64),
])
def test_absent_conflicting_stale_or_postcutoff_contract_never_authorizes(change):
    raw, captured = _fixture()
    side, field, value = change
    if side == "raw":
        raw[field] = value
    else:
        captured[field] = value
        if field != "contentHash":
            captured["contentHash"] = content_hash({
                key: val for key, val in captured.items() if key != "contentHash"
            })
    if (side, field) in {
        ("raw", "direction"), ("raw", "line"), ("raw", "periodLabel")
    }:
        with pytest.raises(ValueError):
            validate_offer_revalidation(raw, snapshots={raw["claimId"]: captured}, cutoff=CUTOFF)
    elif side == "raw" and field == "eventStatus":
        with pytest.raises(ValueError):
            validate_offer_revalidation(raw, snapshots={raw["claimId"]: captured}, cutoff=CUTOFF)
    else:
        offer = validate_offer_revalidation(raw, snapshots={raw["claimId"]: captured}, cutoff=CUTOFF)
        assert offer["productionSelectionPermitted"] is False


def test_untrusted_caller_cannot_set_production_authorization():
    raw, captured = _fixture()
    raw["productionSelectionPermitted"] = True
    captured["platformRulesVerified"] = False
    captured["contentHash"] = content_hash({
        key: val for key, val in captured.items() if key != "contentHash"
    })
    offer = validate_offer_revalidation(raw, snapshots={raw["claimId"]: captured}, cutoff=CUTOFF)
    assert offer["productionSelectionPermitted"] is False
