"""Single-source software identity loaded from VERSION.json.

Do not duplicate drifting constants. Runner, docs, CI, and the portable
release builder all read this module.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ExactVersionMismatch(RuntimeError):
    """Requested --version does not resolve to this build's VERSION.json."""


def _candidates() -> list[Path]:
    env = os.environ.get("DCM_VERSION_JSON")
    here = Path(__file__).resolve()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.extend(
        [
            here.parent / "VERSION.json",
            here.parents[1] / "VERSION.json",
            here.parents[2] / "VERSION.json" if len(here.parents) > 2 else here.parent / "VERSION.json",
            here.parents[3] / "VERSION.json" if len(here.parents) > 3 else here.parent / "VERSION.json",
            Path.cwd() / "VERSION.json",
        ]
    )
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


def version_json_path() -> Path:
    for path in _candidates():
        if path.is_file():
            return path
    raise FileNotFoundError("VERSION_JSON_MISSING")


def load_version_manifest() -> dict[str, Any]:
    path = version_json_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("VERSION_JSON_INVALID")
    data = dict(data)
    data["_path"] = str(path)
    return data


def _manifest() -> dict[str, Any]:
    try:
        return load_version_manifest()
    except FileNotFoundError:
        return {
            "software": "6.0.0+WSAB.E2E.PRODUCTION_PIPELINE.LR000000",
            "softwareShort": "6.0.0",
            "learningRevision": "LR000000",
            "predictiveClaim": "NONE",
            "schemaId": "PHASE_BC_SCHEMA_V2_2026-08-29",
            "expectedV1Hash": "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22",
        }


_M = _manifest()
SOFTWARE = str(_M.get("software") or "6.0.0+WSAB.E2E.PRODUCTION_PIPELINE.LR000000")
SOFTWARE_SHORT = str(_M.get("softwareShort") or "6.0.0")
LEARNING_REVISION = str(_M.get("learningRevision") or "LR000000")
PREDICTIVE_CLAIM = str(_M.get("predictiveClaim") or "NONE")
SCHEMA_V2_ID = str(_M.get("schemaId") or "PHASE_BC_SCHEMA_V2_2026-08-29")
EXPECTED_V1_HASH = str(
    _M.get("expectedV1Hash") or "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22"
)


def accepted_version_tokens(manifest: dict[str, Any] | None = None) -> set[str]:
    data = manifest or load_version_manifest()
    tokens = {str(data.get("software") or SOFTWARE), str(data.get("softwareShort") or SOFTWARE_SHORT)}
    return {t for t in tokens if t}


def resolve_requested_version(requested: str | None) -> dict[str, Any]:
    """Map a CLI --version token onto the VERSION.json manifest.

    Omitted/empty defaults to the current software string and is logged by the
    caller. Any other token must be an exact match of `software` or
    `softwareShort` in VERSION.json. There is no fuzzy / prefix match.
    """
    manifest = load_version_manifest()
    software = str(manifest.get("software") or SOFTWARE)
    tokens = accepted_version_tokens(manifest)
    if requested is None or str(requested).strip() == "":
        return {
            **manifest,
            "software": software,
            "requested": None,
            "resolved": software,
            "defaulted": True,
        }
    token = str(requested).strip()
    if token not in tokens:
        raise ExactVersionMismatch(
            f"EXACT_VERSION_MISMATCH: requested={token!r} software={software!r} "
            f"accepted={sorted(tokens)}"
        )
    return {
        **manifest,
        "software": software,
        "requested": token,
        "resolved": software,
        "defaulted": False,
    }
