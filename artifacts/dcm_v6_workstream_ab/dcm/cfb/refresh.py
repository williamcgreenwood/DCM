"""Final refresh of Top25 / PLAYABLE frontier immediately before freeze.

Refreshes line, offered side, game status, player status, starter/depth,
major injuries, weather, role-changing news. No post-start evidence may
influence an event's pregame freeze.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.contracts.hashes import content_hash
from dcm.model.distributions import from_worlds
from dcm.model.grade import grade as grade_of
from dcm.model.line_surface import surface as line_surface


VOLATILE_FIELDS = (
    "line",
    "offeredHigher",
    "offeredLower",
    "status",
    "gameStatus",
    "starter",
    "injury",
    "weather",
    "role",
)


def apply_final_refresh(
    modeled: list[dict[str, Any]],
    *,
    claims: list[Mapping[str, Any]] | None = None,
    cutoff: str | None = None,
    started_events: set[str] | None = None,
) -> dict[str, Any]:
    started = started_events or set()
    claims = list(claims or [])
    refreshed = 0
    held = 0
    by_scope: dict[tuple[str, str], dict[str, Any]] = {}
    for claim in claims:
        observed = str(claim.get("observed_at") or "")
        if cutoff and observed and observed > str(cutoff):
            continue
        key = (str(claim.get("semantic_scope") or ""), str(claim.get("scope_id") or ""))
        prev = by_scope.get(key)
        if prev is None or str(claim.get("observed_at") or "") >= str(prev.get("observed_at") or ""):
            by_scope[key] = dict(claim)

    out: list[dict[str, Any]] = []
    for prop in modeled:
        rec = dict(prop)
        row = dict(rec.get("row") or rec)
        event_id = str(row.get("eventId") or "")
        if event_id in started:
            rec["finalRefresh"] = "STARTED_EVENT_NO_PREGAME_SELECTION"
            held += 1
            out.append(rec)
            continue
        player_id = str(row.get("playerId") or "")
        updates = []
        for scope, sid in (("SUBJECT", player_id), ("EVENT", event_id), ("ENVIRONMENT", f"env:{event_id}")):
            claim = by_scope.get((scope, sid))
            if not claim:
                continue
            value = claim.get("claim_value") if isinstance(claim.get("claim_value"), dict) else {}
            for field in VOLATILE_FIELDS:
                if field in value and value[field] is not None and row.get(field) != value[field]:
                    row[field] = value[field]
                    updates.append(field)
        if updates:
            rec["row"] = row
            rec["finalRefreshFields"] = updates
            refreshed += 1
            values = rec.get("_worldValues")
            if "line" in updates and isinstance(values, list) and values:
                try:
                    dist = from_worlds([float(v) for v in values], float(row.get("line") or 0.0))
                    rec["pHigher"] = dist["pHigher"]
                    rec["pLower"] = dist["pLower"]
                    rec["pPush"] = dist["pPush"]
                    rec["mean"] = dist["mean"]
                    side = str(rec.get("selectedSide") or "MORE")
                    rec["selectedP"] = dist["pHigher"] if side == "MORE" else dist["pLower"]
                    surf = line_surface([float(v) for v in values], float(row.get("line") or 0.0), side=side)
                    rec["lineSurface"] = surf
                    rec["trueLineTolerance"] = surf.get("true_unclamped_line_tolerance")
                    rec["grade"] = grade_of(
                        selected_p=float(rec.get("evidenceSafeP") or rec.get("selectedP") or 0.5),
                        lower_bound=float(rec.get("lowerBound") or 0.0),
                        demon=str(row.get("modifier") or "") == "DEMON",
                        fragility=float(rec.get("fragility") or 0.0),
                        robustness_area=float(surf.get("robustness_area") or 0.0),
                        elasticity=float(surf.get("edge_elasticity") or 0.0),
                        false_sign=float(rec.get("falseSignRisk") or 0.0),
                    )
                except (TypeError, ValueError, KeyError):
                    pass
        else:
            rec["finalRefreshFields"] = []
        rec["finalRefresh"] = "APPLIED"
        out.append(rec)

    body = {
        "schema": "pillars_dcm.cfb_final_refresh.v1",
        "refreshedCount": refreshed,
        "heldStartedCount": held,
        "volatileFields": list(VOLATILE_FIELDS),
        "cutoff": cutoff,
        "note": "No post-start evidence may influence an event's pregame freeze.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return {"modeled": out, "report": body}
