"""Hierarchical research requests after pre-research classification.

HAR → account → identity → classify → then only model-eligible (and opt-in
shadow) rows receive deep research. Shared SPORT/COMPETITION/EVENT/
AFFILIATION/COUNTERPARTY/ENVIRONMENT/MARKET_DEFINITION entities are emitted
once and fan-out prioritized.

Canonical scopes are universal. PLAYER/TEAM are adapter aliases only and are
not emitted by this planner. Legacy MARKET is not emitted.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.classify import classify_rows, market_definition_id
from dcm.research.scopes import CANONICAL_SCOPES, SCOPE_ORDER, SCOPE_RANK
from dcm.sports.common.plugin import selection_state

# information_importance × freshness_need by canonical scope (doctrine hierarchy, not alpha)
INFO_IMPORTANCE = {
    "SPORT": 1.00,
    "COMPETITION": 0.98,
    "EVENT": 0.95,
    "ENVIRONMENT": 0.90,
    "AFFILIATION": 0.85,
    "COUNTERPARTY": 0.85,
    "SUBJECT": 0.75,
    "MARKET_DEFINITION": 0.70,
    "OFFER": 0.40,
    # Adapter aliases (not emitted here; used by scoring/lookups)
    "TEAM": 0.85,
    "PLAYER": 0.75,
}
FRESHNESS_NEED = {
    "SPORT": 0.40,
    "COMPETITION": 0.45,
    "EVENT": 1.00,
    "ENVIRONMENT": 0.95,
    "AFFILIATION": 0.85,
    "COUNTERPARTY": 0.90,
    "SUBJECT": 1.00,
    "MARKET_DEFINITION": 0.30,
    "OFFER": 0.90,
    "TEAM": 0.85,
    "PLAYER": 1.00,
}
CAP_WEIGHT = {
    "PRODUCTION_SUPPORTED": 1.00,
    "SHADOW_SUPPORTED": 0.35,
    "RESEARCH_ONLY": 0.25,
    "UNSUPPORTED_FAIL_CLOSED": 0.00,
}


def _cap_weight_for_rows(rows: list[dict[str, Any]]) -> float:
    weights = []
    for row in rows:
        cap = selection_state(
            str(row.get("sportFamily") or ""),
            str(row.get("league") or ""),
            str(row.get("market") or ""),
        )
        weights.append(CAP_WEIGHT.get(cap, 0.0))
    return max(weights) if weights else 0.0


def _priority_score(scope: str, rows: list[dict[str, Any]]) -> float:
    n = max(1, len({str(r.get("projectionId") or "") for r in rows}))
    return (
        n
        * _cap_weight_for_rows(rows)
        * float(INFO_IMPORTANCE.get(scope, 0.1))
        * float(FRESHNESS_NEED.get(scope, 0.1))
    )


def _add(
    reqs: dict[str, dict],
    *,
    scope: str,
    scope_id: str,
    need: str,
    cutoff: str,
    extra: dict[str, Any],
    dependents: list[dict[str, Any]],
) -> dict[str, Any]:
    rec = {
        "scope": scope,
        "scope_id": scope_id,
        "need": need,
        "forecast_cutoff": cutoff,
        **extra,
    }
    rec["dependent_prop_count"] = len({str(r.get("projectionId") or "") for r in dependents})
    rec["priority_score"] = round(_priority_score(scope, dependents), 6)
    rec["hierarchy_rank"] = SCOPE_RANK.get(scope, 99)
    rec["request_id"] = "REQ_" + content_hash(
        {k: rec[k] for k in ("scope", "scope_id", "need", "forecast_cutoff") if k in rec}
    )[:16]
    reqs[rec["request_id"]] = rec
    return rec


def _graph_rows(requests: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    return [
        {
            "scopeId": r["scope_id"],
            "requestId": r["request_id"],
            "dependentPropCount": r["dependent_prop_count"],
            "priorityScore": r["priority_score"],
        }
        for r in requests
        if r["scope"] == scope
    ]


def plan_research(
    rows: list[dict[str, Any]],
    cutoff: str,
    *,
    research_shadow: bool = False,
) -> dict[str, Any]:
    classified = classify_rows(rows, research_shadow=research_shadow)
    eligible = classified["eligible"]
    reqs: dict[str, dict] = {}

    by_sport: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_competition: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_event: dict[str, list[dict]] = defaultdict(list)
    by_affiliation: dict[str, list[dict]] = defaultdict(list)
    by_counterparty: dict[str, list[dict]] = defaultdict(list)
    by_subject: dict[str, list[dict]] = defaultdict(list)
    by_environment: dict[str, list[dict]] = defaultdict(list)
    by_def: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        family = str(row.get("sportFamily") or "")
        league = str(row.get("league") or "")
        by_sport[(family, league)].append(row)
        by_competition[(family, league)].append(row)
        event_id = str(row.get("eventId") or "")
        by_event[event_id].append(row)
        if event_id:
            by_environment[f"env:{event_id}"].append(row)
        aff_key = str(row.get("teamId") or row.get("team") or row.get("affiliationId") or "")
        if aff_key:
            by_affiliation[aff_key].append(row)
        opp_key = str(row.get("opponentId") or row.get("opponent") or row.get("counterpartyId") or "")
        if opp_key and opp_key != aff_key:
            by_counterparty[opp_key].append(row)
        by_subject[str(row.get("playerId") or row.get("subjectId") or "")].append(row)
        by_def[market_definition_id(row)].append(row)

    for (family, league), group in by_sport.items():
        _add(
            reqs,
            scope="SPORT",
            scope_id=f"{family}:{league}",
            need="rules_calendar_distribution",
            cutoff=cutoff,
            extra={"league": league, "sportFamily": family, "sportId": family, "competitionId": league},
            dependents=group,
        )

    for (family, league), group in by_competition.items():
        if not family and not league:
            continue
        _add(
            reqs,
            scope="COMPETITION",
            scope_id=f"{family}:{league}",
            need="competition_context",
            cutoff=cutoff,
            extra={"league": league, "sportFamily": family, "sportId": family, "competitionId": league},
            dependents=group,
        )

    for event_id, group in by_event.items():
        if not event_id:
            continue
        sample = group[0]
        _add(
            reqs,
            scope="EVENT",
            scope_id=event_id,
            need="start_venue_starters_environment",
            cutoff=cutoff,
            extra={
                "league": sample.get("league"),
                "label": sample.get("eventLabel"),
                "eventId": event_id,
                "sportFamily": sample.get("sportFamily"),
            },
            dependents=group,
        )

    for env_id, group in by_environment.items():
        if not env_id:
            continue
        sample = group[0]
        _add(
            reqs,
            scope="ENVIRONMENT",
            scope_id=env_id,
            need="weather_surface_venue_effects",
            cutoff=cutoff,
            extra={
                "league": sample.get("league"),
                "eventId": sample.get("eventId"),
                "sportFamily": sample.get("sportFamily"),
            },
            dependents=group,
        )

    for aff_id, group in by_affiliation.items():
        if not aff_id:
            continue
        sample = group[0]
        _add(
            reqs,
            scope="AFFILIATION",
            scope_id=aff_id,
            need="role_pace_matchup",
            cutoff=cutoff,
            extra={
                "league": sample.get("league"),
                "sportFamily": sample.get("sportFamily"),
                "eventId": sample.get("eventId"),
                "affiliationId": aff_id,
            },
            dependents=group,
        )

    for opp_id, group in by_counterparty.items():
        if not opp_id:
            continue
        sample = group[0]
        _add(
            reqs,
            scope="COUNTERPARTY",
            scope_id=opp_id,
            need="suppression_allowance_matchup",
            cutoff=cutoff,
            extra={
                "league": sample.get("league"),
                "sportFamily": sample.get("sportFamily"),
                "eventId": sample.get("eventId"),
                "counterpartyId": opp_id,
                "affiliationId": sample.get("teamId") or sample.get("team"),
            },
            dependents=group,
        )

    for subject_id, group in by_subject.items():
        if not subject_id:
            continue
        sample = group[0]
        markets = sorted({str(r.get("market") or "") for r in group if r.get("market")})
        _add(
            reqs,
            scope="SUBJECT",
            scope_id=subject_id,
            need="status_role_logs_opportunity_efficiency",
            cutoff=cutoff,
            extra={
                "name": sample.get("playerName") or sample.get("subjectName"),
                "league": sample.get("league"),
                "sportFamily": sample.get("sportFamily"),
                "markets": markets,
                "eventId": sample.get("eventId"),
                "affiliationId": sample.get("teamId") or sample.get("team"),
                "opponentId": sample.get("opponentId") or sample.get("opponent"),
                "subjectType": sample.get("subjectType") or "PLAYER",
            },
            dependents=group,
        )

    for def_id, group in by_def.items():
        sample = group[0]
        _add(
            reqs,
            scope="MARKET_DEFINITION",
            scope_id=def_id,
            need="exact_stat_definition",
            cutoff=cutoff,
            extra={
                "market": sample.get("market"),
                "league": sample.get("league"),
                "boardId": sample.get("boardId"),
            },
            dependents=group,
        )

    for row in eligible:
        def_id = market_definition_id(row)
        _add(
            reqs,
            scope="OFFER",
            scope_id=str(row["projectionId"]),
            need="line_sides_modifier",
            cutoff=cutoff,
            extra={
                "market": row.get("market"),
                "line": row.get("line"),
                "playerId": row.get("playerId"),
                "subjectId": row.get("playerId") or row.get("subjectId"),
                "eventId": row.get("eventId"),
                "definition_id": def_id,
            },
            dependents=[row],
        )

    requests = sorted(
        reqs.values(),
        key=lambda r: (
            int(r["hierarchy_rank"] if r.get("hierarchy_rank") is not None else 99),
            -float(r.get("priority_score") or 0.0),
            str(r.get("scope_id") or ""),
            str(r.get("request_id") or ""),
        ),
    )

    unique_scopes = {scope: 0 for scope in SCOPE_ORDER}
    for rec in requests:
        unique_scopes[str(rec["scope"])] = unique_scopes.get(str(rec["scope"]), 0) + 1

    affiliations = _graph_rows(requests, "AFFILIATION")
    counterparties = _graph_rows(requests, "COUNTERPARTY")
    subjects = _graph_rows(requests, "SUBJECT")
    entity_graph = {
        "sports": _graph_rows(requests, "SPORT"),
        "competitions": _graph_rows(requests, "COMPETITION"),
        "events": _graph_rows(requests, "EVENT"),
        "environments": _graph_rows(requests, "ENVIRONMENT"),
        "affiliations": affiliations,
        "subjects": subjects,
        "counterparties": counterparties,
        "marketDefinitions": _graph_rows(requests, "MARKET_DEFINITION"),
        "offers": [
            {
                "scopeId": r["scope_id"],
                "requestId": r["request_id"],
                "definitionId": r.get("definition_id"),
                "dependentPropCount": r["dependent_prop_count"],
                "priorityScore": r["priority_score"],
            }
            for r in requests
            if r["scope"] == "OFFER"
        ],
        # Compatibility projections for leftover PLAYER/TEAM consumers.
        "teams": affiliations + counterparties,
        "players": subjects,
    }

    return {
        "requests": requests,
        "skipped": classified["skipped"],
        "eligible": eligible,
        "eligible_prop_count": classified["eligible_prop_count"],
        "unique_scopes": unique_scopes,
        "entity_graph": entity_graph,
        "research_shadow": research_shadow,
        "legacy_market_emitted": False,
        "canonicalScopes": list(CANONICAL_SCOPES),
        "adapterScopesEmitted": False,
    }


def build_requests(
    rows: list[dict],
    cutoff: str,
    *,
    research_shadow: bool = False,
) -> list[dict]:
    """Backward-compatible wrapper. Does not emit legacy MARKET or PLAYER/TEAM."""
    return plan_research(rows, cutoff, research_shadow=research_shadow)["requests"]
