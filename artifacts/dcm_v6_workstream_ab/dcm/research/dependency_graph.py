"""Universal research dependency graph.

This graph is intentionally independent of team/player vocabulary.  It
describes reusable research dependencies from the canonical
ResearchPopulationManifest and SubjectOfferSets.
"""
from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash


NODE_KINDS = (
    "Sport",
    "Competition",
    "Event",
    "Affiliation",
    "Subject",
    "Counterparty",
    "Environment",
    "MarketDefinition",
    "Offer",
    "SubjectOfferSet",
)
EDGE_KINDS = (
    "member_of",
    "participates_in",
    "affiliated_with",
    "interacts_with",
    "contextualized_by",
    "contains_offer",
    "defined_as",
    "depends_on",
)


def _nid(kind: str, value: Any) -> str:
    text = "" if value is None else str(value)
    return f"{kind}:{text}"


def build_research_dependency_graph(
    subject_offer_sets: list[dict[str, Any]],
    *,
    population: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add_node(kind: str, entity_id: Any, **attrs: Any) -> str:
        if kind not in NODE_KINDS:
            raise ValueError(f"UNKNOWN_RESEARCH_NODE:{kind}")
        node_id = _nid(kind, entity_id)
        existing = nodes.setdefault(node_id, {"id": node_id, "type": kind, "entityId": str(entity_id)})
        for key, value in attrs.items():
            if value not in (None, "", [], {}) and existing.get(key) in (None, "", [], {}):
                existing[key] = value
        return node_id

    def add_edge(kind: str, src: str, dst: str, **attrs: Any) -> None:
        if kind not in EDGE_KINDS:
            raise ValueError(f"UNKNOWN_RESEARCH_EDGE:{kind}")
        key = (kind, src, dst)
        edges.setdefault(key, {"type": kind, "from": src, "to": dst, **attrs})

    for offer_set in subject_offer_sets or []:
        sport = str(offer_set.get("sportId") or "")
        competition = str(offer_set.get("competitionId") or "")
        event = str(offer_set.get("eventId") or "")
        subject = str(offer_set.get("subjectId") or "")
        if not (sport and competition and event and subject):
            continue

        sport_n = add_node("Sport", sport, name=sport)
        competition_n = add_node("Competition", competition, sportId=sport)
        event_n = add_node(
            "Event",
            event,
            label=offer_set.get("eventLabel"),
            start=offer_set.get("eventStart"),
            status=offer_set.get("eventStatus"),
        )
        subject_n = add_node(
            "Subject",
            subject,
            subjectType=offer_set.get("subjectType"),
            name=offer_set.get("subjectName"),
        )
        set_n = add_node(
            "SubjectOfferSet",
            offer_set.get("setId") or f"{subject}|{event}",
            offerCount=offer_set.get("offerCount"),
        )
        add_edge("member_of", competition_n, sport_n)
        add_edge("member_of", event_n, competition_n)
        add_edge("participates_in", subject_n, event_n)
        add_edge("depends_on", set_n, subject_n)
        add_edge("depends_on", set_n, event_n)

        affiliation = offer_set.get("affiliationId")
        if affiliation:
            affiliation_n = add_node("Affiliation", affiliation)
            add_edge("affiliated_with", subject_n, affiliation_n)
            add_edge("participates_in", affiliation_n, event_n)
            add_edge("depends_on", set_n, affiliation_n)

        for counterparty in offer_set.get("counterpartyIds") or []:
            cp_n = add_node("Counterparty", counterparty)
            add_edge("interacts_with", subject_n, cp_n)
            add_edge("participates_in", cp_n, event_n)
            add_edge("depends_on", set_n, cp_n)

        environment = offer_set.get("environmentId")
        if environment:
            env_n = add_node("Environment", environment)
            add_edge("contextualized_by", event_n, env_n)
            add_edge("depends_on", set_n, env_n)

        for offer in offer_set.get("offers") or []:
            offer_id = str(offer.get("projectionId") or "")
            if not offer_id:
                continue
            offer_n = add_node(
                "Offer",
                offer_id,
                market=offer.get("marketCanonicalName"),
                line=offer.get("line"),
            )
            add_edge("contains_offer", set_n, offer_n)
            market_name = str(offer.get("marketCanonicalName") or offer.get("marketRawName") or "")
            if market_name:
                definition_key = f"{sport}|{competition}|{market_name}|{offer.get('period') or ''}"
                definition_n = add_node("MarketDefinition", definition_key, market=market_name)
                add_edge("defined_as", offer_n, definition_n)
                add_edge("depends_on", offer_n, definition_n)

    body = {
        "schema": "pillars_dcm.research_dependency_graph.v1",
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
        "edges": sorted(edges.values(), key=lambda row: (row["type"], row["from"], row["to"])),
        "populationHash": (population or {}).get("contentHash"),
        "reuseLaw": "Research each reusable Sport/Competition/Event/Affiliation/Subject/Counterparty/Environment once, then fan out to dependent offers.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
