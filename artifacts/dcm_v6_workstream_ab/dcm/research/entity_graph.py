"""First-class EntityGraph: Sport → League → Event → Team → Player → PlayerOfferSet → Offer.

Distinct from EvidenceGraph (claims/sources). This graph records reuse:
one Team node is pointed at by every player on that team; opponent edges
reuse the same Team node rather than cloning research.
"""
from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.classify import market_definition_id


NODE_TYPES = (
    "Sport",
    "League",
    "Event",
    "Team",
    "Player",
    "PlayerOfferSet",
    "Offer",
    "MarketDefinition",
    "TeamResearchPacket",
    "EventResearchPacket",
    "OpponentResearchPacket",
    "PlayerResearchPacket",
)
EDGE_TYPES = (
    "member_of",
    "plays_in",
    "opposes",
    "offers",
    "defined_as",
    "researched_by",
    "reuses",
)


def _nid(kind: str, *parts: Any) -> str:
    joined = "|".join(str(p) for p in parts if p is not None and str(p) != "")
    return f"{kind}:{joined}" if joined else f"{kind}:unknown"


def build_entity_graph(
    offer_sets: list[dict[str, Any]] | None = None,
    *,
    team_packets: list[dict[str, Any]] | None = None,
    event_packets: list[dict[str, Any]] | None = None,
    opponent_packets: list[dict[str, Any]] | None = None,
    player_packets: list[dict[str, Any]] | None = None,
    population: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add_node(node_id: str, node_type: str, **attrs: Any) -> str:
        if node_type not in NODE_TYPES:
            raise ValueError(f"UNKNOWN_ENTITY_NODE:{node_type}")
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "type": node_type, **attrs}
        else:
            for k, v in attrs.items():
                if v is not None and nodes[node_id].get(k) in (None, "", [], {}):
                    nodes[node_id][k] = v
        return node_id

    def add_edge(edge_type: str, src: str, dst: str, **attrs: Any) -> None:
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"UNKNOWN_ENTITY_EDGE:{edge_type}")
        edges.append({"type": edge_type, "from": src, "to": dst, **attrs})

    team_by_id = {str(p.get("teamId")): p for p in (team_packets or []) if p.get("teamId")}
    event_by_id = {str(p.get("eventId")): p for p in (event_packets or []) if p.get("eventId")}
    player_by_key = {}
    for packet in player_packets or []:
        ident = packet.get("identity") if isinstance(packet.get("identity"), dict) else {}
        player_by_key[(str(ident.get("playerId") or ""), str(ident.get("eventId") or ""))] = packet

    for offer_set in offer_sets or []:
        family = str(offer_set.get("sportFamily") or "")
        league = str(offer_set.get("league") or "")
        sport_id = add_node(_nid("Sport", family), "Sport", name=family)
        league_id = add_node(_nid("League", family, league), "League", name=league, sportFamily=family)
        add_edge("member_of", league_id, sport_id)
        event_id = str(offer_set.get("eventId") or "")
        ev_nid = add_node(
            _nid("Event", event_id),
            "Event",
            eventId=event_id,
            label=offer_set.get("eventLabel"),
            start=offer_set.get("eventStartTime"),
        )
        add_edge("member_of", ev_nid, league_id)
        team = str(offer_set.get("team") or "")
        opp = str(offer_set.get("opponent") or "")
        team_nid = add_node(_nid("Team", team), "Team", teamId=team, league=league)
        opp_nid = add_node(_nid("Team", opp), "Team", teamId=opp, league=league) if opp else None
        add_edge("plays_in", team_nid, ev_nid)
        if opp_nid:
            add_edge("plays_in", opp_nid, ev_nid)
            add_edge("opposes", team_nid, opp_nid)
            add_edge("opposes", opp_nid, team_nid)
        player = str(offer_set.get("playerId") or "")
        player_nid = add_node(
            _nid("Player", player),
            "Player",
            playerId=player,
            playerName=offer_set.get("playerName"),
        )
        add_edge("member_of", player_nid, team_nid)
        add_edge("plays_in", player_nid, ev_nid)
        set_nid = add_node(
            _nid("PlayerOfferSet", offer_set.get("setId") or f"{player}|{event_id}"),
            "PlayerOfferSet",
            setId=offer_set.get("setId"),
            offerCount=offer_set.get("offerCount"),
        )
        add_edge("offers", player_nid, set_nid)
        if team in team_by_id:
            tp = team_by_id[team]
            tp_nid = add_node(_nid("TeamResearchPacket", tp.get("packetId")), "TeamResearchPacket", packetId=tp.get("packetId"))
            add_edge("researched_by", team_nid, tp_nid)
            add_edge("reuses", player_nid, tp_nid)
        if opp and opp in team_by_id:
            op = team_by_id[opp]
            op_nid = add_node(_nid("TeamResearchPacket", op.get("packetId")), "TeamResearchPacket", packetId=op.get("packetId"))
            add_edge("researched_by", opp_nid, op_nid)
            add_edge("reuses", player_nid, op_nid, role="opponent")
        if event_id in event_by_id:
            ep = event_by_id[event_id]
            ep_nid = add_node(_nid("EventResearchPacket", ep.get("packetId")), "EventResearchPacket", packetId=ep.get("packetId"))
            add_edge("researched_by", ev_nid, ep_nid)
        pp = player_by_key.get((player, event_id))
        if pp:
            pp_nid = add_node(_nid("PlayerResearchPacket", pp.get("packetId")), "PlayerResearchPacket", packetId=pp.get("packetId"))
            add_edge("researched_by", player_nid, pp_nid)
            add_edge("reuses", set_nid, pp_nid)
        for offer in offer_set.get("offers") or []:
            oid = str(offer.get("projectionId") or "")
            if not oid:
                continue
            onid = add_node(_nid("Offer", oid), "Offer", projectionId=oid, market=offer.get("market"), line=offer.get("line"))
            add_edge("offers", set_nid, onid)
            def_id = market_definition_id({
                "sportFamily": family,
                "league": league,
                "market": offer.get("market"),
                "boardId": offer.get("boardId") or "FULL_GAME",
            })
            md_nid = add_node(_nid("MarketDefinition", def_id), "MarketDefinition", definitionId=def_id)
            add_edge("defined_as", onid, md_nid)

    for op in opponent_packets or []:
        nid = add_node(
            _nid("OpponentResearchPacket", op.get("packetId")),
            "OpponentResearchPacket",
            packetId=op.get("packetId"),
            reusedTeamPacketId=op.get("reusedTeamPacketId"),
        )
        if op.get("reusedTeamPacketId"):
            add_edge("reuses", nid, _nid("TeamResearchPacket", op.get("reusedTeamPacketId")))

    body = {
        "schema": "pillars_dcm.entity_graph.v1",
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodes": sorted(nodes.values(), key=lambda n: str(n.get("id") or "")),
        "edges": edges,
        "populationHash": (population or {}).get("contentHash"),
        "reuseRule": "One Team node / one TeamResearchPacket per unique teamId; opponent edges reuse that node.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
