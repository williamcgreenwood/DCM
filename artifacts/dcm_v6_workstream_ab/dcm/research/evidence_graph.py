"""Canonical universal EvidenceGraph.

Evidence transport may still contain legacy PLAYER/TEAM semantic scopes while
sport adapters migrate.  This graph translates those scopes at the boundary;
the canonical graph itself contains Subject/Affiliation/Counterparty, never
Player/Team nodes.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from dcm.contracts.hashes import content_hash
from dcm.research.classify import market_definition_id


NODE_TYPES = (
    "SourceDocument",
    "EvidenceClaim",
    "Sport",
    "Competition",
    "Event",
    "Affiliation",
    "Subject",
    "Counterparty",
    "Environment",
    "MarketDefinition",
    "Offer",
    "NormalizedStat",
    "Feature",
    "RoleState",
    "ParticipationState",
    "OpportunityState",
    "EfficiencyState",
    "ParameterSnapshot",
    "Simulation",
    "PropEvaluation",
    "Selection",
    "Forecast",
    "Settlement",
    "LearningObservation",
)
EDGE_TYPES = (
    "supports",
    "derived_from",
    "applies_to",
    "conflicts_with",
    "member_of",
    "interacts_with",
    "feeds",
    "produces",
    "selects",
    "settles",
)


def _nid(kind: str, *parts: Any) -> str:
    joined = "|".join(str(p) for p in parts if p is not None and str(p) != "")
    return f"{kind}:{joined}" if joined else f"{kind}:unknown"


def _node(node_id: str, node_type: str, **attrs: Any) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, **attrs}


def _edge(edge_type: str, src: str, dst: str, **attrs: Any) -> dict[str, Any]:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"UNKNOWN_EDGE_TYPE:{edge_type}")
    return {"type": edge_type, "from": src, "to": dst, **attrs}


def _canonical_set(offer_set: dict[str, Any]) -> dict[str, Any]:
    """Accept canonical SubjectOfferSet or legacy PlayerOfferSet."""
    if offer_set.get("subjectId"):
        return {
            "subjectId": offer_set.get("subjectId"),
            "subjectType": offer_set.get("subjectType") or "OTHER",
            "subjectName": offer_set.get("subjectName"),
            "sportId": offer_set.get("sportId"),
            "competitionId": offer_set.get("competitionId"),
            "affiliationId": offer_set.get("affiliationId"),
            "counterpartyIds": list(offer_set.get("counterpartyIds") or []),
            "environmentId": offer_set.get("environmentId"),
            "eventId": offer_set.get("eventId"),
            "eventLabel": offer_set.get("eventLabel"),
            "eventStart": offer_set.get("eventStart"),
            "offers": list(offer_set.get("offers") or []),
        }
    opponent = offer_set.get("opponent")
    return {
        "subjectId": offer_set.get("playerId"),
        "subjectType": "PLAYER",
        "subjectName": offer_set.get("playerName"),
        "sportId": offer_set.get("sportFamily"),
        "competitionId": offer_set.get("league"),
        "affiliationId": offer_set.get("team"),
        "counterpartyIds": [opponent] if opponent else [],
        "environmentId": offer_set.get("environmentId"),
        "eventId": offer_set.get("eventId"),
        "eventLabel": offer_set.get("eventLabel"),
        "eventStart": offer_set.get("eventStartTime"),
        "offers": list(offer_set.get("offers") or []),
    }


def _offer_market(offer: dict[str, Any]) -> Any:
    return offer.get("marketCanonicalName") or offer.get("market")


def _offer_period(offer: dict[str, Any]) -> Any:
    return offer.get("period") or offer.get("boardId") or "FULL_GAME"


def build_evidence_graph(
    claims: list[dict[str, Any]],
    offer_sets: list[dict[str, Any]] | None = None,
    packets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    canonical_sets = [_canonical_set(s) for s in (offer_sets or []) if isinstance(s, dict)]

    def add_node(node: dict[str, Any]) -> str:
        nid = str(node["id"])
        if nid not in nodes:
            nodes[nid] = node
        else:
            for k, v in node.items():
                if k == "id":
                    continue
                if v is not None and nodes[nid].get(k) in (None, "", [], {}):
                    nodes[nid][k] = v
        return nid

    # Create canonical entity context before attaching claims.
    for offer_set in canonical_sets:
        subject_id = str(offer_set.get("subjectId") or "")
        event_id = str(offer_set.get("eventId") or "")
        sport_id = str(offer_set.get("sportId") or "")
        competition_id = str(offer_set.get("competitionId") or "")
        if not subject_id:
            continue

        subject_nid = add_node(_node(
            _nid("Subject", subject_id),
            "Subject",
            subjectId=subject_id,
            subjectType=offer_set.get("subjectType"),
            subjectName=offer_set.get("subjectName"),
        ))
        sport_nid = None
        competition_nid = None
        if sport_id:
            sport_nid = add_node(_node(_nid("Sport", sport_id), "Sport", sportId=sport_id))
        if competition_id:
            competition_nid = add_node(_node(
                _nid("Competition", sport_id, competition_id),
                "Competition",
                competitionId=competition_id,
                sportId=sport_id,
            ))
            if sport_nid:
                edges.append(_edge("member_of", competition_nid, sport_nid))
        event_nid = None
        if event_id:
            event_nid = add_node(_node(
                _nid("Event", event_id),
                "Event",
                eventId=event_id,
                eventLabel=offer_set.get("eventLabel"),
                eventStart=offer_set.get("eventStart"),
            ))
            edges.append(_edge("applies_to", subject_nid, event_nid))
            if competition_nid:
                edges.append(_edge("member_of", event_nid, competition_nid))

        affiliation = str(offer_set.get("affiliationId") or "")
        if affiliation:
            aff_nid = add_node(_node(
                _nid("Affiliation", affiliation),
                "Affiliation",
                affiliationId=affiliation,
                competitionId=competition_id,
            ))
            edges.append(_edge("applies_to", subject_nid, aff_nid))
            if event_nid:
                edges.append(_edge("applies_to", aff_nid, event_nid))

        for cp in offer_set.get("counterpartyIds") or []:
            cp_id = str(cp or "")
            if not cp_id:
                continue
            cp_nid = add_node(_node(_nid("Counterparty", cp_id), "Counterparty", counterpartyId=cp_id))
            edges.append(_edge("interacts_with", subject_nid, cp_nid))
            if event_nid:
                edges.append(_edge("applies_to", cp_nid, event_nid))

        environment = str(offer_set.get("environmentId") or "")
        if environment:
            env_nid = add_node(_node(_nid("Environment", environment), "Environment", environmentId=environment))
            if event_nid:
                edges.append(_edge("applies_to", event_nid, env_nid))

        for offer in offer_set.get("offers") or []:
            pid = str(offer.get("projectionId") or "")
            if not pid:
                continue
            market = _offer_market(offer)
            offer_nid = add_node(_node(
                _nid("Offer", pid),
                "Offer",
                projectionId=pid,
                market=market,
                line=offer.get("line"),
                modifier=offer.get("modifier"),
                subjectId=subject_id,
                eventId=event_id,
            ))
            def_id = market_definition_id({
                "sportFamily": sport_id,
                "league": competition_id,
                "market": market,
                "boardId": _offer_period(offer),
            })
            def_nid = add_node(_node(
                _nid("MarketDefinition", def_id),
                "MarketDefinition",
                definitionId=def_id,
                market=market,
                competitionId=competition_id,
                period=_offer_period(offer),
            ))
            edges.append(_edge("applies_to", subject_nid, offer_nid))
            edges.append(_edge("applies_to", offer_nid, def_nid))
            if event_nid:
                edges.append(_edge("applies_to", offer_nid, event_nid))

    # Evidence claims and source documents.
    for claim in claims or []:
        if not isinstance(claim, dict):
            continue
        url = str(claim.get("url") or "")
        source_id = str(claim.get("source_id") or "")
        src_nid = _nid("SourceDocument", claim.get("source_hash") or source_id or url)
        add_node(_node(
            src_nid,
            "SourceDocument",
            sourceId=source_id,
            url=url,
            hostname=urlsplit(url).hostname or "",
            publishedAt=claim.get("published_at"),
            observedAt=claim.get("observed_at"),
            sourceHash=claim.get("source_hash"),
        ))
        claim_nid = _nid("EvidenceClaim", claim.get("claim_hash") or claim.get("claim_type"))
        add_node(_node(
            claim_nid,
            "EvidenceClaim",
            claimHash=claim.get("claim_hash"),
            claimType=claim.get("claim_type"),
            semanticScope=claim.get("semantic_scope"),
            scopeId=claim.get("scope_id"),
            url=url,
        ))
        edges.append(_edge("derived_from", claim_nid, src_nid))
        edges.append(_edge("supports", src_nid, claim_nid, via="source_document"))

        scope = str(claim.get("semantic_scope") or "").upper()
        scope_id = str(claim.get("scope_id") or "")
        targets: list[str] = []
        if scope in {"SUBJECT", "PLAYER"} and scope_id:
            targets.append(add_node(_node(_nid("Subject", scope_id), "Subject", subjectId=scope_id)))
        elif scope in {"AFFILIATION", "TEAM"} and scope_id:
            # TEAM is a compatibility scope. Attach the same evidence to each
            # universal role in which this entity appears.
            if any(str(s.get("affiliationId") or "") == scope_id for s in canonical_sets):
                targets.append(add_node(_node(_nid("Affiliation", scope_id), "Affiliation", affiliationId=scope_id)))
            if any(scope_id in [str(x) for x in (s.get("counterpartyIds") or [])] for s in canonical_sets):
                targets.append(add_node(_node(_nid("Counterparty", scope_id), "Counterparty", counterpartyId=scope_id)))
            if not targets:
                targets.append(add_node(_node(_nid("Affiliation", scope_id), "Affiliation", affiliationId=scope_id)))
        elif scope == "COUNTERPARTY" and scope_id:
            targets.append(add_node(_node(_nid("Counterparty", scope_id), "Counterparty", counterpartyId=scope_id)))
        elif scope == "ENVIRONMENT" and scope_id:
            targets.append(add_node(_node(_nid("Environment", scope_id), "Environment", environmentId=scope_id)))
        elif scope == "EVENT" and scope_id:
            targets.append(add_node(_node(_nid("Event", scope_id), "Event", eventId=scope_id)))
        elif scope == "MARKET_DEFINITION" and scope_id:
            targets.append(add_node(_node(_nid("MarketDefinition", scope_id), "MarketDefinition", definitionId=scope_id)))
        elif scope == "OFFER" and scope_id:
            targets.append(add_node(_node(_nid("Offer", scope_id), "Offer", projectionId=scope_id)))
        elif scope in {"SPORT", "COMPETITION"} and scope_id:
            kind = "Sport" if scope == "SPORT" else "Competition"
            targets.append(add_node(_node(_nid(kind, scope_id), kind, scopeId=scope_id)))
        for target in targets:
            edges.append(_edge("supports", claim_nid, target))

        for other in claim.get("conflicts") or []:
            other_nid = _nid("EvidenceClaim", other)
            add_node(_node(other_nid, "EvidenceClaim", claimHash=str(other)))
            edges.append(_edge("conflicts_with", claim_nid, other_nid))

    # Existing sport-specific packets may still be player-shaped. Translate to
    # Subject and keep normalized stat lineage canonical.
    for packet in packets or []:
        ident = packet.get("identity") if isinstance(packet.get("identity"), dict) else {}
        subject_id = str(ident.get("subjectId") or ident.get("playerId") or "")
        if not subject_id:
            continue
        subject_nid = add_node(_node(
            _nid("Subject", subject_id),
            "Subject",
            subjectId=subject_id,
            subjectType=ident.get("subjectType") or "PLAYER",
            packetId=packet.get("packetId"),
            status=packet.get("status"),
        ))
        for i, log in enumerate(packet.get("gameLogs") or []):
            if not isinstance(log, dict):
                continue
            stat_nid = _nid("NormalizedStat", subject_id, "performance", i)
            add_node(_node(
                stat_nid,
                "NormalizedStat",
                subjectId=subject_id,
                values={k: v for k, v in log.items() if k != "raw"},
                index=i,
            ))
            edges.append(_edge("derived_from", stat_nid, subject_nid))
            edges.append(_edge("supports", stat_nid, subject_nid, via="normalized_history"))
        for h in packet.get("sourceHashes") or []:
            src_nid = _nid("SourceDocument", h)
            add_node(_node(src_nid, "SourceDocument", contentHash=h))
            edges.append(_edge("derived_from", subject_nid, src_nid, via="packet"))
        for pid in packet.get("appliesToProjectionIds") or []:
            offer_nid = _nid("Offer", pid)
            add_node(_node(offer_nid, "Offer", projectionId=pid))
            edges.append(_edge("applies_to", subject_nid, offer_nid, via="packet"))

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
        "schema": "pillars_dcm.evidence_graph.v2",
        "canonical": True,
        "legacyScopeCompatibility": ["PLAYER->SUBJECT", "TEAM->AFFILIATION/COUNTERPARTY"],
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
    """Resolve Selection/Offer → Subject → EvidenceClaim → SourceDocument."""
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
            if reverse and edge.get("to") == nid:
                out.append(str(edge.get("from")))
            elif not reverse and edge.get("from") == nid:
                out.append(str(edge.get("to")))
        return out

    offer = nodes.get(offer_nid)
    if offer:
        path.append(offer)
        subjects = [
            nodes[i]
            for i in neighbors(offer_nid, "applies_to", reverse=True)
            if i in nodes and nodes[i].get("type") == "Subject"
        ]
        if subjects:
            subject = subjects[0]
            path.append(subject)
            claims = [
                nodes[i]
                for i in neighbors(subject["id"], "supports", reverse=True)
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
                sources = [
                    nodes[i]
                    for i in neighbors(subject["id"], "derived_from")
                    if i in nodes and nodes[i].get("type") == "SourceDocument"
                ]
                if sources:
                    path.append(sources[0])
                    source_url = sources[0].get("url")
                    resolved = True

    return {
        "projectionId": projection_id,
        "resolved": resolved,
        "sourceUrl": source_url,
        "path": path,
        "nodeTypes": [n.get("type") for n in path],
    }


def _unique_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for edge in edges:
        key = (str(edge.get("type")), str(edge.get("from")), str(edge.get("to")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(edge)
    unique.sort(key=lambda e: (str(e.get("type")), str(e.get("from")), str(e.get("to"))))
    return unique


def attach_runtime_lineage(
    graph: dict[str, Any] | None,
    *,
    features: list[dict[str, Any]] | None = None,
    snapshots: list[dict[str, Any]] | None = None,
    evaluations: list[dict[str, Any]] | None = None,
    selections: list[dict[str, Any]] | None = None,
    run_id: str = "",
    forecast_cutoff: str = "",
    frozen_forecast_hash: str = "",
    settlements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Populate Feature → State → Parameter → Simulation → Selection → Settlement.

    Additive. Research-only graphs remain valid if runtime artifacts are empty.
    Settlement nodes are intended for a sidecar after freeze; passing them here
    does not rewrite frozen forecast bytes by itself.
    """
    graph = dict(graph or {})
    nodes: dict[str, dict[str, Any]] = {}
    for node in graph.get("nodes") or []:
        if isinstance(node, dict) and node.get("id"):
            nodes[str(node["id"])] = dict(node)
    edges: list[dict[str, Any]] = [dict(e) for e in (graph.get("edges") or []) if isinstance(e, dict)]

    def add_node(node: dict[str, Any]) -> str:
        nid = str(node["id"])
        if nid not in nodes:
            nodes[nid] = node
        else:
            for k, v in node.items():
                if k == "id":
                    continue
                if v is not None and nodes[nid].get(k) in (None, "", [], {}):
                    nodes[nid][k] = v
        return nid

    def add_edge(edge_type: str, src: str, dst: str, **attrs: Any) -> None:
        edges.append(_edge(edge_type, src, dst, **attrs))

    for feat in features or []:
        if not isinstance(feat, dict):
            continue
        entity = str(feat.get("entity") or "")
        name = str(feat.get("featureName") or "")
        if not entity or not name:
            continue
        feat_nid = add_node(_node(
            _nid("Feature", entity, name, feat.get("eventId")),
            "Feature",
            entity=entity,
            featureName=name,
            family=feat.get("family"),
            asOf=feat.get("asOf"),
            trainedModel=False,
        ))
        subject_id = entity.split(":", 1)[-1] if ":" in entity else entity
        subject_nid = add_node(_node(_nid("Subject", subject_id), "Subject", subjectId=subject_id))
        add_edge("derived_from", feat_nid, subject_nid, via="feature_store")
        for h in feat.get("sourceHashes") or []:
            src_nid = add_node(_node(_nid("SourceDocument", h), "SourceDocument", contentHash=h))
            add_edge("derived_from", feat_nid, src_nid, via="feature_source")
        for h in feat.get("claimHashes") or []:
            claim_nid = add_node(_node(_nid("EvidenceClaim", h), "EvidenceClaim", claimHash=h))
            add_edge("feeds", claim_nid, feat_nid, via="claim_hash")

    for snap in snapshots or []:
        if not isinstance(snap, dict):
            continue
        subject_id = str(snap.get("playerId") or snap.get("subjectId") or "")
        event_id = str(snap.get("eventId") or "")
        snap_hash = str(snap.get("parameter_snapshot_hash") or "")
        if not snap_hash:
            continue
        snap_nid = add_node(_node(
            _nid("ParameterSnapshot", snap_hash),
            "ParameterSnapshot",
            parameterSnapshotHash=snap_hash,
            subjectId=subject_id,
            eventId=event_id,
            market=snap.get("market"),
        ))
        if subject_id:
            subject_nid = add_node(_node(_nid("Subject", subject_id), "Subject", subjectId=subject_id))
            add_edge("derived_from", snap_nid, subject_nid)
        if event_id:
            event_nid = add_node(_node(_nid("Event", event_id), "Event", eventId=event_id))
            add_edge("applies_to", snap_nid, event_nid)
        layers = snap.get("layers") if isinstance(snap.get("layers"), dict) else {}
        role = snap.get("role_epoch") if isinstance(snap.get("role_epoch"), dict) else {}
        if role or layers.get("subject"):
            role_nid = add_node(_node(
                _nid("RoleState", subject_id, event_id),
                "RoleState",
                subjectId=subject_id,
                eventId=event_id,
                supportN=(role.get("support_n") if role else None),
            ))
            add_edge("feeds", role_nid, snap_nid)
        part = snap.get("participation") if isinstance(snap.get("participation"), dict) else {}
        if part:
            part_nid = add_node(_node(
                _nid("ParticipationState", part.get("inputHash") or subject_id),
                "ParticipationState",
                unit=part.get("unit"),
                source=part.get("source"),
                inputHash=part.get("inputHash"),
                subjectId=subject_id,
            ))
            add_edge("feeds", part_nid, snap_nid, via="participation_before_opportunity")
        opp_hash = str((layers.get("lineage") or {}).get("opportunityInputHash") or snap.get("opportunityInputHash") or "")
        if not opp_hash:
            opp_hash = str((snap.get("parameters") or {}).get("opportunityInputHash") or "")
        if opp_hash:
            opp_nid = add_node(_node(
                _nid("OpportunityState", opp_hash),
                "OpportunityState",
                inputHash=opp_hash,
                subjectId=subject_id,
            ))
            add_edge("feeds", opp_nid, snap_nid)
            if part:
                add_edge("feeds", _nid("ParticipationState", part.get("inputHash") or subject_id), opp_nid)
        eff_hash = str((layers.get("lineage") or {}).get("efficiencyInputHash") or (snap.get("parameters") or {}).get("efficiencyInputHash") or "")
        if eff_hash:
            eff_nid = add_node(_node(
                _nid("EfficiencyState", eff_hash),
                "EfficiencyState",
                inputHash=eff_hash,
                subjectId=subject_id,
            ))
            add_edge("feeds", eff_nid, snap_nid)
        for h in snap.get("evidence_hashes") or []:
            claim_nid = add_node(_node(_nid("EvidenceClaim", h), "EvidenceClaim", claimHash=h))
            add_edge("feeds", claim_nid, snap_nid, via="evidence_hash")

    for ev in evaluations or []:
        if not isinstance(ev, dict):
            continue
        row = ev.get("row") if isinstance(ev.get("row"), dict) else ev
        pid = str(row.get("projectionId") or ev.get("projectionId") or "")
        if not pid:
            continue
        snap = ev.get("parameterSnapshot") if isinstance(ev.get("parameterSnapshot"), dict) else {}
        snap_hash = str(snap.get("parameter_snapshot_hash") or ev.get("parameterSnapshotHash") or "")
        sim_nid = add_node(_node(
            _nid("Simulation", pid),
            "Simulation",
            projectionId=pid,
            eventId=row.get("eventId"),
            worldCount=ev.get("worldCount") or ev.get("nWorlds"),
        ))
        eval_nid = add_node(_node(
            _nid("PropEvaluation", pid),
            "PropEvaluation",
            projectionId=pid,
            grade=ev.get("grade"),
            pHigher=ev.get("pHigher"),
            pLower=ev.get("pLower"),
            pPush=ev.get("pPush"),
        ))
        offer_nid = add_node(_node(_nid("Offer", pid), "Offer", projectionId=pid))
        add_edge("applies_to", eval_nid, offer_nid)
        add_edge("produces", sim_nid, eval_nid)
        if snap_hash:
            snap_nid = add_node(_node(
                _nid("ParameterSnapshot", snap_hash),
                "ParameterSnapshot",
                parameterSnapshotHash=snap_hash,
            ))
            add_edge("feeds", snap_nid, sim_nid)

    forecast_nid = None
    if run_id:
        forecast_nid = add_node(_node(
            _nid("Forecast", run_id),
            "Forecast",
            runId=run_id,
            forecastCutoff=forecast_cutoff,
            frozenForecastHash=frozen_forecast_hash or None,
        ))

    for sel in selections or []:
        if not isinstance(sel, dict):
            continue
        pid = str(sel.get("projectionId") or (sel.get("row") or {}).get("projectionId") or "")
        if not pid:
            continue
        sel_nid = add_node(_node(
            _nid("Selection", pid),
            "Selection",
            projectionId=pid,
            grade=sel.get("grade"),
            selectedSide=sel.get("selectedSide") or sel.get("direction"),
        ))
        add_edge("selects", sel_nid, _nid("Offer", pid))
        add_edge("derived_from", sel_nid, _nid("PropEvaluation", pid))
        if forecast_nid:
            add_edge("produces", forecast_nid, sel_nid)

    for rec in settlements or []:
        if not isinstance(rec, dict):
            continue
        pid = str(rec.get("projectionId") or "")
        if not pid:
            continue
        set_nid = add_node(_node(
            _nid("Settlement", pid, rec.get("settlement") or rec.get("result")),
            "Settlement",
            projectionId=pid,
            result=rec.get("settlement") or rec.get("result"),
            frozenForecastHash=rec.get("frozenForecastHash") or frozen_forecast_hash or None,
        ))
        add_edge("settles", set_nid, _nid("Offer", pid))
        add_edge("settles", set_nid, _nid("Selection", pid))
        if forecast_nid:
            add_edge("settles", set_nid, forecast_nid)
        learn_nid = add_node(_node(
            _nid("LearningObservation", pid),
            "LearningObservation",
            projectionId=pid,
            futureOnly=True,
            doesNotRewriteForecast=True,
            doesNotDecideResearchReuse=True,
        ))
        add_edge("derived_from", learn_nid, set_nid)

    unique_edges = _unique_edges(edges)
    node_list = [nodes[k] for k in sorted(nodes)]
    body = {
        "schema": "pillars_dcm.evidence_graph.v2",
        "canonical": True,
        "runtimeLineage": True,
        "legacyScopeCompatibility": ["PLAYER->SUBJECT", "TEAM->AFFILIATION/COUNTERPARTY"],
        "nodeTypes": list(NODE_TYPES),
        "edgeTypes": list(EDGE_TYPES),
        "nodeCount": len(node_list),
        "edgeCount": len(unique_edges),
        "nodes": node_list,
        "edges": unique_edges,
        "runId": run_id or graph.get("runId"),
        "forecastCutoff": forecast_cutoff or graph.get("forecastCutoff"),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def trace_runtime_lineage(graph: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    """Selection → PropEvaluation → Simulation → ParameterSnapshot → Feature/Claim."""
    base = trace_selection(graph, selection)
    projection_id = base.get("projectionId") or ""
    nodes = {n["id"]: n for n in graph.get("nodes") or [] if isinstance(n, dict)}
    edges = [e for e in graph.get("edges") or [] if isinstance(e, dict)]

    def neighbors(nid: str, *, reverse: bool = False) -> list[str]:
        out = []
        for edge in edges:
            if reverse and edge.get("to") == nid:
                out.append(str(edge.get("from")))
            elif not reverse and edge.get("from") == nid:
                out.append(str(edge.get("to")))
        return out

    extra: list[dict[str, Any]] = []
    sel_nid = _nid("Selection", projection_id)
    eval_nid = _nid("PropEvaluation", projection_id)
    sim_nid = _nid("Simulation", projection_id)
    for nid in (sel_nid, eval_nid, sim_nid):
        if nid in nodes:
            extra.append(nodes[nid])
    if sim_nid in nodes:
        for parent in neighbors(sim_nid, reverse=True):
            if parent in nodes and nodes[parent].get("type") == "ParameterSnapshot":
                extra.append(nodes[parent])
                for gp in neighbors(parent, reverse=True):
                    if gp in nodes and nodes[gp].get("type") in {
                        "Feature", "RoleState", "ParticipationState",
                        "OpportunityState", "EfficiencyState", "EvidenceClaim",
                    }:
                        extra.append(nodes[gp])
    types = list(base.get("nodeTypes") or []) + [n.get("type") for n in extra]
    return {
        **base,
        "runtimePath": extra,
        "runtimeNodeTypes": [n.get("type") for n in extra],
        "lineageNodeTypes": types,
        "hasParameterSnapshot": "ParameterSnapshot" in types,
        "hasSimulation": "Simulation" in types,
    }

