from pathlib import Path

from dcm.runtime.schema_root import EXPECTED_SHA256, SCHEMA_V2_EXPECTED_SHA256, SCHEMA_V2_ID, sha256_file, verify_schema, verify_schema_v2

ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "dcm_v6_workstream_ab"


def test_v1_expected_hash_is_immutable_and_bytes_unavailable():
    assert EXPECTED_SHA256 == "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22"
    recon = ROOT / "schemas" / "Phase_BC_Immutable_Contracts.json"
    assert recon.is_file()
    assert sha256_file(recon) != EXPECTED_SHA256
    state = verify_schema(ROOT)
    # reconstruction is found relative to workspace or artifacts; either ABSENT or mismatch
    assert state["expectedSha256"] == EXPECTED_SHA256
    assert state["productionEligible"] is False
    assert state["state"] in {"ABSENT", "HASH_MISMATCH_RECONSTRUCTION_NOT_CANONICAL"}


def test_v2_frozen_hash_matches_bytes():
    path = ROOT / "schemas" / "phase_bc_v2" / "phase_bc_schema_v2.json"
    declared = (ROOT / "schemas" / "phase_bc_v2" / "HASH.txt").read_text().strip().split()[0]
    observed = sha256_file(path)
    assert declared == observed
    assert observed == SCHEMA_V2_EXPECTED_SHA256
    state = verify_schema_v2(ROOT)
    assert state["schemaId"] == SCHEMA_V2_ID
    assert state["state"] == "HASH_VERIFIED"
    assert state["frozen"] is True
    assert state["productionEligible"] is False
