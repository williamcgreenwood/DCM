"""Automatic Top100 → frontier research → recompute → Top25 loop.

Top25 is FINAL only when frontierResearchPasses >= 1 OR no unresolved
material research has enough expected value to alter Top25 / PLAYABLE /
direction / line tolerance / portfolio.
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
    """Cheap EVSI stand-in: rank displacement × unresolved materiality × uncertainty."""
    rank = int(row.get("rank") or 99)
    displacement = max(0.0, (26 - min(rank, 26)) / 26.0)
    unc = row.get("uncertainty") if isinstance(row.get("uncertainty"), dict) else {}
    epi = float(unc.get("epistemic") or row.get("epistemicUncertainty") or 0.15)
    material = 1.0 if _unresolved_material(row) else 0.05
    return float(displacement * (0.25 + epi) * material)


def run_frontier_loop(
    modeled: list[dict[str, Any]],
    *,
    telemetry: AlgorithmTelemetry | None = None,
    unresolved_actions: int = 0,
    evidence_imported: bool = False,
    material_facts: Mapping[str, Any] | None = None,
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
    impacts = []
    for row in preliminary.get("rows") or []:
        if str(row.get("offer_id") or "") in frontier_ids:
            impacts.append({
                "offer_id": row.get("offer_id"),
                "rank": row.get("rank"),
                "evsi": estimate_frontier_impact(row),
                "unresolved": _unresolved_material(row),
            })
    material_evsi = [x for x in impacts if float(x["evsi"]) >= 0.02 and x["unresolved"]]
    grades_changed = sum(
        1 for a, b in zip(modeled, recomputed_rows)
        if a.get("grade") != b.get("grade")
    )
    if evidence_imported or grades_changed:
        passes = 1
        recomputed = pre_hash != post_hash or evidence_imported
    elif not material_evsi:
        passes = 0
        recomputed = False
    else:
        passes = 0
        recomputed = False

    top25 = cfb_top25_final(recomputed_rows, telemetry=tel)
    final_ok = passes >= 1 or not material_evsi
    if not final_ok:
        top25["name"] = "CFB_TOP25_INTERIM"
        top25["note"] = "Not FINAL: unresolved material frontier research remains."
    else:
        top25["name"] = "CFB_TOP25_FINAL"
        top25["frontierResearchPasses"] = passes
    top25["final"] = final_ok
    top25["contentHash"] = content_hash({k: v for k, v in top25.items() if k != "contentHash"})

    body = {
        "schema": "pillars_dcm.cfb_frontier_loop.v1",
        "frontierPassCount": passes,
        "recomputed": recomputed,
        "frontierOfferCount": len(frontier_ids),
        "materialEvsiCount": len(material_evsi),
        "unresolvedActionsRemaining": int(unresolved_actions),
        "top25Final": final_ok,
        "offersChanged": grades_changed,
        "ranksChanged": grades_changed,
        "preHash": pre_hash,
        "postHash": post_hash,
        "impacts": impacts[:25],
        "preliminaryHash": preliminary.get("contentHash"),
        "top25Hash": top25.get("contentHash"),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "impacts"}})
    tel.record(
        "ALG-SCHED-008",
        problem_class="SUBMODULAR",
        producer="dcm.cfb.frontier.estimate_frontier_impact",
        consumer="dcm.cfb.frontier.run_frontier_loop",
        artifact="cfb_frontier_loop.json",
        count=max(1, len(material_evsi)),
        phase="EXECUTED",
        note="EVSI-style frontier impact on Top100 displacement; challenger KG unused",
        fallback="ALG-SCHED-001",
    )
    return {
        "preliminary": preliminary,
        "top25": top25,
        "frontierOfferIds": frontier_ids,
        "loop": body,
        "telemetry": tel,
    }
