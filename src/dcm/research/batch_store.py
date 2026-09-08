"""Content-addressed batch envelopes and compare-and-swap checkpoints."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash


BATCH_SCHEMA = "pillars_dcm.research_batch_envelope.v1"
CHECKPOINT_SCHEMA = "pillars_dcm.research_checkpoint.v2"


class BatchEnvelopeError(RuntimeError):
    pass


class BatchEnvelopeOverwriteBlocked(BatchEnvelopeError):
    code = "BATCH_ENVELOPE_OVERWRITE_BLOCKED"


class CheckpointCasMismatch(BatchEnvelopeError):
    code = "CHECKPOINT_CAS_MISMATCH"


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def _atomic_create(path: Path, payload: Mapping[str, Any]) -> None:
    """Create a file without replacing an existing path, even on a race."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = _canonical_bytes(payload)
    with tmp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(tmp, path)
    except FileExistsError:
        raise
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
    _fsync_dir(path.parent)


def _atomic_replace(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("wb") as handle:
        handle.write(_canonical_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _identity(envelope: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {"batchId", "batchContentSha", "ownerToken", "sealedAt", "contentHash"}
    actions = []
    for action in envelope.get("actions") or []:
        if isinstance(action, Mapping):
            actions.append(dict(action))
    body = {str(k): v for k, v in envelope.items() if str(k) not in ignored and str(k) != "actions"}
    body["actions"] = sorted(actions, key=lambda row: (str(row.get("actionId") or ""), str(row.get("requestId") or "")))
    return body


def make_batch_envelope(
    *,
    run_id: str,
    actions: list[Mapping[str, Any]],
    manifest_sha: str,
    har_sha256: str,
    forecast_cutoff: str,
    code_sha: str,
    parent_checkpoint_sha: str | None = None,
    generation: int = 0,
    budgets: Mapping[str, Any] | None = None,
    owner_token: str | None = None,
    sealed_at: str | None = None,
    source_policy_hash: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": BATCH_SCHEMA,
        "schemaVersion": 1,
        "runId": str(run_id),
        "manifestSha": str(manifest_sha),
        "harSha256": str(har_sha256),
        "forecastCutoff": str(forecast_cutoff),
        "codeSha": str(code_sha),
        "parentCheckpointSha": str(parent_checkpoint_sha or "") or None,
        "generation": int(generation),
        "budgets": dict(budgets or {}),
        "sourcePolicyHash": str(source_policy_hash or "") or None,
        "actions": [dict(action) for action in actions if isinstance(action, Mapping)],
    }
    body["actions"] = sorted(body["actions"], key=lambda row: (str(row.get("actionId") or ""), str(row.get("requestId") or "")))
    identity_hash = content_hash(_identity(body))
    body["batchId"] = f"BATCH_{identity_hash[:24]}"
    body["ownerToken"] = str(owner_token or "") or None
    body["sealedAt"] = str(sealed_at or "") or None
    body["batchContentSha"] = content_hash({k: v for k, v in body.items() if k != "batchContentSha"})
    return body


def _validate_envelope(raw: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(raw)
    if body.get("schema") != BATCH_SCHEMA:
        raise BatchEnvelopeError("BATCH_ENVELOPE_INVALID_SCHEMA")
    for key in ("runId", "batchId", "manifestSha", "harSha256", "forecastCutoff", "codeSha", "batchContentSha"):
        if not body.get(key):
            raise BatchEnvelopeError(f"BATCH_ENVELOPE_MISSING:{key}")
    expected_id = f"BATCH_{content_hash(_identity(body))[:24]}"
    if str(body.get("batchId")) != expected_id:
        raise BatchEnvelopeError("BATCH_ENVELOPE_ID_MISMATCH")
    expected_content = content_hash({k: v for k, v in body.items() if k != "batchContentSha"})
    if str(body.get("batchContentSha")) != expected_content:
        raise BatchEnvelopeError("BATCH_ENVELOPE_HASH_MISMATCH")
    if not isinstance(body.get("actions"), list):
        raise BatchEnvelopeError("BATCH_ENVELOPE_ACTIONS_REQUIRED")
    return body


def load_batch(path: Path) -> dict[str, Any]:
    return _validate_envelope(json.loads(Path(path).read_text(encoding="utf-8")))


def seal_batch(path: Path, envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Seal once.  A repeat with the same identity returns the original bytes."""
    path = Path(path)
    candidate = _validate_envelope(make_batch_envelope(**_envelope_args(envelope)) if envelope.get("schema") != BATCH_SCHEMA else envelope)
    if path.is_file():
        existing = load_batch(path)
        if content_hash(_identity(existing)) != content_hash(_identity(candidate)):
            raise BatchEnvelopeOverwriteBlocked(BatchEnvelopeOverwriteBlocked.code)
        # Do not rewrite dynamic fields.  Returning the stored object preserves
        # byte identity for retries after a Work/Codex interruption.
        return existing
    try:
        _atomic_create(path, candidate)
    except FileExistsError:
        existing = load_batch(path)
        if content_hash(_identity(existing)) != content_hash(_identity(candidate)):
            raise BatchEnvelopeOverwriteBlocked(BatchEnvelopeOverwriteBlocked.code)
        return existing
    return candidate


def _envelope_args(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": envelope.get("runId"),
        "actions": list(envelope.get("actions") or []),
        "manifest_sha": envelope.get("manifestSha"),
        "har_sha256": envelope.get("harSha256"),
        "forecast_cutoff": envelope.get("forecastCutoff"),
        "code_sha": envelope.get("codeSha"),
        "parent_checkpoint_sha": envelope.get("parentCheckpointSha"),
        "generation": envelope.get("generation") or 0,
        "budgets": envelope.get("budgets") or {},
        "owner_token": envelope.get("ownerToken"),
        "sealed_at": envelope.get("sealedAt"),
        "source_policy_hash": envelope.get("sourcePolicyHash"),
    }


def _checkpoint_hash(raw: Mapping[str, Any]) -> str:
    return content_hash({k: v for k, v in raw.items() if k != "checkpointHash"})


def write_checkpoint_cas(
    path: Path,
    *,
    expected_parent_sha: str | None,
    run_id: str,
    generation: int,
    active_batch_id: str | None,
    artifacts: Mapping[str, str],
    completed_action_ids: list[str] | tuple[str, ...] = (),
    pending_action_ids: list[str] | tuple[str, ...] = (),
    failed_action_ids: list[str] | tuple[str, ...] = (),
    coverage_sha: str | None = None,
    fence: int | None = None,
) -> dict[str, Any]:
    path = Path(path)
    current: dict[str, Any] | None = None
    if path.is_file():
        current = json.loads(path.read_text(encoding="utf-8"))
        actual = str(current.get("checkpointHash") or _checkpoint_hash(current))
    else:
        actual = None
    if actual != (str(expected_parent_sha) if expected_parent_sha else None):
        raise CheckpointCasMismatch(f"{CheckpointCasMismatch.code}:{actual}!={expected_parent_sha}")
    body: dict[str, Any] = {
        "schema": CHECKPOINT_SCHEMA,
        "runId": str(run_id),
        "generation": int(generation),
        "parentCheckpointSha": actual,
        "activeBatchId": str(active_batch_id or "") or None,
        "artifacts": {str(k): str(v) for k, v in sorted(artifacts.items(), key=lambda item: str(item[0]))},
        "completedActionIds": sorted({str(x) for x in completed_action_ids}),
        "pendingActionIds": sorted({str(x) for x in pending_action_ids}),
        "failedActionIds": sorted({str(x) for x in failed_action_ids}),
        "coverageSha": str(coverage_sha or "") or None,
        "fence": int(fence) if fence is not None else None,
    }
    body["checkpointHash"] = _checkpoint_hash(body)
    _atomic_replace(path, body)
    return body


def verify_checkpoint(path: Path) -> dict[str, Any]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    stored = str(body.get("checkpointHash") or "")
    if not stored or stored != _checkpoint_hash(body):
        raise BatchEnvelopeError("CHECKPOINT_HASH_MISMATCH")
    return {"valid": True, "checkpointHash": stored, "runId": body.get("runId"), "generation": body.get("generation")}


__all__ = [
    "BATCH_SCHEMA",
    "CHECKPOINT_SCHEMA",
    "BatchEnvelopeError",
    "BatchEnvelopeOverwriteBlocked",
    "CheckpointCasMismatch",
    "load_batch",
    "make_batch_envelope",
    "seal_batch",
    "verify_checkpoint",
    "write_checkpoint_cas",
]
