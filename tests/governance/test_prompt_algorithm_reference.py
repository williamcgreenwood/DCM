"""Future prompts/docs must inherit the constitution; silent omission fails CI."""
from __future__ import annotations

from pathlib import Path

VERSION = "DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903"
ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SURFACES = (
    "AGENTS.md",
    "docs/PROGRAM_STATUS.md",
    "docs/CURRENT_WORK_HANDOFF.md",
    "docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md",
    "docs/architecture/CONSTITUTION_INHERITANCE.md",
    "docs/architecture/ADR-ALG-CONST-001-r0.md",
)


def test_prompt_algorithm_reference():
    missing = []
    for rel in REQUIRED_SURFACES:
        path = ROOT / rel
        if not path.is_file():
            missing.append(f"MISSING:{rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if VERSION not in text:
            missing.append(f"NO_VERSION:{rel}")
    assert missing == []
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "silent" in agents.lower() or "Algorithmic Constitution" in agents
    assert "LR000000" in (ROOT / "docs" / "PROGRAM_STATUS.md").read_text(encoding="utf-8")
    assert "NONE" in (ROOT / "docs" / "PROGRAM_STATUS.md").read_text(encoding="utf-8")
