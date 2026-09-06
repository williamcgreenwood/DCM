"""Phase B/C immutable schema root-of-trust gate.

V1 expected SHA-256 is immutable even when original bytes are absent.
V2 is an explicitly new frozen schema with its own hash and ADR.
V2 does not replace or weaken the V1 production gate.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA_ID = "PHASE_BC_SCHEMA_V1_2026-08-25"
EXPECTED_SHA256 = "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22"

SCHEMA_V2_ID = "PHASE_BC_SCHEMA_V2_2026-08-29"
# Filled from frozen bytes at import via HASH.txt if present; also hardcoded after freeze.
SCHEMA_V2_EXPECTED_SHA256 = "6edbc92e94c734ead8c94edcfa8b112c2fb33ec3fb4610a89199b84993df6521"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _v2_hash_from_tree() -> str:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "schemas" / "phase_bc_v2" / "HASH.txt",
        here.parents[2] / "schemas" / "phase_bc_v2" / "HASH.txt",
        here.parents[3] / "schemas" / "phase_bc_v2" / "HASH.txt" if len(here.parents) > 3 else here.parent / "HASH.txt",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip().split()[0]
    return SCHEMA_V2_EXPECTED_SHA256


def verify_schema(workspace: Path = Path("/workspace")) -> dict[str, Any]:
    explicit = Path(os.environ["DCM_PHASE_BC_SCHEMA"]) if os.environ.get("DCM_PHASE_BC_SCHEMA") else None
    candidates = [
        explicit,
        workspace / "dcm_v6" / "canonical_mount" / "Phase_BC_Immutable_Contracts.json",
        workspace / "artifacts" / "dcm_v6_workstream_ab" / "schemas" / "Phase_BC_Immutable_Contracts.json",
        workspace / "schemas" / "Phase_BC_Immutable_Contracts.json",
        Path("/mnt/data/Phase_BC_Immutable_Contracts.json"),
    ]
    path = next((p for p in candidates if p is not None and p.is_file()), None)
    state = {
        "schemaId": SCHEMA_ID,
        "expectedSha256": EXPECTED_SHA256,
        "observedSha256": None,
        "path": str(path) if path else None,
        "state": "ABSENT",
        "productionEligible": False,
        "v1BytesAvailable": False,
        "note": "Do not reconstruct V1 bytes or change expectedSha256.",
    }
    if path is None:
        return state
    observed = sha256_file(path)
    state["observedSha256"] = observed
    if observed != EXPECTED_SHA256:
        state["state"] = "HASH_MISMATCH_RECONSTRUCTION_NOT_CANONICAL"
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, dict) and obj.get("canonical_json_bytes_available") is False:
                state["state"] = "HASH_MISMATCH_RECONSTRUCTION_NOT_CANONICAL"
                state["v1BytesAvailable"] = False
        except (OSError, json.JSONDecodeError):
            pass
        return state
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["state"] = "INVALID_JSON"
        return state
    state["state"] = "HASH_VERIFIED"
    state["productionEligible"] = True
    state["v1BytesAvailable"] = True
    state["topLevelType"] = type(obj).__name__
    return state


def v2_schema_path(workspace: Path | None = None) -> Path | None:
    explicit = Path(os.environ["DCM_PHASE_BC_SCHEMA_V2"]) if os.environ.get("DCM_PHASE_BC_SCHEMA_V2") else None
    here = Path(__file__).resolve()
    candidates = [
        explicit,
        here.parents[1] / "schemas" / "phase_bc_v2" / "phase_bc_schema_v2.json",
        here.parents[2] / "schemas" / "phase_bc_v2" / "phase_bc_schema_v2.json",
        here.parents[3] / "schemas" / "phase_bc_v2" / "phase_bc_schema_v2.json" if len(here.parents) > 3 else None,
        (workspace / "artifacts" / "dcm_v6_workstream_ab" / "schemas" / "phase_bc_v2" / "phase_bc_schema_v2.json") if workspace else None,
        (workspace / "schemas" / "phase_bc_v2" / "phase_bc_schema_v2.json") if workspace else None,
    ]
    return next((p for p in candidates if p is not None and p.is_file()), None)


def verify_schema_v2(workspace: Path | None = None) -> dict[str, Any]:
    expected = _v2_hash_from_tree() or SCHEMA_V2_EXPECTED_SHA256
    path = v2_schema_path(workspace)
    state = {
        "schemaId": SCHEMA_V2_ID,
        "expectedSha256": expected,
        "observedSha256": None,
        "path": str(path) if path else None,
        "state": "ABSENT",
        "frozen": False,
        "productionEligible": False,
        "note": "V2 is a new schema. It does not satisfy the V1 production hash gate.",
    }
    if path is None:
        return state
    observed = sha256_file(path)
    state["observedSha256"] = observed
    if not expected:
        state["state"] = "HASH_UNDECLARED"
        return state
    if observed != expected:
        state["state"] = "HASH_MISMATCH"
        return state
    state["state"] = "HASH_VERIFIED"
    state["frozen"] = True
    # Explicit: V2 freeze is not automatic production promotion.
    state["productionEligible"] = False
    state["acceptedForProduction"] = False
    return state
