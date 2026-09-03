"""Canonical Research OS graphs built BEFORE external research.

BoardGraph, MarketDemandGraph, and RequirementGraph reuse existing
grouping/CSR/hypergraph/Union-Find/Tarjan/Kahn primitives. They do not
replace EvidenceGraph.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from dcm.algorithms.graph import build_csr, cycles, dag_or_reject, hypergraph_from_bundles
from dcm.algorithms.grouping import UnionFind, composite_group, connected_components
from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.contracts.hashes import content_hash
from dcm.research.indexes import BoardIndexes
from dcm.research.scopes import SCOPE_RANK, canonical_scope
from dcm.sports.football.research_requirements import MARKET_REQUIREMENTS


SCOPE_PREREQS = {
    "SPORT": (),
    "COMPETITION": ("SPORT",),
    "EVENT": ("COMPETITION",),
    "ENVIRONMENT": ("EVENT",),
    "AFFILIATION": ("EVENT",),
    "COUNTERPARTY": ("EVENT",),
    "SUBJECT": ("EVENT", "AFFILIATION"),
    "MARKET_DEFINITION": ("SPORT", "COMPETITION"),
    "OFFER": ("SUBJECT", "MARKET_DEFINITION", "EVENT"),
}


def _is_cfb(row: Mapping[str, Any]) -> bool:
    return str(row.get("sportFamily") or "") == "gridiron" and str(row.get("league") or "").upper() == "CFB"


def _offer_id(row: Mapping[str, Any]) -> str:
    return str(row.get("projectionId") or "")


def _attach_dependents(requests: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fill dependent_offer_ids via exact composite-key grouping. No per-prop scans later."""
    by_event = composite_group(rows, ("eventId",))
    by_team = composite_group(rows, ("teamId",))
    by_opp = composite_group(rows, ("opponentId",))
    by_player = composite_group(rows, ("playerId",))
    by_league = composite_group(rows, ("sportFamily", "league"))
    by_market = {}
    for row in rows:
        key = (str(row.get("sportFamily") or ""), str(row.get("league") or ""), str(row.get("market") or ""))
        by_market.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for req in requests:
        rec = dict(req)
        scope = canonical_scope(str(rec.get("scope") or ""))
        sid = str(rec.get("scope_id") or "")
        dependents: list[str] = []
        if scope in {"EVENT", "ENVIRONMENT"}:
            event_id = sid[4:] if sid.startswith("env:") else sid
            dependents = [_offer_id(r) for r in by_event.get((event_id,), ()) if _offer_id(r)]
        elif scope == "AFFILIATION":
            dependents = [_offer_id(r) for r in by_team.get((sid,), ()) if _offer_id(r)]
        elif scope == "COUNTERPARTY":
            dependents = [_offer_id(r) for r in by_opp.get((sid,), ()) if _offer_id(r)]
        elif scope == "SUBJECT":
            dependents = [_offer_id(r) for r in by_player.get((sid,), ()) if _offer_id(r)]
        elif scope in {"SPORT", "COMPETITION"}:
            family, league = (sid.split(":", 1) + [""])[:2] if ":" in sid else ("", sid)
            dependents = [_offer_id(r) for r in by_league.get((family, league), ()) if _offer_id(r)]
        elif scope == "MARKET_DEFINITION":
            parts = sid.split("|")
            family = parts[0] if parts else ""
            league = parts[1] if len(parts) > 1 else ""
            market = parts[2] if len(parts) > 2 else ""
            dependents = [_offer_id(r) for r in by_market.get((family, league, market), ()) if _offer_id(r)]
        elif scope == "OFFER":
            dependents = [sid] if sid else []
        rec["dependent_offer_ids"] = list(dict.fromkeys(dependents))
        rec["dependent_prop_count"] = len(rec["dependent_offer_ids"]) or int(rec.get("dependent_prop_count") or 0)
        out.append(rec)
    return out


