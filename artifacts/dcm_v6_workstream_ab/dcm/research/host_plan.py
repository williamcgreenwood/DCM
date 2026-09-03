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
    "COMPETITION": {
        "priority": 2,
        "requiredFields": ["competition_context"],
        "research": [
            "competition/league/tour/season rules and current context",
        ],
    },
    "EVENT": {
        "priority": 3,
        "requiredFields": ["event_context"],
        "research": [
            "scheduled start time and venue",
            "expected starters/lineup context",
            "weather/roof/surface when materially relevant",
            "rest/travel/schedule context when materially relevant",
        ],
    },
    "ENVIRONMENT": {
        "priority": 4,
        "requiredFields": ["environment_context"],
        "research": [
            "weather/wind/temperature/humidity/roof when material",
            "surface/park/course/track/rink/court effects",
            "altitude or other SportPlugin-declared environmental inputs",
        ],
    },
    "AFFILIATION": {
        "priority": 5,
        "requiredFields": ["affiliation_context"],
        "research": [
            "current injuries and depth/rotation changes",
            "affiliation opportunity environment and pace/plays/possessions",
            "role distribution and season/recent form",
        ],
    },
    "TEAM": {
        "priority": 5,
        "requiredFields": ["team_context"],
        "research": [
            "adapter alias for AFFILIATION; prefer canonical AFFILIATION requests",
            "current injuries and depth/rotation changes",
            "team opportunity environment and pace/plays/possessions",
            "opponent strength and matchup context",
        ],
    },
    "COUNTERPARTY": {
        "priority": 6,
        "requiredFields": ["counterparty_context"],
        "research": [
            "same relevant depth as Affiliation for the interacting entity",
            "opportunities allowed/suppressed against the subject's role/market",
            "direct interaction personnel and scheme/style matchup",
        ],
    },
    "SUBJECT": {
        "priority": 7,
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
    "PLAYER": {
        "priority": 7,
        "requiredFields": [
            "status",
            "role",
            "role_epoch_logs_min_3",
            "opportunity",
            "efficiency",
        ],
        "research": [
            "adapter alias for SUBJECT; prefer canonical SUBJECT requests",
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
        "priority": 8,
        "requiredFields": ["definition_verified"],
        "research": [
            "exact platform/league/board/stat definition, reused across all matching offers",
        ],
    },
    "OFFER": {
        "priority": 9,
        "requiredFields": ["offer_recorded"],
        "research": [
            "projection-specific line, offered sides, modifier, and line history",
        ],
    },
}

_CFB_SCOPE_RESEARCH: dict[str, list[str]] = {
    "EVENT": [
        "CFB: verify scheduled start, event status, venue, home/away, surface/roof, temperature, wind, precipitation and severe-weather risk",
        "CFB: collect consensus spread/game total and meaningful movement when reliably available; use only for workload/game-regime context",
    ],
    "ENVIRONMENT": [
        "CFB: refresh weather close to cutoff; preserve venue/surface facts at longer freshness",
    ],
    "AFFILIATION": [
        "CFB: research team once: 2026 plays/pass attempts/rush attempts/pass yards/rush yards/points plus 2025 system baseline",
        "CFB: identify starting QB, current depth chart, injuries, coordinator/head-coach and major offensive-line/personnel changes",
    ],
    "COUNTERPARTY": [
        "CFB: research opponent once: defensive plays faced, pass/rush attempts and yards allowed, sacks/pressure, turnovers, points/red-zone/explosive context",
        "CFB: include current defensive injuries, depth-chart and coordinator/system changes; shrink tiny 2026 samples toward 2025",
    ],
    "SUBJECT": [
        "CFB: obtain complete 2026 game log to date AND complete 2025 college game log when available; use older college history only when useful and clearly labeled",
        "CFB: verify current school, position, opponent, roster membership, depth-chart role, starter/backup state, injury/availability and transfer history",
        "CFB QB: pass attempts, completions, pass yards/TD/INT, sacks, rush attempts/yards and scrambles/designed rushes when verifiable",
        "CFB RB: carries/rush yards, targets/receptions/receiving yards, snaps/routes/red-zone/goal-line role when verifiable",
        "CFB WR/TE: targets/receptions/receiving yards, routes/snaps/target share/air-yard and red-zone usage when verifiable; never fabricate unavailable advanced fields",
        "CFB transfer/new-role: preserve prior-school production but do not transfer old opportunity share 1:1 into the new offense",
    ],
    "MARKET_DEFINITION": [
        "CFB: verify exact current platform full-game stat definition, overtime/push treatment and any market-specific semantics",
    ],
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
        research_instructions = list(spec["research"])
        if str(request.get("league") or "").upper() == "CFB":
            research_instructions.extend(_CFB_SCOPE_RESEARCH.get(scope, []))
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
                "researchInstructions": research_instructions,
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
