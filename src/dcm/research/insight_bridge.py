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


def _label(value: Any, *, limit: int = 96) -> str:
    """Return a bounded structured label; never forward Insight free text."""
    return " ".join(str(value or "").split())[:limit]


def _team_label(team: dict[str, Any]) -> str:
    return _label(team.get("alias") or team.get("name"))


def _event_context(event: dict[str, Any], *, league: str, family: str, cutoff: str) -> dict[str, Any]:
    """Build the only safe EventResearchPacket projection of joined HAR context."""
    home = event.get("home") if isinstance(event.get("home"), dict) else {}
    away = event.get("away") if isinstance(event.get("away"), dict) else {}
    home_label = _team_label(home)
    away_label = _team_label(away)
    label = _label(f"{away_label} @ {home_label}") if away_label and home_label else ""
    body = {
        "schema": "pillars_dcm.event_research_packet.v1",
        "eventId": _label(event.get("id"), limit=128),
        "label": label or None,
        "league": league,
        "sportFamily": family,
        "homeTeam": home_label or None,
        "awayTeam": away_label or None,
        "homeTeamId": _label(home.get("id"), limit=128) or None,
        "awayTeamId": _label(away.get("id"), limit=128) or None,
        "scheduledStart": _label(event.get("scheduledTime"), limit=64) or None,
        "venue": _label(event.get("venue"), limit=96) or None,
        "gameStatus": _label(event.get("status"), limit=48) or None,
        "sourceHashes": [],
        "asOf": cutoff,
        "contextSource": "SAME_HAR_ENTITIES_SCHEDULE",
        "harIdentityState": "VERIFIED_HAR_LOCAL",
        "rawHarPersisted": False,
        "freeFormInsightTextPersisted": False,
        "evidenceUsed": False,
        "thin": True,
        "priorUsedAsResearch": False,
        "dependentOfferCount": 0,
    }
    body["contentHash"] = content_hash({key: value for key, value in body.items() if key != "contentHash"})
    return body


