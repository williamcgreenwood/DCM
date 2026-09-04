"""Final refresh of Top25 / PLAYABLE frontier immediately before freeze.

Line-only refresh re-evaluates the existing EventWorld distribution at the
new line. Material state change rebuilds ParameterSnapshots/EventWorlds.
No post-start evidence may influence an event's pregame freeze.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from dcm.contracts.hashes import content_hash
from dcm.model.distributions import from_worlds
from dcm.model.grade import grade as default_grade
from dcm.model.line_surface import surface as line_surface
from dcm.research.material_facts import is_after_cutoff


LINE_FIELDS = (
    "line",
    "offeredHigher",
    "offeredLower",
)
MATERIAL_FIELDS = (
    "status",
    "gameStatus",
    "starter",
    "injury",
    "weather",
    "role",
    "depth",
    "qb_id",
    "venue",
    "opponent",
)
VOLATILE_FIELDS = LINE_FIELDS + MATERIAL_FIELDS

RebuildFn = Callable[[dict[str, Any]], list[float] | None]


def _regrade(rec: dict[str, Any], row: Mapping[str, Any], values: list[float], *, grade_fn: Callable[..., str] | None = None) -> dict[str, Any]:
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
    grader = grade_fn or default_grade
    rec["grade"] = grader(
        selected_p=float(rec.get("evidenceSafeP") or rec.get("selectedP") or 0.5),
        lower_bound=float(rec.get("lowerBound") or 0.0),
        demon=str(row.get("modifier") or "") == "DEMON",
        fragility=float(rec.get("fragility") or 0.0),
        robustness_area=float(surf.get("robustness_area") or 0.0),
        elasticity=float(surf.get("edge_elasticity") or 0.0),
        false_sign=float(rec.get("falseSignRisk") or 0.0),
    )
    return rec


def apply_final_refresh(
    modeled: list[dict[str, Any]],
    *,
    claims: list[Mapping[str, Any]] | None = None,
    cutoff: str | None = None,
    started_events: set[str] | None = None,
    resimulate: RebuildFn | None = None,
    grade_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
    started = started_events or set()
    claims = list(claims or [])
    refreshed = 0
    held = 0
    line_only = 0
    material = 0
    rebuilt = 0
    by_scope: dict[tuple[str, str], dict[str, Any]] = {}
    for claim in claims:
        observed = claim.get("observed_at") or claim.get("observedAt")
        if cutoff and is_after_cutoff(observed, cutoff):
            continue
        key = (str(claim.get("semantic_scope") or ""), str(claim.get("scope_id") or ""))
        prev = by_scope.get(key)
        prev_obs = (prev or {}).get("observed_at") if prev else None
        if prev is None or (observed and is_after_cutoff(observed, prev_obs)) or (
            observed and prev_obs is None
        ):
            by_scope[key] = dict(claim)

    out: list[dict[str, Any]] = []
    for prop in modeled:
        rec = dict(prop)
        row = dict(rec.get("row") or rec)
        event_id = str(row.get("eventId") or "")
        if event_id in started:
            rec["finalRefresh"] = "STARTED_EVENT_NO_PREGAME_SELECTION"
            rec["needsWorldRebuild"] = False
            rec["refreshCategory"] = "HELD_STARTED"
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
        rec["needsWorldRebuild"] = False
        rec["refreshCategory"] = "UNCHANGED"
        if updates:
            rec["row"] = row
            rec["finalRefreshFields"] = list(dict.fromkeys(updates))
            refreshed += 1
            material_changed = any(f in MATERIAL_FIELDS for f in updates)
            line_changed = any(f in LINE_FIELDS for f in updates)
            if material_changed:
                rec["needsWorldRebuild"] = True
                rec["refreshCategory"] = "MATERIAL_STATE"
                material += 1
                values = None
                if resimulate is not None:
                    try:
                        values = resimulate(rec)
                    except (TypeError, ValueError, KeyError, RuntimeError):
                        values = None
                if values:
                    rec["_worldValues"] = list(values)
                    rebuilt += 1
                    try:
                        _regrade(rec, row, list(values), grade_fn=grade_fn)
                    except (TypeError, ValueError, KeyError):
                        pass
            elif line_changed:
                rec["refreshCategory"] = "LINE_ONLY"
                line_only += 1
                values = rec.get("_worldValues")
                if isinstance(values, list) and values:
                    try:
                        _regrade(rec, row, [float(v) for v in values], grade_fn=grade_fn)
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
        "lineOnlyCount": line_only,
        "materialStateCount": material,
        "worldsRebuilt": rebuilt,
        "needsWorldRebuild": material > 0,
        "lineFields": list(LINE_FIELDS),
        "materialFields": list(MATERIAL_FIELDS),
        "volatileFields": list(VOLATILE_FIELDS),
        "cutoff": cutoff,
        "note": "Line-only refresh reuses EventWorlds. Material state rebuilds snapshots/worlds. No post-start evidence.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return {"modeled": out, "report": body}
