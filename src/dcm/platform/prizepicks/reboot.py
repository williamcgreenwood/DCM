"""Versioned PrizePicks Reboot evaluation. Snapshot V1. Never guess eligibility."""

from __future__ import annotations

from dataclasses import dataclass

from dcm.contracts.codes import FailureCode
from dcm.contracts.schemas import AdministrativeState, EntryPickContract, PickSide
from dcm.platform.prizepicks.participation import (
    GAME_PHASE_CFB_REBOOT_OK,
    GAME_PHASE_NFL_REBOOT_OK,
    PARTIAL_BOARDS,
    ParticipationFacts,
    board_allows_reboot,
    football_qualifying_exit,
)
from dcm.sports.football.registry import (
    CFB_LEAGUE,
    CFB_PLAYER_REBOOT_ELIGIBLE,
    NFL_DEFENSE_ROLES,
    NFL_LEAGUE,
    NFL_SPECIALISTS,
    NFLP_LEAGUE,
    football_stat_reboot_eligibility,
)


# Re-export so historical imports keep working.
__all__ = ["ParticipationFacts", "RebootDecision", "evaluate_reboot", "SNAPSHOT"]

SNAPSHOT = "PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1"
NBA = "NBA"
WNBA = "WNBA"


@dataclass(frozen=True)
class RebootDecision:
    administrative_state: AdministrativeState
    reason_code: str
    applied: bool
    message: str


def evaluate_reboot(pick: EntryPickContract, facts: ParticipationFacts) -> RebootDecision:
    if pick.reboot_rule_version != SNAPSHOT:
        return RebootDecision(AdministrativeState.UNRESOLVED, FailureCode.UNKNOWN_REBOOT_RULE.value, False, "rule version not in snapshot")

    if facts.status in {"DNP", "INACTIVE"}:
        return RebootDecision(AdministrativeState.DNP, "DNP", False, "did not play")

    league = pick.league

    if league == NFLP_LEAGUE:
        return RebootDecision(
            AdministrativeState.UNRESOLVED,
            FailureCode.PRESEASON_RULE_UNVERIFIED.value,
            False,
            "NFL preseason reboot/settlement rows are not in snapshot V1",
        )

    if facts.board_id in PARTIAL_BOARDS or not board_allows_reboot(facts.board_id):
        return RebootDecision(
            AdministrativeState.ACTIVE,
            FailureCode.PARTIAL_BOARD_NO_REBOOT.value,
            False,
            f"board {facts.board_id} is not reboot-eligible",
        )

    if league in {NBA, WNBA}:
        return _nba_wnba(pick, facts)
    if league == NFL_LEAGUE:
        return _nfl(pick, facts)
    if league == CFB_LEAGUE:
        return _cfb(pick, facts)
    return RebootDecision(
        AdministrativeState.UNRESOLVED,
        FailureCode.UNKNOWN_REBOOT_RULE.value,
        False,
        f"no reboot table for league {league}",
    )


def _nba_wnba(pick: EntryPickContract, facts: ParticipationFacts) -> RebootDecision:
    # MORE only, full-game, eligible stat, leaves 1H, no 2H return.
    if pick.side != PickSide.MORE:
        return RebootDecision(AdministrativeState.ACTIVE, "LESS_NOT_REBOOTED", False, "LESS is not Rebooted under V1")
    if not (facts.left_first_half and facts.no_second_half_return):
        return RebootDecision(AdministrativeState.ACTIVE, "NO_QUALIFYING_EXIT", False, "no 1H-leave / 2H-absent pattern")
    if facts.achieved_before_exit:
        return RebootDecision(AdministrativeState.ACTIVE, "ALREADY_ACHIEVED", False, "MORE already achieved before exit; settle normally")
    return RebootDecision(AdministrativeState.REBOOT, "NBA_WNBA_1H_LEAVE", True, "qualifying first-half exit")


