"""Universal SubjectOfferSet.

The canonical research unit is subject + event, not player + game.  Platform
compatibility aliases (player/team/opponent) are normalized only at this
boundary; the resulting object is sport-neutral.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.contracts.universal_entities import SubjectType, parse_subject_type


def _s(value: Any) -> str:
    return "" if value is None else str(value)


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _unique_strings(value: Any) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, (list, tuple, set)) else [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = _s(item).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def canonical_subject_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Map platform/native fields into universal core fields.

    player/team/opponent aliases are accepted only for backward compatibility.
    No downstream universal artifact is required to understand those aliases.
    """
    subject_id = _s(_first(row, "subjectId", "playerId"))
    explicit_type = _first(row, "subjectType")
    default_type = SubjectType.PLAYER if row.get("playerId") else SubjectType.OTHER
    subject_type = parse_subject_type(explicit_type, default=default_type)
    subject_name = _s(_first(row, "subjectName", "playerName", "name", "subjectId", "playerId"))
    sport_id = _s(_first(row, "sportId", "sportFamily", "sport"))
    competition_id = _s(_first(row, "competitionId", "competition", "league"))
    affiliation_id = _s(_first(row, "affiliationId", "teamId", "team")) or None

    counterparties = _unique_strings(_first(row, "counterpartyIds"))
    if not counterparties:
        counterparties = _unique_strings(_first(row, "counterpartyId", "opponentId", "opponent"))

    return {
        "subjectId": subject_id,
        "subjectType": subject_type.value,
        "subjectName": subject_name,
        "sportId": sport_id,
        "competitionId": competition_id,
        "eventId": _s(_first(row, "eventId")),
        "eventLabel": _s(_first(row, "eventLabel")),
        "eventStart": _s(_first(row, "eventStart", "eventStartTime")),
        "eventStatus": _s(_first(row, "eventStatus", "status")),
        "affiliationId": affiliation_id,
        "counterpartyIds": counterparties,
        "environmentId": _s(_first(row, "environmentId", "venueId", "venue")) or None,
        "captureTime": _s(_first(row, "captureTime", "captureTimestamp", "boardTime")),
        "sourceHashes": _unique_strings(_first(row, "sourceHashes", "HAR_SHA256", "harSha256")),
    }


def universal_offer_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": _s(_first(row, "platform")) or "UNKNOWN_PLATFORM",
        "projectionId": _s(_first(row, "projectionId", "offerId")),
        "marketId": _s(_first(row, "marketId")),
        "marketRawName": _first(row, "marketRawName", "marketRaw", "marketLabel"),
        "marketCanonicalName": _first(row, "marketCanonicalName", "market"),
        "line": row.get("line"),
        "modifier": row.get("modifier"),
        "offeredMore": bool(row.get("offeredMore") if "offeredMore" in row else row.get("offeredHigher")),
        "offeredLess": bool(row.get("offeredLess") if "offeredLess" in row else row.get("offeredLower")),
        "period": _first(row, "period", "boardId"),
        "duration": row.get("duration"),
        "gameWindow": row.get("gameWindow"),
        "isLive": bool(row.get("isLive")),
        "status": row.get("status"),
        "comboSubjects": list(row.get("comboSubjects") or []),
        "captureTimestamp": _first(row, "captureTimestamp", "boardTime"),
        "projectionUpdatedAt": row.get("projectionUpdatedAt"),
        "allowedWagerTypes": list(row.get("allowedWagerTypes") or []),
        "requestScope": row.get("requestScope"),
    }


