"""Static contract checks for visible, diagnosable CI gates."""
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "dcm-v6-ci.yml"


def test_workflow_covers_main_pr_merge_queue_and_dispatch():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "      - main" in text
    assert "  merge_group:" in text
    assert "  workflow_dispatch:" in text
    assert "  pull_request:" in text


def test_workflow_has_visible_gates_and_failure_diagnostics():
    text = WORKFLOW.read_text(encoding="utf-8")
    for job in ("package", "tests", "constitution", "inventory", "research_contract", "python-dcm"):
        assert f"  {job}:" in text
    assert "if: ${{ failure() }}" in text
    assert "scripts/ci/run_gate.py" in text
    assert "actions/upload-artifact@v4" in text
    assert "continue-on-error" not in text
    assert "090826" not in text
    assert "needs.research_contract.result" in text
