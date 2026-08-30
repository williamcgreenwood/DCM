"""Host-facing research plan: bundle-oriented entity graph, not one-file-per-request.

The deterministic DCM core never performs web browsing. The host writes a
single evidence_bundle.jsonl keyed by (scope, scope_id), then resumes.
"""
from __future__ import annotations

from typing import Any

from dcm.research.requests import SCOPE_ORDER

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
        "priority": 99,
        "requiredFields": ["definition_verified"],
        "research": [
            "legacy MARKET is a migration fallback only; prefer MARKET_DEFINITION + OFFER",
        ],
    },
    "MARKET_DEFINITION": {
        "priority": 5,
        "requiredFields": ["definition_verified"],
        "research": [
            "exact platform/league/board/stat definition, reused across all matching offers",
        ],
    },
    "OFFER": {
        "priority": 6,
        "requiredFields": ["offer_recorded"],
        "research": [
            "projection-specific line, offered sides, modifier, and line history",
        ],
    },
}


def build_host_research_plan(
    requests: list[dict[str, Any]],
    *,
    coverage: dict[str, Any] | None = None,
    skipped: dict[str, Any] | None = None,
    entity_graph: dict[str, Any] | None = None,
    unique_scopes: dict[str, int] | None = None,
    eligible_prop_count: int = 0,
    research_shadow: bool = False,
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
                "priorityScore": request.get("priority_score"),
                "dependentPropCount": request.get("dependent_prop_count"),
                "requiredFields": spec["requiredFields"],
                "researchInstructions": spec["research"],
                "knownMissing": cov.get("missing") or [],
                "complete": bool(cov.get("complete")),
                "bundleKey": {"scope": scope, "scopeId": request.get("scope_id")},
                "context": {
                    k: v
                    for k, v in request.items()
                    if k
                    not in {
                        "request_id",
                        "scope",
                        "scope_id",
                        "need",
                        "forecast_cutoff",
                        "priority_score",
                        "dependent_prop_count",
                        "hierarchy_rank",
                    }
                },
            }
        )
    # Hierarchy first, then fan-out score. Never alphabetical-by-scopeId as the primary key.
    tasks.sort(
        key=lambda t: (
            int(t["priority"]),
            -float(t.get("priorityScore") or 0.0),
            str(t.get("scopeId") or ""),
            str(t.get("requestId") or ""),
        )
    )
    scope_counts: dict[str, int] = {name: 0 for name in SCOPE_ORDER}
    for task in tasks:
        scope_counts[str(task["scope"])] = scope_counts.get(str(task["scope"]), 0) + 1
    if unique_scopes:
        for k, v in unique_scopes.items():
            scope_counts[str(k)] = int(v)
    return {
        "mode": "HOST_WEB_RESEARCH_REQUIRED",
        "orientation": "BUNDLE",
        "bundleFile": "evidence_bundle.jsonl",
        "oneFilePerRequest": False,
        "researchHierarchy": list(SCOPE_ORDER),
        "reuseRule": "Research each reusable entity once and reuse evidence for all dependent props.",
        "temporalRule": "Every EvidenceClaim observed_at must be <= forecastCutoff.",
        "priorityFormula": (
            "number_of_dependent_props × production_capability_weight × "
            "information_importance × freshness_need"
        ),
        "legacyMarket": "migration_fallback_only",
        "researchShadow": bool(research_shadow),
        "eligiblePropCount": int(eligible_prop_count),
        "skippedClasses": {
            "goblin": int((skipped or {}).get("goblin") or 0),
            "unsupported_sport": int((skipped or {}).get("unsupported_sport") or 0),
            "live_or_in_progress": int((skipped or {}).get("live_or_in_progress") or 0),
            "side_unknown": int((skipped or {}).get("side_unknown") or 0),
            "unsupported_market": int((skipped or {}).get("unsupported_market") or 0),
            "shadow": int((skipped or {}).get("shadow") or 0),
            "shadow_researched": int((skipped or {}).get("shadow_researched") or 0),
            "unresolved_other": int((skipped or {}).get("unresolved_other") or 0),
            "model_eligible": int((skipped or {}).get("model_eligible") or 0),
        },
        "uniqueScopes": scope_counts,
        "entityGraph": entity_graph or {},
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
            "note": (
                "Write validated claims into evidence_bundle.jsonl keyed by "
                "(semantic_scope, scope_id). Use dcm.research.claims.claim_record "
                "or identical canonical hashing; never invent hashes. "
                "Do not emit one file per request."
            ),
        },
        "taskCount": len(tasks),
        "incompleteTaskCount": sum(not task["complete"] for task in tasks),
        "tasks": tasks,
    }