def _nfl(pick: EntryPickContract, facts: ParticipationFacts) -> RebootDecision:
    if pick.side != PickSide.MORE:
        return RebootDecision(AdministrativeState.ACTIVE, "LESS_NOT_REBOOTED", False, "LESS is not Rebooted under V1")
    if facts.role in NFL_DEFENSE_ROLES:
        return RebootDecision(AdministrativeState.ACTIVE, "DEFENSE_EXCLUDED", False, "defense excluded from NFL reboot path")
    if facts.role in NFL_SPECIALISTS and facts.specialist_attempts == 0 and facts.opportunity_count == 0:
        return RebootDecision(AdministrativeState.REBOOT, "KP_ZERO_OPPORTUNITY", True, "kicker/punter zero-opportunity path")
    eligibility = football_stat_reboot_eligibility(NFL_LEAGUE, pick.stat_key, facts.role)
    if eligibility == "UNKNOWN":
        return RebootDecision(AdministrativeState.UNRESOLVED, FailureCode.UNKNOWN_REBOOT_RULE.value, False, f"stat {pick.stat_key} eligibility unknown")
    if eligibility == "VERIFIED_FALSE":
        return RebootDecision(AdministrativeState.ACTIVE, "STAT_NOT_ELIGIBLE", False, f"{pick.stat_key} not reboot-eligible")
    if facts.game_phase not in GAME_PHASE_NFL_REBOOT_OK:
        return RebootDecision(
            AdministrativeState.UNRESOLVED,
            FailureCode.UNKNOWN_REBOOT_RULE.value,
            False,
            f"NFL game_phase {facts.game_phase} is not a verified reboot phase",
        )
    if not football_qualifying_exit(facts):
        return RebootDecision(AdministrativeState.ACTIVE, "NO_QUALIFYING_EXIT", False, "player did not leave 1H without 2H return")
    if facts.achieved_before_exit:
        return RebootDecision(AdministrativeState.ACTIVE, "ALREADY_ACHIEVED", False, "MORE already achieved before exit")
    return RebootDecision(AdministrativeState.REBOOT, "NFL_OFFENSIVE_REBOOT", True, "qualifying NFL offensive reboot")


def _cfb(pick: EntryPickContract, facts: ParticipationFacts) -> RebootDecision:
    if pick.player_id not in CFB_PLAYER_REBOOT_ELIGIBLE:
        return RebootDecision(
            AdministrativeState.UNRESOLVED,
            FailureCode.CFB_PLAYER_NOT_IN_REBOOT_REGISTRY.value,
            False,
            "CFB reboot requires an explicit frozen player registry entry",
        )
    if pick.side != PickSide.MORE:
        return RebootDecision(AdministrativeState.ACTIVE, "LESS_NOT_REBOOTED", False, "LESS is not Rebooted under V1")
    eligibility = football_stat_reboot_eligibility(CFB_LEAGUE, pick.stat_key, facts.role)
    if eligibility != "VERIFIED_TRUE":
        return RebootDecision(
            AdministrativeState.UNRESOLVED if eligibility == "UNKNOWN" else AdministrativeState.ACTIVE,
            FailureCode.UNKNOWN_REBOOT_RULE.value if eligibility == "UNKNOWN" else "STAT_NOT_ELIGIBLE",
            False,
            f"CFB stat eligibility {eligibility}",
        )
    if not football_qualifying_exit(facts):
        return RebootDecision(AdministrativeState.ACTIVE, "NO_QUALIFYING_EXIT", False, "no qualifying CFB 1H exit")
    if facts.game_phase not in GAME_PHASE_CFB_REBOOT_OK:
        return RebootDecision(
            AdministrativeState.ACTIVE if facts.game_phase in {"REGULAR", "BOWL"} else AdministrativeState.UNRESOLVED,
            FailureCode.CFB_PHASE_NOT_PLAYOFF.value,
            False,
            f"CFB reboot is CFP_PLAYOFF only; got {facts.game_phase}",
        )
    if facts.achieved_before_exit:
        return RebootDecision(AdministrativeState.ACTIVE, "ALREADY_ACHIEVED", False, "MORE already achieved")
    return RebootDecision(AdministrativeState.REBOOT, "CFB_REGISTERED_PLAYER_REBOOT", True, "qualifying CFB reboot for registered player")
