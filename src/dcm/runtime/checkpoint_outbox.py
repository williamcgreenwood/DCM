"""Crash-safe, idempotent checkpoint sync intents.

The outbox is deliberately local and append-only.  A later GitHub/Drive
worker may publish the referenced safe checkpoint artifacts, but a network
failure can never make a local checkpoint appear remotely complete.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash


OUTBOX_SCHEMA = "pillars_dcm.checkpoint_sync_outbox.v1"


def _without_hash(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "contentHash"}


def _validated_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"CHECKPOINT_OUTBOX_CORRUPT_LINE:{number}") from exc
        if not isinstance(row, dict) or row.get("schema") != OUTBOX_SCHEMA:
            raise RuntimeError(f"CHECKPOINT_OUTBOX_INVALID_SCHEMA:{number}")
        stored = str(row.get("contentHash") or "")
        if not stored or stored != content_hash(_without_hash(row)):
            raise RuntimeError(f"CHECKPOINT_OUTBOX_HASH_MISMATCH:{number}")
        if not row.get("idempotencyKey") or not row.get("checkpointHash"):
            raise RuntimeError(f"CHECKPOINT_OUTBOX_REQUIRED_FIELDS:{number}")
        entries.append(row)
    return entries


def load_outbox(path: Path) -> list[dict[str, Any]]:
    """Read and validate every outbox record; partial/corrupt logs fail closed."""
    return _validated_entries(Path(path))


def enqueue_checkpoint_sync(
    path: Path,
    *,
    run_id: str,
    checkpoint_id: str,
    checkpoint_hash: str,
    artifact_root: str,
    actions: tuple[str, ...] = ("github_commit", "drive_upload"),
) -> dict[str, Any]:
    """Append one checkpoint intent, or return the identical existing intent."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _validated_entries(path)
    idempotency = f"{run_id}|{checkpoint_id}|{checkpoint_hash}"
    body: dict[str, Any] = {
        "schema": OUTBOX_SCHEMA,
        "runId": str(run_id),
        "checkpointId": str(checkpoint_id),
        "checkpointHash": str(checkpoint_hash),
        "artifactRoot": Path(str(artifact_root)).name,
        "actions": list(actions),
        "status": "PENDING",
        "idempotencyKey": idempotency,
    }
    body["contentHash"] = content_hash(body)
    for prior in entries:
        if str(prior.get("idempotencyKey")) != idempotency:
            continue
        if prior != body:
            raise RuntimeError("CHECKPOINT_OUTBOX_IDEMPOTENCY_CONFLICT")
        return prior
    line = json.dumps(body, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        data = line.encode("utf-8")
        offset = 0
        while offset < len(data):
            offset += os.write(fd, data[offset:])
        os.fsync(fd)
    finally:
        os.close(fd)
    return body


__all__ = ["OUTBOX_SCHEMA", "enqueue_checkpoint_sync", "load_outbox"]
