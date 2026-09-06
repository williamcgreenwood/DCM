"""Legacy PlayerOfferSet compatibility projection.

Canonical research grouping is SubjectOfferSet.  This module exists so older
basketball/gridiron consumers can migrate without creating a second research
engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.subject_offer_set import build_subject_offer_sets


def _s(value: Any) -> str:
    return "" if value is None else str(value)


def _legacy_offer(offer: dict[str, Any]) -> dict[str, Any]:
    return {
        "projectionId": _s(offer.get("projectionId")),
        "market": offer.get("marketCanonicalName"),
        "line": offer.get("line"),
        "modifier": offer.get("modifier"),
        "offeredHigher": bool(offer.get("offeredMore")),
        "offeredLower": bool(offer.get("offeredLess")),
        "boardId": offer.get("period") or "FULL_GAME",
        "raw": {
            "status": offer.get("status"),
            "isLive": offer.get("isLive"),
            "marketRaw": offer.get("marketRawName"),
        },
    }


@dataclass
class PlayerOfferSet:
    playerId: str
    playerName: str
    sportFamily: str
    league: str
    team: str
    opponent: str
    eventId: str
    eventLabel: str
    eventStartTime: str
    offers: list[dict[str, Any]] = field(default_factory=list)

    @property
    def set_id(self) -> str:
        return f"POS|{self.playerId}|{self.eventId}"

    def to_dict(self) -> dict[str, Any]:
        offers = sorted(self.offers, key=lambda o: (_s(o.get("projectionId")), _s(o.get("market"))))
        body = {
            "setId": self.set_id,
            "playerId": self.playerId,
            "playerName": self.playerName,
            "sportFamily": self.sportFamily,
            "league": self.league,
            "team": self.team,
            "opponent": self.opponent,
            "eventId": self.eventId,
            "eventLabel": self.eventLabel,
            "eventStartTime": self.eventStartTime,
            "offerCount": len(offers),
            "markets": sorted({_s(o.get("market")) for o in offers if o.get("market")}),
            "offers": offers,
            "canonicalType": "SubjectOfferSetCompatibilityView",
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body


def build_player_offer_sets(board_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project canonical PLAYER SubjectOfferSets into the legacy shape."""
    out: list[dict[str, Any]] = []
    for subject_set in build_subject_offer_sets(board_rows):
        if str(subject_set.get("subjectType") or "") != "PLAYER":
            continue
        counterparties = list(subject_set.get("counterpartyIds") or [])
        player_set = PlayerOfferSet(
            playerId=_s(subject_set.get("subjectId")),
            playerName=_s(subject_set.get("subjectName")),
            sportFamily=_s(subject_set.get("sportId")),
            league=_s(subject_set.get("competitionId")),
            team=_s(subject_set.get("affiliationId")),
            opponent=_s(counterparties[0] if counterparties else ""),
            eventId=_s(subject_set.get("eventId")),
            eventLabel=_s(subject_set.get("eventLabel")),
            eventStartTime=_s(subject_set.get("eventStart")),
            offers=[_legacy_offer(o) for o in subject_set.get("offers") or []],
        )
        out.append(player_set.to_dict())
    out.sort(key=lambda s: (s["playerId"], s["eventId"], s["setId"]))
    return out


def player_offer_sets_document(sets: list[dict[str, Any]]) -> dict[str, Any]:
    body = {
        "schema": "pillars_dcm.player_offer_sets.v1",
        "setCount": len(sets),
        "offerCount": sum(int(s.get("offerCount") or len(s.get("offers") or [])) for s in sets),
        "sets": sets,
        "compatibilityOnly": True,
        "canonicalArtifact": "subject_offer_sets.json",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