def _request_labels(event: dict[str, Any], player: dict[str, Any], scope: str) -> dict[str, str]:
    home = event.get("home") if isinstance(event.get("home"), dict) else {}
    away = event.get("away") if isinstance(event.get("away"), dict) else {}
    team_id = _label(player.get("teamId"), limit=128)
    home_id, away_id = _label(home.get("id"), limit=128), _label(away.get("id"), limit=128)
    if team_id == home_id:
        team_label, opponent_label = _team_label(home), _team_label(away)
    elif team_id == away_id:
        team_label, opponent_label = _team_label(away), _team_label(home)
    else:
        team_label, opponent_label = "", ""
    home_label, away_label = _team_label(home), _team_label(away)
    labels = {
        "eventLabel": _label(f"{away_label} @ {home_label}") if away_label and home_label else "",
        "affiliation": team_label,
        "opponent": opponent_label,
    }
    if scope == "EVENT":
        return {"eventLabel": labels["eventLabel"]}
    if scope == "AFFILIATION":
        return {"eventLabel": labels["eventLabel"], "affiliation": team_label}
    if scope == "COUNTERPARTY":
        return {"eventLabel": labels["eventLabel"], "opponent": opponent_label}
    return labels


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
    event_packets: dict[str, dict[str, Any]] = {}
    for claim in eligible:
        identity = claim["harIdentity"]
        event = identity["event"]
        player = identity["player"]
        league = str(claim.get("leagueId") or "").upper()
        family = _FAMILY.get(league, "")
        event_id = str(event.get("id") or "")
        team_id = str(player.get("teamId") or "")
        home = event.get("home") if isinstance(event.get("home"), dict) else {}
        away = event.get("away") if isinstance(event.get("away"), dict) else {}
        opponent = ""
        if team_id and event_id:
            opponent = str(away.get("id") if str(home.get("id") or "") == team_id else home.get("id") or "")
        if event_id:
            event_packets.setdefault(event_id, _event_context(event, league=league, family=family, cutoff=cutoff))
        for scope, scope_id, need, extra in (
            ("EVENT", event_id, "start_venue_starters_environment", {"eventId": event_id}),
            ("AFFILIATION", team_id, "role_pace_matchup", {"eventId": event_id, "affiliationId": team_id}),
            ("COUNTERPARTY", opponent, "opponent_defense_matchup", {"eventId": event_id, "counterpartyId": opponent}),
            ("SUBJECT", str(player.get("id") or ""), "availability_role_opportunity_recent_performance", {"eventId": event_id, "subjectId": str(player.get("id") or ""), "subjectName": _label(player.get("name"))}),
        ):
            if scope_id:
                grouped[(scope, scope_id, need)].append(claim)

    requests: list[dict[str, Any]] = []
    for (scope, scope_id, need), members in sorted(grouped.items()):
        sample = members[0]
        event = sample["harIdentity"]["event"]
        player = sample["harIdentity"]["player"]
        requests.append(_request(
            scope=scope, scope_id=scope_id, need=need, cutoff=cutoff, claims=members,
            extra={
                "league": str(sample.get("leagueId") or "").upper(),
                "sportFamily": _FAMILY.get(str(sample.get("leagueId") or "").upper(), ""),
                "eventId": str(event.get("id") or ""),
                "harIdentityState": sample.get("harIdentityState"),
                **_request_labels(event, player, scope),
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
        "eventPackets": [event_packets[event_id] for event_id in sorted(event_packets)],
        "accounting": {
            "inputClaimCount": len(claims), "researchProjectionCount": len(eligible),
            "requestCount": len(requests), "blocked": dict(sorted(blocked.items())),
            "productionSelectionPermitted": False,
        },
    }


def _finite_line(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def insights_offer_snapshots(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Promote Insights claims with exact line + HIGHER/LOWER into offer-equivalent snapshots.

    These are research-only InsightsOfferSnapshots.  They do not invent the
    opposite side, do not become BoardOffers, and never flip predictiveClaim.
    Missing side / missing line fail-closes that claim.
    """
    snapshots: list[dict[str, Any]] = []
    blocked: defaultdict[str, int] = defaultdict(int)
    for claim in claims:
        if not isinstance(claim, dict):
            blocked["NOT_A_CLAIM"] += 1
            continue
        if claim.get("disposition") != "PLAYER_PROP_CANDIDATE":
            blocked["NOT_PLAYER_PROP_CANDIDATE"] += 1
            continue
        line = _finite_line(claim.get("line"))
        direction = str(claim.get("direction") or "").upper()
        direction_class = str(claim.get("directionClass") or "")
        if line is None:
            blocked["MISSING_LINE"] += 1
            continue
        if direction_class != "HIGHER_LOWER" or direction not in {"HIGHER", "LOWER"}:
            blocked["MISSING_SIDE"] += 1
            continue
        identity = claim.get("harIdentity") if isinstance(claim.get("harIdentity"), dict) else {}
        player = identity.get("player") if isinstance(identity.get("player"), dict) else {}
        event = identity.get("event") if isinstance(identity.get("event"), dict) else {}
        league = str(claim.get("leagueId") or "").upper()
        family = _FAMILY.get(league, "")
        offered_higher = direction == "HIGHER"
        offered_lower = direction == "LOWER"
        body = {
            "schema": "pillars_dcm.insights_offer_snapshot.v1",
            "offerKind": "INSIGHTS_OFFER_SNAPSHOT",
            "candidateClass": "RESEARCH_CANDIDATE",
            "offerBacking": "INSIGHTS_OFFER_BACKED",
            "boardOffer": False,
            "productionSelectionPermitted": False,
            "predictiveClaim": "NONE",
            "learningRevision": "LR000000",
            "claimId": claim.get("claimId"),
            "insightId": claim.get("insightId"),
            "projectionId": str(claim.get("claimId") or claim.get("insightId") or ""),
            "subjectId": str(player.get("id") or claim.get("subjectId") or claim.get("playerId") or ""),
            "subjectName": _label(player.get("name") or claim.get("subjectName")),
            "playerId": str(player.get("id") or claim.get("playerId") or ""),
            "teamId": str(player.get("teamId") or claim.get("teamId") or ""),
            "eventId": str(event.get("id") or (claim.get("event") or {}).get("eventId") or ""),
            "league": league,
            "leagueId": league,
            "sportFamily": family,
            "market": _label(claim.get("proposition") or claim.get("marketType"), limit=64).lower(),
            "proposition": claim.get("proposition"),
            "line": line,
            "side": direction,
            "direction": direction,
            "offeredHigher": offered_higher,
            "offeredLower": offered_lower,
            "offeredMore": offered_higher,
            "offeredLess": offered_lower,
            "modifier": "STANDARD",
            "status": "pre_game",
            "isLive": False,
            "sourceAdapter": "INSIGHTS_EVIDENCE",
            "harIdentityState": claim.get("harIdentityState"),
            "sourceHarSha256": claim.get("sourceHarSha256"),
            "sourceBodyHash": claim.get("sourceBodyHash"),
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        snapshots.append(body)
    snapshots.sort(key=lambda row: (str(row.get("league") or ""), str(row.get("claimId") or "")))
    out = {
        "schema": "pillars_dcm.insights_offer_snapshots.v1",
        "offerKind": "INSIGHTS_OFFER_SNAPSHOT",
        "candidateClass": "RESEARCH_CANDIDATE",
        "offerBacking": "INSIGHTS_OFFER_BACKED",
        "boardOfferCount": 0,
        "insightsOfferCount": len(snapshots),
        "snapshots": snapshots,
        "accounting": {
            "inputClaimCount": len(claims),
            "snapshotCount": len(snapshots),
            "blocked": dict(sorted(blocked.items())),
            "productionSelectionPermitted": False,
            "predictiveClaim": "NONE",
            "learningRevision": "LR000000",
        },
    }
    out["contentHash"] = content_hash({k: v for k, v in out.items() if k != "contentHash"})
    return out
