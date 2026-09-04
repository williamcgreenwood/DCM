"""AcquisitionAction live scheduler: CELF + weighted set-cover + batch packing.

One AcquisitionAction covers many requirements and offers. The live selector
is LazyGreedyScheduler; set-cover is both a selector input and telemetry.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from dcm.algorithms.graph import hypergraph_from_bundles
from dcm.algorithms.scheduling import (
    LazyGreedyScheduler,
    acquisition_cost,
    cover_actions,
    expected_marginal_gain,
    first_fit_decreasing,
    greedy_value_density_pack,
    requirement_weight,
)
from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.contracts.hashes import content_hash
from dcm.research.indexes import EvidenceIndexes
from dcm.research.os_graphs import _attach_dependents
from dcm.research.scopes import SCOPE_RANK, canonical_scope
from dcm.research.source_health import SourceHealthRegistry, default_cfb_source_health
from dcm.sports.football.research_requirements import MARKET_REQUIREMENTS


CFB_ACTION_ORDER = {
    "EVENT": 1,
    "ENVIRONMENT": 2,
    "AFFILIATION": 3,
    "COUNTERPARTY": 4,
    "SUBJECT": 5,
    "MARKET_DEFINITION": 6,
    "OFFER": 7,
    "SPORT": 0,
    "COMPETITION": 0,
}

WEATHER_APPLICABLE_MARKETS = frozenset(
    {"pass_yds", "rush_yds", "rec_yds", "pass_rush_yds", "rush_rec_yds", "pass_att", "rush_att"}
)


def _req_id(req: Mapping[str, Any]) -> str:
    return str(req.get("request_id") or req.get("requestId") or "")


def build_acquisition_actions(
    rows: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    *,
    coverage: dict[str, Any] | None = None,
    evidence: EvidenceIndexes | None = None,
    frontier_offer_ids: set[str] | None = None,
    telemetry: AlgorithmTelemetry | None = None,
    source_health: SourceHealthRegistry | None = None,
) -> dict[str, Any]:
    """Group reusable-entity requests into fan-out AcquisitionActions."""
    tel = telemetry or AlgorithmTelemetry()
    health = source_health or default_cfb_source_health()
    reqs = _attach_dependents(list(requests or []), rows)
    coverage_by_id = {
        str(row.get("requestId") or row.get("request_id") or ""): row
        for row in ((coverage or {}).get("requests") or [])
        if isinstance(row, dict)
    }
    complete_ids: set[str] = set()
    for rec in reqs:
        rid = _req_id(rec)
        cov = coverage_by_id.get(rid) or {}
        if cov.get("complete"):
            complete_ids.add(rid)
        if evidence is not None:
            hits = evidence.lookup_scope(str(rec.get("scope") or ""), str(rec.get("scope_id") or ""))
            if hits:
                complete_ids.add(rid)

    actions: dict[str, dict[str, Any]] = {}
    for rec in reqs:
        rid = _req_id(rec)
        if not rid or rid in complete_ids:
            continue
        scope = canonical_scope(str(rec.get("scope") or ""))
        sid = str(rec.get("scope_id") or "")
        action_id = f"AA_{scope}_{sid}"
        act = actions.setdefault(
            action_id,
            {
                "actionId": action_id,
                "scope": scope,
                "scopeId": sid,
                "sourceFamily": {
                    "EVENT": "event_schedule_venue_status",
                    "ENVIRONMENT": "event_weather_surface",
                    "AFFILIATION": "team_game_logs_depth_offense",
                    "COUNTERPARTY": "opponent_defense_depth",
                    "SUBJECT": "player_role_history",
                    "MARKET_DEFINITION": "market_definition",
                    "OFFER": "offer_line_sides",
                    "SPORT": "sport_rules",
                    "COMPETITION": "competition_context",
                }.get(scope, "generic"),
                "requirementIds": [],
                "offerIds": [],
                "eventId": rec.get("eventId") or (sid if scope in {"EVENT", "ENVIRONMENT"} else None),
                "cfbFanoutPriority": CFB_ACTION_ORDER.get(scope, 9),
                "needsPassDefense": False,
                "needsRushDefense": False,
                "weatherApplicable": False,
            },
        )
        act["requirementIds"].append(rid)
        for oid in rec.get("dependent_offer_ids") or []:
            if oid not in act["offerIds"]:
                act["offerIds"].append(oid)

    offer_map = {str(r.get("projectionId") or ""): r for r in rows}
    for act in actions.values():
        markets = [str((offer_map.get(oid) or {}).get("market") or "").lower() for oid in act["offerIds"]]
        act["needsPassDefense"] = any(bool((MARKET_REQUIREMENTS.get(m) or {}).get("needs_pass_defense")) for m in markets)
        act["needsRushDefense"] = any(bool((MARKET_REQUIREMENTS.get(m) or {}).get("needs_rush_defense")) for m in markets)
        act["weatherApplicable"] = any(m in WEATHER_APPLICABLE_MARKETS for m in markets)
        offer_n = max(1, len(act["offerIds"]))
        # SPORT/COMPETITION are one-shot context. Counting every dependent offer
        # as mass lets them dominate CELF and blow the batch offer budget.
        mass = 1.0 if act["scope"] in {"SPORT", "COMPETITION"} else float(offer_n)
        frontier_n = len(set(act["offerIds"]) & (frontier_offer_ids or set()))
        act["weight"] = round(
            requirement_weight(
                dependent_offer_mass=mass,
                criticality=1.0 if act["scope"] in {"EVENT", "AFFILIATION", "SUBJECT"} else 0.6,
                information_importance=max(0.1, 1.0 - 0.08 * int(act["cfbFanoutPriority"])),
                freshness_urgency=1.0 if act["scope"] in {"EVENT", "ENVIRONMENT", "SUBJECT"} else 0.5,
                current_uncertainty=1.0,
                eligibility_unlock=1.0 if act["scope"] in {"SUBJECT", "AFFILIATION"} else 0.4,
                frontier_weight=float(frontier_n) / float(offer_n),
                deadline_urgency=0.8,
            ),
            6,
        )
        act["cost"] = round(
            acquisition_cost(
                web_calls=1.0,
                input_tokens=800.0,
                output_tokens=400.0,
                latency=1.0,
                risk=0.05 if act["scope"] != "OFFER" else 0.0,
            ),
            6,
        )
        uncovered = [act["weight"] / max(1, len(act["requirementIds"]))] * len(act["requirementIds"])
        act["expectedGain"] = round(
            expected_marginal_gain(
                p_success=0.85,
                authority_quality=0.8,
                novelty=1.0,
                uncovered_weights=uncovered,
            ),
            6,
        )
        act["requirementIds"] = list(dict.fromkeys(act["requirementIds"]))
        act["offerIds"] = list(dict.fromkeys(act["offerIds"]))
        act["dependentOfferCount"] = len(act["offerIds"])
        act["requirementCount"] = len(act["requirementIds"])
        candidates = health.route(claim_type=str(act.get("scope") or "SUBJECT"), sport="CFB")
        act["sourceCandidates"] = candidates
        act["sourceId"] = candidates[0] if candidates else None
        act["pSuccess"] = 0.85
        act["authority"] = 0.8
        if act["sourceId"]:
            row = health._state.get(str(act["sourceId"])) or {}
            act["pSuccess"] = float(row.get("historicalSuccessProbability") or 0.85)
            auth_map = row.get("authorityByClaimType") or {}
            act["authority"] = float(auth_map.get(str(act.get("scope") or ""), 80)) / 100.0
            act["freshness"] = float(row.get("observedFreshness") or row.get("expectedFreshness") or 0.5)

    hg = hypergraph_from_bundles({aid: act["requirementIds"] for aid, act in actions.items()})
    reverse_action_req = {aid: list(act["requirementIds"]) for aid, act in actions.items()}
    reverse_req_action: dict[str, list[str]] = defaultdict(list)
    reverse_action_offer = {aid: list(act["offerIds"]) for aid, act in actions.items()}
    for aid, req_ids in reverse_action_req.items():
        for rid in req_ids:
            reverse_req_action[rid].append(aid)

    tel.record("ALG-INDEX-014", problem_class="GRAPH_TRAVERSAL", producer="dcm.research.acquisition.build_acquisition_actions", consumer="dcm.research.batch", count=len(actions), downstream_used=True)
    tel.record("ALG-GROUP-006", problem_class="HAR_GROUPING", producer="dcm.research.acquisition.build_acquisition_actions", consumer="dcm.research.batch", count=len(actions), downstream_used=True)

    payload = {
        "schema": "pillars_dcm.acquisition_actions.v1",
        "actionCount": len(actions),
        "requirementCount": len(reqs),
        "completeRequirementCount": len(complete_ids),
        "actions": sorted(actions.values(), key=lambda a: (int(a["cfbFanoutPriority"]), -float(a["weight"]), str(a["actionId"]))),
        "hyperedges": {k: list(v) for k, v in hg.edge_members.items()},
        "reverseIndexes": {
            "actionToRequirements": reverse_action_req,
            "requirementToActions": dict(reverse_req_action),
            "actionToOffers": reverse_action_offer,
        },
        "reusedEvidenceLookup": bool(evidence is not None),
        "cfbFanoutLaw": "event/team before player; one action populates every board-relevant entity from that source",
    }
    payload["contentHash"] = content_hash({k: v for k, v in payload.items() if k != "contentHash"})
    return payload


def schedule_acquisition_actions(
    action_doc: dict[str, Any],
    *,
    max_actions: int = 25,
    max_dependent_offers: int = 500,
    telemetry: AlgorithmTelemetry | None = None,
) -> dict[str, Any]:
    """Live CELF selector with set-cover + constrained batch packing."""
    tel = telemetry or AlgorithmTelemetry()
    actions = {str(a["actionId"]): dict(a) for a in (action_doc.get("actions") or [])}
    if not actions:
        empty = {
            "schema": "pillars_dcm.acquisition_schedule.v1",
            "selectedActionIds": [],
            "packedBatches": [],
            "setCoverActionIds": [],
            "algorithmIds": ["ALG-SCHED-001", "ALG-SCHED-002", "ALG-SCHED-003", "ALG-SCHED-004", "ALG-SEARCH-019"],
        }
        empty["contentHash"] = content_hash(empty)
        return empty

    universe: list[str] = []
    cover_sets: dict[str, list[str]] = {}
    for aid, act in actions.items():
        cover_sets[aid] = list(act.get("requirementIds") or [])
        universe.extend(cover_sets[aid])
    universe = list(dict.fromkeys(universe))
    weights = {aid: float(act.get("cost") or 1.0) for aid, act in actions.items()}
    set_cover_ids = cover_actions(universe, cover_sets, weights)
    tel.record("ALG-SEARCH-019", problem_class="SET_COVER", producer="dcm.research.acquisition.schedule_acquisition_actions", consumer="dcm.research.batch", count=len(set_cover_ids) or 1, downstream_used=True)
    tel.record("ALG-SCHED-002", problem_class="RESEARCH_SCHEDULE", producer="dcm.research.acquisition.schedule_acquisition_actions", consumer="dcm.research.batch", downstream_used=True)

    covered: set[str] = set()

    def gain_fn(aid: str, selected: frozenset[str]) -> float:
        act = actions[aid]
        fresh = [rid for rid in act.get("requirementIds") or [] if rid not in covered]
        if selected:
            for other in selected:
                fresh = [rid for rid in fresh if rid not in (actions[other].get("requirementIds") or [])]
        if not fresh:
            return 0.0
        return float(act.get("expectedGain") or 0.0) * (len(fresh) / max(1, len(act.get("requirementIds") or [1])))

    def cost_fn(aid: str) -> float:
        return max(1e-6, float(actions[aid].get("cost") or 1.0))

    scheduler = LazyGreedyScheduler(gain_fn, cost_fn)
    celf_ids = scheduler.run(list(actions), k=max_actions)
    tel.record("ALG-SCHED-001", problem_class="RESEARCH_SCHEDULE", producer="dcm.algorithms.scheduling.LazyGreedyScheduler", consumer="dcm.research.acquisition.schedule_acquisition_actions", count=len(celf_ids) or 1, downstream_used=True)
    tel.record("ALG-SEARCH-020", problem_class="SUBMODULAR", producer="dcm.research.acquisition.schedule_acquisition_actions", consumer="dcm.research.batch", downstream_used=True)

    # Recompute covered after CELF; prefer CELF order as live selector.
    # SPORT/COMPETITION do not consume the unique-offer budget.
    selected: list[str] = []
    covered_offers: set[str] = set()
    for aid in celf_ids:
        act = actions[aid]
        scope = str(act.get("scope") or "")
        oids = [str(x) for x in (act.get("offerIds") or []) if x]
        budgeted = scope not in {"SPORT", "COMPETITION"}
        new_offers = [oid for oid in oids if oid not in covered_offers] if budgeted else []
        if selected and budgeted and (len(covered_offers) + len(new_offers) > max_dependent_offers):
            continue
        selected.append(aid)
        if budgeted:
            covered_offers.update(new_offers)
        covered.update(act.get("requirementIds") or [])
        if len(selected) >= max_actions:
            break
    offer_budget = len(covered_offers)

    values = {aid: float(actions[aid].get("expectedGain") or 0.0) for aid in selected}
    packed = greedy_value_density_pack(selected, values, weights, capacity=float(max_actions))
    tel.record("ALG-SCHED-003", problem_class="BATCH_PACK", producer="dcm.algorithms.scheduling.greedy_value_density_pack", consumer="dcm.research.batch", downstream_used=True)
    sizes = {aid: float(max(1, actions[aid].get("dependentOfferCount") or 1)) for aid in packed}
    bins = first_fit_decreasing(packed, sizes, bin_capacity=float(max(1, max_dependent_offers)), max_bins=max(1, max_actions))
    tel.record("ALG-SCHED-004", problem_class="BATCH_PACK", producer="dcm.algorithms.scheduling.first_fit_decreasing", consumer="dcm.research.batch", downstream_used=True)

    by_event: dict[str, list[str]] = defaultdict(list)
    for aid in packed:
        by_event[str(actions[aid].get("eventId") or "UNGROUPED")].append(aid)
    batches = []
    for event_id, aids in sorted(by_event.items(), key=lambda kv: (-sum(float(actions[a].get("weight") or 0) for a in kv[1]), kv[0])):
        tasks = [actions[a] for a in aids]
        batches.append(
            {
                "eventId": event_id,
                "actionIds": aids,
                "entityCount": len(aids),
                "dependentOfferCount": sum(int(actions[a].get("dependentOfferCount") or 0) for a in aids),
                "tasks": [
                    {
                        "actionId": t["actionId"],
                        "requestIds": t["requirementIds"],
                        "scope": t["scope"],
                        "scopeId": t["scopeId"],
                        "sourceFamily": t["sourceFamily"],
                        "dependentOfferCount": t["dependentOfferCount"],
                        "weight": t["weight"],
                        "researchOnce": True,
                    }
                    for t in tasks
                ],
            }
        )

    body = {
        "schema": "pillars_dcm.acquisition_schedule.v1",
        "liveSelector": "ALG-SCHED-001",
        "algorithmIds": ["ALG-SCHED-001", "ALG-SCHED-002", "ALG-SCHED-003", "ALG-SCHED-004", "ALG-SEARCH-019", "ALG-SEARCH-020"],
        "selectedActionIds": packed,
        "celfActionIds": celf_ids,
        "setCoverActionIds": set_cover_ids,
        "packedBatches": batches,
        "ffdBins": bins,
        "selectedCount": len(packed),
        "unresolvedActionCount": len(actions),
        "dependentOfferBudgetUsed": offer_budget,
        "maxActions": max_actions,
        "maxDependentOffers": max_dependent_offers,
        "stopWhen": "coverage closed or additional research cannot change PLAYABLE/Top25 enough to justify cost",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
