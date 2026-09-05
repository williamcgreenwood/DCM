from __future__ import annotations

import json
from pathlib import Path

from dcm.runtime.schema_root import EXPECTED_SHA256, SCHEMA_V2_EXPECTED_SHA256, sha256_file, verify_schema_v2
from dcm.sports.basketball.minimal import basketball_conservation
from dcm.sports.baseball.pa import conservation as mlb_conservation
from dcm.model.worlds import sample_basketball

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "phase_bc_v2" / "phase_bc_schema_v2.json"

REQUIRED_DEFS = [
    "EventWorldSet", "EventWorld", "EventLatentState", "PlayerWorldState",
    "OpportunityState", "EfficiencyState", "PrimitiveStatLedger", "PrimitiveStatEntry",
    "MarketDefinition", "Offer", "EvidenceClaim", "EvidenceBundleManifest",
    "WorldProjection", "EntryPickContract", "EntryContract", "PickSettlement",
    "LineupSettlement", "WorldLineupOutcome", "ProductionReadiness",
]


def _validate(schema_def: dict, sample: dict) -> list[str]:
    missing = [k for k in schema_def.get("required") or [] if k not in sample]
    errors = [f"missing:{k}" for k in missing]
    props = schema_def.get("properties") or {}
    for key, spec in props.items():
        if key not in sample:
            continue
        expected = spec.get("type")
        value = sample[key]
        if expected == "string" and not isinstance(value, str):
            errors.append(f"type:{key}")
        elif expected == "integer" and not isinstance(value, int):
            errors.append(f"type:{key}")
        elif expected == "number" and not isinstance(value, (int, float)):
            errors.append(f"type:{key}")
        elif expected == "boolean" and not isinstance(value, bool):
            errors.append(f"type:{key}")
        elif expected == "array" and not isinstance(value, list):
            errors.append(f"type:{key}")
        elif expected == "object" and not isinstance(value, dict):
            errors.append(f"type:{key}")
        if spec.get("const") is not None and value != spec["const"]:
            errors.append(f"const:{key}")
    return errors


def test_schema_files_load_and_required_keys_present():
    data = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert data["schema_freeze_id"] == "PHASE_BC_SCHEMA_V2_2026-08-29"
    assert data["productionEligible"] is False
    assert data["acceptedForProduction"] is False
    assert data["predecessor_expected_sha256"] == EXPECTED_SHA256
    defs = data["$defs"]
    for name in REQUIRED_DEFS:
        assert name in defs, name
        assert defs[name].get("required"), name
        assert defs[name].get("properties"), name
    assert sha256_file(SCHEMA) == SCHEMA_V2_EXPECTED_SHA256
    state = verify_schema_v2(ROOT)
    assert state["productionEligible"] is False
    assert state["acceptedForProduction"] is False


def test_sample_objects_validate_against_field_schema():
    data = json.loads(SCHEMA.read_text(encoding="utf-8"))
    defs = data["$defs"]
    samples = {
        "OpportunityState": {"support_n": 3, "minutes_mean": 32.0},
        "EfficiencyState": {"support_n": 3, "rates": {"fga_per_min": 0.5}},
        "MarketDefinition": {
            "definitionId": "prizepicks|WNBA|pts|FULL_GAME",
            "platform": "prizepicks",
            "league": "WNBA",
            "market": "pts",
            "boardId": "FULL_GAME",
            "definitionVerified": True,
            "contentHash": "a" * 64,
        },
        "Offer": {
            "offerId": "p1",
            "projectionId": "p1",
            "definitionId": "prizepicks|WNBA|pts|FULL_GAME",
            "line": 20.5,
            "offeredHigher": True,
            "offeredLower": True,
            "modifier": "STANDARD",
            "contentHash": "b" * 64,
        },
        "ProductionReadiness": {
            "productionSelectionReady": False,
            "systemCertified": False,
            "predictiveValidationEarned": False,
            "productionEligible": False,
            "acceptedForProduction": False,
            "learningRevision": "LR000000",
            "predictiveClaim": "NONE",
        },
        "EvidenceClaim": {
            "source_id": "TEST",
            "url": "https://www.wnba.com/x",
            "published_at": "2026-08-27T00:00:00Z",
            "observed_at": "2026-08-27T00:00:00Z",
            "forecast_cutoff": "2026-08-28T00:00:00Z",
            "semantic_scope": "SPORT",
            "scope_id": "basketball:WNBA",
            "claim_type": "rules",
            "claim_value": {"ok": True},
            "reliability": 0.9,
            "freshness": 0.8,
            "source_hash": "c" * 64,
            "claim_hash": "d" * 64,
        },
    }
    for name, sample in samples.items():
        errors = _validate(defs[name], sample)
        assert not errors, (name, errors)


def test_conservation_identities_still_declared_and_enforced():
    data = json.loads(SCHEMA.read_text(encoding="utf-8"))
    ids = data["identities"]
    assert ids["basketball"]["PTS"] == "2*2PM + 3*3PM + FTM"
    assert ids["football"]["rush_att"] == "designed_rush_att + scramble_att"
    assert ids["mlb_shadow"]["H"] == "1B + 2B + 3B + HR"
    w = sample_basketball(__import__("random").Random(3), 34.0)
    assert all(r.passed for r in basketball_conservation(w))
    mlb = {
        "PA": 4, "AB": 4, "BB": 0, "HBP": 0, "SF": 0, "SH": 0, "SO": 1,
        "H": 1, "1B": 1, "2B": 0, "3B": 0, "HR": 0, "TB": 1,
    }
    assert all(c["passed"] for c in mlb_conservation(mlb))
