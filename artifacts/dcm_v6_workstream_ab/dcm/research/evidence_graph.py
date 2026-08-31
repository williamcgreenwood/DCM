"""First-class EvidenceGraph: typed nodes + edges over the jsonl transport.

Transport remains evidence_bundle.jsonl. This graph is the logical structure
so a selection can be traced Selection → Offer → Player/Claim → SourceDocument.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from dcm.contracts.hashes import content_hash
from dcm.research.classify import market_definition_id


NODE_TYPES = (
    "SourceDocument",
    "EvidenceClaim",
    "Player",
    "Team",
    "Event",
    "MarketDefinition",
    "Offer",
    "NormalizedStat",
)
EDGE_TYPES = ("supports", "derived_from", "applies_to", "conflicts_with")


def _nid(kind: str, *parts: Any) -> str:
    joined = "|".join(str(p) for p in parts if p is not None and str(p) != "")
    return f"{kind}:{joined}" if joined else f"{kind}:unknown"


def _node(node_id: str, node_type: str, **attrs: Any) -> dict[str, Any]:
    body = {"id": node_id, "type": node_type, **attrs}
    return body


def _edge(edge_type: str, src: str, dst: str, **attrs: Any) -> dict[str, Any]:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"UNKNOWN_EDGE_TYPE:{edge_type}")
    return {"type": edge_type, "from": src, "to": dst, **attrs}


def build_evidence_graph(
    claims: list[dict[str, Any]],
    player_offer_sets: list[dict[str, Any]] | None = None,
    packets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add_node(node: dict[str, Any]) -> str:
        nid = str(node["id"])
        if nid not in nodes:
            nodes[nid] = node
        else:
            for k, v in node.items():
                if k == "id":
                    continue
                if v is not None and (nodes[nid].get(k) in (None, "", [], {})):
                    nodes[nid][k] = v
        return nid

    for claim in claims or []:
        if not isinstance(claim, dict):
            continue
        url = str(claim.get("url") or "")
        source_id = str(claim.get("source_id") or "")
        src_nid = _nid("SourceDocument", claim.get("source_hash") or source_id or url)
        add_node(
            _node(
                src_nid,
                "SourceDocument",
                sourceId=source_id,
                url=url,
                hostname=urlsplit(url).hostname or "",
                publishedAt=claim.get("published_at"),
                observedAt=claim.get("observed_at"),
                sourceHash=claim.get("source_hash"),
            )
        )
        claim_nid = _nid("EvidenceClaim", claim.get("claim_hash") or claim.get("claim_type"))
        add_node(
            _node(
                claim_nid,
                "EvidenceClaim",
                claimHash=claim.get("claim_hash"),
                claimType=claim.get("claim_type"),
                semanticScope=claim.get("semantic_scope"),
                scopeId=claim.get("scope_id"),
                url=url,
            )
        )
        edges.append(_edge("derived_from", claim_nid, src_nid))
        edges.append(_edge("supports", src_nid, claim_nid, via="source_document"))

        scope = str(claim.get("semantic_scope") or "")
        scope_id = str(claim.get("scope_id") or "")
        target_type = {
            "PLAYER": "Player",
            "TEAM": "Team",
            "EVENT": "Event",
            "MARKET_DEFINITION": "MarketDefinition",
            "OFFER": "Offer",
        }.get(scope)
        if target_type and scope_id:
            target_nid = _nid(target_type, scope_id)
            add_node(_node(target_nid, target_type, scopeId=scope_id))
            edges.append(_edge("supports", claim_nid, target_nid))
        for other in claim.get("conflicts") or []:
            other_nid = _nid("EvidenceClaim", other)
            add_node(_node(other_nid, "EvidenceClaim", claimHash=str(other)))
            edges.append(_edge("conflicts_with", claim_nid, other_nid))

    for offer_set in player_offer_sets or []:
        player_nid = _nid("Player", offer_set.get("playerId"))
        add_node(
            _node(
                player_nid,
                "Player",
                playerId=offer_set.get("playerId"),
                playerName=offer_set.get("playerName"),
                league=offer_set.get("league"),
                team=offer_set.get("team"),
                eventId=offer_set.get("eventId"),
            )
        )
        event_nid = _nid("Event", offer_set.get("eventId"))
        add_node(
            _node(
                event_nid,
                "Event",
                eventId=offer_set.get("eventId"),
                eventLabel=offer_set.get("eventLabel"),
                eventStartTime=offer_set.get("eventStartTime"),
            )
        )
        team_nid = _nid("Team", offer_set.get("team") or offer_set.get("playerId"))
        add_node(_node(team_nid, "Team", team=offer_set.get("team"), league=offer_set.get("league")))
        edges.append(_edge("applies_to", player_nid, event_nid))
        for offer in offer_set.get("offers") or []:
            pid = str(offer.get("projectionId") or "")
            if not pid:
                continue
            offer_nid = _nid("Offer", pid)
            def_id = market_definition_id(
                {
                    "league": offer_set.get("league"),
                    "market": offer.get("market"),
                    "boardId": offer.get("boardId"),
                }
            )
            def_nid = _nid("MarketDefinition", def_id)
            add_node(
                _node(
                    offer_nid,
                    "Offer",
                    projectionId=pid,
                    market=offer.get("market"),
                    line=offer.get("line"),
                    modifier=offer.get("modifier"),
                    playerId=offer_set.get("playerId"),
                    eventId=offer_set.get("eventId"),
                )
            )
            add_node(
                _node(
                    def_nid,
                    "MarketDefinition",
                    definitionId=def_id,
                    market=offer.get("market"),
                    league=offer_set.get("league"),
                    boardId=offer.get("boardId"),
                )
            )
            edges.append(_edge("applies_to", player_nid, offer_nid))
            edges.append(_edge("applies_to", offer_nid, def_nid))
            edges.append(_edge("applies_to", offer_nid, event_nid))

    for packet in packets or []:
        ident = packet.get("identity") or {}
        player_nid = _nid("Player", ident.get("playerId"))
        add_node(
            _node(
                player_nid,
                "Player",
                playerId=ident.get("playerId"),
                packetId=packet.get("packetId"),
                status=packet.get("status"),
            )
        )
        for i, log in enumerate(packet.get("gameLogs") or []):
            if not isinstance(log, dict):
                continue
            stat_nid = _nid("NormalizedStat", ident.get("playerId"), "game", i, log.get("minutes"))
            add_node(
                _node(
                    stat_nid,
                    "NormalizedStat",
                    playerId=ident.get("playerId"),
                    minutes=log.get("minutes"),
                    pts=log.get("pts"),
                    reb=log.get("reb"),
                    ast=log.get("ast"),
                    fga=log.get("fga"),
                    index=i,
                )
            )
            edges.append(_edge("derived_from", stat_nid, player_nid))
            edges.append(_edge("supports", stat_nid, player_nid, via="normalized_log"))
        for h in packet.get("sourceHashes") or []:
            src_nid = _nid("SourceDocument", h)
            add_node(_node(src_nid, "SourceDocument", contentHash=h))
            edges.append(_edge("derived_from", player_nid, src_nid, via="packet"))
        for pid in packet.get("appliesToProjectionIds") or []:
            offer_nid = _nid("Offer", pid)
            add_node(_node(offer_nid, "Offer", projectionId=pid))
            edges.append(_edge("applies_to", player_nid, offer_nid, via="packet"))

    # Deduplicate edges.
    seen: set[tuple[str, str, str]] = set()
    unique_edges: list[dict[str, Any]] = []
    for edge in edges:
        key = (str(edge["type"]), str(edge["from"]), str(edge["to"]))
        if key in seen:
            continue
        seen.add(key)
        unique_edges.append(edge)
    unique_edges.sort(key=lambda e: (e["type"], e["from"], e["to"]))
    node_list = [nodes[k] for k in sorted(nodes)]
    body = {
        "schema": "pillars_dcm.evidence_graph.v1",
        "nodeTypes": list(NODE_TYPES),
        "edgeTypes": list(EDGE_TYPES),
        "nodeCount": len(node_list),
        "edgeCount": len(unique_edges),
        "nodes": node_list,
        "edges": unique_edges,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def trace_selection(graph: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    """Resolve Selection → Offer → Player/Claim → SourceDocument for card picks."""
    projection_id = str(
        selection.get("projectionId")
        or selection.get("offerId")
        or (selection.get("row") or {}).get("projectionId")
        or ""
    )
    nodes = {n["id"]: n for n in graph.get("nodes") or [] if isinstance(n, dict)}
    edges = [e for e in graph.get("edges") or [] if isinstance(e, dict)]
    offer_nid = _nid("Offer", projection_id)
    path: list[dict[str, Any]] = []
    source_url = None
    resolved = False

    def neighbors(nid: str, edge_type: str | None = None, *, reverse: bool = False) -> list[str]:
        out = []
        for edge in edges:
            if edge_type and edge.get("type") != edge_type:
                continue
            if reverse:
                if edge.get("to") == nid:
                    out.append(str(edge.get("from")))
            else:
                if edge.get("from") == nid:
                    out.append(str(edge.get("to")))
        return out

    offer = nodes.get(offer_nid)
    if offer:
        path.append(offer)
        # Player --applies_to--> Offer
        players = neighbors(offer_nid, "applies_to", reverse=True)
        player_nodes = [nodes[i] for i in players if i in nodes and nodes[i].get("type") == "Player"]
        if player_nodes:
            path.append(player_nodes[0])
            player_id = player_nodes[0]["id"]
            claims = [
                nodes[i]
                for i in neighbors(player_id, "supports", reverse=True)
                if i in nodes and nodes[i].get("type") == "EvidenceClaim"
            ]
            if claims:
                path.append(claims[0])
                sources = [
                    nodes[i]
                    for i in neighbors(claims[0]["id"], "derived_from")
                    if i in nodes and nodes[i].get("type") == "SourceDocument"
                ]
                if not sources:
                    sources = [
                        nodes[i]
                        for i in neighbors(claims[0]["id"], "supports", reverse=True)
                        if i in nodes and nodes[i].get("type") == "SourceDocument"
                    ]
                if sources:
                    path.append(sources[0])
                    source_url = sources[0].get("url")
                    resolved = True
            if not resolved:
                # packet-derived source hashes on the player
                srcs = [
                    nodes[i]
                    for i in neighbors(player_id, "derived_from")
                    if i in nodes and nodes[i].get("type") == "SourceDocument"
                ]
                if srcs:
                    path.append(srcs[0])
                    source_url = srcs[0].get("url")
                    resolved = bool(source_url) or True

    return {
        "projectionId": projection_id,
        "resolved": resolved,
        "sourceUrl": source_url,
        "path": path,
        "nodeTypes": [n.get("type") for n in path],
    }
