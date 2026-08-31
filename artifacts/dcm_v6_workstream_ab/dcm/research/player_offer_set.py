"""PlayerOfferSet: one research subject per player+event, not per market.

Paige-style invariant: N offers for one player in one event → 1 PlayerOfferSet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.adapters.prizepicks import PrizePicksOfferAdapter


def _s(value: Any) -> str:
    return "" if value is None else str(value)


def offer_dict_from_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "projectionId": _s(fields.get("projectionId")),
        "market": fields.get("market"),
        "line": fields.get("line"),
        "modifier": fields.get("modifier"),
        "offeredHigher": bool(fields.get("offeredHigher")),
        "offeredLower": bool(fields.get("offeredLower")),
        "boardId": fields.get("boardId") or "FULL_GAME",
        "raw": {
            "side": fields.get("side"),
            "status": fields.get("status"),
            "isLive": fields.get("isLive"),
            "marketRaw": fields.get("marketRaw"),
            "productType": fields.get("productType"),
            "teamId": fields.get("teamId"),
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
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body


def build_player_offer_sets(board_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group board rows by (playerId, eventId). Same player, different games stay separate."""
    adapter = PrizePicksOfferAdapter()
    records = adapter.normalize_rows([r for r in board_rows if isinstance(r, dict)])
    groups: dict[tuple[str, str], PlayerOfferSet] = {}
    for rec in records:
        fields = rec.get("fields") or {}
        player_id = _s(fields.get("playerId"))
        if not player_id:
            continue
        event_id = _s(fields.get("eventId"))
        key = (player_id, event_id)
        if key not in groups:
            groups[key] = PlayerOfferSet(
                playerId=player_id,
                playerName=_s(fields.get("playerName")),
                sportFamily=_s(fields.get("sportFamily")),
                league=_s(fields.get("league")),
                team=_s(fields.get("team")),
                opponent=_s(fields.get("opponent")),
                eventId=event_id,
                eventLabel=_s(fields.get("eventLabel")),
                eventStartTime=_s(fields.get("eventStartTime")),
                offers=[],
            )
        groups[key].offers.append(offer_dict_from_fields(fields))
    sets = [g.to_dict() for g in groups.values()]
    sets.sort(key=lambda s: (s["playerId"], s["eventId"], s["setId"]))
    return sets


def player_offer_sets_document(sets: list[dict[str, Any]]) -> dict[str, Any]:
    body = {
        "schema": "pillars_dcm.player_offer_sets.v1",
        "setCount": len(sets),
        "offerCount": sum(int(s.get("offerCount") or len(s.get("offers") or [])) for s in sets),
        "sets": sets,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
