"""Load and hash the committed Algorithmic Constitution document."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

ALGORITHM_CONSTITUTION_VERSION = "DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903"
PROMPT_DECLARED_CONSTITUTION_SHA256 = "bba7b082bf67e12d87e675ac58d5b6f96d9cbad9b6a487a0aa157bf7cef9e599"
CONSTITUTION_RELATIVE = "docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md"


def _candidates() -> list[Path]:
    env = os.environ.get("DCM_ALGORITHMIC_CONSTITUTION")
    here = Path(__file__).resolve()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    # repo root from dcm/algorithms/this file → parents[4] is repo root in checkout
    for parent in here.parents:
        out.append(parent / CONSTITUTION_RELATIVE)
    out.append(here.parent / "data" / "DCM_ALGORITHMIC_CONSTITUTION.md")
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in out:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def constitution_path() -> Path:
    for path in _candidates():
        if path.is_file():
            return path
    raise FileNotFoundError("ALGORITHM_CONSTITUTION_MISSING")


def load_constitution_text() -> str:
    return constitution_path().read_text(encoding="utf-8")


def constitution_sha256(text: str | None = None) -> str:
    raw = (text if text is not None else load_constitution_text()).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def prompt_declared_constitution_sha256() -> str:
    """Lineage hash declared by the v3 master prompt. Not a substitute for file bytes."""
    return PROMPT_DECLARED_CONSTITUTION_SHA256


def constitution_identity() -> dict[str, str]:
    from dcm.algorithms.registry import algorithm_registry_sha256

    text = load_constitution_text()
    if ALGORITHM_CONSTITUTION_VERSION not in text:
        raise RuntimeError("ALGORITHM_CONSTITUTION_VERSION_DRIFT")
    if "REQUIRED_CORE" not in text or "PERMANENT_CHALLENGER" not in text:
        raise RuntimeError("ALGORITHM_CONSTITUTION_BODY_INCOMPLETE")
    return {
        "version": ALGORITHM_CONSTITUTION_VERSION,
        "sha256": constitution_sha256(text),
        "path": str(constitution_path()),
        "promptDeclaredSha256": PROMPT_DECLARED_CONSTITUTION_SHA256,
        "registrySha256": algorithm_registry_sha256(),
    }
