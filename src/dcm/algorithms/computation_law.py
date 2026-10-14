"""Identity for the permanent cross-cutting computation and discovery law."""
from __future__ import annotations

import hashlib
from pathlib import Path

COMPUTATION_LAW_VERSION = "PILLARS-UNIVERSAL-ALGORITHMIC-COMPUTATION-v1.0.0-20261014"
COMPUTATION_LAW_SHA256 = "9ff2ee25592c97342585623901eaebe2a782379e01572042c5af7b00c1bee598"
LAW_RELATIVE_PATH = Path("docs/engineering/UNIVERSAL_ALGORITHMIC_COMPUTATION_AND_RESEARCH_DISCOVERY_LAW.md")


def law_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / LAW_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("UNIVERSAL_COMPUTATION_LAW_MISSING")


def computation_law_identity() -> dict[str, str]:
    try:
        path = law_path()
    except FileNotFoundError:
        # Wheels do not include repository engineering docs. The constant is
        # generated from the committed canonical document and CI verifies it.
        return {"version": COMPUTATION_LAW_VERSION, "sha256": COMPUTATION_LAW_SHA256,
                "path": LAW_RELATIVE_PATH.as_posix()}
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if COMPUTATION_LAW_VERSION not in text or hashlib.sha256(raw).hexdigest() != COMPUTATION_LAW_SHA256:
        raise RuntimeError("UNIVERSAL_COMPUTATION_LAW_VERSION_OR_HASH_DRIFT")
    return {
        "version": COMPUTATION_LAW_VERSION,
        "sha256": COMPUTATION_LAW_SHA256,
        "path": LAW_RELATIVE_PATH.as_posix(),
    }
