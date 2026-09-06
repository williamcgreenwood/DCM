"""Deterministic request-scope reconciliation across one or more HAR captures."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dcm.contracts.hashes import content_hash

SUCCESS_STATES = {"SUCCESS_NONEMPTY", "SUCCESS_EMPTY_VERIFIED"}
FAILURE_STATES = {
    "HTTP_FAILURE",
    "DECODE_FAILURE",
    "SCHEMA_FAILURE",
    "TRUNCATED_OR_PAGINATION_INCOMPLETE",
    "DENIED_SECURITY_SCOPE",
}


def _time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _attempt_key(attempt: dict[str, Any]) -> tuple:
    return (
        _time(attempt.get("startedDateTime")) or datetime.min.replace(tzinfo=timezone.utc),
        str(attempt.get("sourceHarSha256") or ""),
        int(attempt.get("entryOrdinal") or 0),
        str(attempt.get("responseHash") or ""),
        str(attempt.get("state") or ""),
    )


def _row_key(row: dict[str, Any]) -> tuple:
    return (
        _time(row.get("sourceUpdatedAt"))
        or _time(row.get("sourceSnapshotTime"))
        or datetime.min.replace(tzinfo=timezone.utc),
        _time(row.get("sourceSnapshotTime"))
        or datetime.min.replace(tzinfo=timezone.utc),
        str(row.get("sourceBodyHash") or ""),
        str(row.get("requestScope") or ""),
    )


def _changed_states(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    states: list[str] = []
    if old.get("line") != new.get("line"):
        states.append("LINE_CHANGED")
    if old.get("modifier") != new.get("modifier"):
        states.append("MODIFIER_CHANGED")
    if (old.get("offeredHigher"), old.get("offeredLower")) != (
        new.get("offeredHigher"),
        new.get("offeredLower"),
    ):
        states.append("SIDE_CHANGED")
    if old.get("status") != new.get("status"):
        states.append("STATUS_CHANGED")
    if old.get("eventStartTime") != new.get("eventStartTime"):
        states.append("START_TIME_CHANGED")
    return states or ["REFRESHED_UNCHANGED"]


def reconcile_scope_attempts(
    attempts: list[dict[str, Any]],
    *,
    cutoff: str | None = None,
) -> dict[str, Any]:
    """Select latest successful response independently for every canonical request scope."""
    cut = _time(cutoff) if cutoff else None
    scope_state: dict[str, dict[str, Any]] = {}
    failed_refreshes: list[dict[str, Any]] = []
    post_cutoff_attempts = 0
    for attempt in sorted((dict(a) for a in attempts), key=_attempt_key):
        started = _time(attempt.get("startedDateTime"))
        if cut is not None and started is not None and started > cut:
            post_cutoff_attempts += 1
            continue
        scope = str(attempt.get("requestScope") or "")
        state = str(attempt.get("state") or "")
        if not scope:
            continue
        if state in SUCCESS_STATES:
            scope_state[scope] = attempt
        elif state in FAILURE_STATES and scope in scope_state:
            failed_refreshes.append(
                {
                    "requestScope": scope,
                    "state": state,
                    "startedDateTime": attempt.get("startedDateTime"),
                    "sourceHarSha256": attempt.get("sourceHarSha256"),
                    "retainedResponseHash": scope_state[scope].get("responseHash"),
                }
            )

    rows_by_id: dict[str, dict[str, Any]] = {}
    post_cutoff_updates = 0
    for scope, attempt in scope_state.items():
        for row in attempt.get("rows") or []:
            rec = dict(row)
            rec["requestScope"] = scope
            updated = _time(rec.get("sourceUpdatedAt"))
            if cut is not None and updated is not None and updated > cut:
                post_cutoff_updates += 1
                continue
            pid = str(rec.get("projectionId") or "")
            if not pid:
                continue
            prior = rows_by_id.get(pid)
            if prior is None or _row_key(rec) > _row_key(prior):
                rows_by_id[pid] = rec

    scope_meta = {
        scope: {
            "state": attempt.get("state"),
            "responseHash": attempt.get("responseHash"),
            "startedDateTime": attempt.get("startedDateTime"),
            "sourceHarSha256": attempt.get("sourceHarSha256"),
            "rowCount": len(attempt.get("rows") or []),
        }
        for scope, attempt in sorted(scope_state.items())
    }
    rows = sorted(rows_by_id.values(), key=lambda r: str(r.get("projectionId")))
    return {
        "rows": rows,
        "scopeState": scope_meta,
        "failedRefreshes": failed_refreshes,
        "stats": {
            "post_cutoff_attempts_excluded": post_cutoff_attempts,
            "post_cutoff_updates_excluded": post_cutoff_updates,
            "selected_scope_count": len(scope_state),
            "failed_refreshes_retained": len(failed_refreshes),
        },
        "reconciliationHash": content_hash(
            {
                "scopeState": scope_meta,
                "rows": [
                    {
                        "projectionId": r.get("projectionId"),
                        "line": r.get("line"),
                        "modifier": r.get("modifier"),
                        "offeredHigher": r.get("offeredHigher"),
                        "offeredLower": r.get("offeredLower"),
                        "requestScope": r.get("requestScope"),
                        "sourceBodyHash": r.get("sourceBodyHash"),
                    }
                    for r in rows
                ],
            }
        ),
    }


def compose_ingests(ingests: list[dict[str, Any]]) -> dict[str, Any]:
    """Compose captures by latest successful response per canonical request scope.

    Input order is intentionally irrelevant. Capture chronology + source hash are
    the deterministic ordering keys.
    """
    if not ingests:
        raise ValueError("NO_HAR_CAPTURES")
    if len(ingests) == 1:
        return dict(ingests[0])

    captures = sorted(
        (dict(i) for i in ingests),
        key=lambda i: (
            _time(i.get("captureEnd")) or datetime.min.replace(tzinfo=timezone.utc),
            str(i.get("harSha256") or ""),
        ),
    )
    cumulative: list[dict[str, Any]] = []
    previous: dict[str, dict[str, Any]] = {}
    lifecycle: list[dict[str, Any]] = []
    merged_history: dict[str, list[dict[str, Any]]] = {}

    for sequence, capture in enumerate(captures, 1):
        capture_attempts = [dict(a) for a in (capture.get("scopeAttempts") or [])]
        cumulative.extend(capture_attempts)
        for pid, hist in (capture.get("rowHistory") or {}).items():
            merged_history.setdefault(str(pid), []).extend(dict(x) for x in hist if isinstance(x, dict))

        current_result = reconcile_scope_attempts(cumulative)
        current = {str(r["projectionId"]): r for r in current_result["rows"]}
        successful_scopes = {
            str(a.get("requestScope"))
            for a in capture_attempts
            if str(a.get("state")) in SUCCESS_STATES
        }
        failed_scopes = {
            str(a.get("requestScope"))
            for a in capture_attempts
            if str(a.get("state")) in FAILURE_STATES
        }

        for pid in sorted(set(previous) | set(current)):
            old, new = previous.get(pid), current.get(pid)
            if old is None and new is not None:
                states = ["ADDED"]
            elif old is not None and new is None:
                states = (
                    ["REMOVED_BY_IDENTICAL_SCOPE_REFRESH"]
                    if str(old.get("requestScope")) in successful_scopes
                    else ["AMBIGUOUS_SCOPE_GAP"]
                )
            elif old is not None and new is not None:
                scope = str(new.get("requestScope") or old.get("requestScope") or "")
                if _row_key(old) == _row_key(new):
                    if scope in failed_scopes and scope not in successful_scopes:
                        states = ["FAILED_REFRESH_PRIOR_RETAINED"]
                    elif scope not in successful_scopes:
                        states = ["SCOPE_NOT_RECAPTURED_RETAINED"]
                    else:
                        states = ["REFRESHED_UNCHANGED"]
                else:
                    states = _changed_states(old, new)
            else:
                continue
            lifecycle.append(
                {
                    "captureSequence": sequence,
                    "sourceHarSha256": capture.get("harSha256"),
                    "projectionId": pid,
                    "states": states,
                    "previousLine": old.get("line") if old else None,
                    "currentLine": new.get("line") if new else None,
                    "requestScope": (new or old).get("requestScope") if (new or old) else "",
                }
            )
        previous = current

    final = reconcile_scope_attempts(cumulative)
    source_hashes = sorted(str(i.get("harSha256") or "") for i in captures)
    warnings = sorted({str(w) for i in captures for w in (i.get("warnings") or [])})
    index_stats: dict[str, int] = {}
    for capture in captures:
        for key, value in (capture.get("indexStats") or {}).items():
            if isinstance(value, int):
                index_stats[key] = index_stats.get(key, 0) + value
    index_stats.update(
        {
            "capture_count": len(captures),
            "composite_scope_count": len(final["scopeState"]),
            "failed_refreshes_retained": len(final["failedRefreshes"]),
            "unique_projection_ids": len(final["rows"]),
        }
    )

    composite_id = content_hash(
        {
            "sourceHarSha256s": source_hashes,
            "reconciliationHash": final["reconciliationHash"],
        }
    )
    return {
        "adapter": "MULTI_HAR_COMPOSITE",
        "parserVersion": "HAR_COMPOSITE_V1_2026-08-29",
        "harSha256": composite_id,
        "compositeCaptureId": composite_id,
        "contributingHarSha256s": source_hashes,
        "rows": final["rows"],
        "rowHistory": merged_history,
        "scopeAttempts": sorted(cumulative, key=_attempt_key),
        "scopeState": final["scopeState"],
        "failedRefreshes": final["failedRefreshes"],
        "reconciliationHash": final["reconciliationHash"],
        "timeline": lifecycle,
        "redactedSecrets": sum(int(i.get("redactedSecrets") or 0) for i in captures),
        "warnings": warnings,
        "indexStats": index_stats,
        "captureStart": min((str(i.get("captureStart") or "") for i in captures if i.get("captureStart")), default=""),
        "captureEnd": max((str(i.get("captureEnd") or "") for i in captures if i.get("captureEnd")), default=""),
        "synthetic": any(bool(i.get("synthetic")) for i in captures),
        "v5Decoder": "NOT_MOUNTED",
    }
