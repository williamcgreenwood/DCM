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
        "dependentClaimCount": 0,
        "researchOnly": True,
        "offerVerificationState": "NOT_A_BOARD_OFFER",
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
    claim_ids = sorted(str(c.get("claimId") or "") for c in claims if str(c.get("claimId") or ""))
    record = {
        "scope": scope, "scope_id": scope_id, "need": need,
        "forecast_cutoff": cutoff, "dependent_prop_count": len(claims),
        "dependent_claim_ids": claim_ids,
        "dependentClaimCount": len(claim_ids),
        "dependentOfferCount": 0,
        "priority_score": float(len(claims)), "hierarchy_rank": SCOPE_RANK.get(scope, 99),
        "sourceClass": "INDEPENDENT_PLAYER_PERFORMANCE_OR_EVENT_CONTEXT",
        "offerVerificationState": "NOT_A_BOARD_OFFER",
        "researchOnly": True,
        "insightClaimIds": claim_ids,
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
                "claimId": str(c.get("claimId") or ""), "eventId": str(c["harIdentity"]["event"].get("id") or ""),
                "playerId": str(c["harIdentity"]["player"].get("id") or ""), "teamId": str(c["harIdentity"]["player"].get("teamId") or ""),
                "league": str(c.get("leagueId") or "").upper(), "sportFamily": _FAMILY.get(str(c.get("leagueId") or "").upper(), ""),
                "subjectName": _label(c.get("subjectName")),
                "researchOnly": True,
                "offerVerificationState": "NOT_A_BOARD_OFFER",
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
def build_insight_research_graph(bridge: dict[str, Any] | None) -> dict[str, Any]:
    """Build a non-offer graph for the Insights research population.

    Insights are research signals, not platform offers.  They therefore cannot
    be represented as ``Offer`` nodes in the board or universal dependency
    graph.  This companion graph preserves the same reusable event/team/player
    relationships while making the research-only boundary explicit.
    """
    bridge = bridge if isinstance(bridge, dict) else {}
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add_node(kind: str, entity_id: Any, **attrs: Any) -> str:
        value = _label(entity_id, limit=160)
        if not value:
            return ""
        node_id = f"{kind}:{value}"
        node = nodes.setdefault(node_id, {"id": node_id, "type": kind, "entityId": value})
        for key, item in attrs.items():
            if item not in (None, "", [], {}) and node.get(key) in (None, "", [], {}):
                node[key] = item
        return node_id

    def add_edge(kind: str, source: str, target: str) -> None:
        if not source or not target:
            return
        key = (kind, source, target)
        edges.setdefault(key, {"type": kind, "from": source, "to": target})

    for packet in bridge.get("eventPackets") or []:
        if not isinstance(packet, dict):
            continue
        event_id = str(packet.get("eventId") or "")
        event_node = add_node(
            "Event", event_id, label=packet.get("label"), league=packet.get("league"),
            sportFamily=packet.get("sportFamily"), scheduledStart=packet.get("scheduledStart"),
        )
        competition_node = add_node("Competition", packet.get("league"), sportFamily=packet.get("sportFamily"))
        sport_node = add_node("Sport", packet.get("sportFamily"))
        add_edge("member_of", event_node, competition_node)
        add_edge("member_of", competition_node, sport_node)
        for kind, id_key, label_key in (
            ("Affiliation", "homeTeamId", "homeTeam"),
            ("Affiliation", "awayTeamId", "awayTeam"),
        ):
            team_node = add_node(kind, packet.get(id_key), name=packet.get(label_key), league=packet.get("league"))
            add_edge("participates_in", team_node, event_node)

    scope_kind = {
        "EVENT": "Event",
        "AFFILIATION": "Affiliation",
        "COUNTERPARTY": "Counterparty",
        "SUBJECT": "Subject",
    }
    claim_count = 0
    request_count = 0
    for request in bridge.get("requests") or []:
        if not isinstance(request, dict):
            continue
        request_id = str(request.get("request_id") or request.get("requestId") or "")
        request_node = add_node(
            "ResearchRequirement", request_id, scope=request.get("scope"),
            need=request.get("need"), researchOnly=True,
        )
        request_count += bool(request_node)
        entity_node = add_node(
            scope_kind.get(str(request.get("scope") or "").upper(), "ResearchEntity"),
            request.get("scope_id"),
            eventId=request.get("eventId"),
            league=request.get("league"),
            label=request.get("eventLabel") or request.get("subjectName") or request.get("affiliation") or request.get("opponent"),
            researchOnly=True,
        )
        add_edge("requires", request_node, entity_node)
        claim_ids = request.get("dependent_claim_ids") or request.get("insightClaimIds") or []
        for claim_id in claim_ids:
            claim_node = add_node("InsightClaim", claim_id, researchOnly=True, offerVerificationState="NOT_A_BOARD_OFFER")
            if claim_node:
                claim_count += 1
                add_edge("drives", claim_node, request_node)
        event_id = str(request.get("eventId") or "")
        if event_id:
            add_edge("contextualized_by", request_node, add_node("Event", event_id))

    body = {
        "schema": "pillars_dcm.insight_research_dependency_graph.v1",
        "researchOnly": True,
        "platformOfferCount": 0,
        "requestCount": int(request_count),
        "claimCount": len({node_id for node_id, node in nodes.items() if node.get("type") == "InsightClaim"}),
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodes": sorted(nodes.values(), key=lambda row: str(row.get("id") or "")),
        "edges": sorted(edges.values(), key=lambda row: (str(row.get("type") or ""), str(row.get("from") or ""), str(row.get("to") or ""))),
        "reuseLaw": "Research each reusable Insights event, affiliation, counterparty, and subject once; retain claim fan-out without creating platform offers.",
        "productionSelectionPermitted": False,
    }
    body["contentHash"] = content_hash({key: value for key, value in body.items() if key != "contentHash"})
    return body
