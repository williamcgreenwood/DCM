"""Validate current-market observations for Insights-backed candidates.

Insights line/side claims are an authorized platform capture for research.  A
production selection still needs a separately observed current offer.  This
module is the narrow, source-aware boundary for that observation; it never
turns an Insights claim into a board offer by inference and never asks for a
second HAR.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from dcm.chat.state import read_json, write_json
from dcm.contracts.hashes import content_hash
from dcm.research.provider import _validate_source_url


REVALIDATION_SCHEMA = "pillars_dcm.offer_revalidation.v1"
UNAVAILABLE = "OFFER_REVALIDATION_UNAVAILABLE"


class OfferRevalidationError(ValueError):
    """A current-offer observation is not safe to consume."""


def _text(value: Any, limit: int = 512) -> str:
    return str(value or "").strip()[:limit]


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or abs(number) == float("inf"):
        return None
    return number


def _time(value: Any) -> datetime | None:
    text = _text(value, 64)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _key(row: Mapping[str, Any]) -> tuple[str, str, str, str, float | None, str]:
    nested_event = row.get("event") if isinstance(row.get("event"), Mapping) else {}
    return (
        _text(row.get("eventId") or nested_event.get("eventId") or nested_event.get("id"), 160),
        _text(row.get("subjectId") or row.get("playerId") or row.get("teamId"), 160),
        _text(row.get("proposition") or row.get("market") or row.get("marketType"), 128).upper(),
        _text(row.get("periodLabel") or row.get("period"), 64).upper(),
        _number(row.get("line")),
        _text(row.get("direction") or row.get("side"), 32).upper(),
    )


def _snapshot_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, float | None, str]:
    return _key(row)


def _known_by_id(snapshots: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in snapshots:
        if not isinstance(row, Mapping):
            continue
        for key in ("claimId", "projectionId", "insightId"):
            value = _text(row.get(key), 256)
            if value:
                out[value] = dict(row)
    return out


def validate_offer_revalidation(
    row: Mapping[str, Any],
    *,
    snapshots: Mapping[str, Mapping[str, Any]],
    cutoff: str | None,
) -> dict[str, Any]:
    """Return one canonical current-offer snapshot or raise a typed error."""
    raw = dict(row)
    claim_id = _text(raw.get("claimId") or raw.get("projectionId") or raw.get("insightId"), 256)
    if not claim_id:
        raise OfferRevalidationError("OFFER_REVALIDATION_CLAIM_ID_REQUIRED")
    captured = snapshots.get(claim_id)
    if not captured:
        raise OfferRevalidationError("OFFER_REVALIDATION_CLAIM_NOT_IN_CAPTURE")

    line = _number(raw.get("line"))
    direction = _text(raw.get("direction") or raw.get("side"), 32).upper()
    if line is None:
        raise OfferRevalidationError("OFFER_REVALIDATION_LINE_REQUIRED")
    if direction not in {"HIGHER", "LOWER"}:
        raise OfferRevalidationError("OFFER_REVALIDATION_SIDE_REQUIRED")
    captured_line = _number(captured.get("line"))
    captured_direction = _text(captured.get("direction") or captured.get("side"), 32).upper()
    if captured_line is None or abs(captured_line - line) > 1e-12:
        raise OfferRevalidationError("OFFER_REVALIDATION_LINE_MISMATCH")
    if captured_direction != direction:
        raise OfferRevalidationError("OFFER_REVALIDATION_SIDE_MISMATCH")

    identity = _key({**dict(captured), "line": line, "direction": direction})
    supplied_identity = _key({**raw, "line": line, "direction": direction})
    if identity != supplied_identity:
        raise OfferRevalidationError("OFFER_REVALIDATION_IDENTITY_MISMATCH")

    source_url = _text(raw.get("sourceUrl") or raw.get("url"), 2048)
    source_id = _text(raw.get("sourceId") or raw.get("source_id"), 256)
    source_hash = _text(raw.get("sourceHash") or raw.get("sourceBodyHash"), 256)
    retrieved_at = _text(raw.get("retrievedAt") or raw.get("observedAt") or raw.get("observed_at"), 64)
    authority = _text(raw.get("authority"), 256)
    if not source_id or not source_url or not source_hash or not retrieved_at or not authority:
        raise OfferRevalidationError("OFFER_REVALIDATION_PROVENANCE_REQUIRED")
    _validate_source_url(source_url)
    if _time(retrieved_at) is None:
        raise OfferRevalidationError("OFFER_REVALIDATION_RETRIEVED_AT_INVALID")

    event_status = _text(raw.get("eventStatus") or raw.get("status"), 64).upper().replace(" ", "_")
    if event_status in {"FINAL", "FINALIZED", "CLOSED", "SETTLED", "LIVE", "IN_PROGRESS", "SUSPENDED"}:
        raise OfferRevalidationError("OFFER_REVALIDATION_EVENT_NOT_FUTURE")
    captured_status = _text(captured.get("status"), 64).lower() or "pre_game"
    if captured_status in {"final", "closed", "settled", "live", "in_progress", "suspended"}:
        raise OfferRevalidationError("OFFER_REVALIDATION_CAPTURE_EVENT_NOT_FUTURE")

    current = raw.get("current")
    if current is False or raw.get("marketActive") is False or raw.get("isActive") is False:
        raise OfferRevalidationError("OFFER_REVALIDATION_OFFER_INACTIVE")

    normalized = {
        "schema": REVALIDATION_SCHEMA,
        "state": "VALID",
        "claimId": claim_id,
        "projectionId": _text(raw.get("projectionId") or captured.get("projectionId") or claim_id, 256),
        "insightId": _text(captured.get("insightId") or raw.get("insightId"), 256) or None,
        "eventId": identity[0],
        "subjectId": identity[1],
        "proposition": identity[2],
        "periodLabel": identity[3],
        "line": line,
        "direction": direction,
        "side": direction,
        "modifier": _text(raw.get("modifier") or captured.get("modifier") or "STANDARD", 64).upper(),
        "offerTimestamp": _text(raw.get("offerTimestamp") or raw.get("observedAt") or retrieved_at, 64),
        "retrievedAt": retrieved_at,
        "sourceId": source_id,
        "sourceUrl": source_url,
        "sourceHash": source_hash,
        "authority": authority,
        "eventStatus": event_status or "PRE_GAME",
        "scheduledTime": _text(
            raw.get("scheduledTime")
            or raw.get("eventStartTime")
            or (captured.get("scheduledTime") if isinstance(captured, Mapping) else None)
            or (captured.get("eventStartTime") if isinstance(captured, Mapping) else None),
            64,
        ) or None,
        "marketDefinitionId": _text(raw.get("marketDefinitionId"), 256) or None,
        "settlementRuleHash": _text(raw.get("settlementRuleHash"), 256) or None,
        "sourceHarSha256": _text(captured.get("sourceHarSha256"), 128) or None,
        "offerBacking": "CURRENT_OFFER_REVALIDATED",
        "researchOnly": False,
        "productionSelectionPermitted": False,
    }
    normalized["offerHash"] = content_hash({key: value for key, value in normalized.items() if key != "offerHash"})
    return normalized


def import_offer_revalidations(
    dest: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    snapshots: Iterable[Mapping[str, Any]],
    cutoff: str | None,
) -> dict[str, Any]:
    """Validate and persist current offers without overwriting prior versions."""
    dest = Path(dest)
    known = _known_by_id(snapshots)
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            rejected.append({"index": index, "code": "OFFER_REVALIDATION_ROW_INVALID"})
            continue
        try:
            valid.append(validate_offer_revalidation(row, snapshots=known, cutoff=cutoff))
        except (OfferRevalidationError, ValueError, TypeError) as exc:
            rejected.append({"index": index, "code": str(exc)[:160]})

    path = dest / "offer_revalidation.jsonl"
    existing: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                previous = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(previous, dict):
                existing.append(previous)
    existing_hashes = {str(row.get("offerHash") or "") for row in existing}
    appended = 0
    if valid:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for row in valid:
                if str(row.get("offerHash")) in existing_hashes:
                    continue
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
                existing.append(row)
                existing_hashes.add(str(row.get("offerHash")))
                appended += 1

    latest: dict[str, dict[str, Any]] = {}
    for row in existing:
        key = str(row.get("claimId") or row.get("projectionId") or "")
        if not key:
            continue
        prior = latest.get(key)
        if prior is None or str(row.get("retrievedAt") or "") >= str(prior.get("retrievedAt") or ""):
            latest[key] = row
    blockers = Counter(str(row.get("code") or "OFFER_REVALIDATION_INVALID") for row in rejected)
    if not latest:
        blockers[UNAVAILABLE] += 1
    payload = {
        "schema": REVALIDATION_SCHEMA,
        "status": "AVAILABLE" if latest else "UNAVAILABLE",
        "blocker": None if latest else UNAVAILABLE,
        "validCount": len(valid),
        "rejectedCount": len(rejected),
        "appendedCount": appended,
        "snapshotCount": len(latest),
        "snapshots": sorted(latest.values(), key=lambda row: str(row.get("claimId") or "")),
        "rejected": rejected,
        "blockers": dict(sorted(blockers.items())),
        "appendOnly": True,
        "boardHarRequired": False,
        "productionSelectionPermitted": False,
    }
    payload["contentHash"] = content_hash(payload)
    write_json(dest / "current_offer_snapshots.json", payload)
    return payload


def load_current_offers(dest: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(Path(dest) / "current_offer_snapshots.json") or {}
    rows = payload.get("snapshots") if isinstance(payload, Mapping) else []
    return {
        str(row.get("claimId") or row.get("projectionId")): dict(row)
        for row in rows or []
        if isinstance(row, Mapping) and str(row.get("claimId") or row.get("projectionId") or "")
    }


__all__ = [
    "REVALIDATION_SCHEMA",
    "UNAVAILABLE",
    "OfferRevalidationError",
    "import_offer_revalidations",
    "load_current_offers",
    "validate_offer_revalidation",
]
