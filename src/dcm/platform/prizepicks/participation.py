"""Sports participation facts. Physical fact ≠ platform Reboot rule."""

from __future__ import annotations

from dataclasses import dataclass


FULL_GAME = "FULL_GAME"
PARTIAL_BOARDS = frozenset({
    "NFL_1H", "NFL_2H", "NFL_1Q", "NFL_4Q", "NFLSZN", "NFLP",
    "CFB_1H", "CFB_2H", "CFB_1Q", "CFB_4Q", "CFBSZN",
    "NBA_1H", "NBA_2H", "NBA_1Q", "NBA_4Q", "NBASZN", "NBAP",
})

GAME_PHASE_NFL_REBOOT_OK = frozenset({"REGULAR", "POSTSEASON", "UNSPECIFIED"})
GAME_PHASE_CFB_REBOOT_OK = frozenset({"CFP_PLAYOFF"})


@dataclass(frozen=True)
class ParticipationFacts:
    """World-realized participation. Reboot evaluation consumes this; it does not decide economics."""

    status: str  # PLAYED | DNP | INACTIVE | LEFT_EARLY
    role: str
    opportunity_count: float
    left_first_half: bool = False
    no_second_half_return: bool = False
    left_early: bool = False  # legacy alias; official window is left_first_half
    did_not_return: bool = False  # legacy alias; official window is no_second_half_return
    achieved_before_exit: bool = False
    specialist_attempts: float = 0.0
    official_stat_value: float | None = None
    board_id: str = FULL_GAME
    game_phase: str = "UNSPECIFIED"
    plate_appearances: float | None = None


def football_qualifying_exit(facts: ParticipationFacts) -> bool:
    """Official window: leave 1H and do not return in 2H.

    Legacy left_early+did_not_return is accepted only when left_first_half was
    not explicitly contradicted (both 1H flags false). New tests must set 1H flags.
    """
    if facts.left_first_half and facts.no_second_half_return:
        return True
    if facts.left_early and facts.did_not_return and not facts.left_first_half:
        # legacy path used by historical WSAB fixtures
        return True
    return False


def board_allows_reboot(board_id: str) -> bool:
    return board_id == FULL_GAME or board_id in {"", "FULL_GAME"}
