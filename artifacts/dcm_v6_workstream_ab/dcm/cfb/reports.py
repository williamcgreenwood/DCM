"""CFB Top100 / Top25 / Playables reports with required columns."""
from __future__ import annotations

from typing import Any

from dcm.algorithms.sorting import heap_topk, timsort
from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.contracts.hashes import content_hash
from dcm.model.ranking import selection_score
from dcm.selection.portfolio import build_card


def _row(p: dict[str, Any]) -> dict[str, Any]:
    return p.get("row") if isinstance(p.get("row"), dict) else p


def _is_cfb(p: dict[str, Any]) -> bool:
    r = _row(p)
    return str(r.get("sportFamily") or "") == "gridiron" and str(r.get("league") or "").upper() == "CFB"


def _offered_sides(r: dict[str, Any]) -> list[str]:
    sides: list[str] = []
    if r.get("offeredHigher"):
        sides.append("MORE")
    if r.get("offeredLower"):
        sides.append("LESS")
    return sides


def _support(p: dict[str, Any]) -> dict[str, Any]:
    snap = p.get("parameterSnapshot") if isinstance(p.get("parameterSnapshot"), dict) else {}
    support = snap.get("model_support") if isinstance(snap.get("model_support"), dict) else {}
    return support


def cfb_prop_flags(p: dict[str, Any]) -> dict[str, Any]:
    snap = p.get("parameterSnapshot") if isinstance(p.get("parameterSnapshot"), dict) else {}
    support = _support(p)
    coverage = p.get("coverage") if isinstance(p.get("coverage"), dict) else {}
    modelable = bool(support.get("modelable", snap.get("minimum_model_support")))
    playable = bool(support.get("playableSupport")) and bool(p.get("modeledPlayable"))
    # Five flags persist independently. Do not infer research-complete from modelable.
    if "requiredComplete" in coverage:
        research_complete = bool(coverage.get("requiredComplete"))
    elif "propResearchComplete" in p:
        research_complete = bool(p.get("propResearchComplete"))
    else:
        research_complete = False
    if "propFrontierResearchEligible" in p:
        frontier = bool(p.get("propFrontierResearchEligible"))
    elif "frontierEligible" in coverage:
        frontier = bool(coverage.get("frontierEligible"))
    else:
        frontier = bool(p.get("grade") in {"PLAYABLE", "LEAN"}) and not playable
    global_complete = bool(coverage.get("globalComplete", p.get("globalCoverageComplete")))
    return {
        "propResearchComplete": research_complete,
        "propModelable": modelable,
        "propPlayableEligible": playable,
        "propFrontierResearchEligible": frontier,
        "globalCoverageComplete": global_complete,
        "footballModelable": modelable,
        "playableSupport": bool(support.get("playableSupport")),
    }


def cfb_top100_row(p: dict[str, Any], *, rank: int) -> dict[str, Any]:
    r = _row(p)
    surf = p.get("lineSurface") if isinstance(p.get("lineSurface"), dict) else {}
    flags = cfb_prop_flags(p)
    support = _support(p)
    blockers = []
    if p.get("blocker"):
        blockers.append(str(p.get("blocker")))
    blockers.extend(str(x) for x in (support.get("playableBlockers") or support.get("modelBlockers") or []) if x)
    uncertainty = {
        "epistemic": p.get("epistemicUncertainty"),
        "aleatoric": p.get("aleatoricUncertainty"),
        "monteCarloSE": p.get("monteCarloSE"),
    }
    return {
        "rank": rank,
        "offer_id": r.get("projectionId"),
        "player": r.get("playerName"),
        "subject": r.get("playerId") or r.get("subjectId"),
        "team": r.get("team") or r.get("teamId"),
        "opponent": r.get("opponent") or r.get("opponentId"),
        "market": r.get("market"),
        "line": r.get("line"),
        "offered_sides": _offered_sides(r),
        "preferred_direction": p.get("selectedSide") or r.get("side"),
        "P_Higher": p.get("pHigher"),
        "P_Lower": p.get("pLower"),
        "push_probability": p.get("pPush"),
        "uncertainty": uncertainty,
        "Reliability": p.get("reliability"),
        "Data_Quality": p.get("dataQuality"),
        "Volatility": p.get("volatility"),
        "Fragility": p.get("fragility"),
        "OOD": p.get("oodRisk"),
        "Selection_Score": p.get("selectionScore"),
        "grade": p.get("grade"),
        "true_line_tolerance": surf.get("true_unclamped_line_tolerance") or p.get("trueLineTolerance"),
        "research_modelability_state": {
            **flags,
            "state": p.get("state"),
            "modeledPlayable": p.get("modeledPlayable"),
            "productionSelectable": p.get("productionSelectable"),
        },
        "material_blockers": list(dict.fromkeys(blockers)),
        "event": r.get("eventLabel") or r.get("eventId"),
        "modifier": r.get("modifier"),
        "not_a_recommendation": True,
    }


