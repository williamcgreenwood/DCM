"""Phase B/C immutable schema root-of-trust gate."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA_ID = "PHASE_BC_SCHEMA_V1_2026-08-25"
EXPECTED_SHA256 = "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    }
    if path is None:
        return state
    observed = sha256_file(path)
    state["observedSha256"] = observed
    if observed != EXPECTED_SHA256:
        state["state"] = "HASH_MISMATCH_RECONSTRUCTION_NOT_CANONICAL"
        return state
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["state"] = "INVALID_JSON"
        return state
    state["state"] = "HASH_VERIFIED"
    state["productionEligible"] = True
    state["topLevelType"] = type(obj).__name__
    return state
