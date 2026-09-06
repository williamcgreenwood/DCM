"""Thin loader for docs/requirements/REQUIREMENT_LEDGER.v1.json.

Behavior-preserving: read-only access for agents/CI. Does not execute handoff
ZIP content and does not activate donor engines.
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

STATUS_VALUES = frozenset(
    {"IMPLEMENTED", "PARTIAL", "MISSING", "EXTERNAL", "SUPERSEDED", "N/A"}
)

_SCHEMA = "pillars_dcm.requirement_ledger.v1"


def _default_ledger_path() -> Path:
    # Prefer in-repo docs relative to this package: src/dcm/governance → repo root
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "docs" / "requirements" / "REQUIREMENT_LEDGER.v1.json",
        Path.cwd() / "docs" / "requirements" / "REQUIREMENT_LEDGER.v1.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "REQUIREMENT_LEDGER.v1.json not found under docs/requirements/"
    )


@lru_cache(maxsize=4)
def load_requirement_ledger(path: str | None = None) -> dict[str, Any]:
    """Load and lightly validate the canonical requirement ledger."""
    ledger_path = Path(path) if path else _default_ledger_path()
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    if data.get("schema") != _SCHEMA:
        raise ValueError(f"unexpected ledger schema: {data.get('schema')!r}")
    requirements = data.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("ledger requirements must be a non-empty list")
    for item in requirements:
        status = item.get("status")
        if status not in STATUS_VALUES:
            raise ValueError(
                f"invalid status {status!r} on {item.get('requirement_id')!r}"
            )
        if not item.get("requirement_id"):
            raise ValueError("requirement_id required")
    return data


def summarize_by_status(
    ledger: dict[str, Any] | None = None,
    *,
    atomic_only: bool = True,
) -> dict[str, int]:
    """Return status → count. By default counts atomic REQ-* rows only."""
    doc = ledger if ledger is not None else load_requirement_ledger()
    rows = doc["requirements"]
    if atomic_only:
        rows = [r for r in rows if str(r["requirement_id"]).startswith("REQ-")]
    return dict(sorted(Counter(r["status"] for r in rows).items()))


def cfb_critical_blockers(ledger: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return CFB-critical atomics that are not IMPLEMENTED."""
    doc = ledger if ledger is not None else load_requirement_ledger()
    open_statuses = {"PARTIAL", "MISSING", "EXTERNAL"}
    out: list[dict[str, Any]] = []
    for row in doc["requirements"]:
        if not str(row["requirement_id"]).startswith("REQ-"):
            continue
        if not row.get("cfb_critical_path"):
            continue
        if row.get("status") not in open_statuses:
            continue
        out.append(
            {
                "requirement_id": row["requirement_id"],
                "title": row.get("title"),
                "status": row.get("status"),
                "blocker": row.get("blocker"),
            }
        )
    return out
