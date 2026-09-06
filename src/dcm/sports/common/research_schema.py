"""SportResearchSchema registry.

The universal core asks which evidence families are required; each sport
defines the sport-specific fields and thresholds. Unknown sports fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PRODUCTION_SUPPORTED = "PRODUCTION_SUPPORTED"
SHADOW_SUPPORTED = "SHADOW_SUPPORTED"
RESEARCH_ONLY = "RESEARCH_ONLY"
UNSUPPORTED_FAIL_CLOSED = "UNSUPPORTED_FAIL_CLOSED"


@dataclass(frozen=True)
class SportResearchSchema:
    sport_id: str
    schema_version: str
    capability_state: str
    required_identity_fields: tuple[str, ...]
    required_historical_fields: tuple[str, ...]
    required_participation_fields: tuple[str, ...]
    required_opportunity_fields: tuple[str, ...]
    required_efficiency_fields: tuple[str, ...]
    required_affiliation_context: tuple[str, ...]
    required_counterparty_context: tuple[str, ...]
    required_event_context: tuple[str, ...]
    optional_advanced_fields: tuple[str, ...] = ()
    availability_requirements: tuple[str, ...] = ()
    minimum_support_thresholds: dict[str, int] = field(default_factory=dict)
    normalization_rules: tuple[str, ...] = ()
    source_preference_hierarchy: tuple[str, ...] = ()
    freshness_requirements: dict[str, str] = field(default_factory=dict)

    def validate_contract(self) -> list[str]:
        missing: list[str] = []
        required_collections = {
            "required_identity_fields": self.required_identity_fields,
            "required_historical_fields": self.required_historical_fields,
            "required_participation_fields": self.required_participation_fields,
            "required_opportunity_fields": self.required_opportunity_fields,
            "required_efficiency_fields": self.required_efficiency_fields,
            "required_event_context": self.required_event_context,
            "availability_requirements": self.availability_requirements,
            "normalization_rules": self.normalization_rules,
            "source_preference_hierarchy": self.source_preference_hierarchy,
        }
        if not self.sport_id:
            missing.append("sport_id")
        if not self.schema_version:
            missing.append("schema_version")
        if self.capability_state not in {
            PRODUCTION_SUPPORTED,
            SHADOW_SUPPORTED,
            RESEARCH_ONLY,
            UNSUPPORTED_FAIL_CLOSED,
        }:
            missing.append("capability_state")
        for name, values in required_collections.items():
            if not values:
                missing.append(name)
        if int(self.minimum_support_thresholds.get("role_comparable_history", 0)) <= 0:
            missing.append("minimum_support_thresholds.role_comparable_history")
        return missing

    @property
    def contract_complete(self) -> bool:
        return not self.validate_contract()

    def subject_requirements(self) -> dict[str, Any]:
        return {
            "identity": list(self.required_identity_fields),
            "historical": list(self.required_historical_fields),
            "participation": list(self.required_participation_fields),
            "opportunity": list(self.required_opportunity_fields),
            "efficiency": list(self.required_efficiency_fields),
            "availability": list(self.availability_requirements),
            "minimumSupport": dict(self.minimum_support_thresholds),
            "normalizationRules": list(self.normalization_rules),
            "sourcePreferenceHierarchy": list(self.source_preference_hierarchy),
            "freshnessRequirements": dict(self.freshness_requirements),
        }

    def context_requirements(self) -> dict[str, Any]:
        return {
            "affiliation": list(self.required_affiliation_context),
            "counterparty": list(self.required_counterparty_context),
            "event": list(self.required_event_context),
            "optionalAdvanced": list(self.optional_advanced_fields),
        }


REGISTRY: dict[str, SportResearchSchema] = {}


def register_research_schema(schema: SportResearchSchema) -> None:
    errors = schema.validate_contract()
    if errors:
        raise ValueError(
            f"INCOMPLETE_SPORT_RESEARCH_SCHEMA:{schema.sport_id}:" + ",".join(errors)
        )
    REGISTRY[schema.sport_id] = schema


def lookup_research_schema(sport_id: str) -> SportResearchSchema | None:
    return REGISTRY.get(str(sport_id or "").strip().lower())


def require_research_schema(sport_id: str) -> SportResearchSchema:
    schema = lookup_research_schema(sport_id)
    if schema is None:
        raise LookupError(f"SPORT_RESEARCH_SCHEMA_UNSUPPORTED:{sport_id}")
    return schema


register_research_schema(
    SportResearchSchema(
        sport_id="basketball",
        schema_version="BASKETBALL_RESEARCH_V1_2026-08-31",
        capability_state=PRODUCTION_SUPPORTED,
        required_identity_fields=("subjectId", "subjectName", "competitionId", "eventId"),
        required_historical_fields=("game_logs", "game_date", "opponent", "minutes"),
        required_participation_fields=("status", "role", "minutes"),
        required_opportunity_fields=("fga", "three_point_attempts", "fta", "rebound_or_assist_opportunity_inputs"),
        required_efficiency_fields=("shooting_conversion", "rebound_conversion", "assist_conversion"),
        required_affiliation_context=("pace_or_possessions", "offensive_context", "defensive_context", "availability"),
        required_counterparty_context=("defensive_context", "pace_or_possessions", "availability"),
        required_event_context=("scheduled_start", "event_status", "venue_or_environment"),
        optional_advanced_fields=("lineup", "on_off", "usage", "travel", "rest"),
        availability_requirements=("official_or_high_authority_status", "role_or_starter_state"),
        minimum_support_thresholds={
            "role_comparable_history": 3,
            "recent_window": 3,
        },
        normalization_rules=(
            "minutes must be numeric and nonnegative",
            "2PA = FGA - 3PA when components are present",
            "recent windows derive from chronological full history",
            "do not fabricate missing attempts/conversion denominators",
        ),
        source_preference_hierarchy=("official", "historical_stats_authority", "reputable_status_news", "platform_offer"),
        freshness_requirements={
            "status": "same_event_day_or_newer_when_available",
            "lineup": "latest_pre_cutoff",
            "historical_game": "immutable_after_official_final",
        },
    )
)

register_research_schema(
    SportResearchSchema(
        sport_id="gridiron",
        schema_version="GRIDIRON_RESEARCH_V1_2026-08-31",
        capability_state=PRODUCTION_SUPPORTED,
        required_identity_fields=("subjectId", "subjectName", "competitionId", "eventId"),
        required_historical_fields=("game_logs", "game_date", "opponent"),
        required_participation_fields=("status", "role", "snaps_or_role_opportunity"),
        required_opportunity_fields=("dropbacks_or_pass_attempts", "carries", "targets_or_routes_when_applicable"),
        required_efficiency_fields=("completion_or_catch_conversion", "yardage_efficiency"),
        required_affiliation_context=("plays_or_pace", "depth_or_injury_context"),
        required_counterparty_context=("pass_defense", "rush_defense"),
        required_event_context=("scheduled_start", "event_status", "surface_or_weather"),
        optional_advanced_fields=("routes", "first_read_share", "red_zone_role", "travel", "rest"),
        availability_requirements=("official_or_high_authority_status", "depth_role"),
        minimum_support_thresholds={
            "role_comparable_history": 3,
            "recent_window": 3,
        },
        normalization_rules=(
            "do not infer routes from targets",
            "pass/rush/receiving opportunity units remain distinct",
            "recent windows derive from chronological full history",
            "preseason rotation and regular-season role are not interchangeable",
        ),
        source_preference_hierarchy=("official", "historical_stats_authority", "depth_status_authority", "platform_offer"),
        freshness_requirements={
            "status": "same_event_day_or_newer_when_available",
            "depth": "latest_pre_cutoff",
            "weather": "latest_material_pre_cutoff",
            "historical_game": "immutable_after_official_final",
        },
    )
)