@dataclass
class SubjectOfferSet:
    subjectId: str
    subjectType: str
    subjectName: str
    sportId: str
    competitionId: str
    eventId: str
    eventLabel: str = ""
    eventStart: str = ""
    eventStatus: str = ""
    affiliationId: str | None = None
    counterpartyIds: list[str] = field(default_factory=list)
    environmentId: str | None = None
    offers: list[dict[str, Any]] = field(default_factory=list)
    captureTime: str = ""
    sourceHashes: list[str] = field(default_factory=list)

    @property
    def set_id(self) -> str:
        return f"SOS|{self.subjectId}|{self.eventId}"

    def validate(self) -> None:
        if not self.subjectId:
            raise ValueError("SUBJECT_ID_REQUIRED")
        if not self.sportId:
            raise ValueError("SPORT_ID_REQUIRED")
        if not self.competitionId:
            raise ValueError("COMPETITION_ID_REQUIRED")
        if not self.eventId:
            raise ValueError("EVENT_ID_REQUIRED")
        if self.subjectType not in {member.value for member in SubjectType}:
            raise ValueError(f"UNKNOWN_SUBJECT_TYPE:{self.subjectType}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        offers = sorted(
            self.offers,
            key=lambda o: (_s(o.get("projectionId")), _s(o.get("marketCanonicalName"))),
        )
        body = {
            "setId": self.set_id,
            "subjectId": self.subjectId,
            "subjectType": self.subjectType,
            "subjectName": self.subjectName,
            "sportId": self.sportId,
            "competitionId": self.competitionId,
            "eventId": self.eventId,
            "eventLabel": self.eventLabel,
            "eventStart": self.eventStart,
            "eventStatus": self.eventStatus,
            "affiliationId": self.affiliationId,
            "counterpartyIds": sorted(set(self.counterpartyIds)),
            "environmentId": self.environmentId,
            "captureTime": self.captureTime,
            "sourceHashes": sorted(set(self.sourceHashes)),
            "offerCount": len(offers),
            "markets": sorted(
                {
                    _s(o.get("marketCanonicalName"))
                    for o in offers
                    if o.get("marketCanonicalName")
                }
            ),
            "offers": offers,
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body


def build_subject_offer_sets(board_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], SubjectOfferSet] = {}
    for row in board_rows:
        if not isinstance(row, dict):
            continue
        fields = canonical_subject_fields(row)
        subject_id = fields["subjectId"]
        event_id = fields["eventId"]
        if not subject_id or not event_id:
            continue
        key = (subject_id, event_id)
        if key not in groups:
            groups[key] = SubjectOfferSet(
                subjectId=subject_id,
                subjectType=fields["subjectType"],
                subjectName=fields["subjectName"],
                sportId=fields["sportId"],
                competitionId=fields["competitionId"],
                eventId=event_id,
                eventLabel=fields["eventLabel"],
                eventStart=fields["eventStart"],
                eventStatus=fields["eventStatus"],
                affiliationId=fields["affiliationId"],
                counterpartyIds=list(fields["counterpartyIds"]),
                environmentId=fields["environmentId"],
                captureTime=fields["captureTime"],
                sourceHashes=list(fields["sourceHashes"]),
            )
        else:
            current = groups[key]
            current.counterpartyIds.extend(fields["counterpartyIds"])
            current.sourceHashes.extend(fields["sourceHashes"])
            if not current.affiliationId and fields["affiliationId"]:
                current.affiliationId = fields["affiliationId"]
            if not current.environmentId and fields["environmentId"]:
                current.environmentId = fields["environmentId"]
        groups[key].offers.append(universal_offer_from_row(row))

    sets = [group.to_dict() for group in groups.values()]
    sets.sort(key=lambda s: (s["subjectId"], s["eventId"], s["setId"]))
    return sets


def subject_offer_sets_document(sets: list[dict[str, Any]]) -> dict[str, Any]:
    body = {
        "schema": "pillars_dcm.subject_offer_sets.v1",
        "setCount": len(sets),
        "offerCount": sum(int(s.get("offerCount") or len(s.get("offers") or [])) for s in sets),
        "sets": sets,
        "compatibility": {
            "playerOfferSet": "legacy projection only; canonical research unit is SubjectOfferSet"
        },
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
