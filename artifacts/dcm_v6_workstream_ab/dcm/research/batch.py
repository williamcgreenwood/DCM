"""Event-first iterative host research batching.

Score = fanout × information_importance × freshness_need × uncertainty_reduction / cost

Reusable entities are researched once. Unresolved work is grouped by Event.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dcm.research.requests import FRESHNESS_NEED, INFO_IMPORTANCE
from dcm.research.classify_runtime import classify_requests
from dcm.research.research_store import ResearchStore
from dcm.research.scopes import CANONICAL_SCOPES, SCOPE_RANK, canonical_scope
from dcm.research.source_catalog import estimated_cost

UNCERTAINTY_BY_DELTA = {
    "REUSE_VALID": 0.0,
    "NOT_APPLICABLE": 0.0,
    "APPEND_MISSING_HISTORY": 0.7,
    "REFRESH_STALE": 0.55,
    "REFRESH_CURRENT_CONTEXT": 0.8,
    "NEW_OPPONENT_REQUIRED": 0.85,
    "ROLE_EPOCH_CHANGED": 0.9,
    "TEAM_CHANGED": 0.95,
    "DEFINITION_CHANGED": 0.7,
    "CONTRADICTED_REVERIFY": 1.0,
    "REPLACE_INVALIDATED": 1.0,
    "NEW_ENTITY_FULL_RESEARCH": 1.0,
    "RESEARCH_NEW": 1.0,
}

BATCH_SCOPE_ORDER = CANONICAL_SCOPES


def scheduler_score(
    request: dict[str, Any],
    *,
    uncertainty_reduction: float = 1.0,
    cost: float = 1.0,
) -> float:
    scope = canonical_scope(str(request.get("scope") or ""))
    fanout = max(1, int(request.get("dependent_prop_count") or request.get("dependentOfferCount") or 1))
    importance = float(INFO_IMPORTANCE.get(scope, INFO_IMPORTANCE.get(str(request.get("scope") or ""), 0.1)))
    freshness = float(FRESHNESS_NEED.get(scope, FRESHNESS_NEED.get(str(request.get("scope") or ""), 0.1)))
    return (fanout * importance * freshness * float(uncertainty_reduction)) / max(float(cost), 1e-6)


def _event_id_of(request: dict[str, Any]) -> str:
    extra = request.get("context") if isinstance(request.get("context"), dict) else request
    return str(
        request.get("eventId")
        or extra.get("eventId")
        or extra.get("event_id")
        or (request.get("scope_id") if canonical_scope(str(request.get("scope") or "")) in {"EVENT", "ENVIRONMENT"} else "")
        or ""
    )


def build_next_research_batch(
    requests: list[dict[str, Any]],
    *,
    coverage: dict[str, Any] | None = None,
    store: ResearchStore | None = None,
    max_entities: int = 25,
    max_dependent_offers: int = 500,
    catalog_source_id: str = "generic_web_search",
) -> dict[str, Any]:
    classified = classify_requests(list(requests or []), store)
    coverage_by_id = {
        str(row.get("requestId") or ""): row
        for row in ((coverage or {}).get("requests") or [])
        if isinstance(row, dict)
    }
    cost = estimated_cost(catalog_source_id)
    scored: list[dict[str, Any]] = []
    for rec in classified:
        req_id = str(rec.get("request_id") or rec.get("requestId") or "")
        cov = coverage_by_id.get(req_id) or {}
        complete = bool(cov.get("complete")) and rec.get("deltaClass") == "REUSE_VALID"
        if complete or rec.get("deltaClass") == "REUSE_VALID":
            rec = dict(rec)
            rec["acquire"] = False
            rec["uncertaintyReduction"] = 0.0
            rec["schedulerScore"] = 0.0
            rec["knownMissing"] = cov.get("missing") or []
            rec["coverageComplete"] = bool(cov.get("complete"))
            scored.append(rec)
            continue
        delta = str(rec.get("deltaClass") or "RESEARCH_NEW")
        u = float(UNCERTAINTY_BY_DELTA.get(delta, 1.0))
        rec = dict(rec)
        rec["uncertaintyReduction"] = u
        rec["estimatedCost"] = cost
        rec["schedulerScore"] = round(scheduler_score(rec, uncertainty_reduction=u, cost=cost), 6)
        rec["knownMissing"] = cov.get("missing") or []
        rec["coverageComplete"] = bool(cov.get("complete"))
        rec["eventId"] = _event_id_of(rec)
        scored.append(rec)

    acquire = [r for r in scored if r.get("acquire")]
    acquire.sort(
        key=lambda r: (
            SCOPE_RANK.get(canonical_scope(str(r.get("scope") or "")), 99),
            -float(r.get("schedulerScore") or 0.0),
            str(r.get("eventId") or ""),
            str(r.get("scope_id") or ""),
        )
    )

    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ungrouped: list[dict[str, Any]] = []
    for rec in acquire:
        eid = str(rec.get("eventId") or "")
        if eid:
            by_event[eid].append(rec)
        else:
            ungrouped.append(rec)

    batches: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    offer_budget = 0
    for event_id, group in sorted(by_event.items(), key=lambda kv: -sum(float(r.get("schedulerScore") or 0) for r in kv[1])):
        remaining = max_entities - len(selected)
        if remaining <= 0:
            break
        group_sorted = sorted(
            group,
            key=lambda r: (
                SCOPE_RANK.get(canonical_scope(str(r.get("scope") or "")), 99),
                -float(r.get("schedulerScore") or 0.0),
            ),
        )
        take = group_sorted[:remaining]
        dep = sum(int(r.get("dependent_prop_count") or 0) for r in take)
        if offer_budget and offer_budget + dep > max_dependent_offers:
            continue
        selected.extend(take)
        offer_budget += dep
        batches.append(
            {
                "eventId": event_id,
                "entityCount": len(take),
                "dependentOfferCount": dep,
                "tasks": [
                    {
                        "requestId": r.get("request_id"),
                        "scope": canonical_scope(str(r.get("scope") or "")),
                        "scopeId": r.get("scope_id"),
                        "need": r.get("need"),
                        "deltaClass": r.get("deltaClass"),
                        "schedulerScore": r.get("schedulerScore"),
                        "dependentPropCount": r.get("dependent_prop_count"),
                        "knownMissing": r.get("knownMissing") or [],
                        "researchOnce": True,
                    }
                    for r in take
                ],
            }
        )
        if len(selected) >= max_entities or offer_budget >= max_dependent_offers:
            break

    if len(selected) < max_entities:
        for rec in ungrouped:
            if len(selected) >= max_entities:
                break
            selected.append(rec)

    reused = [r for r in scored if not r.get("acquire")]
    return {
        "schema": "pillars_dcm.host_research_batch.v1",
        "priorityFormula": (
            "fanout × information_importance × freshness_need × "
            "uncertainty_reduction / estimated_acquisition_cost"
        ),
        "batching": "event_first",
        "maxEntities": int(max_entities),
        "maxDependentOffers": int(max_dependent_offers),
        "unresolvedCount": len(acquire),
        "selectedCount": len(selected),
        "reusedCount": len(reused),
        "eventBatchCount": len(batches),
        "dependentOfferBudgetUsed": offer_budget,
        "stopWhen": "coverage closed or additional research cannot change production eligibility enough to justify cost",
        "hostInstruction": (
            "Research reusable entities once. Do not invent hashes, reliability, "
            "or internal request IDs. Return simple host observations."
        ),
        "batches": batches,
        "tasks": [
            {
                "requestId": r.get("request_id"),
                "scope": canonical_scope(str(r.get("scope") or "")),
                "scopeId": r.get("scope_id"),
                "need": r.get("need"),
                "deltaClass": r.get("deltaClass"),
                "schedulerScore": r.get("schedulerScore"),
                "dependentPropCount": r.get("dependent_prop_count"),
                "eventId": r.get("eventId"),
                "knownMissing": r.get("knownMissing") or [],
            }
            for r in selected
        ],
        "reused": [
            {
                "requestId": r.get("request_id"),
                "scope": canonical_scope(str(r.get("scope") or "")),
                "scopeId": r.get("scope_id"),
                "deltaClass": r.get("deltaClass"),
            }
            for r in reused[:200]
        ],
    }
