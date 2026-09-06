"""Tests for the thin requirement ledger loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from dcm.governance.requirement_ledger import (
    STATUS_VALUES,
    cfb_critical_blockers,
    load_requirement_ledger,
    summarize_by_status,
)

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs" / "requirements" / "REQUIREMENT_LEDGER.v1.json"


def test_ledger_file_exists():
    assert LEDGER.is_file()


def test_load_requirement_ledger_schema_and_statuses():
    doc = load_requirement_ledger(str(LEDGER))
    assert doc["schema"] == "pillars_dcm.requirement_ledger.v1"
    assert doc["inspected_main_sha"].startswith("c017243")
    assert len(doc["requirements"]) >= 50
    for row in doc["requirements"]:
        assert row["status"] in STATUS_VALUES
        assert row["requirement_id"]


def test_summarize_by_status_atomic():
    summary = summarize_by_status(load_requirement_ledger(str(LEDGER)), atomic_only=True)
    assert "IMPLEMENTED" in summary
    assert sum(summary.values()) == sum(
        1
        for r in load_requirement_ledger(str(LEDGER))["requirements"]
        if r["requirement_id"].startswith("REQ-")
    )


def test_p380x_policy_present_and_no_engine_copy_claim():
    doc = load_requirement_ledger(str(LEDGER))
    policy = doc["p380x_policy"]
    assert "catalog" in policy["pillars_are"].lower()
    assert "1500" in policy["forbidden"] or "engines" in policy["forbidden"]
    skipped = " ".join(doc["deliberately_not_copied_from_zip"]).lower()
    assert "1500" in skipped or "p380x" in skipped
    assert "har" in skipped


def test_cfb_critical_blockers_nonempty_honest():
    blockers = cfb_critical_blockers(load_requirement_ledger(str(LEDGER)))
    assert blockers, "CFB path should still list open blockers"
    assert all(b["status"] in {"PARTIAL", "MISSING", "EXTERNAL"} for b in blockers)


def test_invalid_status_rejected(tmp_path: Path):
    bad = {
        "schema": "pillars_dcm.requirement_ledger.v1",
        "requirements": [
            {"requirement_id": "REQ-X", "status": "DONE_SHIPPED"},
        ],
    }
    path = tmp_path / "bad.json"
    path.write_text(__import__("json").dumps(bad))
    with pytest.raises(ValueError, match="invalid status"):
        load_requirement_ledger(str(path))
