"""PrizePicks offer adapter — board rows only, never hits the web."""
from __future__ import annotations

from typing import Any

from dcm.research.adapters.base import adapter_record


ADAPTER_ID = "PrizePicksOfferAdapter"
ADAPTER_VERSION = "pp-board-1"
SOURCE_CLASS = "OFFICIAL_PLATFORM"
DEFAULT_URL = "https://api.prizepicks.com/projections"


def offer_fields_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "projectionId": row.get("projectionId"),
        "playerId": row.get("playerId"),
        "playerName": row.get("playerName"),
        "sportFamily": row.get("sportFamily"),
        "league": row.get("league"),
        "team": row.get("team") or row.get("teamId"),
        "teamId": row.get("teamId"),
        "opponent": row.get("opponent"),
        "eventId": row.get("eventId"),
        "eventLabel": row.get("eventLabel"),
        "eventStartTime": row.get("eventStartTime"),
        "market": row.get("market"),
        "marketRaw": row.get("marketRaw") or row.get("marketLabel"),
        "line": row.get("line"),
        "modifier": row.get("modifier"),
        "offeredHigher": bool(row.get("offeredHigher")),
        "offeredLower": bool(row.get("offeredLower")),
        "boardId": row.get("boardId") or "FULL_GAME",
        "status": row.get("status"),
        "isLive": bool(row.get("isLive")),
        "side": row.get("side"),
    }


class PrizePicksOfferAdapter:
    adapter_id = ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    source_class = SOURCE_CLASS

    def __init__(self, *, retrieved_at: str | None = None, url: str = DEFAULT_URL):
        self.retrieved_at = retrieved_at
        self.url = url

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        rows = spec.get("rows") or spec.get("board_rows") or spec.get("offers") or []
        if not isinstance(rows, list):
            rows = []
        return {
            "url": str(spec.get("url") or self.url),
            "rows": rows,
            "retrievedAt": spec.get("retrieved_at") or spec.get("retrievedAt") or self.retrieved_at,
            "publishedAt": spec.get("published_at") or spec.get("publishedAt"),
        }

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        url = str(document.get("url") or self.url)
        retrieved = document.get("retrievedAt") or document.get("retrieved_at") or self.retrieved_at
        published = document.get("publishedAt") or document.get("published_at") or retrieved
        rows = document.get("rows") or []
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            fields = offer_fields_from_row(row)
            out.append(
                adapter_record(
                    url=url,
                    raw={
                        "projectionId": row.get("projectionId"),
                        "playerId": row.get("playerId"),
                        "market": row.get("market"),
                        "line": row.get("line"),
                        "modifier": row.get("modifier"),
                    },
                    fields=fields,
                    retrieved_at=retrieved,
                    published_at=published,
                    source_class=self.source_class,
                    adapter_id=self.adapter_id,
                    adapter_version=self.adapter_version,
                    extra={"kind": "OFFER"},
                )
            )
        return out

    def normalize_rows(self, rows: list[dict[str, Any]], *, retrieved_at: str | None = None) -> list[dict[str, Any]]:
        return self.normalize(self.fetch({"rows": rows, "retrieved_at": retrieved_at or self.retrieved_at}))
