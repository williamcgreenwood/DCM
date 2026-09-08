"""Machine-readable failure ledger for the resumable research worker.

Failures are data, not prose in a chat transcript.  The ledger is append-only,
content addressed, and deliberately contains only safe identifiers and
controlled reason codes.  A caller can therefore retry a batch without
reconstructing state from model output or exposing a captured request body.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash


FAILURE_SCHEMA = "pillars_dcm.research_failure.v1"
FAILURE_LEDGER_SCHEMA = "pillars_dcm.research_failure_ledger.v1"

# Closed vocabulary keeps runtime recovery automatable and prevents an LLM
# from smuggling arbitrary instructions into a control record.
FAILURE_CODES = frozenset(
    {
        "SOURCE_UNAVAILABLE",
        "SOURCE_RATE_LIMITED",
        "SOURCE_UNAUTHORIZED",
        "SOURCE_NOT_FOUND",
        "SOURCE_MALFORMED",
        "SOURCE_CONTRADICTORY",
        "CUTOFF_VIOLATION",
        "PERMISSION_BLOCKED",
        "SCHEMA_INVALID",
        "REQUIRED_FIELD_MISSING",
        "ENTITY_NOT_RESOLVED",
        "ACTION_TIMEOUT",
        "ACTION_CANCELLED",
        "BATCH_ENVELOPE_OVERWRITE_BLOCKED",
        "CHECKPOINT_CAS_MISMATCH",
        "RUN_BUSY",
        "INTERNAL_ERROR",
    }
)
EXCLUSION_SCOPES = frozenset(
    {"ATTEMPT_ONLY", "BATCH", "REQUEST", "SOURCE", "RUN", "GLOBAL_POLICY"}
)
RETRY_STATES = frozenset({"RETRYABLE", "PERMANENT", "BLOCKED", "RECORDED"})


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _without_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in value.items() if k not in {"contentHash", "failureId"}}


def _failure_identity(body: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runId": str(body.get("runId") or ""),
        "batchId": str(body.get("batchId") or ""),
        "actionId": str(body.get("actionId") or ""),
        "requestId": str(body.get("requestId") or ""),
        "attempt": int(body.get("attempt") or 0),
        "code": str(body.get("code") or ""),
        "exclusionScope": str(body.get("exclusionScope") or "ATTEMPT_ONLY"),
        "sourceId": str(body.get("sourceId") or ""),
    }


def failure_record(
    *,
    run_id: str,
    batch_id: str,
    action_id: str,
    request_id: str | None = None,
    source_id: str | None = None,
    code: str,
    exclusion_scope: str = "ATTEMPT_ONLY",
    attempt: int = 1,
    retryable: bool = False,
    retry_state: str | None = None,
    recorded_at: str | None = None,
    next_retry_at: str | None = None,
    missing_fields: list[str] | tuple[str, ...] = (),
    source_attempts: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] = (),
    cutoff_decision: str | None = None,
    safe_reason: str | None = None,
    recovery_command: str | None = None,
    failure_key: str | None = None,
) -> dict[str, Any]:
    """Build and validate one safe failure record.

    ``safe_reason`` is intentionally bounded to a short, redacted diagnostic;
    the full exception must stay in local CI diagnostics, never in the ledger.
    """
    code = str(code).upper()
    exclusion_scope = str(exclusion_scope).upper()
    if code not in FAILURE_CODES:
        raise ValueError(f"UNKNOWN_FAILURE_CODE:{code}")
    if exclusion_scope not in EXCLUSION_SCOPES:
        raise ValueError(f"UNKNOWN_EXCLUSION_SCOPE:{exclusion_scope}")
    if int(attempt) < 1:
        raise ValueError("FAILURE_ATTEMPT_MUST_BE_POSITIVE")
    state = str(retry_state or ("RETRYABLE" if retryable else "PERMANENT")).upper()
    if state not in RETRY_STATES:
        raise ValueError(f"UNKNOWN_RETRY_STATE:{state}")
    safe_sources = []
    for source in source_attempts:
        if not isinstance(source, Mapping):
            continue
        safe_sources.append(
            {
                "sourceId": str(source.get("sourceId") or source.get("source_id") or ""),
                "status": str(source.get("status") or "UNKNOWN").upper(),
                "code": str(source.get("code") or "")[:64],
            }
        )
    body: dict[str, Any] = {
        "schema": FAILURE_SCHEMA,
        "runId": str(run_id),
        "batchId": str(batch_id),
        "actionId": str(action_id),
        "requestId": str(request_id or "") or None,
        "sourceId": str(source_id or "") or None,
        "attempt": int(attempt),
        "code": code,
        "exclusionScope": exclusion_scope,
        "retryable": bool(retryable),
        "retryState": state,
        "recordedAt": str(recorded_at or utc_now()),
        "nextRetryAt": str(next_retry_at or "") or None,
        "missingFields": sorted({str(x) for x in missing_fields if str(x)}),
        "sourceAttempts": sorted(safe_sources, key=lambda x: (x["sourceId"], x["status"], x["code"])),
        "cutoffDecision": str(cutoff_decision or "") or None,
        "safeReason": str(safe_reason or "")[:240] or None,
        "recoveryCommand": str(recovery_command or "")[:240] or None,
    }
    if failure_key:
        body["failureKey"] = str(failure_key)
    identity = _failure_identity(body)
    body["idempotencyKey"] = content_hash(identity)
    body["failureId"] = content_hash({**identity, "idempotencyKey": body["idempotencyKey"]})
    body["contentHash"] = content_hash(_without_hash(body))
    return body


def _validate(row: Mapping[str, Any]) -> dict[str, Any]:
    if row.get("schema") != FAILURE_SCHEMA:
        raise RuntimeError("FAILURE_LEDGER_INVALID_SCHEMA")
    required = ("failureId", "idempotencyKey", "runId", "batchId", "actionId", "code")
    if any(not row.get(key) for key in required):
        raise RuntimeError("FAILURE_LEDGER_REQUIRED_FIELD")
    expected_id = content_hash({**_failure_identity(row), "idempotencyKey": str(row["idempotencyKey"])})
    if str(row.get("failureId")) != expected_id:
        raise RuntimeError("FAILURE_LEDGER_ID_MISMATCH")
    if str(row.get("contentHash")) != content_hash(_without_hash(row)):
        raise RuntimeError("FAILURE_LEDGER_HASH_MISMATCH")
    if str(row.get("code")) not in FAILURE_CODES:
        raise RuntimeError("FAILURE_LEDGER_UNKNOWN_CODE")
    if str(row.get("exclusionScope")) not in EXCLUSION_SCOPES:
        raise RuntimeError("FAILURE_LEDGER_UNKNOWN_SCOPE")
    return dict(row)


def load_failures(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"FAILURE_LEDGER_CORRUPT_LINE:{number}") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"FAILURE_LEDGER_INVALID_ROW:{number}")
        rows.append(_validate(parsed))
    return rows


def append_failure(path: Path, record: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """Append a failure exactly once; conflicting reuse fails closed."""
    path = Path(path)
    row = dict(record) if record is not None else failure_record(**kwargs)
    row = _validate(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = load_failures(path)
    for existing in prior:
        if existing.get("idempotencyKey") != row.get("idempotencyKey"):
            continue
        if existing != row:
            raise RuntimeError("FAILURE_IDEMPOTENCY_CONFLICT")
        return existing
    encoded = (json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        os.close(fd)
    return row


def failure_ledger(path: Path) -> dict[str, Any]:
    rows = load_failures(path)
    body: dict[str, Any] = {
        "schema": FAILURE_LEDGER_SCHEMA,
        "count": len(rows),
        "failureIds": [str(r["failureId"]) for r in rows],
        "retryableCount": sum(bool(r.get("retryable")) for r in rows),
        "permanentCount": sum(not bool(r.get("retryable")) for r in rows),
    }
    body["contentHash"] = content_hash(body)
    return body


__all__ = [
    "EXCLUSION_SCOPES",
    "FAILURE_CODES",
    "FAILURE_LEDGER_SCHEMA",
    "FAILURE_SCHEMA",
    "append_failure",
    "failure_ledger",
    "failure_record",
    "load_failures",
]
