"""Universal research packet containers.

Sport-specific payloads stay inside plugins/adapters. These wrappers expose
Subject / Affiliation / Counterparty / Event / Environment packets while
projecting existing player/team/opponent packets as compatibility views.
"""
from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.entity_packets import build_entity_packets
from dcm.research.player_packet import build_packets_for_offer_sets
from dcm.research.scopes import canonical_scope


def _s(value: Any) -> str:
    return "" if value is None else str(value)


def _wrap_subject(player_packet: dict[str, Any]) -> dict[str, Any]:
    ident = player_packet.get("identity") if isinstance(player_packet.get("identity"), dict) else {}
    body = {
        "schema": "pillars_dcm.subject_research_packet.v1",
        "subjectId": _s(ident.get("playerId") or player_packet.get("playerId")),
        "subjectType": "PLAYER",
        "subjectName": _s(ident.get("playerName") or ident.get("name") or player_packet.get("playerName")),
        "sportId": _s(ident.get("sportFamily") or player_packet.get("sportFamily")),
        "competitionId": _s(ident.get("league") or player_packet.get("league")),
        "affiliationId": _s(ident.get("team") or ident.get("teamId") or player_packet.get("teamId")),
        "eventId": _s(ident.get("eventId") or player_packet.get("eventId")),
        "status": player_packet.get("status"),
        "role": (player_packet.get("roleHints") or {}).get("role") if isinstance(player_packet.get("roleHints"), dict) else player_packet.get("role"),
        "historicalPerformances": player_packet.get("gameLogs") or [],
        "opportunity": player_packet.get("opportunity"),
        "efficiency": player_packet.get("efficiency"),
        "windows": player_packet.get("windows"),
        "sourceHashes": list(player_packet.get("sourceHashes") or []),
        "asOf": player_packet.get("asOf"),
        "evidenceUsed": bool(player_packet.get("evidenceUsed")),
        "thin": bool(player_packet.get("thin")),
        "compatibilityPlayerPacketHash": player_packet.get("contentHash"),
        "sportSpecificPayload": player_packet,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "sportSpecificPayload"}})
    return body


def _wrap_affiliation(team_packet: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": "pillars_dcm.affiliation_research_packet.v1",
        "affiliationId": _s(team_packet.get("teamId")),
        "affiliationName": _s(team_packet.get("name") or team_packet.get("teamId")),
        "sportId": _s(team_packet.get("sportFamily")),
        "competitionId": _s(team_packet.get("league")),
        "opportunityEnvironment": {
            "pace": team_packet.get("pace"),
            "ortg": team_packet.get("ortg"),
            "drtg": team_packet.get("drtg"),
            "paceMultiplier": team_packet.get("paceMultiplier"),
        },
        "gameLogCount": team_packet.get("gameLogCount"),
        "sourceHashes": list(team_packet.get("sourceHashes") or []),
        "asOf": team_packet.get("asOf"),
        "evidenceUsed": bool(team_packet.get("evidenceUsed")),
        "thin": bool(team_packet.get("thin")),
        "fixturePriorOnly": bool(team_packet.get("fixturePriorOnly")),
        "compatibilityTeamPacketHash": team_packet.get("contentHash"),
        "sportSpecificPayload": team_packet,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "sportSpecificPayload"}})
    return body


def _wrap_counterparty(opp_packet: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": "pillars_dcm.counterparty_research_packet.v1",
        "counterpartyId": _s(opp_packet.get("teamId")),
        "versusAffiliationId": _s(opp_packet.get("versusTeamId")),
        "eventId": _s(opp_packet.get("eventId")),
        "reusedAffiliationPacketId": opp_packet.get("reusedTeamPacketId"),
        "reusedAffiliationPacketHash": opp_packet.get("reusedTeamPacketHash"),
        "h2hDominates": bool(opp_packet.get("h2hDominates")),
        "asOf": opp_packet.get("asOf"),
        "compatibilityOpponentPacketHash": opp_packet.get("contentHash"),
        "sportSpecificPayload": opp_packet,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "sportSpecificPayload"}})
    return body


