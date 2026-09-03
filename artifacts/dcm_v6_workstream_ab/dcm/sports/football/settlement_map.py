"""Stub-free PrizePicks football settlement mapping.

Maps already-supported PrizePicks football markets onto primitive ledger
identities. Unknown labels fail closed — never nearest-match, never invent
a scoring formula.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.contracts.codes import FailureCode
from dcm.model.market_derive import (
    GRIDIRON_MARKET_REGISTRY_VERSION,
    UnknownMarketError,
    canonicalize_market,
    derive_market,
    looks_like_gridiron_ledger,
)
from dcm.sports.football.projection import ProjectionError, project_football_market
from dcm.sports.football.registry import lookup_market

SETTLEMENT_MAP_VERSION = "PP_FOOTBALL_SETTLE_V1_2026-08-30"

# PrizePicks board labels already in ingest/markets.py → canonical market.
# Only markets with a ledger identity are listed. Everything else is unknown.
PRIZEPICKS_FOOTBALL_MARKETS: dict[str, str] = {
    "pass_yds": "pass_yds",
    "passing yards": "pass_yds",
    "pass yds": "pass_yds",
    "pass yards": "pass_yds",
    "pass_att": "pass_att",
    "pass attempts": "pass_att",
    "passing attempts": "pass_att",
    "pass_cmp": "pass_cmp",
    "completions": "pass_cmp",
    "passing completions": "pass_cmp",
    "rush_yds": "rush_yds",
    "rush_att": "rush_att",
    "rush attempts": "rush_att",
    "rushing attempts": "rush_att",
    "rushing yards": "rush_yds",
    "rush yds": "rush_yds",
    "rec_yds": "rec_yds",
    "receiving yards": "rec_yds",
    "rec yds": "rec_yds",
    "receptions": "receptions",
    "pass_rush_yds": "pass_rush_yds",
    "passing rushing yards": "pass_rush_yds",
    "pass rush yds": "pass_rush_yds",
    "pass rush yards": "pass_rush_yds",
    "rush_rec_yds": "rush_rec_yds",
    "rush rec yds": "rush_rec_yds",
    "rushing receiving yards": "rush_rec_yds",
}

PRODUCTION_SETTLEMENT_MARKETS = frozenset({
    "pass_yds", "pass_att", "pass_cmp", "rush_yds", "rush_att", "rec_yds", "receptions", "pass_rush_yds", "rush_rec_yds",
})


def canonicalize_prizepicks_football_market(label: str) -> str | None:
    raw = str(label or "").strip()
    if not raw:
        return None
    key = " ".join(raw.lower().replace("_", " ").replace("+", " ").replace("-", " ").split())
    if key in PRIZEPICKS_FOOTBALL_MARKETS:
        return PRIZEPICKS_FOOTBALL_MARKETS[key]
    slug = key.replace(" ", "_")
    if slug in PRIZEPICKS_FOOTBALL_MARKETS:
        return PRIZEPICKS_FOOTBALL_MARKETS[slug]
    return canonicalize_market(raw)


def settle_football_market(ledger: Mapping[str, Any] | dict[str, Any], market: str) -> float:
    """Map a primitive ledger + PrizePicks football market to a scalar identity."""
    canon = canonicalize_prizepicks_football_market(market)
    if canon is None or canon not in PRODUCTION_SETTLEMENT_MARKETS:
        raise UnknownMarketError(str(market), blocker="UNVERIFIED_MARKET_DEFINITION")
    values: dict[str, Any]
    if hasattr(ledger, "values_for"):
        raise TypeError("use settle_football_player for PrimitiveStatLedger")
    values = dict(ledger)
    if not looks_like_gridiron_ledger(values) and canon not in values and not (
        {"pass_yds", "rush_yds", "rec_yds", "receptions"} & set(values)
    ):
        raise UnknownMarketError(str(market), blocker="DERIVED_IDENTITY_FAILURE")
    return float(derive_market(values, canon))


def settle_football_player(ledger, *, player_id: str, market: str, league: str | None = None):
    """World-projection settlement from a PrimitiveStatLedger. Unknown → fail closed."""
    canon = canonicalize_prizepicks_football_market(market)
    if canon is None or canon not in PRODUCTION_SETTLEMENT_MARKETS:
        raise ProjectionError(FailureCode.UNVERIFIED_MARKET_DEFINITION, f"{market}")
    definition = lookup_market(league or getattr(ledger, "league", ""), canon)
    return project_football_market(
        ledger, player_id=player_id, market=canon, definition=definition,
    )


__all__ = [
    "SETTLEMENT_MAP_VERSION",
    "GRIDIRON_MARKET_REGISTRY_VERSION",
    "PRIZEPICKS_FOOTBALL_MARKETS",
    "PRODUCTION_SETTLEMENT_MARKETS",
    "canonicalize_prizepicks_football_market",
    "settle_football_market",
    "settle_football_player",
]
