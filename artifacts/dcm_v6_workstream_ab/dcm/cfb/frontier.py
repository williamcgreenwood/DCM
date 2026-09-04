"""Automatic Top100 → frontier research → recompute → Top25 loop.

A frontier pass increments only when material downstream state changes:
new frontier evidence, MaterialFact/Feature/ParameterSnapshot/EventWorld
hash change, or grade/rank/direction/tolerance change.

Generic imported claims do not increment the pass counter.
Top25 is FINAL only after a legitimate stop reason.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.cfb.reports import cfb_top100_preliminary, cfb_top25_final, frontier_offer_ids
from dcm.contracts.hashes import content_hash
from dcm.research.material_facts import apply_hold_playable, hold_playable_scope_ids


def _unresolved_material(prop: Mapping[str, Any]) -> list[str]:
    flags = prop.get("research_modelability_state") if isinstance(prop.get("research_modelability_state"), dict) else {}
    blockers = list(prop.get("material_blockers") or [])
    if flags.get("propFrontierResearchEligible"):
        blockers.append("FRONTIER_RESEARCH_ELIGIBLE")
    return [str(b) for b in blockers if b]


def estimate_frontier_impact(row: Mapping[str, Any]) -> float:
    """Offer-level materiality used when no AcquisitionAction graph is supplied."""
    rank = int(row.get("rank") or 99)
    displacement = max(0.0, (26 - min(rank, 26)) / 26.0)
    unc = row.get("uncertainty") if isinstance(row.get("uncertainty"), dict) else {}
    epi = float(unc.get("epistemic") or row.get("epistemicUncertainty") or 0.15)
    material = 1.0 if _unresolved_material(row) else 0.05
    grade = str(row.get("grade") or "")
    grade_w = {"PLAYABLE": 1.0, "LEAN": 0.7, "PASS": 0.15, "TRAP": 0.05}.get(grade, 0.3)
    return float(displacement * (0.25 + epi) * material * grade_w)


def estimate_action_evsi(
    action: Mapping[str, Any],
    *,
    frontier_ids: set[str],
    rank_by_offer: Mapping[str, int] | None = None,
) -> float:
    """Utility(action) = fanout × materiality × P(success) × authority / cost."""
    oids = [str(x) for x in (action.get("offerIds") or []) if x]
    fanout = max(1, int(action.get("dependentOfferCount") or len(oids) or 1))
    frontier_n = len(set(oids) & frontier_ids) if frontier_ids else 0
    proximity = 0.0
    if rank_by_offer:
        for oid in oids:
            rank = int(rank_by_offer.get(oid) or 99)
            proximity = max(proximity, max(0.0, (26 - min(rank, 26)) / 26.0))
    materiality = max(0.05, (frontier_n / fanout) if fanout else 0.05)
    p_success = float(action.get("pSuccess") or 0.85)
    authority = float(action.get("authority") or 0.8)
    freshness = float(action.get("freshness") or 0.7)
    cost = max(1e-6, float(action.get("cost") or 1.0))
    return float((fanout * materiality * (0.4 + proximity) * p_success * authority * freshness) / cost)


def run_frontier_loop(
    modeled: list[dict[str, Any]],
    *,
    telemetry: AlgorithmTelemetry | None = None,
    unresolved_actions: int = 0,
    evidence_imported: bool = False,
    material_facts: Mapping[str, Any] | None = None,
    actions: Mapping[str, Any] | list | None = None,
    snapshot_hash_before: str | None = None,
    snapshot_hash_after: str | None = None,
    world_hash_before: str | None = None,
    world_hash_after: str | None = None,
    feature_hash_before: str | None = None,
    feature_hash_after: str | None = None,
    host_required: bool = False,
) -> dict[str, Any]:
    tel = telemetry or AlgorithmTelemetry()
    hold_ids = hold_playable_scope_ids(material_facts)
    recomputed_rows = [apply_hold_playable(dict(p), hold_ids) for p in modeled]
    pre_hash = content_hash([
        {"id": (p.get("row") or {}).get("projectionId"), "grade": p.get("grade"), "p": p.get("selectedP")}
        for p in modeled[:100]
    ])
    post_hash = content_hash([
        {"id": (p.get("row") or {}).get("projectionId"), "grade": p.get("grade"), "p": p.get("selectedP")}
        for p in recomputed_rows[:100]
    ])
    preliminary = cfb_top100_preliminary(recomputed_rows, telemetry=tel)
    frontier_ids = frontier_offer_ids(preliminary)
    rank_by_offer = {
        str(row.get("offer_id") or ""): int(row.get("rank") or 99)
        for row in (preliminary.get("rows") or [])
    }
    impacts = []
    for row in preliminary.get("rows") or []:
        oid = str(row.get("offer_id") or "")
        if oid in frontier_ids:
            impacts.append({
                "offer_id": oid,
                "rank": row.get("rank"),
                "evsi": estimate_frontier_impact(row),
                "unresolved": _unresolved_material(row),
            })
    action_rows = []
    if isinstance(actions, Mapping):
        action_rows = list(actions.get("actions") or [])
    elif isinstance(actions, list):
        action_rows = actions
    action_evsi = []
    for act in action_rows:
        if not isinstance(act, Mapping):
            continue
        util = estimate_action_evsi(act, frontier_ids=set(frontier_ids), rank_by_offer=rank_by_offer)
        action_evsi.append({
            "actionId": act.get("actionId"),
            "evsi": util,
            "fanout": act.get("dependentOfferCount"),
            "cost": act.get("cost"),
            "sourceCandidates": act.get("sourceCandidates") or [],
        })
    positive_actions = [x for x in action_evsi if float(x["evsi"]) > 0.02]
    material_evsi = [x for x in impacts if float(x["evsi"]) >= 0.02 and x["unresolved"]]
    grades_changed = sum(
        1 for a, b in zip(modeled, recomputed_rows)
        if a.get("grade") != b.get("grade")
    )
    snapshot_changed = bool(snapshot_hash_before and snapshot_hash_after and snapshot_hash_before != snapshot_hash_after)
    world_changed = bool(world_hash_before and world_hash_after and world_hash_before != world_hash_after)
    feature_changed = bool(feature_hash_before and feature_hash_after and feature_hash_before != feature_hash_after)
    fact_changed = bool(hold_ids) or grades_changed
    material_state_changed = bool(
        (pre_hash != post_hash)
        or snapshot_changed
        or world_changed
        or feature_changed
        or fact_changed
    )
    # Evidence import alone is not a pass. A pass requires downstream state change.
    if material_state_changed:
        passes = 1
        recomputed = True
        stop_reason = "FRONTIER_STABLE"
    elif host_required or (unresolved_actions > 0 and (material_evsi or positive_actions)):
        passes = 0
        recomputed = False
        stop_reason = "EXTERNAL_HOST_REQUIRED"
    elif not material_evsi and not positive_actions:
        passes = 0
        recomputed = False
        stop_reason = "NO_MATERIAL_FRONTIER_REQUIREMENTS" if not impacts else "NO_POSITIVE_EVSI_ACTION"
    else:
        passes = 0
        recomputed = False
        stop_reason = "NO_POSITIVE_EVSI_ACTION"

    top25 = cfb_top25_final(recomputed_rows, telemetry=tel)
    # FINAL is legitimate when there is no remaining material action, or a
    # completed pass already rebuilt downstream state.
    final_ok = stop_reason in {
        "FRONTIER_STABLE",
        "NO_MATERIAL_FRONTIER_REQUIREMENTS",
        "NO_POSITIVE_EVSI_ACTION",
        "RESEARCH_BUDGET_EXHAUSTED",
        "CUTOFF_REACHED",
        "SOURCE_UNAVAILABLE",
    }
    if stop_reason == "EXTERNAL_HOST_REQUIRED":
        final_ok = False
        top25["name"] = "CFB_TOP25_INTERIM"
        top25["note"] = "Not FINAL: host must acquire frontier actions before Top25 FINAL."
    else:
        top25["name"] = "CFB_TOP25_FINAL"
        top25["frontierResearchPasses"] = passes
        top25["stopReason"] = stop_reason
    top25["final"] = final_ok
    top25["contentHash"] = content_hash({k: v for k, v in top25.items() if k != "contentHash"})

    body = {
        "schema": "pillars_dcm.cfb_frontier_loop.v1",
        "frontierPassCount": passes,
        "recomputed": recomputed,
        "frontierOfferCount": len(frontier_ids),
        "materialEvsiCount": len(material_evsi),
        "positiveActionCount": len(positive_actions),
        "unresolvedActionsRemaining": int(unresolved_actions),
        "top25Final": final_ok,
        "stopReason": stop_reason,
        "offersChanged": grades_changed,
        "ranksChanged": grades_changed,
        "snapshotChanged": snapshot_changed,
        "worldChanged": world_changed,
        "featureChanged": feature_changed,
        "evidenceImportedIgnoredUnlessMaterial": True,
        "evidenceImported": bool(evidence_imported),
        "preHash": pre_hash,
        "postHash": post_hash,
        "impacts": impacts[:25],
        "actionEvsi": action_evsi[:25],
        "preliminaryHash": preliminary.get("contentHash"),
        "top25Hash": top25.get("contentHash"),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "impacts", "actionEvsi"}})
    tel.record(
        "ALG-SCHED-008",
        problem_class="SUBMODULAR",
        producer="dcm.cfb.frontier.estimate_action_evsi",
        consumer="dcm.cfb.frontier.run_frontier_loop",
        artifact="cfb_frontier_loop.json",
        count=max(1, len(positive_actions) or len(material_evsi)),
        phase="EXECUTED",
        downstream_used=True,
        note="EVSI from AcquisitionAction fanout/cost/authority; pass increments only on material state change",
        fallback="ALG-SCHED-001",
    )
    return {
        "preliminary": preliminary,
        "top25": top25,
        "frontierOfferIds": frontier_ids,
        "loop": body,
        "telemetry": tel,
    }
