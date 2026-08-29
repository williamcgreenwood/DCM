"""Host-facing research plan for ChatGPT/Codex evidence acquisition.

The deterministic DCM core never performs web browsing. Instead it emits this
plan so a capable host can gather current evidence, write validated EvidenceClaim
files, and resume the exact frozen run.
"""
from __future__ import annotations

from typing import Any


_SCOPE_SPEC: dict[str, dict[str, Any]] = {
    "SPORT": {
        "priority": 1,
        "requiredFields": ["rules_or_distribution_context"],
        "research": [
            "official league/stat rules and current season context",
            "sport-specific stat definitions that affect modeled markets",
        ],
    },
    "EVENT": {
        "priority": 2,
        "requiredFields": ["event_context"],
        "research": [
            "scheduled start time and venue",
            "expected starters/lineup context",
            "weather/roof/surface when materially relevant",
            "rest/travel/schedule context when materially relevant",
        ],
    },
    "TEAM": {
        "priority": 3,
        "requiredFields": ["team_context"],
        "research": [
            "current injuries and depth/rotation changes",
            "team opportunity environment and pace/plays/possessions",
            "opponent strength and matchup context",
        ],
    },
    "PLAYER": {
        "priority": 4,
        "requiredFields": [
            "status",
            "role",
            "role_epoch_logs_min_3",
            "opportunity",
            "efficiency",
        ],
        "research": [
            "current active/inactive status from a current source",
            "current role, starter/bench/depth position and teammate dependencies",
            "role-comparable game logs, preferably enough to support recent and season views",
            "opportunity variables appropriate to the sport",
            "conditional efficiency variables appropriate to the sport",
            "news/sentiment only as contextual evidence, never as a substitute for stats",
        ],
    },
    "MARKET": {
        "priority": 5,
        "requiredFields": ["definition_verified"],
        "research": [
            "exact platform/stat definition for the offered market",
            "current line/offered side/modifier consistency",
            "meaningful line movement when reliable prior observations exist",
        ],
    },
}


def build_host_research_plan(
    requests: list[dict[str, Any]],
    *,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coverage_by_id = {
        str(row.get("requestId")): row
        for row in ((coverage or {}).get("requests") or [])
        if isinstance(row, dict)
    }
    tasks = []
    for request in requests:
        scope = str(request.get("scope") or "")
        spec = _SCOPE_SPEC.get(scope, {"priority": 99, "requiredFields": [], "research": []})
        req_id = str(request.get("request_id") or "")
        cov = coverage_by_id.get(req_id) or {}
        tasks.append(
            {
                "requestId": req_id,
                "scope": scope,
                "scopeId": request.get("scope_id"),
                "need": request.get("need"),
                "forecastCutoff": request.get("forecast_cutoff"),
                "priority": spec["priority"],
                "requiredFields": spec["requiredFields"],
                "researchInstructions": spec["research"],
                "knownMissing": cov.get("missing") or [],
                "complete": bool(cov.get("complete")),
                "outputFile": f"evidence/{req_id}.json",
                "context": {
                    k: v
                    for k, v in request.items()
                    if k not in {"request_id", "scope", "scope_id", "need", "forecast_cutoff"}
                },
            }
        )
    tasks.sort(key=lambda t: (int(t["priority"]), str(t["scope"]), str(t["scopeId"]), str(t["requestId"])))
    return {
        "mode": "HOST_WEB_RESEARCH_REQUIRED",
        "researchHierarchy": ["SPORT", "EVENT", "TEAM", "PLAYER", "MARKET"],
        "reuseRule": "Research each reusable entity once and reuse evidence for all dependent props.",
        "temporalRule": "Every EvidenceClaim observed_at must be <= forecastCutoff.",
        "evidenceContract": {
            "requiredFields": [
                "source_id",
                "url",
                "published_at",
                "observed_at",
                "forecast_cutoff",
                "semantic_scope",
                "scope_id",
                "claim_type",
                "claim_value",
                "reliability",
                "freshness",
                "source_hash",
                "claim_hash",
            ],
            "note": "Use dcm.research.claims.claim_record or identical canonical hashing; never invent hashes.",
        },
        "taskCount": len(tasks),
        "incompleteTaskCount": sum(not task["complete"] for task in tasks),
        "tasks": tasks,
    }
