"""Pure reconciliation of local checkpoint intent and remote acknowledgements."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash
from dcm.runtime.checkpoint_outbox import load_outbox


RECONCILIATION_SCHEMA = "pillars_dcm.checkpoint_reconciliation.v1"


def _remote_state(remote: Mapping[str, Any] | None, expected: str) -> dict[str, Any]:
    if remote is None:
        return {"state": "NOT_CHECKED", "verified": False}
    observed = str(remote.get("checkpointHash") or remote.get("contentHash") or "")
    if not observed:
        return {"state": "ACK_UNVERIFIED", "verified": False}
    if observed != expected:
        return {"state": "DIVERGED_FAIL_CLOSED", "verified": False, "observedHash": observed}
    return {"state": "VERIFIED", "verified": True, "observedHash": observed}


def reconcile_checkpoint_outbox(
    checkpoint: Mapping[str, Any],
    outbox_path: Path,
    *,
    github: Mapping[str, Any] | None = None,
    drive: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    checkpoint_hash = str(checkpoint.get("checkpointHash") or "")
    entries: list[dict[str, Any]] = []
    outbox_state = "VALIDATED"
    try:
        entries = load_outbox(Path(outbox_path))
    except (OSError, RuntimeError) as exc:
        outbox_state = f"INVALID_FAIL_CLOSED:{type(exc).__name__}"
    matching = [entry for entry in entries if str(entry.get("checkpointHash") or "") == checkpoint_hash]
    github_state = _remote_state(github, checkpoint_hash)
    drive_state = _remote_state(drive, checkpoint_hash)
    divergence = github_state["state"].startswith("DIVERGED") or drive_state["state"].startswith("DIVERGED")
    verified = bool(matching) and github_state["verified"] and drive_state["verified"] and not divergence
    body: dict[str, Any] = {
        "schema": RECONCILIATION_SCHEMA,
        "checkpointId": str(checkpoint.get("runId") or "") + "|" + checkpoint_hash,
        "checkpointHash": checkpoint_hash,
        "localState": "DURABLE_VALIDATED",
        "outboxState": outbox_state,
        "outboxMatchCount": len(matching),
        "github": github_state,
        "drive": drive_state,
        "resumePointer": "REMOTE_VERIFIED" if verified else "LOCAL_ONLY_EXTERNAL_UNVERIFIED",
        "failClosed": not verified or divergence or outbox_state != "VALIDATED",
        "nextAction": "none" if verified else "reconcile_remote_checkpoint_and_read_back",
    }
    body["contentHash"] = content_hash(body)
    return body


__all__ = ["RECONCILIATION_SCHEMA", "reconcile_checkpoint_outbox"]
