"""Sport-neutral entity contracts for the universal DCM core.

These containers deliberately avoid player/team/minutes/etc.  Sport and
platform adapters are responsible for mapping their native vocabulary into
these abstractions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EntityKind(str, Enum):
    SPORT = "SPORT"
    COMPETITION = "COMPETITION"
    EVENT = "EVENT"
    SIDE = "SIDE"
    AFFILIATION = "AFFILIATION"
    SUBJECT = "SUBJECT"
    COUNTERPARTY = "COUNTERPARTY"
    ENVIRONMENT = "ENVIRONMENT"
    MARKET_DEFINITION = "MARKET_DEFINITION"
    OFFER = "OFFER"


class SubjectType(str, Enum):
    PLAYER = "PLAYER"
    TEAM = "TEAM"
    PITCHER = "PITCHER"
    BATTER = "BATTER"
    GOALIE = "GOALIE"
    FIGHTER = "FIGHTER"
    TENNIS_PLAYER = "TENNIS_PLAYER"
    GOLFER = "GOLFER"
    DRIVER = "DRIVER"
    ESPORTS_PLAYER = "ESPORTS_PLAYER"
    ESPORTS_TEAM = "ESPORTS_TEAM"
    COMBO = "COMBO"
    EVENT = "EVENT"
    OTHER = "OTHER"


@dataclass(frozen=True)
class EntityRef:
    """Minimal immutable universal entity reference."""

    kind: EntityKind
    entity_id: str
    name: str = ""
    sport_id: str = ""
    competition_id: str = ""

    def __post_init__(self) -> None:
        if not str(self.entity_id).strip():
            raise ValueError(f"ENTITY_ID_REQUIRED:{self.kind.value}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "entityId": self.entity_id,
            "name": self.name,
            "sportId": self.sport_id,
            "competitionId": self.competition_id,
        }


@dataclass(frozen=True)
class SubjectRef:
    subject_id: str
    subject_type: SubjectType
    subject_name: str
    sport_id: str
    competition_id: str
    affiliation_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.subject_id).strip():
            raise ValueError("SUBJECT_ID_REQUIRED")
        if not str(self.sport_id).strip():
            raise ValueError("SPORT_ID_REQUIRED")
        if not str(self.competition_id).strip():
            raise ValueError("COMPETITION_ID_REQUIRED")

    def to_dict(self) -> dict[str, Any]:
        return {
            "subjectId": self.subject_id,
            "subjectType": self.subject_type.value,
            "subjectName": self.subject_name,
            "sportId": self.sport_id,
            "competitionId": self.competition_id,
            "affiliationId": self.affiliation_id,
        }


def parse_subject_type(value: Any, *, default: SubjectType = SubjectType.OTHER) -> SubjectType:
    raw = str(value or "").strip().upper()
    if not raw:
        return default
    try:
        return SubjectType(raw)
    except ValueError:
        return SubjectType.OTHER
