"""Recover platform offer metadata from the authorized HAR board.

Offer metadata is a different data class from player/team research.  This
stage never searches the web and never infers an inverse side: it matches each
OFFER request to the as-of board row by projection identity and emits a
content-addressed EvidenceClaim only when the captured board contains an
offered side.  Missing sides remain unresolved and are reported explicitly.
"""
from __future__ import annotations

from typing import Any

from dcm.research.claims import claim_record


_PLATFORM_URL = "https://api.prizepicks.com"


def recover_offer_metadata(
    rows: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    *,
    cutoff: str,
) -> dict[str, Any]:
    """Return HAR-backed claims, counts, and exact unresolved reasons."""
    by_projection = {str(row.get("projectionId") or ""): row for row in rows}
    claims: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    recovered = 0
    for request in requests:
        if str(request.get("scope") or "") != "OFFER":
            continue
        projection_id = str(request.get("scope_id") or "")
        row = by_projection.get(projection_id)
        if row is None:
            unresolved.append({"requestId": request.get("request_id"), "reason": "OFFER_NOT_IN_ASOF_BOARD"})
            continue
        higher = bool(row.get("offeredHigher"))
        lower = bool(row.get("offeredLower"))
        if not higher and not lower:
            unresolved.append({
                "requestId": request.get("request_id"),
                "projectionId": projection_id,
                "reason": "UNRESOLVED_PLATFORM_METADATA:OFFERED_SIDE_MISSING",
            })
            continue
        observed = str(row.get("sourceSnapshotTime") or cutoff)
        # The source hash/body hash are HAR lineage, not host-supplied hashes.
        value = {
            "offer_recorded": True,
            "projection_id": projection_id,
            "event_id": str(row.get("eventId") or ""),
            "market": str(row.get("market") or ""),
            "market_definition": str(row.get("statTypeRaw") or row.get("market") or ""),
            "line": row.get("line"),
            "modifier": str(row.get("modifier") or ""),
            "period": row.get("boardId") or row.get("period") or "FULL_GAME",
            "offered_higher": higher,
            "offered_lower": lower,
            "source_body_hash": str(row.get("sourceBodyHash") or ""),
            "capture_time": observed,
        }
        claims.append(
            claim_record(
                source_id="HAR_PLATFORM_BOARD",
                url=_PLATFORM_URL,
                published_at=observed,
                observed_at=observed,
                forecast_cutoff=cutoff,
                semantic_scope="OFFER",
                scope_id=projection_id,
                claim_type="line_sides_modifier",
                claim_value=value,
                reliability=1.0,
                freshness=1.0,
            )
        )
        recovered += 1
    return {
        "claims": claims,
        "recovered": recovered,
        "unresolved": unresolved,
        "requested": sum(1 for request in requests if str(request.get("scope") or "") == "OFFER"),
        "recoveryComplete": not unresolved,
        "source": "AUTHORIZED_HAR_BOARD_ONLY",
    }
