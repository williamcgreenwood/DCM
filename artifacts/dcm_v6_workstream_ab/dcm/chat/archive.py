"""Host archive/audit wrappers over the existing GitHub pack path."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dcm.chat.state import read_json
from dcm.runtime.github_archive import (
    append_index,
    build_run_audit,
    certification_fields,
    materialize_github_pack,
)
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE


def audit_run(dest: Path) -> dict[str, Any]:
    return build_run_audit(Path(dest))


def archive_run(dest: Path, *, repo_root: Path | None = None, format: str = "github-pack") -> dict[str, Any]:
    dest = Path(dest)
    audit = build_run_audit(dest)
    root = Path(repo_root) if repo_root is not None else dest.parents[2] if len(dest.parents) > 2 else dest.parent
    pack = materialize_github_pack(dest, root)
    run_id = str(audit.get("runId") or dest.name)
    append_index(
        root,
        {
            "runId": run_id,
            "path": f"audit/runs/{run_id}",
            "hallucinationRisk": audit.get("hallucinationRisk"),
            "runState": audit.get("runState"),
            "frozenForecastHash": audit.get("frozenForecastHash"),
            "createdAtUtc": audit.get("createdAtUtc"),
            "software": audit.get("software") or SOFTWARE,
            "learningRevision": audit.get("learningRevision") or LEARNING_REVISION,
            "predictiveClaim": audit.get("predictiveClaim") or PREDICTIVE_CLAIM,
            "format": format,
            **certification_fields(audit),
        },
    )
    freeze = read_json(dest / "freeze.json") or {}
    return {
        "runId": run_id,
        "archivePath": str(pack),
        "format": format,
        "githubWriteRequiredForForecast": False,
        "frozenForecastHash": freeze.get("frozenForecastHash") or audit.get("frozenForecastHash"),
        **certification_fields(audit),
    }
