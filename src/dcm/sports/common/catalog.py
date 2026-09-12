"""Canonical sport-family vocabulary used by ingest, research and plugins.

The universal engine must know *what kind of world* it is researching without
pretending that every world is already modelable.  Profiles therefore describe
stable structural semantics only.  Production/model capability remains owned
by the 24-component :mod:`dcm.sports.common.contract` registry.
"""
from __future__ import annotations

from dataclasses import dataclass

from dcm.contracts.universal_entities import SubjectType


@dataclass(frozen=True)
class SportProfile:
    sport_id: str
    aliases: tuple[str, ...]
    event_structure: str
    segment_structure: str
    default_subject_type: SubjectType
    opportunity_resources: tuple[str, ...]
    world_kind: str
    harvest_strategy: str
    environment_policy: str

    def to_dict(self) -> dict[str, object]:
        return {
            "sportId": self.sport_id,
            "eventStructure": self.event_structure,
            "segmentStructure": self.segment_structure,
            "defaultSubjectType": self.default_subject_type.value,
            "opportunityResources": list(self.opportunity_resources),
            "worldKind": self.world_kind,
            "harvestStrategy": self.harvest_strategy,
            "environmentPolicy": self.environment_policy,
        }


PROFILES: dict[str, SportProfile] = {}
ALIASES: dict[str, str] = {}


def _register(profile: SportProfile) -> None:
    if profile.sport_id in PROFILES:
        raise ValueError(f"DUPLICATE_SPORT_PROFILE:{profile.sport_id}")
    PROFILES[profile.sport_id] = profile
    for token in (profile.sport_id, *profile.aliases):
        key = str(token).strip().lower().replace("-", "_").replace(" ", "_")
        previous = ALIASES.get(key)
        if previous is not None and previous != profile.sport_id:
            raise ValueError(f"AMBIGUOUS_SPORT_ALIAS:{key}:{previous}:{profile.sport_id}")
        ALIASES[key] = profile.sport_id


def normalize_sport_id(value: object) -> str:
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return ALIASES.get(key, key)


def lookup_sport_profile(value: object) -> SportProfile | None:
    return PROFILES.get(normalize_sport_id(value))


def require_sport_profile(value: object) -> SportProfile:
    profile = lookup_sport_profile(value)
    if profile is None:
        raise LookupError(f"SPORT_PROFILE_UNSUPPORTED:{value}")
    return profile


_PROFILE_ROWS = (
    ("gridiron", ("football", "american_football"), "GAME", "quarter", SubjectType.PLAYER,
     ("plays", "dropbacks", "rush_attempts", "routes", "targets"), "EventWorld",
     "schedule_gamebooks_then_both_teams", "OUTDOOR_OR_VENUE_DEPENDENT"),
    ("basketball", ("basketball_5x5",), "GAME", "quarter_or_period", SubjectType.PLAYER,
     ("minutes", "possessions", "shot_attempts", "assist_chances", "rebound_chances"), "EventWorld",
     "schedule_boxscores_then_both_teams", "INDOOR_DEFAULT"),
    ("baseball", ("softball",), "GAME", "inning_or_plate_appearance", SubjectType.PLAYER,
     ("plate_appearances", "batters_faced", "pitches", "innings"), "GameWorld",
     "schedule_game_pages_then_lineups_and_pitchers", "PARK_ROOF_WEATHER_DEPENDENT"),
    ("soccer", ("association_football", "global_football"), "MATCH", "half_or_extra_time", SubjectType.PLAYER,
     ("minutes", "possessions", "touches", "shots", "passes", "set_pieces"), "MatchWorld",
     "competition_match_pages_then_both_squads", "OUTDOOR_OR_VENUE_DEPENDENT"),
    ("hockey", ("ice_hockey",), "GAME", "period", SubjectType.PLAYER,
     ("ice_time", "shifts", "shot_attempts", "power_play_time"), "EventWorld",
     "schedule_game_pages_then_lines_and_goalies", "INDOOR_DEFAULT"),
    ("cricket", (), "MATCH", "innings_over_ball", SubjectType.PLAYER,
     ("balls_faced", "overs_bowled", "wickets", "innings_opportunity"), "MatchWorld",
     "match_scorecards_then_both_sides", "PITCH_GROUND_WEATHER_DEPENDENT"),
    ("combat", ("mma", "ufc", "boxing", "fight_sports"), "BOUT", "round", SubjectType.FIGHTER,
     ("scheduled_rounds", "fight_time", "striking_exchanges", "grappling_exchanges"), "FightWorld",
     "event_card_then_both_fighters_per_bout", "INDOOR_DEFAULT"),
    ("racket", ("tennis", "badminton", "table_tennis", "pickleball"), "MATCH", "set_game_point", SubjectType.TENNIS_PLAYER,
     ("serve_points", "return_points", "games", "sets"), "MatchWorld",
     "tournament_match_pages_then_both_competitors", "SURFACE_AND_VENUE_DEPENDENT"),
    ("golf", ("pga", "lpga"), "TOURNAMENT", "round_hole", SubjectType.GOLFER,
     ("holes", "strokes", "scoring_opportunities"), "CourseWorld",
     "field_leaderboard_round_pages_then_frontier_drilldown", "COURSE_WAVE_WEATHER_DEPENDENT"),
    ("motorsport", ("f1", "formula_1", "nascar", "indycar"), "RACE_WEEKEND", "session_lap_stint", SubjectType.DRIVER,
     ("laps", "stints", "pit_stops", "sector_opportunities"), "RaceWorld",
     "session_classification_for_whole_field_then_driver_drilldown", "TRACK_SESSION_WEATHER_DEPENDENT"),
    ("australian_rules", ("afl", "australian_football"), "GAME", "quarter", SubjectType.PLAYER,
     ("playing_time", "possessions", "entries", "disposals"), "EventWorld",
     "schedule_game_pages_then_both_teams", "OUTDOOR_DEFAULT"),
    ("handball", (), "MATCH", "half", SubjectType.PLAYER,
     ("playing_time", "possessions", "shots", "assists"), "MatchWorld",
     "schedule_match_pages_then_both_teams", "INDOOR_DEFAULT"),
    ("lacrosse", ("lax",), "GAME", "quarter_or_period", SubjectType.PLAYER,
     ("playing_time", "possessions", "shots", "faceoffs"), "EventWorld",
     "schedule_game_pages_then_both_teams", "VENUE_DEPENDENT"),
    ("darts", (), "MATCH", "set_leg_visit", SubjectType.PLAYER,
     ("sets", "legs", "visits", "throws", "checkout_opportunities"), "MatchWorld",
     "tournament_match_pages_then_both_competitors", "NOT_APPLICABLE_DEFAULT"),
    ("rugby", ("rugby_union", "rugby_league"), "MATCH", "half", SubjectType.PLAYER,
     ("playing_time", "possessions", "carries", "tackles"), "MatchWorld",
     "schedule_match_pages_then_both_sides", "OUTDOOR_DEFAULT"),
    ("volleyball", ("beach_volleyball",), "MATCH", "set_rally", SubjectType.PLAYER,
     ("rotations", "rallies", "attacks", "serve_opportunities"), "MatchWorld",
     "tournament_match_pages_then_both_sides", "VENUE_DEPENDENT"),
    ("esports", ("e_sports",), "SERIES", "map_round", SubjectType.ESPORTS_PLAYER,
     ("maps", "rounds", "map_time", "objective_events"), "SeriesWorld",
     "event_series_pages_then_both_rosters", "PATCH_MAP_SERVER_DEPENDENT"),
)

for _row in _PROFILE_ROWS:
    _register(SportProfile(*_row))

