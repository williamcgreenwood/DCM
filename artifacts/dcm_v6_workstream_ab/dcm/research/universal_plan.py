"""Host-facing universal research plan derived from canonical population.

This is the vocabulary contract for ChatGPT/Grok/web acquisition.  Provider
adapters may internally translate to legacy scopes until migration completes.
"""
from __future__ import annotations

from typing import Any

from dcm.sports.common.research_schema import lookup_research_schema


ENTITY_ORDER = (
    "SPORT",
    "COMPETITION",
    "EVENT",
    "AFFILIATION",
    "SUBJECT",
    "COUNTERPARTY",
    "ENVIRONMENT",
    "MARKET_DEFINITION",
    "OFFER",
)
ENTITY_RANK = {name: i for i, name in enumerate(ENTITY_ORDER)}

RESEARCH_SCHEMA: dict[str, dict[str, Any]] = {
    "SPORT": {
        "required": ["rules", "stat_semantics"],
        "questions": [
            "What pre-cutoff rules, formats, timing and stat semantics govern this sport?",
            "Which structural resources and primitive outcomes must the active SportPlugin model?",
        ],
    },
    "COMPETITION": {
        "required": ["competition_context"],
        "questions": [
            "What competition/league/tour/season rules and current context materially change the event model?",
        ],
    },
    "EVENT": {
        "required": ["start_status", "event_context"],
        "questions": [
            "What are the official start/status, format, participants and venue/context as of cutoff?",
            "What event-level conditions can materially alter participation, opportunity, efficiency or duration?",
        ],
    },
    "AFFILIATION": {
        "required": ["affiliation_context"],
        "questions": [
            "What current organizational/side context changes the subject's role, participation or opportunity?",
            "What recent and season-level performance context is reusable across dependent subjects?",
        ],
    },
    "SUBJECT": {
        "required": [
            "identity",
            "historical_performances",
            "participation",
            "role",
            "availability",
            "opportunity",
            "efficiency",
        ],
        "questions": [
            "What valid pre-cutoff information can materially alter this subject's offered-stat distribution?",
            "What is the broadest useful historical sample, and which history is role-comparable today?",
            "What are the current participation, role, workload and availability states?",
            "What opportunity and efficiency evidence should be modeled separately?",
        ],
    },
    "COUNTERPARTY": {
        "required": ["counterparty_context"],
        "questions": [
            "Which interacting/opposing entity materially affects the subject, and how?",
            "What matchup evidence is role/stat comparable without over-weighting tiny head-to-head samples?",
        ],
    },
    "ENVIRONMENT": {
        "required": ["environment_context"],
        "questions": [
            "Which venue/weather/surface/course/map/patch conditions materially alter this event's outcomes?",
        ],
    },
    "MARKET_DEFINITION": {
        "required": ["exact_definition"],
        "questions": [
            "What exact statistic, units, period/duration, push, overtime, DNP and reboot semantics define this market?",
        ],
    },
    "OFFER": {
        "required": ["line", "offered_sides", "modifier"],
        "questions": [
            "What exact line, modifier, offered directions, update time and meaningful movement apply to this offer?",
        ],
    },
}


def build_universal_host_research_plan(
    population: dict[str, Any],
    *,
    subject_offer_sets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for row in population.get("fanOut") or []:
        if not isinstance(row, dict):
            continue
        entity_type = str(row.get("entityType") or "")
        if entity_type not in RESEARCH_SCHEMA:
            continue
        spec = RESEARCH_SCHEMA[entity_type]
        sport_id = str(row.get("sportId") or "").strip().lower()
        sport_schema = lookup_research_schema(sport_id) if sport_id else None
        task = {
            "entityType": entity_type,
            "entityId": row.get("entityId"),
            "dependentOfferCount": int(row.get("dependentOfferCount") or 0),
            "priorityScore": row.get("fanOutPriority"),
            "requiredEvidence": list(spec["required"]),
            "researchQuestions": list(spec["questions"]),
            "sportId": row.get("sportId"),
            "competitionId": row.get("competitionId"),
            "eventId": row.get("eventId"),
            "subjectId": row.get("subjectId"),
            "subjectType": row.get("subjectType"),
            "affiliationId": row.get("affiliationId"),
            "sportResearchSchemaState": (
                sport_schema.capability_state if sport_schema is not None else "UNSUPPORTED_FAIL_CLOSED"
            ),
            "sportResearchSchemaVersion": (
                sport_schema.schema_version if sport_schema is not None else None
            ),
        }
        if sport_schema is not None:
            if entity_type == "SUBJECT":
                task["sportSpecificRequirements"] = sport_schema.subject_requirements()
            elif entity_type in {"AFFILIATION", "COUNTERPARTY", "EVENT"}:
                contexts = sport_schema.context_requirements()
                key = {
                    "AFFILIATION": "affiliation",
                    "COUNTERPARTY": "counterparty",
                    "EVENT": "event",
                }[entity_type]
                task["sportSpecificRequirements"] = contexts[key]
        tasks.append(task)
    tasks.sort(
        key=lambda t: (
            ENTITY_RANK.get(str(t.get("entityType") or ""), 99),
            -float(t.get("priorityScore") or 0.0),
            str(t.get("entityId") or ""),
        )
    )
    body = {
        "schema": "pillars_dcm.universal_host_research_plan.v1",
        "canonical": True,
        "researchHierarchy": list(ENTITY_ORDER),
        "taskCount": len(tasks),
        "subjectOfferSetCount": len(subject_offer_sets or []),
        "priorityRule": "dependentOfferCount × informationImportance × freshnessNeed; research reusable entities once.",
        "semanticRule": "No player/team/minutes/etc. concept is required by the universal core; SportPlugin defines applicable fields.",
        "historyRule": "Acquire broad useful history first; derive recent windows from complete history; shrink small role-comparable samples.",
        "temporalRule": "Only evidence known at or before forecast cutoff may enter a frozen forecast.",
        "outputContract": "Structured EvidenceClaims with source lineage; no invented data, sample sizes, status or probability.",
        "tasks": tasks,
    }
    return body
