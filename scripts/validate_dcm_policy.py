#!/usr/bin/env python3
"""Cheap CI gate for permanent DCM coding/prompt policy inheritance."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STANDARD = ROOT / "docs/engineering/DCM_CODING_AND_PROMPT_STANDARD.md"
HIERARCHY = ROOT / "docs/engineering/DCM_DRIVE_HIERARCHY.md"
AGENTS = ROOT / "AGENTS.md"
REGISTRY = ROOT / "configs/algorithm_registry.json"


def main() -> int:
    errors: list[str] = []
    required = {
        STANDARD: ("cutoff", "lineage", "Drive", "PLAYABLE", "checkpoint", "benchmark"),
        HIERARCHY: ("00_control", "02_research", "09_engineering", "read back", "raw HAR"),
        AGENTS: ("Algorithmic Constitution", "main", "fail closed", "future-only", "storage_router"),
    }
    for path, needles in required.items():
        if not path.is_file():
            errors.append(f"MISSING:{path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle.lower() not in text.lower():
                errors.append(f"POLICY_TEXT_MISSING:{path.relative_to(ROOT)}:{needle}")

    if REGISTRY.is_file():
        try:
            payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
            rows = payload.get("algorithms") if isinstance(payload, dict) else None
            if not isinstance(rows, list) or not rows:
                errors.append("ALGORITHM_REGISTRY_EMPTY")
            else:
                for row in rows:
                    if not isinstance(row, dict) or not row.get("algorithm_id"):
                        errors.append("ALGORITHM_REGISTRY_ID_MISSING")
                        break
                    if str(row["algorithm_id"]) in {"ALG-001", "ALG-002", "ALG-003", "ALG-004", "ALG-005", "ALG-006", "ALG-007"}:
                        errors.append("ALGORITHM_REGISTRY_PLACEHOLDER_ID")
                        break
        except json.JSONDecodeError:
            errors.append("ALGORITHM_REGISTRY_INVALID_JSON")

    try:
        tracked = subprocess.run(
            ["git", "ls-files", "*.har", "*.sqlite", "*.sqlite3"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        ).stdout.splitlines()
    except OSError:
        tracked = []
    for item in tracked:
        normalized = item.replace("\\", "/").lower()
        if "fixtures/sanitized_live_har/" not in normalized:
            errors.append(f"FORBIDDEN_TRACKED_RAW_ARTIFACT:{item}")

    if errors:
        for error in errors:
            print(error)
        return 1
    print("DCM_POLICY_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
