"""SportResearchSchema registry.

The universal core asks which evidence families are required; each sport
defines the sport-specific fields and thresholds. Unknown sports fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dcm.sports.common.catalog import normalize_sport_id


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
    REGISTRY[normalize_sport_id(schema.sport_id)] = schema


def lookup_research_schema(sport_id: str) -> SportResearchSchema | None:
    return REGISTRY.get(normalize_sport_id(sport_id))


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

# These are executable research contracts derived from the Universal Adaptive
# Research OS sport-family requirements.  They intentionally name native
# participation, opportunity, efficiency, matchup and environment concepts;
# a generic ``participation_units`` placeholder is not enough to direct safe
# host research.  RESEARCH_ONLY means facts may be acquired/indexed/reused but
# cannot be promoted into a production forecast until the full SportPlugin
# contract and market/settlement rules are implemented and accepted.
_RESEARCH_ONLY_SPORTS: dict[str, dict[str, tuple[str, ...]]] = {
    "australian_rules": {
        "participation": ("official_status", "selected_side", "position_or_role", "playing_time"),
        "opportunity": ("team_possessions", "inside_50s", "disposal_share", "clearance_opportunities"),
        "efficiency": ("disposals_per_playing_time", "score_involvement_rate", "turnover_rate"),
        "affiliation": ("lineup", "team_possessions", "territory_profile", "injuries"),
        "counterparty": ("opponent_territory", "role_suppression", "matchup_style"),
        "event": ("scheduled_start", "event_status", "venue", "weather", "surface"),
        "advanced": ("center_bounce_role", "kick_in_role", "travel", "rest"),
    },
    "baseball": {
        "participation": ("official_status", "confirmed_lineup_or_starter", "lineup_slot", "pitch_limit"),
        "opportunity": ("plate_appearances", "batters_faced", "pitch_count", "innings", "bullpen_availability"),
        "efficiency": ("handedness_splits", "batted_ball_quality", "contact_or_strikeout_rate", "pitch_efficiency"),
        "affiliation": ("lineup", "starter", "bullpen_state", "team_run_environment"),
        "counterparty": ("opposing_pitcher_or_hitters", "handedness", "pitch_mix_or_batted_ball_matchup"),
        "event": ("scheduled_start", "event_status", "park", "roof_state", "weather"),
        "advanced": ("umpire_when_supportable", "travel", "rest", "park_factors"),
    },
    "combat": {
        "participation": ("bout_status", "weigh_in_status", "scheduled_rounds", "weight_class"),
        "opportunity": ("expected_fight_time", "striking_exchanges", "takedown_attempts", "control_opportunities"),
        "efficiency": ("strike_accuracy_defense", "takedown_accuracy_defense", "submission_rate", "finish_hazard"),
        "affiliation": ("camp", "coach_or_team_change", "weight_class_change"),
        "counterparty": ("opponent_quality", "stance", "reach_size", "style_interaction"),
        "event": ("scheduled_start", "bout_order", "event_status", "venue", "ruleset"),
        "advanced": ("layoff", "travel", "altitude", "late_replacement", "judges_or_referee_when_modeled"),
    },
    "cricket": {
        "participation": ("official_status", "selected_xi", "batting_position", "bowling_role"),
        "opportunity": ("expected_balls_faced", "overs_bowled", "innings_state", "wicket_opportunities"),
        "efficiency": ("strike_rate", "dismissal_rate", "economy_rate", "wicket_rate"),
        "affiliation": ("lineup", "batting_order", "bowling_rotation", "team_form"),
        "counterparty": ("bowling_or_batting_matchup", "handedness", "opponent_quality"),
        "event": ("scheduled_start", "event_status", "format", "pitch_ground", "weather", "dls_risk"),
        "advanced": ("toss_when_pre_cutoff", "travel", "rest", "venue_history"),
    },
    "darts": {
        "participation": ("official_status", "draw_position", "match_format", "scheduled_sets_or_legs"),
        "opportunity": ("expected_legs", "visits", "throws", "checkout_opportunities"),
        "efficiency": ("three_dart_average", "first_nine_average", "rate_180", "checkout_conversion"),
        "affiliation": ("tournament_context", "stage", "schedule_load"),
        "counterparty": ("opponent_scoring_rate", "opponent_checkout_rate", "pace_or_hold_effect"),
        "event": ("scheduled_start", "event_status", "set_leg_format", "throw_order_rules"),
        "advanced": ("recent_format_comparables", "travel", "rest"),
    },
    "esports": {
        "participation": ("roster_status", "starting_status", "role", "map_pool"),
        "opportunity": ("expected_maps", "rounds", "map_time", "objective_opportunities"),
        "efficiency": ("kills_or_assists_per_round", "damage_efficiency", "objective_conversion"),
        "affiliation": ("roster", "team_form", "map_selection", "patch_adaptation"),
        "counterparty": ("opponent_map_pool", "role_matchup", "pace"),
        "event": ("scheduled_start", "event_status", "format", "patch", "server_or_lan"),
        "advanced": ("side_selection", "travel", "roster_change", "latency"),
    },
    "golf": {
        "participation": ("field_status", "withdrawal_status", "tee_time", "wave"),
        "opportunity": ("holes_scheduled", "rounds_survived", "scoring_opportunities", "cut_probability_inputs"),
        "efficiency": ("strokes_gained_components", "birdie_rate", "bogey_avoidance", "putting_conversion"),
        "affiliation": ("tour_field_strength", "caddie_or_equipment_change", "travel"),
        "counterparty": ("field_strength", "matchup_opponent_when_applicable", "course_fit_comparables"),
        "event": ("scheduled_start", "event_status", "course_profile", "tee_wave_weather", "cut_rules"),
        "advanced": ("course_history", "altitude", "grass_type", "withdrawal_risk"),
    },
    "handball": {
        "participation": ("official_status", "lineup", "role", "expected_minutes"),
        "opportunity": ("team_possessions", "shots", "assists_opportunities", "goalkeeper_shots_faced"),
        "efficiency": ("shot_conversion", "assist_conversion", "save_rate", "turnover_rate"),
        "affiliation": ("lineup", "team_pace", "attack_defense_profile", "injuries"),
        "counterparty": ("opponent_pace", "position_suppression", "tactical_matchup"),
        "event": ("scheduled_start", "event_status", "venue", "competition_rules"),
        "advanced": ("travel", "rest", "rotation_change"),
    },
    "hockey": {
        "participation": ("official_status", "line_assignment", "power_play_penalty_kill_role", "projected_ice_time", "goalie_confirmation"),
        "opportunity": ("shifts", "ice_time", "shot_attempts", "power_play_time", "shots_faced"),
        "efficiency": ("shot_on_goal_rate", "shooting_rate", "point_rate", "save_rate"),
        "affiliation": ("lines", "defense_pairs", "goalie", "special_teams", "injuries"),
        "counterparty": ("shot_suppression", "goal_suppression", "special_teams_matchup", "opponent_goalie"),
        "event": ("scheduled_start", "event_status", "venue_type", "travel", "back_to_back"),
        "advanced": ("on_ice_expected_goals", "score_state_role", "last_change"),
    },
    "lacrosse": {
        "participation": ("official_status", "lineup", "role", "playing_time"),
        "opportunity": ("possessions", "shots", "faceoffs", "caused_turnover_opportunities"),
        "efficiency": ("shot_conversion", "assist_rate", "faceoff_rate", "save_rate"),
        "affiliation": ("lineup", "team_possessions", "special_units", "injuries"),
        "counterparty": ("opponent_pace", "position_suppression", "goalie_or_faceoff_matchup"),
        "event": ("scheduled_start", "event_status", "venue", "surface", "weather_when_outdoor"),
        "advanced": ("travel", "rest", "man_up_role"),
    },
    "motorsport": {
        "participation": ("entry_status", "driver_start_status", "grid_position", "session_participation"),
        "opportunity": ("scheduled_laps", "stints", "pit_stop_opportunities", "green_flag_laps"),
        "efficiency": ("race_pace", "qualifying_pace", "sector_times", "pit_stop_efficiency"),
        "affiliation": ("constructor_pace", "reliability", "strategy", "teammate_context"),
        "counterparty": ("field_pace", "track_position", "competitor_strategy"),
        "event": ("session_start", "session_status", "track_profile", "session_weather", "safety_car_regime"),
        "advanced": ("tire_compounds", "degradation", "upgrades", "dnf_hazard"),
    },
    "racket": {
        "participation": ("official_status", "draw", "surface", "best_of_format", "retirement_status"),
        "opportunity": ("expected_sets", "service_points", "return_points", "games"),
        "efficiency": ("hold_break_rate", "ace_rate", "double_fault_rate", "serve_return_points_won"),
        "affiliation": ("tournament_context", "coach_change", "schedule_load"),
        "counterparty": ("opponent_serve_return", "handedness", "surface_style_matchup"),
        "event": ("scheduled_start", "event_status", "surface", "best_of_format", "indoor_outdoor", "weather_when_outdoor"),
        "advanced": ("recent_workload", "injury", "travel", "altitude", "ball_speed"),
    },
    "rugby": {
        "participation": ("official_status", "starting_side", "position", "expected_minutes"),
        "opportunity": ("team_possessions", "carries", "tackles", "kicking_opportunities"),
        "efficiency": ("meters_per_carry", "tackle_rate", "goal_kicking_conversion", "turnover_rate"),
        "affiliation": ("lineup", "team_style", "set_piece_strength", "injuries"),
        "counterparty": ("opponent_style", "position_matchup", "territory_and_possession"),
        "event": ("scheduled_start", "event_status", "venue", "surface", "weather"),
        "advanced": ("travel", "rest", "referee_when_supportable"),
    },
    "soccer": {
        "participation": ("official_status", "start_probability", "confirmed_lineup", "position_role", "expected_minutes"),
        "opportunity": ("team_possession", "touches", "shots", "chances", "passes", "tackles", "shots_faced"),
        "efficiency": ("shot_on_target_rate", "goal_conversion", "chance_creation", "pass_or_tackle_rate", "save_rate"),
        "affiliation": ("formation", "lineup", "possession_attack_profile", "set_piece_penalty_roles"),
        "counterparty": ("tactical_block_or_press", "position_suppression", "opponent_lineup", "goalkeeper_state"),
        "event": ("scheduled_start", "event_status", "competition_rules", "venue", "surface", "weather"),
        "advanced": ("set_piece_role", "penalty_role", "travel", "rest", "rotation_risk"),
    },
    "volleyball": {
        "participation": ("official_status", "starting_rotation", "position_role", "expected_sets"),
        "opportunity": ("rotations", "attacks", "serve_opportunities", "block_opportunities", "reception_opportunities"),
        "efficiency": ("attack_efficiency", "ace_rate", "block_rate", "reception_quality"),
        "affiliation": ("lineup", "rotation", "team_pace", "injuries"),
        "counterparty": ("opponent_block", "serve_receive_matchup", "rotation_matchup"),
        "event": ("scheduled_start", "event_status", "best_of_format", "venue"),
        "advanced": ("travel", "rest", "setter_change"),
    },
}

for _sport_id, _spec in _RESEARCH_ONLY_SPORTS.items():
    register_research_schema(
        SportResearchSchema(
            sport_id=_sport_id,
            schema_version=f"{_sport_id.upper()}_RESEARCH_V1_2026-09-07",
            capability_state=RESEARCH_ONLY,
            required_identity_fields=("subjectId", "subjectName", "competitionId", "eventId"),
            required_historical_fields=("event_logs", "event_date", "counterparty"),
            required_participation_fields=_spec["participation"],
            required_opportunity_fields=_spec["opportunity"],
            required_efficiency_fields=_spec["efficiency"],
            required_affiliation_context=_spec["affiliation"],
            required_counterparty_context=_spec["counterparty"],
            required_event_context=_spec["event"],
            optional_advanced_fields=_spec["advanced"],
            availability_requirements=("official_or_high_authority_status", "role_or_start_state"),
            minimum_support_thresholds={"role_comparable_history": 3, "recent_window": 3},
            normalization_rules=(
                "preserve sport-native units and periods",
                "derive windows from chronological complete history",
                "do not infer participation or efficiency denominators",
                "unknown market semantics fail closed",
            ),
            source_preference_hierarchy=("official", "historical_stats_authority", "reputable_status_news", "platform_offer"),
            freshness_requirements={
                "status": "same_event_day_or_newer_when_available",
                "event": "latest_pre_cutoff",
                "historical_event": "immutable_after_official_final",
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
