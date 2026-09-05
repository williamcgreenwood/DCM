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
    assert lookup_research_schema("motorsport") is None
    with pytest.raises(LookupError, match="SPORT_RESEARCH_SCHEMA_UNSUPPORTED"):
        require_research_schema("motorsport")


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
    requirements = basketball["sportSpecificRequirements"]
    assert "minutes" in requirements["participation"]
    assert requirements["minimumSupport"]["role_comparable_history"] >= 3

    motorsport = next(t for t in plan["tasks"] if t["entityId"] == "D1")
    assert motorsport["sportResearchSchemaState"] == "UNSUPPORTED_FAIL_CLOSED"
    assert motorsport["sportResearchSchemaVersion"] is None
    assert "sportSpecificRequirements" not in motorsport