def rank_cfb_modeled(
    modeled: list[dict[str, Any]],
    *,
    k: int = 100,
    telemetry: AlgorithmTelemetry | None = None,
) -> list[dict[str, Any]]:
    """Filter CFB → heap partial Top-K → deterministic Timsort of the frontier."""
    tel = telemetry or AlgorithmTelemetry()
    cfb = [p for p in modeled if _is_cfb(p)]
    for p in cfb:
        if p.get("selectionScore") is None:
            p["selectionScore"] = selection_score(p)
    tel.record("ALG-SORT-003", problem_class="TOPK_PARTIAL", producer="dcm.algorithms.sorting.heap_topk", consumer="dcm.cfb.reports.rank_cfb_modeled", count=1)
    frontier = heap_topk(
        cfb,
        min(k, len(cfb)),
        key=lambda p: (float(p.get("selectionScore") or -999), str((_row(p).get("projectionId") or ""))),
    )
    ranked = timsort(
        frontier,
        key=lambda p: (float(p.get("selectionScore") or -999), str((_row(p).get("projectionId") or ""))),
        reverse=True,
    )
    tel.record("ALG-SORT-001", problem_class="FINAL_RANK", producer="dcm.algorithms.sorting.timsort", consumer="dcm.cfb.reports.rank_cfb_modeled")
    for i, p in enumerate(ranked, 1):
        p["cfbRank"] = i
    return ranked


def cfb_top100_preliminary(modeled: list[dict[str, Any]], *, telemetry: AlgorithmTelemetry | None = None) -> dict[str, Any]:
    ranked = rank_cfb_modeled(modeled, k=100, telemetry=telemetry)
    rows = [cfb_top100_row(p, rank=i) for i, p in enumerate(ranked, 1)]
    body = {
        "schema": "pillars_dcm.cfb_top100_preliminary.v1",
        "name": "CFB_TOP100_PRELIMINARY",
        "count": len(rows),
        "note": "Not recommendations. Grades are actual PLAYABLE/LEAN/PASS/TRAP.",
        "rows": rows,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def cfb_top25_final(modeled: list[dict[str, Any]], *, telemetry: AlgorithmTelemetry | None = None) -> dict[str, Any]:
    ranked = rank_cfb_modeled(modeled, k=25, telemetry=telemetry)
    rows = [cfb_top100_row(p, rank=i) for i, p in enumerate(ranked, 1)]
    body = {
        "schema": "pillars_dcm.cfb_top25_final.v1",
        "name": "CFB_TOP25_FINAL",
        "count": len(rows),
        "note": "Do not force 25. Count equals competitive modeled CFB after frontier recompute.",
        "rows": rows,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def cfb_playables_final(
    qualified: list[dict[str, Any]],
    *,
    telemetry: AlgorithmTelemetry | None = None,
) -> dict[str, Any]:
    tel = telemetry or AlgorithmTelemetry()
    cfb_qualified = [p for p in qualified if _is_cfb(p)]
    card = build_card(cfb_qualified, max_size=6, max_per_event=2)
    tel.record("ALG-GROUP-009", problem_class="HAR_GROUPING", producer="dcm.selection.portfolio.build_card", consumer="dcm.cfb.reports.cfb_playables_final", count=len(card) or 1)
    rows = [cfb_top100_row(p, rank=i) for i, p in enumerate(card, 1)]
    for row, p in zip(rows, card):
        row["not_a_recommendation"] = False
        row["playableSelected"] = True
        flags = cfb_prop_flags(p)
        row["research_modelability_state"] = {**row["research_modelability_state"], **flags}
    body = {
        "schema": "pillars_dcm.cfb_playables_final.v1",
        "name": "CFB_PLAYABLES_FINAL",
        "count": len(rows),
        "neverForceSix": True,
        "constraints": [
            "unique-player",
            "combo/component",
            "same-event <=2",
            "shared team/QB",
            "weather",
            "injury",
            "evidence-path",
            "correlation",
        ],
        "rows": rows,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def frontier_offer_ids(top100: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for row in top100.get("rows") or []:
        state = row.get("research_modelability_state") or {}
        if state.get("propFrontierResearchEligible") or row.get("grade") in {"PLAYABLE", "LEAN"}:
            if row.get("offer_id"):
                out.add(str(row["offer_id"]))
        elif int(row.get("rank") or 999) <= 25:
            if row.get("offer_id"):
                out.add(str(row["offer_id"]))
    return out
