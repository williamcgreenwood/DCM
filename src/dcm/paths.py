"""Repo/archive path resolution that survives the src/ package layout.

Behavior-preserving helpers: fixtures/configs that still live under the
historical workstream archive remain reachable without making that archive the
install root.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_ARCHIVE_REL = Path("artifacts") / "dcm_v6_workstream_ab"


@lru_cache(maxsize=1)
def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "VERSION.json").is_file() and (parent / "pyproject.toml").is_file():
            return parent
    # Installed / editable edge: walk until VERSION.json alone.
    for parent in here.parents:
        if (parent / "VERSION.json").is_file():
            return parent
    return Path.cwd()


def package_dir() -> Path:
    """Directory containing the installed/editable ``dcm`` package."""
    return Path(__file__).resolve().parent


def src_root() -> Path:
    """Parent of the ``dcm`` package (``src/`` in checkout)."""
    return package_dir().parent


@lru_cache(maxsize=1)
def archive_root() -> Path:
    """Historical workstream archive (fixtures/configs/docs). Not install root."""
    candidate = repo_root() / _ARCHIVE_REL
    if candidate.is_dir():
        return candidate
    return candidate  # deterministic path even if absent


def default_workspace() -> Path:
    root = repo_root()
    if (root / "VERSION.json").is_file():
        return root
    return Path.cwd()
