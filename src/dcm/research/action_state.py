"""Failure-aware, deterministic action state transitions."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash
from dcm.research.failures import EXCLUSION_SCOPES, failure_record, load_failures, append_failure


ACTION_STATE_SCHEMA = "pillars_dcm.action_state.v1"
ACTION_STATES = frozenset(
    {
        "PENDING",
        "SELECTED",
        "RESEARCH_PENDING",
        "IN_FLIGHT",
        "IMPORTING",
        "PARTIAL",
        "SUCCEEDED",
        "FAILED_RETRYABLE",
        "FAILED_PERMANENT",
        "DEFERRED",
        "BLOCKED_CUTOFF",
        "BLOCKED_PERMISSION",
        "BLOCKED_SCHEMA",
        "CANCELLED",
    }
)
TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED_PERMANENT", "BLOCKED_CUTOFF", "BLOCKED_PERMISSION", "BLOCKED_SCHEMA", "CANCELLED"})
RETRYABLE_STATES = frozenset({"FAILED_RETRYABLE", "DEFERRED", "PARTIAL"})
TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"SELECTED", "DEFERRED", "CANCELLED", "BLOCKED_CUTOFF", "BLOCKED_PERMISSION"}),
    "SELECTED": frozenset({"RESEARCH_PENDING", "IN_FLIGHT", "IMPORTING", "DEFERRED", "CANCELLED"}),
    "RESEARCH_PENDING": frozenset({"IN_FLIGHT", "DEFERRED", "CANCELLED"}),
    "IN_FLIGHT": frozenset({"IMPORTING", "PARTIAL", "SUCCEEDED", "FAILED_RETRYABLE", "FAILED_PERMANENT", "BLOCKED_CUTOFF", "BLOCKED_PERMISSION", "BLOCKED_SCHEMA"}),
    "IMPORTING": frozenset({"PARTIAL", "SUCCEEDED", "FAILED_RETRYABLE", "FAILED_PERMANENT", "BLOCKED_SCHEMA"}),
    "PARTIAL": frozenset({"SELECTED", "RESEARCH_PENDING", "IN_FLIGHT", "SUCCEEDED", "FAILED_RETRYABLE", "FAILED_PERMANENT"}),
    "FAILED_RETRYABLE": frozenset({"SELECTED", "RESEARCH_PENDING", "IN_FLIGHT", "FAILED_PERMANENT", "CANCELLED"}),
    # A later packet may contain useful evidence plus a non-retryable missing
    # field.  Evidence import can therefore reopen a terminal action as
    # PARTIAL without making the failure itself retryable.
    "FAILED_PERMANENT": frozenset({"PARTIAL"}),
    "BLOCKED_CUTOFF": frozenset({"PARTIAL"}),
    "DEFERRED": frozenset({"SELECTED", "RESEARCH_PENDING", "IN_FLIGHT", "CANCELLED"}),
}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        result = datetime.fromisoformat(text)
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def deterministic_backoff(attempt: int, *, base_seconds: int = 30, cap_seconds: int = 3600) -> int:
    attempt = max(1, int(attempt))
    return min(int(cap_seconds), int(base_seconds) * (2 ** (attempt - 1)))


def transition(current: str, target: str) -> None:
    current, target = str(current), str(target)
    if current not in ACTION_STATES or target not in ACTION_STATES:
        raise ValueError("ACTION_STATE_UNKNOWN")
    if current == target:
        return
    if target not in TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"ACTION_STATE_INVALID_TRANSITION:{current}->{target}")


def initial_action_state(action_id: str, *, now: str | None = None) -> dict[str, Any]:
    return {
        "actionId": str(action_id),
        "state": "PENDING",
        "attempt": 0,
        "lastFailureId": None,
        "nextRetryAt": None,
        "updatedAt": now,
    }


def load_action_state(path: Path) -> dict[str, dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return {}
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or parsed.get("schema") != ACTION_STATE_SCHEMA:
        raise RuntimeError("ACTION_STATE_INVALID_SCHEMA")
    rows = parsed.get("actions")
    if not isinstance(rows, list):
        raise RuntimeError("ACTION_STATE_ACTIONS_REQUIRED")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("actionId"):
            raise RuntimeError("ACTION_STATE_INVALID_ROW")
        state = str(row.get("state") or "")
        if state not in ACTION_STATES:
            raise RuntimeError("ACTION_STATE_UNKNOWN")
        out[str(row["actionId"])] = dict(row)
    stored = parsed.get("contentHash")
    body = {k: v for k, v in parsed.items() if k != "contentHash"}
    if stored and stored != content_hash(body):
        raise RuntimeError("ACTION_STATE_HASH_MISMATCH")
    return out


def save_action_state(path: Path, states: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for action_id, raw in sorted(states.items(), key=lambda item: str(item[0])):
        row = dict(raw)
        row["actionId"] = str(action_id)
        if str(row.get("state") or "") not in ACTION_STATES:
            raise ValueError("ACTION_STATE_UNKNOWN")
        rows.append(row)
    body: dict[str, Any] = {"schema": ACTION_STATE_SCHEMA, "actions": rows}
    body["contentHash"] = content_hash(body)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(body, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
        handle.flush()
        import os
        os.fsync(handle.fileno())
    import os
    os.replace(tmp, path)
    try:
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError:
        pass
    return body


def apply_transition(states: dict[str, dict[str, Any]], action_id: str, target: str, *, now: str | None = None, **updates: Any) -> dict[str, Any]:
    action_id = str(action_id)
    row = dict(states.get(action_id) or initial_action_state(action_id, now=now))
    transition(str(row.get("state") or "PENDING"), str(target))
    row.update(updates)
    row["actionId"] = action_id
    row["state"] = str(target)
    row["updatedAt"] = now
    states[action_id] = row
    return row


def apply_failure(
    states: dict[str, dict[str, Any]],
    *,
    run_id: str,
    batch_id: str,
    action_id: str,
    request_id: str | None,
    source_id: str | None = None,
    code: str,
    retryable: bool,
    exclusion_scope: str = "ATTEMPT_ONLY",
    now: str | None = None,
    max_attempts: int = 4,
    next_retry_at: str | None = None,
    failure_path: Path | None = None,
    missing_fields: Iterable[str] = (),
    source_attempts: Iterable[Mapping[str, Any]] = (),
    safe_reason: str | None = None,
    failure_key: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = dict(states.get(str(action_id)) or initial_action_state(str(action_id), now=now))
    if failure_path is not None and failure_key:
        for prior in load_failures(failure_path):
            if str(prior.get("failureKey") or "") == str(failure_key):
                prior_retryable = bool(prior.get("retryable"))
                row.update({
                    "state": "FAILED_RETRYABLE" if prior_retryable else "FAILED_PERMANENT",
                    "attempt": int(prior.get("attempt") or row.get("attempt") or 1),
                    "lastFailureId": prior.get("failureId"),
                    "nextRetryAt": prior.get("nextRetryAt"),
                    "updatedAt": now,
                })
                states[str(action_id)] = row
                return row, prior
    attempt = int(row.get("attempt") or 0) + 1
    effective_retryable = bool(retryable and attempt < int(max_attempts))
    state = "FAILED_RETRYABLE" if effective_retryable else "FAILED_PERMANENT"
    retry_at = next_retry_at
    if effective_retryable and not retry_at:
        base = _parse_time(now) or datetime.now(timezone.utc)
        retry_at = (base + timedelta(seconds=deterministic_backoff(attempt))).isoformat().replace("+00:00", "Z")
    failure = failure_record(
        run_id=run_id,
        batch_id=batch_id,
        action_id=action_id,
        request_id=request_id,
        source_id=source_id,
        code=code,
        exclusion_scope=exclusion_scope,
        attempt=attempt,
        retryable=effective_retryable,
        retry_state="RETRYABLE" if effective_retryable else "PERMANENT",
        recorded_at=now,
        next_retry_at=retry_at,
        missing_fields=list(missing_fields),
        source_attempts=list(source_attempts),
        safe_reason=safe_reason,
        failure_key=failure_key,
    )
    if failure_path is not None:
        append_failure(failure_path, failure)
    # A retryable failure can be selected only after its due time.  Permanent
    # and scoped failures remain excluded by eligible_action_ids.
    row.update({"state": state, "attempt": attempt, "lastFailureId": failure["failureId"], "nextRetryAt": retry_at, "updatedAt": now})
    states[str(action_id)] = row
    return row, failure


def _failure_applies(action: Mapping[str, Any], failure: Mapping[str, Any], *, run_id: str | None = None, batch_id: str | None = None, source_id: str | None = None) -> bool:
    scope = str(failure.get("exclusionScope") or "ATTEMPT_ONLY")
    aid = str(action.get("actionId") or "")
    if scope == "GLOBAL_POLICY":
        return True
    if scope == "RUN":
        return bool(run_id and str(failure.get("runId") or "") == str(run_id))
    if scope == "BATCH":
        return bool(batch_id and str(failure.get("batchId") or "") == str(batch_id))
    if scope == "REQUEST":
        request_id = str(failure.get("requestId") or "")
        return request_id in {str(x) for x in (action.get("requirementIds") or [])} or request_id == str(action.get("requestId") or "")
    if scope == "SOURCE":
        return bool(source_id and str(failure.get("sourceId") or "") == str(source_id))
    return str(failure.get("actionId") or "") == aid


def eligible_action_ids(
    actions: Iterable[Mapping[str, Any]],
    *,
    states: Mapping[str, Mapping[str, Any]] | None = None,
    failures: Iterable[Mapping[str, Any]] = (),
    now: str | None = None,
    run_id: str | None = None,
    batch_id: str | None = None,
) -> set[str]:
    """Return only actions safe to schedule at this instant."""
    states = states or {}
    current = _parse_time(now)
    failures_list = list(failures)
    eligible: set[str] = set()
    for action in actions:
        aid = str(action.get("actionId") or "")
        if not aid:
            continue
        row = states.get(aid) or {}
        state = str(row.get("state") or "PENDING")
        if state in TERMINAL_STATES:
            continue
        retry_at = _parse_time(str(row.get("nextRetryAt") or ""))
        if retry_at and current and retry_at > current:
            continue
        excluded = False
        for failure in failures_list:
            if not _failure_applies(action, failure, run_id=run_id, batch_id=batch_id, source_id=str(action.get("sourceId") or "")):
                continue
            if not bool(failure.get("retryable")) or state in TERMINAL_STATES:
                excluded = True
                break
            due = _parse_time(str(failure.get("nextRetryAt") or ""))
            if due and current and due > current:
                excluded = True
                break
        if not excluded:
            eligible.add(aid)
    return eligible


__all__ = [
    "ACTION_STATE_SCHEMA",
    "ACTION_STATES",
    "RETRYABLE_STATES",
    "TERMINAL_STATES",
    "apply_failure",
    "apply_transition",
    "deterministic_backoff",
    "eligible_action_ids",
    "initial_action_state",
    "load_action_state",
    "save_action_state",
    "transition",
]
