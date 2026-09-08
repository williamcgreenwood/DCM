"""Sport-neutral fan-out blueprint consumed by the Work/Codex batch prompt."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash
from dcm.research.search_query import compile_query


BLUEPRINT_SCHEMA = "pillars_dcm.search_blueprint.v1"
SCOPE_ORDER = ("SPORT", "COMPETITION", "EVENT", "ENVIRONMENT", "AFFILIATION", "COUNTERPARTY", "SUBJECT", "MARKET_DEFINITION", "OFFER")


def compile_action_blueprint(action: Mapping[str, Any], *, request: Mapping[str, Any] | None = None, cutoff: str | None = None) -> dict[str, Any]:
    query = compile_query(action, request=request, cutoff=cutoff)
    scope = str(action.get("scope") or (request or {}).get("scope") or "SUBJECT").upper()
    dependent = int(action.get("dependentOfferCount") or (request or {}).get("dependent_prop_count") or 0)
    return {
        "actionId": str(action.get("actionId") or "") or None,
        "scope": scope,
        "scopeId": str(action.get("scopeId") or (request or {}).get("scope_id") or "") or None,
        "researchOnce": True,
        "dependentOfferCount": dependent,
        "queryPlan": query,
        "requiredFieldPolicy": "all_required_fields_or_machine_failure",
        "temporalPolicy": "published_or_valid_time_must_not_exceed_forecast_cutoff",
        "fanoutPolicy": "one_valid_observation_may_cover_all_dependent_offers_at_same_scope",
    }


def build_search_blueprint(
    *,
    actions: Iterable[Mapping[str, Any]] = (),
    requests: Iterable[Mapping[str, Any]] = (),
    cutoff: str | None = None,
    breakdown: Mapping[str, Any] | None = None,
    max_actions: int = 25,
    max_dependent_offers: int = 500,
) -> dict[str, Any]:
    requests_by_id = {str(req.get("request_id") or req.get("requestId") or ""): req for req in requests if isinstance(req, Mapping)}
    compiled = []
    for action in sorted((dict(a) for a in actions if isinstance(a, Mapping)), key=lambda a: str(a.get("actionId") or "")):
        request = requests_by_id.get(str(action.get("requestId") or ""))
        if request is None:
            # AcquisitionActions are fan-out nodes and normally carry
            # requirementIds rather than one requestId.  Resolve the first
            # canonical requirement deterministically so the blueprint still
            # contains the exact required fields for grouped searches.
            for requirement_id in sorted(str(value) for value in (action.get("requirementIds") or [])):
                request = requests_by_id.get(requirement_id)
                if request is not None:
                    break
        compiled.append(compile_action_blueprint(action, request=request, cutoff=cutoff))
    demand = (breakdown or {}).get("research_demand") or (breakdown or {}).get("researchDemand") or {}
    predicted = sum(int(row.get("dependentOfferCount") or 0) for row in compiled)
    verified = int(demand.get("offerRowCount") or 0)
    body: dict[str, Any] = {
        "schema": BLUEPRINT_SCHEMA,
        "version": 1,
        "sportNeutral": True,
        "hierarchy": list(SCOPE_ORDER),
        "orderingRule": "event/team/opponent before participant; definition before offer; exact scope identity before approximate retrieval",
        "actions": compiled,
        "predictedDependentOfferCount": predicted,
        "verifiedHarOfferRowCount": verified,
        "fanoutRatio": round(predicted / max(1, len(compiled)), 6),
        "fanoutClaimPolicy": "predicted is not verified; no extrapolation from a pilot to all sports",
        "batchBudget": {
            "maxActions": int(max_actions),
            "maxDependentOffers": int(max_dependent_offers),
            "maxSearchCallsPerAction": 3,
            "maxSourcesPerAction": 8,
        },
        "algorithmIds": ["ALG-GROUP-006", "ALG-SEARCH-001", "ALG-SEARCH-013", "ALG-SEARCH-014", "ALG-SCHED-001", "ALG-SCHED-002", "ALG-SCHED-003", "ALG-SCHED-004"],
        "failurePolicy": {"missingField": "REQUIRED_FIELD_MISSING", "unresolvedEntity": "ENTITY_NOT_RESOLVED", "cutoff": "CUTOFF_VIOLATION", "terminalFailureExcluded": True},
    }
    body["blueprintHash"] = content_hash(body)
    return body


__all__ = ["BLUEPRINT_SCHEMA", "SCOPE_ORDER", "build_search_blueprint", "compile_action_blueprint"]
