"""Forecast cutoff policy. Never default to a hardcoded calendar date."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class CutoffRequired(ValueError):
    """--cutoff omitted and --cutoff-from-capture was not set (or capture times absent)."""


CUTOFF_FROM_CAPTURE_POLICY = "CAPTURE_MAX_STARTED_DATETIME"
HARDCODED_STALE_CUTOFF = "2026-08-28T00:00:00Z"

POLICY_DOC = """
Cutoff policy
=============

The runner never silently defaults to a hardcoded calendar date
(historically 2026-08-28T00:00:00Z). An operator must choose one of:

1. --cutoff <RFC3339>
   Explicit evidence/production firewall. Used as-is.

2. --cutoff-from-capture
   Derive the cutoff from the capture itself:
     max(HAR log.entries[].startedDateTime, row.sourceSnapshotTime, row.board_time)
   which is ingest.captureEnd when the HAR has startedDateTime values.
   Policy id: CAPTURE_MAX_STARTED_DATETIME.

If both are supplied, the explicit --cutoff wins and the derived value is
recorded only as capture metadata. Resume always uses the frozen checkpoint
cutoff; a later CLI default cannot change forecast semantics.

Accounting may still use asof_policy=account_capture so a HAR taken after the
evidence cutoff is fully counted. Evidence claims remain firewalled at cutoff.
""".strip()


def _parse(value: Any) -> datetime | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _fmt(dt: datetime) -> str:
    """Format an RFC3339 timestamp without discarding capture precision.

    ``--cutoff-from-capture`` is a self-contained temporal boundary.  Rounding
    a capture end down to whole seconds can make the final records from that
    very capture appear post-cutoff, so retain a fractional component whenever
    the source supplied one.  Explicit operator cutoffs remain untouched.
    """
    utc = dt.astimezone(timezone.utc)
    base = utc.strftime("%Y-%m-%dT%H:%M:%S")
    if not utc.microsecond:
        return base + "Z"
    return f"{base}.{utc.microsecond:06d}".rstrip("0") + "Z"


def derive_cutoff_from_capture(ingest: dict[str, Any]) -> str:
    """Return the latest capture timestamp under CAPTURE_MAX_STARTED_DATETIME."""
    candidates: list[str] = []
    for key in ("captureEnd", "captureStart"):
        value = ingest.get(key)
        if value:
            candidates.append(str(value))
    for row in ingest.get("rows") or []:
        if not isinstance(row, dict):
            continue
        for key in ("sourceSnapshotTime", "board_time", "boardTime", "sourceUpdatedAt"):
            value = row.get(key)
            if value:
                candidates.append(str(value))
    parsed = [(_parse(c), c) for c in candidates]
    dated = [(dt, raw) for dt, raw in parsed if dt is not None]
    if not dated:
        raise CutoffRequired(
            "FORECAST_CUTOFF_REQUIRED: --cutoff-from-capture set but capture timestamps are absent. "
            "Pass an explicit --cutoff."
        )
    dated.sort(key=lambda item: item[0])
    return _fmt(dated[-1][0])


def resolve_forecast_cutoff(
    *,
    explicit: str | None,
    from_capture: bool,
    ingest: dict[str, Any] | None,
    resume_cutoff: str | None = None,
) -> dict[str, Any]:
    if resume_cutoff:
        return {
            "cutoff": resume_cutoff,
            "source": "RESUME_CHECKPOINT",
            "policy": None,
            "derived": None,
        }
    explicit_s = str(explicit or "").strip() or None
    derived = None
    if from_capture:
        if ingest is None:
            raise CutoffRequired("FORECAST_CUTOFF_REQUIRED: --cutoff-from-capture needs a HAR ingest")
        derived = derive_cutoff_from_capture(ingest)
    if explicit_s:
        return {
            "cutoff": explicit_s,
            "source": "EXPLICIT_FLAG",
            "policy": CUTOFF_FROM_CAPTURE_POLICY if from_capture else "EXPLICIT",
            "derived": derived,
        }
    if derived:
        return {
            "cutoff": derived,
            "source": "CAPTURE",
            "policy": CUTOFF_FROM_CAPTURE_POLICY,
            "derived": derived,
        }
    raise CutoffRequired(
        "FORECAST_CUTOFF_REQUIRED: pass --cutoff <RFC3339> or --cutoff-from-capture. "
        "There is no hardcoded default cutoff."
    )
