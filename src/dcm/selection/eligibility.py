"""Production selection gates. Green Goblins have no executable path into a submitted contract."""

from __future__ import annotations

from dcm.contracts.codes import FailureCode
from dcm.contracts.schemas import EntryPickContract, PickModifier
from dcm.exclusions import PERMANENT_EXCLUDED_PLAYER_IDS


class SelectionForbidden(RuntimeError):
    def __init__(self, code: FailureCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


def reject_permanent_subject(pick: EntryPickContract) -> None:
    if str(pick.player_id or "").strip().lower() in PERMANENT_EXCLUDED_PLAYER_IDS:
        raise SelectionForbidden(
            FailureCode.PERMANENT_SUBJECT_EXCLUSION,
            f"permanently excluded subject {pick.player_id} cannot enter a production EntryContract",
        )


def reject_goblin_selection(pick: EntryPickContract) -> None:
    reject_permanent_subject(pick)
    if pick.modifier == PickModifier.GOBLIN:
        raise SelectionForbidden(
            FailureCode.GOBLIN_SELECTION_FORBIDDEN,
            f"Green Goblin {pick.projection_id} cannot enter a production EntryContract",
        )


def demon_requires_cushion(pick: EntryPickContract, edge: float, required_cushion: float) -> bool:
    """Red Demon is demotion-only: extra cushion must actually change the gate."""
    if pick.modifier != PickModifier.DEMON:
        return True
    return edge >= required_cushion
