"""Hierarchical research requests after pre-research classification.

HAR → account → identity → classify → then only model-eligible (and opt-in
shadow) rows receive deep research. Shared SPORT/EVENT/TEAM/MARKET_DEFINITION
entities are emitted once and fan-out prioritized.

Legacy MARKET is not emitted. MARKET_DEFINITION + OFFER are the production
scopes. Priority is never alphabetical.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.classify import classify_rows, market_definition_id
from dcm.sports.common.plugin import selection_state

SCOPE_ORDER = ("SPORT", "EVENT", "TEAM", "PLAYER", "MARKET_DEFINITION", "OFFER")
SCOPE_RANK = {name: i for i, name in enumerate(SCOPE_ORDER)}

# information_importance × freshness_need by scope (doctrine hierarchy, not alpha)
INFO_IMPORTANCE = {
    "SPORT": 1.00,
    "EVENT": 0.95,
    "TEAM": 0.85,
    "PLAYER": 0.75,
    "MARKET_DEFINITION": 0.70,
    "OFFER": 0.40,
}
FRESHNESS_NEED = {
    "SPORT": 0.40,
    "EVENT": 1.00,
    "TEAM": 0.85,
    "PLAYER": 1.00,
    "MARKET_DEFINITION": 0.30,
    "OFFER": 0.90,
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
    by_event: dict[str, list[dict]] = defaultdict(list)
    by_team: dict[str, list[dict]] = defaultdict(list)
    by_player: dict[str, list[dict]] = defaultdict(list)
    by_def: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        by_sport[(str(row.get("sportFamily") or ""), str(row.get("league") or ""))].append(row)
        by_event[str(row.get("eventId") or "")].append(row)
        by_team[str(row.get("teamId") or "")].append(row)
        by_player[str(row.get("playerId") or "")].append(row)
        by_def[market_definition_id(row)].append(row)

    for (family, league), group in by_sport.items():
        _add(
            reqs,
            scope="SPORT",
            scope_id=f"{family}:{league}",
            need="rules_calendar_distribution",
            cutoff=cutoff,
            extra={"league": league, "sportFamily": family},
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
            extra={"league": sample.get("league"), "label": sample.get("eventLabel")},
            dependents=group,
        )

    for team_id, group in by_team.items():
        if not team_id:
            continue
        sample = group[0]
        _add(
            reqs,
            scope="TEAM",
            scope_id=team_id,
            need="role_pace_matchup",
            cutoff=cutoff,
            extra={"league": sample.get("league")},
            dependents=group,
        )

    for player_id, group in by_player.items():
        if not player_id:
            continue
        sample = group[0]
        _add(
            reqs,
            scope="PLAYER",
            scope_id=player_id,
            need="status_role_logs_opportunity_efficiency",
            cutoff=cutoff,
            extra={"name": sample.get("playerName"), "league": sample.get("league")},
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

    entity_graph = {
        "sports": [
            {
                "scopeId": r["scope_id"],
                "requestId": r["request_id"],
                "dependentPropCount": r["dependent_prop_count"],
                "priorityScore": r["priority_score"],
            }
            for r in requests
            if r["scope"] == "SPORT"
        ],
        "events": [
            {
                "scopeId": r["scope_id"],
                "requestId": r["request_id"],
                "dependentPropCount": r["dependent_prop_count"],
                "priorityScore": r["priority_score"],
            }
            for r in requests
            if r["scope"] == "EVENT"
        ],
        "teams": [
            {
                "scopeId": r["scope_id"],
                "requestId": r["request_id"],
                "dependentPropCount": r["dependent_prop_count"],
                "priorityScore": r["priority_score"],
            }
            for r in requests
            if r["scope"] == "TEAM"
        ],
        "players": [
            {
                "scopeId": r["scope_id"],
                "requestId": r["request_id"],
                "dependentPropCount": r["dependent_prop_count"],
                "priorityScore": r["priority_score"],
            }
            for r in requests
            if r["scope"] == "PLAYER"
        ],
        "marketDefinitions": [
            {
                "scopeId": r["scope_id"],
                "requestId": r["request_id"],
                "dependentPropCount": r["dependent_prop_count"],
                "priorityScore": r["priority_score"],
            }
            for r in requests
            if r["scope"] == "MARKET_DEFINITION"
        ],
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
    }


def build_requests(
    rows: list[dict],
    cutoff: str,
    *,
    research_shadow: bool = False,
) -> list[dict]:
    """Backward-compatible wrapper. Does not emit legacy MARKET."""
    return plan_research(rows, cutoff, research_shadow=research_shadow)["requests"]
