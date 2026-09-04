"""Safe capability and authority manifest for a ChatGPT-native run."""
from __future__ import annotations

import hashlib
import importlib.util
import platform
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from dcm.contracts.hashes import content_hash


def _git(workspace: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(workspace), capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    value = (proc.stdout or "").strip()
    return value if proc.returncode == 0 and value else None


def _file_descriptor(path: Path) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "name": path.name,
        "exists": path.is_file(),
        "rawSensitive": path.suffix.lower() in {".har", ".json", ".jsonl"} and "evidence" not in path.parts,
        "replayAllowed": False,
    }
    if path.is_file():
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(block)
        descriptor.update({"sizeBytes": path.stat().st_size, "sha256": h.hexdigest()})
    return descriptor


def build_capability_manifest(
    *,
    workspace: Path,
    run_id: str,
    forecast_cutoff: str,
    input_paths: Iterable[Path] = (),
    har_sha256: str = "",
    timebox_minutes: int = 45,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    deadline = started + timedelta(minutes=max(1, int(timebox_minutes)))
    body: dict[str, Any] = {
        "schema": "pillars_dcm.capability_authority_manifest.v1",
        "runId": str(run_id),
        "sessionStartedAtUtc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timeboxDeadlineUtc": deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "forecastCutoff": str(forecast_cutoff),
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pytestDiscoverable": importlib.util.find_spec("pytest") is not None,
        },
        "repository": {
            "rootName": workspace.name,
            "branch": _git(workspace, "branch", "--show-current"),
            "commit": _git(workspace, "rev-parse", "HEAD"),
        },
        "externalCapabilities": {
            "github": {"authorizedByWorkMode": True, "remoteWriteExecutedBy": "connector", "credentialsRecorded": False},
            "googleDrive": {"authorizedByWorkMode": True, "remoteWriteExecutedBy": "connector", "credentialsRecorded": False},
            "webAcquisition": {"availableToHost": True, "executedByPythonRunner": False},
        },
        "inputBoundary": {
            "harSha256": str(har_sha256),
            "files": [_file_descriptor(Path(path)) for path in input_paths],
            "rawArtifactsCommitted": False,
            "rawArtifactsUploaded": False,
        },
        "authority": {
            "statisticalFacts": "CFB_STATISTICAL_LEDGER",
            "platformSettlement": "PRIZEPICKS_PLATFORM_RULES",
            "predictiveClaim": "NONE",
            "learningRevision": "LR000000",
        },
        "gates": {
            "softwareClosed": False,
            "harAccountingAccepted": False,
            "operationalAcceptedWithCurrentHar": False,
            "predictiveCertified": False,
            "productionRootCertified": False,
        },
    }
    body["contentHash"] = content_hash({key: value for key, value in body.items() if key != "contentHash"})
    return body


def persist_capability_manifest(dest: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "capability_manifest.json").write_text(
        __import__("json").dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest


__all__ = ["build_capability_manifest", "persist_capability_manifest"]
