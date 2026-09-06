"""Atomic checkpoint / resume. write temp → fsync → hash → rename."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash


def atomic_write(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    digest = content_hash(payload)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)
    # Persist the directory entry as well as the file contents so a power loss
    # cannot acknowledge a checkpoint whose rename was still only cached.
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        # Filesystems that do not permit directory fsync still retain the
        # validated checkpoint; the outbox records the remote-sync intent.
        pass
    return digest


def load_checkpoint(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    stored = data.get("checkpointHash")
    check = {k: v for k, v in data.items() if k != "checkpointHash"}
    got = content_hash(check)
    if stored and stored != got:
        raise RuntimeError(f"CHECKPOINT_HASH_MISMATCH: {stored} != {got}")
    return data


def write_checkpoint(dest: Path, payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body.pop("checkpointHash", None)
    digest = content_hash(body)
    body["checkpointHash"] = digest
    atomic_write(dest, body)
    # The checkpoint itself is durable before the sync intent is appended.
    # Remote publication is intentionally a separate, idempotent action.
    try:
        from dcm.runtime.checkpoint_outbox import enqueue_checkpoint_sync

        completed_stages = body.get("completedStages") or []
        checkpoint_id = str(
            body.get("checkpointId")
            or (completed_stages[-1] if isinstance(completed_stages, list) and completed_stages else "checkpoint")
        )
        enqueue_checkpoint_sync(
            dest.parent / "checkpoint_outbox.jsonl",
            run_id=str(body.get("runId") or ""),
            checkpoint_id=checkpoint_id,
            checkpoint_hash=digest,
            artifact_root=str(body.get("artifactRoot") or dest.parent),
        )
    except Exception as exc:  # noqa: BLE001 - preserve local checkpoint, expose status
        error = {
            "schema": "pillars_dcm.checkpoint_outbox_error.v1",
            "checkpointHash": digest,
            "error": type(exc).__name__,
        }
        atomic_write(dest.parent / "checkpoint_outbox_error.json", error)
    try:
        from dcm.runtime.checkpoint_reconciliation import reconcile_checkpoint_outbox

        reconciliation = reconcile_checkpoint_outbox(
            body, dest.parent / "checkpoint_outbox.jsonl",
        )
        atomic_write(dest.parent / "checkpoint_reconciliation.json", reconciliation)
    except Exception as exc:  # noqa: BLE001 - local checkpoint remains authoritative
        atomic_write(dest.parent / "checkpoint_reconciliation_error.json", {
            "schema": "pillars_dcm.checkpoint_reconciliation_error.v1",
            "checkpointHash": digest,
            "error": type(exc).__name__,
        })
    return body
