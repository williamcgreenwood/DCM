"""ResearchPopulationManifest: unique entities after classify/plan_research.

Fan-out priority = dependentOfferCount × information_importance.
Account/classify path always emits this so the host researches players once.
"""
from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.requests import INFO_IMPORTANCE, SCOPE_ORDER, plan_research


def _entity_rows(requests: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    rows = []
    importance = float(INFO_IMPORTANCE.get(scope, 0.1))
    for rec in requests:
        if rec.get("scope") != scope:
            continue
        dep = int(rec.get("dependent_prop_count") or 0)
        rows.append(
            {
                "scope": scope,
                "scopeId": rec.get("scope_id"),
                "requestId": rec.get("request_id"),
                "dependentOfferCount": dep,
                "importance": importance,
                "fanOutPriority": round(dep * importance, 6),
                "priorityScore": rec.get("priority_score"),
                "league": rec.get("league"),
                "sportFamily": rec.get("sportFamily"),
                "name": rec.get("name"),
                "market": rec.get("market"),
                "markets": rec.get("markets"),
                "definitionId": rec.get("definition_id"),
                "label": rec.get("label"),
            }
        )
    rows.sort(key=lambda r: (-float(r.get("fanOutPriority") or 0.0), str(r.get("scopeId") or "")))
    return rows


def build_research_population_manifest(
    board_rows: list[dict[str, Any]] | None = None,
    *,
    planned: dict[str, Any] | None = None,
    cutoff: str = "",
    research_shadow: bool = False,
) -> dict[str, Any]:
    if planned is None:
        planned = plan_research(list(board_rows or []), cutoff, research_shadow=research_shadow)
    requests = list(planned.get("requests") or [])
    entities = {
        "events": _entity_rows(requests, "EVENT"),
        "teams": _entity_rows(requests, "TEAM"),
        "players": _entity_rows(requests, "PLAYER"),
        "marketDefinitions": _entity_rows(requests, "MARKET_DEFINITION"),
        "offers": _entity_rows(requests, "OFFER"),
        "sports": _entity_rows(requests, "SPORT"),
    }
    fan_out = []
    for scope in SCOPE_ORDER:
        key = {
            "SPORT": "sports",
            "EVENT": "events",
            "TEAM": "teams",
            "PLAYER": "players",
            "MARKET_DEFINITION": "marketDefinitions",
            "OFFER": "offers",
        }.get(scope)
        if key:
            fan_out.extend(entities[key])
    unique_scopes = planned.get("unique_scopes") or {}
    body = {
        "schema": "pillars_dcm.research_population_manifest.v1",
        "forecastCutoff": cutoff or (requests[0].get("forecast_cutoff") if requests else ""),
        "researchShadow": bool(planned.get("research_shadow")),
        "eligiblePropCount": int(planned.get("eligible_prop_count") or 0),
        "skipped": dict(planned.get("skipped") or {}),
        "uniqueCounts": {scope: int(unique_scopes.get(scope) or 0) for scope in SCOPE_ORDER},
        "entities": entities,
        "fanOut": fan_out,
        "priorityFormula": "dependentOfferCount × information_importance",
        "reuseRule": "N offers for one player → 1 PLAYER entity / 1 PlayerOfferSet, not N research subjects.",
        "legacyMarketEmitted": bool(planned.get("legacy_market_emitted")),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
