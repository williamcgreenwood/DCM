"""Production selection gates. Green Goblins have no executable path into a submitted contract."""

from __future__ import annotations

from dcm.contracts.codes import FailureCode
from dcm.contracts.schemas import EntryPickContract, PickModifier


class SelectionForbidden(RuntimeError):
    def __init__(self, code: FailureCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


def reject_goblin_selection(pick: EntryPickContract) -> None:
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
