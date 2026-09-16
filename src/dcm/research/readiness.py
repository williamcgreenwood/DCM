"""ResearchOSReadiness: the only artifact that may authorize researchMayBegin=true.

AlgorithmExecutionPlan is created with researchMayBegin=false. External
acquisition fails closed until this artifact proves the Research OS
prerequisites exist and are valid.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash


REQUIRED_PREREQS = (
    "boardGraphValid",
    "marketDemandGraphValid",
    "requirementGraphValid",
    "requirementGraphAcyclic",
    "indexesConstructed",
    "reusableEvidenceLookupCompleted",
    "acquisitionActionsCreated",
    "sourceRoutingValid",
)


def evaluate_research_os_readiness(
    *,
    board_graph: Mapping[str, Any] | None,
    market_demand_graph: Mapping[str, Any] | None,
    requirement_graph: Mapping[str, Any] | None,
    indexes_meta: Mapping[str, Any] | None,
    reused_evidence_scopes: int | None,
    acquisition_actions: Mapping[str, Any] | None,
    source_routing: Mapping[str, Any] | None = None,
    research_signal_graph: Mapping[str, Any] | None = None,
    research_only: bool = False,
) -> dict[str, Any]:
    blockers: list[str] = []
    board_ok = bool(board_graph and board_graph.get("contentHash") and int(board_graph.get("nodeCount") or 0) > 0)
    demand_ok = bool(market_demand_graph and market_demand_graph.get("contentHash") and "definitionCount" in market_demand_graph)
    req_ok = bool(requirement_graph and requirement_graph.get("contentHash") and "nodeCount" in requirement_graph)
    acyclic = bool(requirement_graph and requirement_graph.get("topoOk") is True)
    indexes_ok = bool(indexes_meta and indexes_meta.get("contentHash") and int(indexes_meta.get("offerCount") or 0) >= 0)
    evidence_ok = reused_evidence_scopes is not None
    actions_ok = bool(
        isinstance(acquisition_actions, Mapping)
        and acquisition_actions.get("schema")
        and "actionCount" in acquisition_actions
    )
    routing = source_routing if isinstance(source_routing, Mapping) else {}
    routing_ok = bool(routing.get("valid", True)) and "circuitOpenAll" not in set(routing.get("blockers") or [])
    signal = research_signal_graph if isinstance(research_signal_graph, Mapping) else {}
    signal_payload = {key: value for key, value in signal.items() if key != "contentHash"}
    signal_hash_ok = bool(
        signal
        and signal.get("schema") == "pillars_dcm.insight_research_dependency_graph.v1"
        and signal.get("researchOnly") is True
        and int(signal.get("platformOfferCount") or 0) == 0
        and int(signal.get("nodeCount") or 0) > 0
        and int(signal.get("requestCount") or 0) > 0
        and signal.get("productionSelectionPermitted") is False
        and signal.get("contentHash")
        and str(signal.get("contentHash")) == content_hash(signal_payload)
    )
    signal_mode = bool(research_only and signal_hash_ok)

    if not board_ok and not signal_mode:
        blockers.append("BOARD_GRAPH_INVALID")
    if research_only and not signal_hash_ok:
        blockers.append("INSIGHT_RESEARCH_GRAPH_INVALID")
    if not demand_ok:
        blockers.append("MARKET_DEMAND_GRAPH_INVALID")
    if not req_ok:
        blockers.append("REQUIREMENT_GRAPH_INVALID")
    if not acyclic:
        blockers.append("REQUIREMENT_GRAPH_CYCLIC")
    if not indexes_ok:
        blockers.append("INDEXES_NOT_CONSTRUCTED")
    if not evidence_ok:
        blockers.append("REUSABLE_EVIDENCE_LOOKUP_INCOMPLETE")
    if not actions_ok:
        blockers.append("ACQUISITION_ACTIONS_MISSING")
    if not routing_ok:
        blockers.append("SOURCE_ROUTING_INVALID")

    ready = not blockers
    body = {
        "schema": "pillars_dcm.research_os_readiness.v1",
        "researchMayBegin": ready,
        "prerequisites": {
            "boardGraphValid": board_ok,
            "marketDemandGraphValid": demand_ok,
            "requirementGraphValid": req_ok,
            "requirementGraphAcyclic": acyclic,
            "indexesConstructed": indexes_ok,
            "reusableEvidenceLookupCompleted": evidence_ok,
            "acquisitionActionsCreated": actions_ok,
            "sourceRoutingValid": routing_ok,
        },
        "researchMode": "INSIGHTS_RESEARCH_ONLY" if research_only else "BOARD_RESEARCH",
        "researchOnly": bool(research_only),
        "researchSignalGraphValid": signal_hash_ok,
        "boardGraphRequired": not bool(research_only),
        "authorizationBasis": "VALID_INSIGHT_RESEARCH_GRAPH" if signal_mode else "VALID_BOARD_RESEARCH_GRAPH",
        "blockers": blockers,
        "requiredPrerequisites": list(REQUIRED_PREREQS),
        "note": "Only this artifact may authorize researchMayBegin=true. The AlgorithmExecutionPlan is created false.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def persist_research_os_readiness(dest: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "research_os_readiness.json"
    body = dict(payload)
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    plan_path = dest / "algorithm_execution_plan.json"
    if plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["researchMayBegin"] = bool(body.get("researchMayBegin"))
        plan["researchOsReadinessHash"] = body.get("contentHash")
        if body.get("researchMayBegin"):
            notes = list(plan.get("notes") or [])
            notes.append("ResearchOSReadiness authorized researchMayBegin=true.")
            plan["notes"] = notes
        plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return body


def load_research_os_readiness(dest: Path) -> dict[str, Any] | None:
    path = Path(dest) / "research_os_readiness.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def require_research_may_begin(dest: Path) -> dict[str, Any]:
    """Fail closed: external acquisition is illegal without readiness."""
    payload = load_research_os_readiness(dest)
    if not payload or payload.get("researchMayBegin") is not True:
        raise RuntimeError("RESEARCH_MAY_BEGIN_DENIED: ResearchOSReadiness missing or false")
    return payload
