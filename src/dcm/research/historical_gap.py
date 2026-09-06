"""HistoricalGapResolver — DCM6-ROS-EG-001 event-sequence algorithm.

stored verified completed event IDs
versus
authoritative expected completed event IDs before cutoff.

REUSE existing verified events.
APPEND only missing event IDs.
AUDIT unexpected extra stored events.
Preserve revisions. Never silently delete.
"""
from __future__ import annotations

from typing import Any, Iterable

from dcm.research.research_store import extract_game_logs, game_identity


def _ids(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        ident = str(value or "").strip()
        if not ident or ident in seen:
            continue
        seen.add(ident)
        out.append(ident)
    return out


def stored_event_ids(logs: Iterable[dict[str, Any]] | None) -> list[str]:
    ids: list[str] = []
    for log in logs or []:
        if not isinstance(log, dict):
            continue
        ident = str(log.get("eventId") or log.get("event_id") or "")
        if not ident:
            ident = game_identity(log)
        ids.append(ident)
    return _ids(ids)


def resolve_history_gap(
    *,
    stored_event_ids: Iterable[str],
    expected_completed_event_ids: Iterable[str],
) -> dict[str, Any]:
    stored = _ids(stored_event_ids)
    expected = _ids(expected_completed_event_ids)
    stored_set = set(stored)
    expected_set = set(expected)
    reuse = [eid for eid in stored if eid in expected_set]
    append = [eid for eid in expected if eid not in stored_set]
    unexpected_extra = [eid for eid in stored if eid not in expected_set]
    return {
        "schema": "pillars_dcm.historical_gap.v1",
        "storedCount": len(stored),
        "expectedCount": len(expected),
        "reuseEventIds": reuse,
        "appendEventIds": append,
        "unexpectedExtraEventIds": unexpected_extra,
        "deletedEventIds": [],
        "silentlyDeleted": False,
        "reacquireStored": False,
        "acquire": bool(append),
        "deltaClass": "APPEND_MISSING_HISTORY" if append else "REUSE_VALID",
    }


def apply_history_gap(
    request: dict[str, Any],
    prior: dict[str, Any] | None,
    delta: dict[str, Any],
) -> dict[str, Any]:
    extra = request.get("context") if isinstance(request.get("context"), dict) else {}
    expected = extra.get("expectedCompletedEventIds") or request.get("expectedCompletedEventIds")
    if not expected:
        return delta
    logs = []
    if prior:
        logs = prior.get("gameLogs") or extract_game_logs(prior) or []
    resolved = resolve_history_gap(
        stored_event_ids=stored_event_ids(logs if isinstance(logs, list) else []),
        expected_completed_event_ids=list(expected),
    )
    out = dict(delta)
    out["historyGap"] = resolved
    if resolved["appendEventIds"]:
        out["deltaClass"] = "APPEND_MISSING_HISTORY"
        out["deltaReason"] = "HISTORY_GAP"
        out["acquire"] = True
        out["appendEventIds"] = resolved["appendEventIds"]
        out["reuseEventIds"] = resolved["reuseEventIds"]
        out["lastVerified"] = resolved["reuseEventIds"][-1] if resolved["reuseEventIds"] else None
    return out
