"""Explicit, run-scoped integration-test policy.

Historical replay runs may need to accept observations retrieved after their
frozen cutoff so the research plumbing can be exercised.  That exception is
opt-in, bound to one run directory, and fail-closed when its declaration is
missing or malformed.  Production runs have no ``test_mode.json`` and retain
normal cutoff enforcement.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TEST_MODE_SCHEMA = "pillars_dcm.research_test_mode.v1"


def load_test_mode(run_dir: Path) -> dict[str, Any]:
    """Load and validate a run-local test policy.

    A malformed declaration is an error rather than permission to bypass a
    guard.  An absent file is the ordinary production/default mode.
    """
    path = Path(run_dir) / "test_mode.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("TEST_MODE_INVALID") from exc
    if not isinstance(raw, dict):
        raise ValueError("TEST_MODE_INVALID")
    enabled = raw.get("cutoffBypass") is True
    if not enabled:
        # A marker without an enabled bypass is ambiguous and must not be
        # allowed to influence downstream eligibility decisions.
        if raw.get("testOnlyCutoffBypass") is True:
            raise ValueError("TEST_MODE_INVALID")
        return raw
    required = {
        "schema": TEST_MODE_SCHEMA,
        "runId": Path(run_dir).name,
        "testOnlyCutoffBypass": True,
        "productionEligible": False,
        "predictiveClaim": "NONE",
    }
    if any(raw.get(key) != value for key, value in required.items()):
        raise ValueError("TEST_MODE_INVALID")
    if not str(raw.get("reason") or "").strip():
        raise ValueError("TEST_MODE_INVALID")
    return raw


def cutoff_enforced(run_dir: Path) -> bool:
    """Return whether source observations must satisfy the frozen cutoff."""
    return load_test_mode(Path(run_dir)).get("cutoffBypass") is not True


def production_eligible(run_dir: Path) -> bool:
    """Return whether this run's research may be used for production."""
    return load_test_mode(Path(run_dir)).get("cutoffBypass") is not True


__all__ = ["TEST_MODE_SCHEMA", "load_test_mode", "cutoff_enforced", "production_eligible"]
