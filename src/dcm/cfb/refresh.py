"""Final refresh of Top25 / PLAYABLE frontier immediately before freeze.

Line-only refresh re-evaluates the existing EventWorld distribution at the
new line. Material state change is flagged for the runner to rebuild
ParameterSnapshots + shared EventWorlds. This module does not resimulate.
No post-start evidence may influence an event's pregame freeze.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from dcm.cfb.recompute import recompute_full_bundle
from dcm.contracts.hashes import content_hash
from dcm.research.material_facts import facts_for_refresh, is_after_cutoff


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
    "pace",
    "pass_rate",
    "pass_defense",
    "rush_defense",
    "team",
)
VOLATILE_FIELDS = LINE_FIELDS + MATERIAL_FIELDS

RebuildFn = Callable[[dict[str, Any]], list[float] | None]


def _fact_field_value(fact: Mapping[str, Any], field: str) -> Any:
    if fact.get("field") == field and fact.get("fieldValue") is not None:
        return fact.get("fieldValue")
    value = fact.get("value")
    if isinstance(value, Mapping) and field in value and value[field] is not None:
        return value[field]
    if str(fact.get("claimType") or "").lower() == field.lower() and not isinstance(value, Mapping):
        return value
    if str(fact.get("field") or "").lower() == field.lower() and fact.get("fieldValue") is not None:
        return fact.get("fieldValue")
    return None


def apply_final_refresh(
    modeled: list[dict[str, Any]],
    *,
    claims: list[Mapping[str, Any]] | None = None,
    facts: Mapping[str, Any] | None = None,
    cutoff: str | None = None,
    started_events: set[str] | None = None,
    resimulate: RebuildFn | None = None,
    grade_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Classify line-only vs material. Never independently resimulate worlds.

    `resimulate` is accepted for signature compatibility and ignored. The
    runner rebuilds ParameterSnapshots + shared EventWorlds from rebuild keys.
    """
    started = started_events or set()
    claims = list(claims or [])
    refreshed = 0
    held = 0
    line_only = 0
    material = 0
    fact_index = facts_for_refresh(facts)
    line_by_scope: dict[tuple[str, str], dict[str, Any]] = {}
    for claim in claims:
        observed = claim.get("observed_at") or claim.get("observedAt")
        if cutoff and is_after_cutoff(observed, cutoff):
            continue
        key = (str(claim.get("semantic_scope") or claim.get("scope") or ""), str(claim.get("scope_id") or ""))
        prev = line_by_scope.get(key)
        prev_obs = (prev or {}).get("observed_at") if prev else None
        if prev is None or (observed and is_after_cutoff(observed, prev_obs)) or (
            observed and prev_obs is None
        ):
            line_by_scope[key] = dict(claim)

    out: list[dict[str, Any]] = []
    rebuild_players: set[str] = set()
    rebuild_events: set[str] = set()
    rebuild_teams: set[str] = set()
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
        team_id = str(row.get("teamId") or row.get("team") or "")
        opp_id = str(row.get("opponentId") or row.get("opponent") or "")
        updates: list[str] = []
        scope_ids = {
            "SUBJECT": player_id,
            "PLAYER": player_id,
            "EVENT": event_id,
            "ENVIRONMENT": f"env:{event_id}",
            "AFFILIATION": team_id,
            "TEAM": team_id,
            "COUNTERPARTY": opp_id,
            "OPPONENT": opp_id,
        }
        for (scope, sid, _ctype), fact in fact_index.items():
            want = scope_ids.get(scope)
            if not want or sid not in {want, event_id, player_id, team_id, opp_id, f"env:{event_id}"}:
                if sid not in {player_id, event_id, team_id, opp_id, f"env:{event_id}"}:
                    continue
            for field in MATERIAL_FIELDS:
                val = _fact_field_value(fact, field)
                if val is not None and row.get(field) != val:
                    row[field] = val
                    updates.append(field)
        for scope, sid in (("SUBJECT", player_id), ("EVENT", event_id), ("OFFER", str(row.get("projectionId") or "")), ("ENVIRONMENT", f"env:{event_id}")):
            claim = line_by_scope.get((scope, sid))
            if not claim:
                continue
            value = claim.get("claim_value") if isinstance(claim.get("claim_value"), dict) else {}
            for field in LINE_FIELDS:
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
                rebuild_players.add(player_id)
                if event_id:
                    rebuild_events.add(event_id)
                if team_id:
                    rebuild_teams.add(team_id)
            elif line_changed:
                rec["refreshCategory"] = "LINE_ONLY"
                line_only += 1
                values = rec.get("_worldValues")
                if isinstance(values, list) and values:
                    try:
                        rec = recompute_full_bundle(rec, grade_fn=grade_fn)
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
        "worldsRebuilt": 0,
        "needsWorldRebuild": material > 0,
        "rebuildPlayerIds": sorted(p for p in rebuild_players if p),
        "rebuildEventIds": sorted(e for e in rebuild_events if e),
        "rebuildTeamIds": sorted(t for t in rebuild_teams if t),
        "lineFields": list(LINE_FIELDS),
        "materialFields": list(MATERIAL_FIELDS),
        "volatileFields": list(VOLATILE_FIELDS),
        "cutoff": cutoff,
        "resimulateIgnored": resimulate is not None,
        "note": "Line-only refresh reuses EventWorlds. Material state returns rebuild keys; the runner rebuilds snapshots + joint worlds. No post-start evidence.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return {"modeled": out, "report": body}
