"""Team opportunity pools and player shares. Efficiency stays out of this module."""

from __future__ import annotations

from dataclasses import dataclass

from dcm.contracts.immutables import FrozenMap
from dcm.contracts.schemas import OpportunityState


OPP_VERSION = "FOOTBALL_OPP_V1_2026-08-27"


@dataclass(frozen=True)
class TeamOpportunityPool:
    team_id: str
    off_plays: int
    pass_att: int
    designed_rush_att: int
    sacks_taken: int
    scramble_att: int
    targets: int

    @property
    def rush_att(self) -> int:
        return self.designed_rush_att + self.scramble_att

    @property
    def dropbacks(self) -> int:
        return self.pass_att + self.sacks_taken + self.scramble_att

    def as_team_stats(self) -> dict[str, float]:
        return {
            "team_off_plays": float(self.off_plays),
            "team_pass_att": float(self.pass_att),
            "team_rush_att": float(self.rush_att),
            "team_sacks_taken": float(self.sacks_taken),
            "team_designed_rush_att": float(self.designed_rush_att),
            "team_dropbacks": float(self.dropbacks),
            "team_targets": float(self.targets),
        }

    def validate_internal(self) -> None:
        if self.off_plays != self.pass_att + self.rush_att + self.sacks_taken:
            raise ValueError("team pool violates play identity")
        if self.targets < 0 or self.pass_att < 0:
            raise ValueError("negative team opportunity")


def player_opportunity(
    *,
    off_snaps: float,
    routes: float,
    targets: float,
    dropbacks: float,
    pass_att: float,
    designed_rush_att: float,
    scramble_att: float,
    rz_att: float = 0.0,
    fg_att: float = 0.0,
    xp_att: float = 0.0,
    punt_att: float = 0.0,
) -> OpportunityState:
    rush_att = designed_rush_att + scramble_att
    return OpportunityState(
        shares=FrozenMap({
            "off_snaps": off_snaps,
            "routes": routes,
            "targets": targets,
            "dropbacks": dropbacks,
            "pass_att": pass_att,
            "designed_rush_att": designed_rush_att,
            "scramble_att": scramble_att,
            "rush_att": rush_att,
            "rz_att": rz_att,
            "fg_att": fg_att,
            "xp_att": xp_att,
            "punt_att": punt_att,
        }),
        unit="count",
        definition_version=OPP_VERSION,
    )
