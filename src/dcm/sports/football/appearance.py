"""Football appearance process payload.

Lives inside existing opportunity / regime objects. Not a new schema class.
"""

from __future__ import annotations

from dataclasses import dataclass

from dcm.contracts.immutables import FrozenMap
from dcm.sports.football.registry import CFB_LEAGUE, NFL_LEAGUE, NFLP_LEAGUE


@dataclass(frozen=True)
class FootballAppearanceProcess:
    atom_type: str
    league: str
    eligibility_rule: str
    generation_process: str
    termination_rule: str
    zero_opportunity_paths: tuple[str, ...]
    platform_participation_map: str

    def as_payload(self) -> FrozenMap:
        return FrozenMap({
            "atom_type": self.atom_type,
            "league": self.league,
            "eligibility_rule": self.eligibility_rule,
            "generation_process": self.generation_process,
            "termination_rule": self.termination_rule,
            "zero_opportunity_paths": self.zero_opportunity_paths,
            "platform_participation_map": self.platform_participation_map,
        })


def appearance_process_for(league: str) -> FootballAppearanceProcess:
    if league not in {NFL_LEAGUE, CFB_LEAGUE, NFLP_LEAGUE}:
        raise ValueError(f"unsupported football league: {league}")
    zero = [
        "INACTIVE",
        "DNP",
        "EMERGENCY_QB_NO_SNAP",
        "SPECIALIST_NO_ATTEMPT",
        "BLOWOUT_SIT",
    ]
    if league == NFLP_LEAGUE:
        zero.append("PRESEASON_ROLE_UNSTABLE")
    return FootballAppearanceProcess(
        atom_type="PLAY_SNAP_TARGET_CARRY",
        league=league,
        eligibility_rule="on_field_for_play AND role_allows_stat_family",
        generation_process="team_play_transition_then_role_share",
        termination_rule="game_clock_or_end_of_regulation_plus_ot_if_definition_includes",
        zero_opportunity_paths=tuple(zero),
        platform_participation_map="PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1",
    )