def _wrap_event(event_packet: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": "pillars_dcm.event_research_packet_universal.v1",
        "eventId": _s(event_packet.get("eventId")),
        "competitionId": _s(event_packet.get("league")),
        "sportId": _s(event_packet.get("sportFamily")),
        "scheduledStart": event_packet.get("scheduledStart"),
        "venue": event_packet.get("venue"),
        "format": event_packet.get("format") or event_packet.get("boardId"),
        "status": event_packet.get("gameStatus"),
        "environment": event_packet.get("environment"),
        "sourceHashes": list(event_packet.get("sourceHashes") or []),
        "asOf": event_packet.get("asOf"),
        "evidenceUsed": bool(event_packet.get("evidenceUsed")),
        "thin": bool(event_packet.get("thin")),
        "compatibilityEventPacketHash": event_packet.get("contentHash"),
        "sportSpecificPayload": event_packet,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "sportSpecificPayload"}})
    return body


def _wrap_environment(event_packet: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": "pillars_dcm.environment_research_packet.v1",
        "environmentId": f"env:{_s(event_packet.get('eventId'))}",
        "eventId": _s(event_packet.get("eventId")),
        "venue": event_packet.get("venue"),
        "surface": (event_packet.get("parameterFields") or {}).get("surface") if isinstance(event_packet.get("parameterFields"), dict) else None,
        "weather": (event_packet.get("parameterFields") or {}).get("weather") if isinstance(event_packet.get("parameterFields"), dict) else event_packet.get("environment"),
        "roof": None,
        "altitude": None,
        "asOf": event_packet.get("asOf"),
        "evidenceUsed": bool(event_packet.get("environment") or event_packet.get("venue")),
        "compatibilityEventPacketHash": event_packet.get("contentHash"),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def build_universal_packets(
    offer_sets: list[dict[str, Any]],
    *,
    claims: list[dict[str, Any]] | None = None,
    as_of: str = "",
    population: dict[str, Any] | None = None,
    player_packets: list[dict[str, Any]] | None = None,
    entity_packets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packets = player_packets if player_packets is not None else build_packets_for_offer_sets(
        offer_sets, claims=claims or [], as_of=as_of
    )
    entities = entity_packets if entity_packets is not None else build_entity_packets(
        offer_sets, claims=claims or [], as_of=as_of, population=population
    )
    subjects = [_wrap_subject(p) for p in packets if isinstance(p, dict)]
    affiliations = [_wrap_affiliation(t) for t in (entities.get("teams") or []) if isinstance(t, dict)]
    counterparties = [_wrap_counterparty(o) for o in (entities.get("opponents") or []) if isinstance(o, dict)]
    events = [_wrap_event(e) for e in (entities.get("events") or []) if isinstance(e, dict)]
    environments = [_wrap_environment(e) for e in (entities.get("events") or []) if isinstance(e, dict)]
    body = {
        "schema": "pillars_dcm.universal_research_packets.v1",
        "canonical": True,
        "subjectPacketCount": len(subjects),
        "affiliationPacketCount": len(affiliations),
        "counterpartyPacketCount": len(counterparties),
        "eventPacketCount": len(events),
        "environmentPacketCount": len(environments),
        "subjects": subjects,
        "affiliations": affiliations,
        "counterparties": counterparties,
        "events": events,
        "environments": environments,
        "compatibility": {
            "playerPackets": "player_research_packets.json",
            "teamPackets": "team_research_packets.json",
            "opponentPackets": "opponent_research_packets.json",
            "eventPackets": "event_research_packets.json",
        },
        "rule": "PLAYER/TEAM terminology terminates at sport/source adapters and compatibility projections.",
        "canonicalKinds": [canonical_scope(k) for k in ("SUBJECT", "AFFILIATION", "COUNTERPARTY", "EVENT", "ENVIRONMENT")],
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
