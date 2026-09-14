"""Convert joined Insight claims into canonical research-director acquisition jobs."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.scopes import SCOPE_RANK

_FAMILY = {
    "NFL": "gridiron", "NCAAFB": "gridiron", "CFB": "gridiron",
    "WNBA": "basketball", "NBA": "basketball", "MLB": "baseball",
    "SOCCER": "soccer", "NHL": "hockey",
}


def _request(
    *, scope: str, scope_id: str, need: str, cutoff: str, claims: list[dict[str, Any]],
    extra: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "scope": scope, "scope_id": scope_id, "need": need,
        "forecast_cutoff": cutoff, "dependent_prop_count": len(claims),
        "priority_score": float(len(claims)), "hierarchy_rank": SCOPE_RANK.get(scope, 99),
        "sourceClass": "INDEPENDENT_PLAYER_PERFORMANCE_OR_EVENT_CONTEXT",
        "offerVerificationState": "NOT_A_BOARD_OFFER",
        "insightClaimIds": sorted(str(c.get("claimId") or "") for c in claims),
        **extra,
    }
    record["request_id"] = "REQ_" + content_hash(
        {key: record[key] for key in ("scope", "scope_id", "need", "forecast_cutoff")}
    )[:16]
    return record


def plan_insight_host_research(claims: list[dict[str, Any]], cutoff: str) -> dict[str, Any]:
    """Create reusable EVENT/AFFILIATION/COUNTERPARTY/SUBJECT jobs.

    Only complete player-prop claims with exact same-HAR identity joins may enter.
    The output stays research-only and is deliberately not a platform offer.
    """
    eligible: list[dict[str, Any]] = []
    blocked: defaultdict[str, int] = defaultdict(int)
    for claim in claims:
        if claim.get("disposition") != "PLAYER_PROP_CANDIDATE":
            blocked["NOT_PLAYER_PROP_CANDIDATE"] += 1
        elif not bool(claim.get("paginationComplete")):
            blocked["PAGINATION_INCOMPLETE"] += 1
        elif claim.get("harIdentityState") not in {"VERIFIED_HAR_LOCAL", "HAR_ALIAS_CACHED_UNVERIFIED"}:
            blocked["HAR_IDENTITY_UNRESOLVED"] += 1
        else:
            eligible.append(claim)

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for claim in eligible:
        identity = claim["harIdentity"]
        event = identity["event"]
        player = identity["player"]
        league = str(claim.get("leagueId") or "").upper()
        family = _FAMILY.get(league, "")
        event_id = str(event.get("id") or "")
        team_id = str(player.get("teamId") or "")
        opponent = ""
        if team_id and event_id:
            home = event.get("home") or {}
            away = event.get("away") or {}
            opponent = str(away.get("id") if str(home.get("id") or "") == team_id else home.get("id") or "")
        for scope, scope_id, need, extra in (
            ("EVENT", event_id, "start_venue_starters_environment", {"eventId": event_id}),
            ("AFFILIATION", team_id, "role_pace_matchup", {"eventId": event_id, "affiliationId": team_id}),
            ("COUNTERPARTY", opponent, "opponent_defense_matchup", {"eventId": event_id, "counterpartyId": opponent}),
            ("SUBJECT", str(player.get("id") or ""), "availability_role_opportunity_recent_performance", {"eventId": event_id, "subjectId": str(player.get("id") or ""), "subjectName": player.get("name") or ""}),
        ):
            if scope_id:
                grouped[(scope, scope_id, need)].append(claim)

    requests: list[dict[str, Any]] = []
    for (scope, scope_id, need), members in sorted(grouped.items()):
        sample = members[0]
        event = sample["harIdentity"]["event"]
        requests.append(_request(
            scope=scope, scope_id=scope_id, need=need, cutoff=cutoff, claims=members,
            extra={
                "league": str(sample.get("leagueId") or "").upper(),
                "sportFamily": _FAMILY.get(str(sample.get("leagueId") or "").upper(), ""),
                "eventId": str(event.get("id") or ""),
                "harIdentityState": sample.get("harIdentityState"),
            },
        ))
    return {
        "schema": "pillars_dcm.insight_research_director_bridge.v1",
        "researchRows": [
            {
                "projectionId": str(c.get("claimId") or ""), "eventId": str(c["harIdentity"]["event"].get("id") or ""),
                "playerId": str(c["harIdentity"]["player"].get("id") or ""), "teamId": str(c["harIdentity"]["player"].get("teamId") or ""),
                "league": str(c.get("leagueId") or "").upper(), "sportFamily": _FAMILY.get(str(c.get("leagueId") or "").upper(), ""),
            } for c in eligible
        ],
        "requests": requests,
        "accounting": {
            "inputClaimCount": len(claims), "researchProjectionCount": len(eligible),
            "requestCount": len(requests), "blocked": dict(sorted(blocked.items())),
            "productionSelectionPermitted": False,
        },
    }
