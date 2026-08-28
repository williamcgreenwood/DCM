import json
from pathlib import Path

from dcm.contracts.hashes import LINEAGE_STAGES, content_hash, require_lineage
from dcm.contracts.hashes import LineageError
from dcm.contracts.schemas import SCHEMA_VERSION


def test_schema_version_matches_freeze_id():
    assert SCHEMA_VERSION == "PHASE_BC_SCHEMA_V1_2026-08-25"


def test_schema_inventory_adds_no_new_common_types():
    path = Path(__file__).resolve().parents[1] / "schemas" / "Phase_BC_Immutable_Contracts.json"
    data = json.loads(path.read_text())
    assert data["new_common_types_added"] == []
    assert data["canonical_json_bytes_available"] is False
    assert "EntryContract" in data["objects"]
    assert "WorldLineupOutcome" in data["objects"]


def test_lineage_cannot_skip_stages():
    populated = {"evidence_graph_hash": "a"}
    try:
        require_lineage(populated, through="primitive_ledger_hash")
        assert False
    except LineageError:
        pass


def test_lineage_stage_order_matches_blueprint():
    assert LINEAGE_STAGES[0] == "evidence_graph_hash"
    assert LINEAGE_STAGES[-1] == "world_lineup_outcome_hash"
    assert "entry_contract_hash" in LINEAGE_STAGES


def test_content_hash_is_deterministic():
    assert content_hash({"x": 1, "y": [2, 3]}) == content_hash({"y": [2, 3], "x": 1})