def build_board_graph(
    rows: list[dict[str, Any]],
    *,
    indexes: BoardIndexes | None = None,
    telemetry: AlgorithmTelemetry | None = None,
) -> dict[str, Any]:
    tel = telemetry or AlgorithmTelemetry()
    indexes = indexes or BoardIndexes(rows, telemetry=tel)
    uf = UnionFind()
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str, str]] = []

    def add_node(kind: str, entity_id: str, **attrs: Any) -> str:
        nid = f"{kind}:{entity_id}"
        rec = nodes.setdefault(nid, {"id": nid, "type": kind, "entityId": entity_id})
        for k, v in attrs.items():
            if v not in (None, "", [], {}) and rec.get(k) in (None, "", [], {}):
                rec[k] = v
        uf.find(nid)
        return nid

    for row in rows:
        oid = _offer_id(row)
        if not oid:
            continue
        offer_n = add_node("Offer", oid, market=row.get("market"), line=row.get("line"), league=row.get("league"), modifier=row.get("modifier"))
        event_n = add_node("Event", str(row.get("eventId") or ""), label=row.get("eventLabel"), status=row.get("status"))
        subject_n = add_node("Subject", str(row.get("playerId") or ""), name=row.get("playerName"), role=row.get("role"))
        aff_n = add_node("Affiliation", str(row.get("teamId") or row.get("team") or ""), name=row.get("team"))
        cp_n = add_node("Counterparty", str(row.get("opponentId") or row.get("opponent") or ""), name=row.get("opponent"))
        mkt_n = add_node("MarketDefinition", str(row.get("market") or ""), league=row.get("league"))
        env_n = add_node("Environment", f"env:{row.get('eventId') or ''}")
        edges.extend(
            [
                ("participates_in", subject_n, event_n),
                ("affiliated_with", subject_n, aff_n),
                ("participates_in", aff_n, event_n),
                ("participates_in", cp_n, event_n),
                ("interacts_with", aff_n, cp_n),
                ("contains_offer", event_n, offer_n),
                ("contains_offer", subject_n, offer_n),
                ("defined_as", offer_n, mkt_n),
                ("contextualized_by", event_n, env_n),
            ]
        )
        # Alias consolidation: same playerId unifies name variants; same normalized name unifies ids.
        name_key = f"ALIAS:{(str(row.get('playerName') or '').strip().lower())}"
        pid_key = f"ALIASID:{row.get('playerId')}"
        uf.union(subject_n, pid_key)
        if str(row.get("playerName") or "").strip():
            uf.union(subject_n, name_key)

    undirected = [(a, b) for _k, a, b in edges]
    components = connected_components(undirected, nodes)
    csr = build_csr((a, b) for _k, a, b in edges)
    adj: dict[str, list[str]] = defaultdict(list)
    for _k, a, b in edges:
        adj[a].append(b)
    sccs = cycles(adj)
    tel.record("ALG-GROUP-001", problem_class="HAR_GROUPING", producer="dcm.research.os_graphs.build_board_graph", consumer="dcm.cfb.launch")
    tel.record("ALG-GROUP-002", problem_class="ENTITY_MERGE", producer="dcm.research.os_graphs.build_board_graph", consumer="dcm.identity.resolve")
    tel.record("ALG-GROUP-003", problem_class="RESEARCH_COMMUNITY", producer="dcm.research.os_graphs.build_board_graph", consumer="dcm.cfb.launch", count=len(components))
    tel.record("ALG-INDEX-012", problem_class="GRAPH_TRAVERSAL", producer="dcm.algorithms.indexing.CSRGraph", consumer="dcm.research.os_graphs.build_board_graph")
    tel.record("ALG-GROUP-004", problem_class="CYCLE_SAFETY", producer="dcm.research.os_graphs.build_board_graph", consumer="dcm.cfb.launch", count=len(sccs) or 1)

    reverse_event = {eid: list(oids) for eid, oids in indexes.by_event.items() if eid}
    reverse_team = {tid: list(oids) for tid, oids in indexes.by_affiliation.items() if tid}
    reverse_subject = {sid: list(oids) for sid, oids in indexes.by_subject.items() if sid}
    body = {
        "schema": "pillars_dcm.board_graph.v1",
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "componentCount": len(components),
        "cycleCount": len(sccs),
        "csrForwardDegree": {k: len(v) for k, v in list(csr.forward.items())[:64]},
        "nodes": sorted(nodes.values(), key=lambda r: r["id"]),
        "edges": [{"type": t, "from": a, "to": b} for t, a, b in sorted(edges)],
        "aliasComponents": {str(k): [str(x) for x in v if str(x).startswith(("Subject:", "ALIAS:"))] for k, v in uf.components().items() if any(str(x).startswith("Subject:") for x in v)},
        "reverseIndexes": {
            "eventToOffers": reverse_event,
            "affiliationToOffers": reverse_team,
            "subjectToOffers": reverse_subject,
            "marketToOffers": {m: list(oids) for m, oids in indexes.by_market.items() if m},
        },
        "cfbOfferIds": list(indexes.by_league.get("CFB") or []),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def build_market_demand_graph(
    rows: list[dict[str, Any]],
    *,
    telemetry: AlgorithmTelemetry | None = None,
) -> dict[str, Any]:
    tel = telemetry or AlgorithmTelemetry()
    groups = composite_group(rows, ("sportFamily", "league", "market"))
    bundles: dict[str, list[str]] = {}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for key, group in groups.items():
        family, league, market = (str(key[0]), str(key[1]).upper(), str(key[2]).lower())
        def_id = f"MarketDefinition:{family}|{league}|{market}"
        offer_ids = [_offer_id(r) for r in group if _offer_id(r)]
        bundles[def_id] = offer_ids
        supported = league == "CFB" and market in MARKET_REQUIREMENTS
        nodes.append(
            {
                "id": def_id,
                "type": "MarketDefinition",
                "sportFamily": family,
                "league": league,
                "market": market,
                "offerCount": len(offer_ids),
                "guardedLaunchSupported": supported,
                "requirements": dict(MARKET_REQUIREMENTS.get(market) or {}) if supported else None,
            }
        )
        for oid in offer_ids:
            edges.append({"type": "demands", "from": f"Offer:{oid}", "to": def_id})
    hg = hypergraph_from_bundles(bundles)
    tel.record("ALG-GROUP-001", problem_class="HAR_GROUPING", producer="dcm.research.os_graphs.build_market_demand_graph", consumer="dcm.cfb.launch")
    tel.record("ALG-INDEX-014", problem_class="GRAPH_TRAVERSAL", producer="dcm.algorithms.graph.hypergraph_from_bundles", consumer="dcm.research.os_graphs.build_market_demand_graph", count=len(bundles))
    body = {
        "schema": "pillars_dcm.market_demand_graph.v1",
        "nodeCount": len(nodes) + sum(len(v) for v in bundles.values()),
        "definitionCount": len(nodes),
        "edgeCount": len(edges),
        "hyperedges": {k: list(v) for k, v in hg.edge_members.items()},
        "nodes": sorted(nodes, key=lambda r: r["id"]),
        "edges": sorted(edges, key=lambda r: (r["to"], r["from"])),
        "cfbSupportedDefinitions": [n["market"] for n in nodes if n.get("guardedLaunchSupported")],
        "cfbUnsupportedOnBoard": sorted(
            {
                str(r.get("market") or "")
                for r in rows
                if _is_cfb(r) and str(r.get("market") or "").lower() not in MARKET_REQUIREMENTS
            }
        ),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def build_requirement_graph(
    rows: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    *,
    telemetry: AlgorithmTelemetry | None = None,
) -> dict[str, Any]:
    tel = telemetry or AlgorithmTelemetry()
    reqs = _attach_dependents(requests, rows)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str]] = []
    reverse_req_offers: dict[str, list[str]] = {}
    reverse_offer_reqs: dict[str, list[str]] = defaultdict(list)
    by_scope: dict[str, list[str]] = defaultdict(list)

    for rec in reqs:
        rid = str(rec.get("request_id") or "")
        if not rid:
            continue
        scope = canonical_scope(str(rec.get("scope") or ""))
        nid = f"Requirement:{rid}"
        nodes[nid] = {
            "id": nid,
            "requestId": rid,
            "scope": scope,
            "scopeId": rec.get("scope_id"),
            "need": rec.get("need"),
            "dependentOfferCount": rec.get("dependent_prop_count"),
            "dependentOfferIds": rec.get("dependent_offer_ids") or [],
            "hierarchyRank": SCOPE_RANK.get(scope, 99),
        }
        reverse_req_offers[rid] = list(rec.get("dependent_offer_ids") or [])
        for oid in reverse_req_offers[rid]:
            reverse_offer_reqs[oid].append(rid)
        by_scope[scope].append(nid)

    # Prerequisite edges by scope, bound to matching event/affiliation where possible.
    scope_to_nodes = by_scope
    for rec in reqs:
        rid = str(rec.get("request_id") or "")
        scope = canonical_scope(str(rec.get("scope") or ""))
        src = f"Requirement:{rid}"
        extra = rec if isinstance(rec, dict) else {}
        event_id = str(extra.get("eventId") or extra.get("event_id") or "")
        child_offers = set(rec.get("dependent_offer_ids") or [])
        for parent_scope in SCOPE_PREREQS.get(scope, ()):
            for parent_nid in scope_to_nodes.get(parent_scope, ()):
                parent = nodes[parent_nid]
                parent_sid = str(parent.get("scopeId") or "")
                parent_offers = set(parent.get("dependentOfferIds") or [])
                if parent_scope in {"EVENT", "ENVIRONMENT"}:
                    if event_id and parent_sid not in {event_id, f"env:{event_id}"}:
                        continue
                elif parent_scope not in {"SPORT", "COMPETITION"}:
                    if child_offers and parent_offers and child_offers.isdisjoint(parent_offers):
                        continue
                edges.append((parent_nid, src))

    adj: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
    sccs = cycles(adj)
    try:
        layers = dag_or_reject(list(nodes), edges)
        topo_ok = True
    except Exception:
        layers = []
        topo_ok = False
    tel.record("ALG-GROUP-005", problem_class="DEPENDENCY_ORDER", producer="dcm.research.os_graphs.build_requirement_graph", consumer="dcm.research.acquisition", count=len(layers) or 1)
    tel.record("ALG-SORT-008", problem_class="DEPENDENCY_ORDER", producer="dcm.algorithms.sorting.topological_kahn", consumer="dcm.research.os_graphs.build_requirement_graph", count=len(layers) or 1)
    tel.record("ALG-GROUP-004", problem_class="CYCLE_SAFETY", producer="dcm.research.os_graphs.build_requirement_graph", consumer="dcm.research.acquisition", count=len(sccs) or 1)
    tel.record("ALG-INDEX-013", problem_class="HOT_HASH_INDEX", producer="dcm.research.os_graphs.build_requirement_graph", consumer="dcm.research.acquisition", count=len(reverse_req_offers), applicability="APPLICABLE", note="CSC reverse Requirement→Offers")
    tel.record("ALG-INDEX-008", problem_class="HOT_HASH_INDEX", producer="dcm.research.os_graphs.build_requirement_graph", consumer="dcm.research.acquisition", count=1, note="python bitset eligibility")

    body = {
        "schema": "pillars_dcm.requirement_graph.v1",
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "topoOk": topo_ok,
        "cycleCount": len(sccs),
        "topoLayers": layers,
        "nodes": sorted(nodes.values(), key=lambda r: (int(r.get("hierarchyRank") or 99), str(r["id"]))),
        "edges": [{"type": "depends_on", "from": a, "to": b} for a, b in edges],
        "reverseIndexes": {
            "requirementToOffers": reverse_req_offers,
            "offerToRequirements": dict(reverse_offer_reqs),
        },
        "requests": reqs,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def persist_research_os_graphs(
    dest,
    rows: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    *,
    telemetry: AlgorithmTelemetry | None = None,
    indexes: BoardIndexes | None = None,
) -> dict[str, Any]:
    from pathlib import Path
    import json

    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    tel = telemetry or AlgorithmTelemetry()
    indexes = indexes or BoardIndexes(rows, telemetry=tel)
    board_graph = build_board_graph(rows, indexes=indexes, telemetry=tel)
    demand = build_market_demand_graph(rows, telemetry=tel)
    req_graph = build_requirement_graph(rows, requests, telemetry=tel)
    (dest / "board_graph.json").write_text(json.dumps(board_graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "market_demand_graph.json").write_text(json.dumps(demand, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "requirement_graph.json").write_text(json.dumps(req_graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "boardGraph": board_graph,
        "marketDemandGraph": demand,
        "requirementGraph": req_graph,
        "indexes": indexes,
        "telemetry": tel,
    }
