from __future__ import annotations

import pytest

from dcm.research.universal_plan import build_universal_host_research_plan
from dcm.sports.common.research_schema import (
    PRODUCTION_SUPPORTED,
    lookup_research_schema,
    require_research_schema,
)


def test_basketball_and_gridiron_research_schemas_are_complete():
    for sport in ("basketball", "gridiron"):
        schema = require_research_schema(sport)
        assert schema.contract_complete is True
        assert schema.capability_state == PRODUCTION_SUPPORTED
        assert schema.required_participation_fields
        assert schema.required_opportunity_fields
        assert schema.required_efficiency_fields
        assert schema.minimum_support_thresholds["role_comparable_history"] >= 3


def test_unknown_sport_research_schema_fails_closed():
    assert lookup_research_schema("unknown_sport") is None
    with pytest.raises(LookupError, match="SPORT_RESEARCH_SCHEMA_UNSUPPORTED"):
        require_research_schema("unknown_sport")


def test_universal_sports_have_explicit_research_contracts():
    sports = (
        "australian_rules", "baseball", "combat", "cricket", "esports", "golf",
        "handball", "hockey", "lacrosse", "motorsport", "racket", "rugby",
        "soccer", "volleyball", "darts",
    )
    for sport in sports:
        schema = require_research_schema(sport)
        assert schema.contract_complete is True
        assert schema.capability_state == "RESEARCH_ONLY"
        assert schema.minimum_support_thresholds["role_comparable_history"] >= 3
        assert "participation_units" not in schema.required_participation_fields


def test_universal_host_plan_includes_sport_specific_subject_requirements():
    population = {
        "fanOut": [
            {
                "entityType": "SUBJECT",
                "entityId": "P1",
                "dependentOfferCount": 9,
                "fanOutPriority": 6.75,
                "sportId": "basketball",
                "competitionId": "WNBA",
                "eventId": "E1",
                "subjectId": "P1",
                "subjectType": "PLAYER",
            },
            {
                "entityType": "SUBJECT",
                "entityId": "D1",
                "dependentOfferCount": 1,
                "fanOutPriority": 0.75,
                "sportId": "motorsport",
                "competitionId": "F1",
                "eventId": "RACE1",
                "subjectId": "D1",
                "subjectType": "DRIVER",
            },
        ]
    }
    plan = build_universal_host_research_plan(population)
    basketball = next(t for t in plan["tasks"] if t["entityId"] == "P1")
    assert basketball["sportResearchSchemaState"] == PRODUCTION_SUPPORTED
    assert any(source["sourceId"] == "official_wnba" for source in basketball["sourceCandidates"])
    requirements = basketball["sportSpecificRequirements"]
    assert "minutes" in requirements["participation"]
    assert requirements["minimumSupport"]["role_comparable_history"] >= 3

    motorsport = next(t for t in plan["tasks"] if t["entityId"] == "D1")
    assert motorsport["sportResearchSchemaState"] == "RESEARCH_ONLY"
    assert motorsport["sportResearchSchemaVersion"]
    assert motorsport["sportProfile"]["worldKind"] == "RaceWorld"
    assert motorsport["sportProfile"]["harvestStrategy"].startswith("session_classification")
    assert motorsport["sportSpecificRequirements"]["minimumSupport"]["role_comparable_history"] >= 3
    assert any(source["sourceId"] == "generic_web_search" for source in motorsport["sourceCandidates"])
    assert plan["sourceCatalogVersion"] == "2026-09-12"
    assert plan["sourceCatalogHash"]


def test_alias_sports_resolve_to_native_research_contracts():
    assert require_research_schema("F1").sport_id == "motorsport"
    assert require_research_schema("tennis").sport_id == "racket"
    assert require_research_schema("boxing").sport_id == "combat"


def test_research_contracts_preserve_sport_native_gray_areas():
    assert "goalie_confirmation" in require_research_schema("hockey").required_participation_fields
    assert "tee_wave_weather" in require_research_schema("golf").required_event_context
    assert "dls_risk" in require_research_schema("cricket").required_event_context
    assert "checkout_conversion" in require_research_schema("darts").required_efficiency_fields
    assert "confirmed_lineup" in require_research_schema("soccer").required_participation_fields
