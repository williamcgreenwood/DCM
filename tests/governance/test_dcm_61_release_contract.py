"""The 6.1 release prompt and control contract must stay executable and honest."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/releases/DCM_6_1_ACCEPTANCE_CONTRACT.md"
PROMPT = ROOT / "docs/prompts/DCM_6_1_EXECUTION_PROMPT.md"
ADR = ROOT / "docs/architecture/ADR-DCM-6-1-NATIVE-RUNTIME.md"
LEDGER = ROOT / "docs/requirements/DCM_6_1_REQUIREMENT_LEDGER.json"


def test_dcm_61_control_artifacts_exist_and_inherit_policy():
    for path in (CONTRACT, PROMPT, ADR, LEDGER):
        assert path.is_file(), path
        assert "DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903" in path.read_text(
            encoding="utf-8"
        )


def test_dcm_61_ledger_covers_the_release_gates_without_false_certification():
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    rows = payload["requirements"]
    assert payload["release"] == "6.1.0"
    assert {row["id"] for row in rows} == {f"DCM61-{i:02d}" for i in range(1, 21)}
    assert all(row["status"] in payload["status_values"] for row in rows)
    assert any(row["status"] == "EXTERNAL_BLOCKED" for row in rows)


def test_dcm_61_prompt_preserves_privacy_fail_closed_and_release_states():
    text = PROMPT.read_text(encoding="utf-8")
    for needle in (
        "Raw HARs",
        "fail closed",
        "LR000000",
        "NONE",
        "dcm-host run",
        "CFB and NFL only",
        "branch → PR",
    ):
        assert needle in text
    assert "LEGACY_RUNTIME_UNAVAILABLE" in ADR.read_text(encoding="utf-8")
