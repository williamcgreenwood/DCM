"""CLI: build a GitHub-verifiable audit pack for an existing DCM run dest.

python -m dcm.archive --dest dcm_v6/RUNS/<id> [--repo PATH] [--push] [--no-archive-push]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dcm.runtime.github_archive import (
    append_index,
    build_run_audit,
    certification_fields,
    materialize_github_pack,
    push_to_github,
)
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE


def _find_repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "VERSION.json").is_file() and (candidate / ".git").exists():
            return candidate
        if (candidate / "VERSION.json").is_file() and (candidate / "pyproject.toml").is_file():
            return candidate
    return here


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a GitHub-verifiable DCM run audit (no HARs, no sqlite)."
    )
    parser.add_argument("--dest", type=Path, required=True, help="Existing run directory")
    parser.add_argument("--repo", type=Path, default=None, help="Git repo root to write audit/runs/<id>")
    parser.add_argument("--push", action="store_true", help="git push origin HEAD after commit (optional)")
    parser.add_argument(
        "--no-archive-push",
        action="store_true",
        help="Write the local pack (and commit if possible) but do not git push. Default is local-only.",
    )
    args = parser.parse_args(argv)

    dest = args.dest.expanduser().resolve()
    if not dest.is_dir():
        print(f"DEST_NOT_FOUND: {dest}", file=sys.stderr)
        return 2
    repo = (args.repo.expanduser().resolve() if args.repo else _find_repo_root(dest))

    audit = build_run_audit(dest)
    pack = materialize_github_pack(dest, repo)
    run_id = str(audit.get("runId") or dest.name)
    append_index(
        repo,
        {
            "runId": run_id,
            "path": f"audit/runs/{run_id}",
            "locksCertified": audit.get("locksCertified"),
            "hallucinationRisk": audit.get("hallucinationRisk"),
            "runState": audit.get("runState"),
            "frozenForecastHash": audit.get("frozenForecastHash"),
            "createdAtUtc": audit.get("createdAtUtc"),
            "software": audit.get("software") or SOFTWARE,
            "learningRevision": audit.get("learningRevision") or LEARNING_REVISION,
            "predictiveClaim": audit.get("predictiveClaim") or PREDICTIVE_CLAIM,
            **certification_fields(audit),
        },
    )
    gh: dict[str, Any] = push_to_github(repo, run_id, push=bool(args.push) and not bool(args.no_archive_push))
    print(
        json.dumps(
            {
                "runId": run_id,
                "dest": str(dest),
                "archivePath": str(pack),
                "locksCertified": audit.get("locksCertified"),
                "archiveIntegrityCertified": audit.get("archiveIntegrityCertified"),
                "evidenceCoverageCertified": audit.get("evidenceCoverageCertified"),
                "evidenceTemporalCertified": audit.get("evidenceTemporalCertified"),
                "modelRunCertified": audit.get("modelRunCertified"),
                "selectionCertified": audit.get("selectionCertified"),
                "productionRootCertified": audit.get("productionRootCertified"),
                "predictiveValidationEarned": audit.get("predictiveValidationEarned"),
                "hashCertifiedPythonFreeze": audit.get("hashCertifiedPythonFreeze"),
                "hallucinationRisk": audit.get("hallucinationRisk"),
                "githubCommit": gh.get("commit"),
                "pushed": gh.get("pushed"),
                "error": gh.get("error"),
                "software": SOFTWARE,
                "learningRevision": LEARNING_REVISION,
                "predictiveClaim": PREDICTIVE_CLAIM,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
