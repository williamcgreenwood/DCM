"""ResearchPopulationManifest.

V2 is the canonical sport-neutral population:
Sport/Competition/Event/Affiliation/Subject/Counterparty/Environment/
MarketDefinition/Offer.

The legacy request-scope view remains available only to keep existing provider
adapters operational during migration.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from dcm.contracts.hashes import content_hash
from dcm.research.classify import market_definition_id
from dcm.research.requests import INFO_IMPORTANCE, SCOPE_ORDER, plan_research
from dcm.research.subject_offer_set import canonical_subject_fields, build_subject_offer_sets


UNIVERSAL_IMPORTANCE = {
    "SPORT": 1.00,
    "COMPETITION": 0.95,
    "EVENT": 0.95,
    "AFFILIATION": 0.85,
    "SUBJECT": 0.75,
    "COUNTERPARTY": 0.85,
    "ENVIRONMENT": 0.80,
    "MARKET_DEFINITION": 0.70,
    "OFFER": 0.40,
}
UNIVERSAL_FRESHNESS = {
    "SPORT": 0.40,
    "COMPETITION": 0.50,
    "EVENT": 1.00,
    "AFFILIATION": 0.85,
    "SUBJECT": 1.00,
    "COUNTERPARTY": 0.85,
    "ENVIRONMENT": 1.00,
    "MARKET_DEFINITION": 0.30,
    "OFFER": 0.90,
}


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


def build_legacy_research_population_manifest(
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
        "reuseRule": "Legacy compatibility planner: TEAM/PLAYER scopes map into universal Affiliation/Counterparty/Subject entities.",
        "legacyMarketEmitted": bool(planned.get("legacy_market_emitted")),
        "compatibilityOnly": True,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def _grouped_entity_rows(
    rows: list[dict[str, Any]],
    *,
    entity_type: str,
    key_fn: Callable[[dict[str, Any], dict[str, Any]], list[str]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        fields = canonical_subject_fields(row)
        for key in key_fn(row, fields):
            key = str(key or "")
            if not key:
                continue
            groups[key].append(row)
            metadata.setdefault(
                key,
                {
                    "sportId": fields.get("sportId"),
                    "competitionId": fields.get("competitionId"),
                    "eventId": fields.get("eventId"),
                    "subjectId": fields.get("subjectId"),
                    "subjectType": fields.get("subjectType"),
                    "affiliationId": fields.get("affiliationId"),
                },
            )

    importance = float(UNIVERSAL_IMPORTANCE[entity_type])
    freshness = float(UNIVERSAL_FRESHNESS[entity_type])
    out: list[dict[str, Any]] = []
    for entity_id, dependent_rows in groups.items():
        dep = len({str(r.get("projectionId") or "") for r in dependent_rows})
        rec = {
            "entityType": entity_type,
            "entityId": entity_id,
            "dependentOfferCount": dep,
            "informationImportance": importance,
            "freshnessNeed": freshness,
            "fanOutPriority": round(dep * importance * freshness, 6),
            **metadata.get(entity_id, {}),
        }
        out.append(rec)
    out.sort(key=lambda r: (-float(r["fanOutPriority"]), str(r["entityId"])))
    return out


def build_universal_research_population_manifest(
    board_rows: list[dict[str, Any]] | None = None,
    *,
    planned: dict[str, Any] | None = None,
    cutoff: str = "",
    research_shadow: bool = False,
) -> dict[str, Any]:
    rows = list(board_rows or [])
    if planned is None:
        planned = plan_research(rows, cutoff, research_shadow=research_shadow)
    eligible = [r for r in (planned.get("eligible") or []) if isinstance(r, dict)]

    entities = {
        "sports": _grouped_entity_rows(
            eligible, entity_type="SPORT", key_fn=lambda _r, f: [f["sportId"]]
        ),
        "competitions": _grouped_entity_rows(
            eligible,
            entity_type="COMPETITION",
            key_fn=lambda _r, f: [f'{f["sportId"]}:{f["competitionId"]}'],
        ),
        "events": _grouped_entity_rows(
            eligible, entity_type="EVENT", key_fn=lambda _r, f: [f["eventId"]]
        ),
        "affiliations": _grouped_entity_rows(
            eligible, entity_type="AFFILIATION", key_fn=lambda _r, f: [f["affiliationId"]]
        ),
        "subjects": _grouped_entity_rows(
            eligible, entity_type="SUBJECT", key_fn=lambda _r, f: [f["subjectId"]]
        ),
        "counterparties": _grouped_entity_rows(
            eligible, entity_type="COUNTERPARTY", key_fn=lambda _r, f: list(f["counterpartyIds"])
        ),
        "environments": _grouped_entity_rows(
            eligible, entity_type="ENVIRONMENT", key_fn=lambda _r, f: [f["environmentId"]]
        ),
        "marketDefinitions": _grouped_entity_rows(
            eligible,
            entity_type="MARKET_DEFINITION",
            key_fn=lambda r, _f: [market_definition_id(r)],
        ),
        "offers": _grouped_entity_rows(
            eligible,
            entity_type="OFFER",
            key_fn=lambda r, _f: [str(r.get("projectionId") or "")],
        ),
    }
    order = (
        "sports",
        "competitions",
        "events",
        "affiliations",
        "subjects",
        "counterparties",
        "environments",
        "marketDefinitions",
        "offers",
    )
    fan_out = [item for key in order for item in entities[key]]
    counts = {key: len(entities[key]) for key in order}
    subject_sets = build_subject_offer_sets(eligible)
    body = {
        "schema": "pillars_dcm.research_population_manifest.v2",
        "canonical": True,
        "forecastCutoff": cutoff,
        "researchShadow": bool(planned.get("research_shadow")),
        "eligibleOfferCount": int(planned.get("eligible_prop_count") or len(eligible)),
        "subjectOfferSetCount": len(subject_sets),
        "skipped": dict(planned.get("skipped") or {}),
        "uniqueCounts": counts,
        "entities": entities,
        "fanOut": fan_out,
        "priorityFormula": "dependentOfferCount × informationImportance × freshnessNeed",
        "reuseRule": "Research reusable universal entities once; SubjectOfferSet fans one subject+event packet into every dependent offer.",
        "legacyPlannerScopes": list(SCOPE_ORDER),
        "legacyPlannerCompatibility": True,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def build_research_population_manifest(
    board_rows: list[dict[str, Any]] | None = None,
    *,
    planned: dict[str, Any] | None = None,
    cutoff: str = "",
    research_shadow: bool = False,
) -> dict[str, Any]:
    """Canonical public builder now returns the universal V2 manifest."""
    return build_universal_research_population_manifest(
        board_rows,
        planned=planned,
        cutoff=cutoff,
        research_shadow=research_shadow,
    )
