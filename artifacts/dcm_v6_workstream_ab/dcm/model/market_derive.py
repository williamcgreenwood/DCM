"""Versioned market derivation from a PrimitiveStatLedger.

Basketball and gridiron composites are identities on one ledger. Unknown keys
fail closed — no fuzzy match. Fantasy Score is listed as a key but has no
PrizePicks scoring version, so it fails closed until an exact definition hash
is registered.
"""
from __future__ import annotations

from typing import Any, Callable

MARKET_REGISTRY_VERSION = "PP_BBALL_MARKET_V1_2026-08-30"

# Exact aliases only. A slug that is not in this map is unknown.
_ALIASES: dict[str, str] = {
    "pts": "pts",
    "points": "pts",
    "reb": "reb",
    "rebounds": "reb",
    "rebound": "reb",
    "ast": "ast",
    "assists": "ast",
    "assist": "ast",
    "pra": "pra",
    "pts_reb_ast": "pra",
    "pts_rebs_asts": "pra",
    "pr": "pr",
    "pts_rebs": "pr",
    "pts_reb": "pr",
    "points_rebounds": "pr",
    "pa": "pa",
    "pts_asts": "pa",
    "pts_ast": "pa",
    "points_assists": "pa",
    "ra": "ra",
    "rebs_asts": "ra",
    "reb_ast": "ra",
    "rebounds_assists": "ra",
    "3pm": "3pm",
    "3ptm": "3pm",
    "tpm": "3pm",
    "three_pm": "3pm",
    "threes": "3pm",
    "3pa": "3pa",
    "tpa": "3pa",
    "three_pa": "3pa",
    "3pta": "3pa",
    "fgm": "fgm",
    "fg_made": "fgm",
    "fga": "fga",
    "fg_att": "fga",
    "2pm": "2pm",
    "twopm": "2pm",
    "fg2m": "2pm",
    "2pa": "2pa",
    "twopa": "2pa",
    "ftm": "ftm",
    "fta": "fta",
    "tov": "tov",
    "to": "tov",
    "turnovers": "tov",
    "turnover": "tov",
    "oreb": "oreb",
    "stl": "stl",
    "steals": "stl",
    "steal": "stl",
    "blk": "blk",
    "blocks": "blk",
    "blk_stl": "blk_stl",
    "blks_stls": "blk_stl",
    "qtrs_w_3plus_pts": "qtrs_w_3plus_pts",
    "qtrs_w_3_pts": "qtrs_w_3plus_pts",
    "fantasy": "fantasy",
}

GRIDIRON_MARKET_REGISTRY_VERSION = "PP_FOOTBALL_MARKET_V1_2026-08-30"

_GRIDIRON_ALIASES: dict[str, str] = {
    "pass_yds": "pass_yds",
    "passing_yards": "pass_yds",
    "pass_yards": "pass_yds",
    "passyds": "pass_yds",
    "pass_att": "pass_att",
    "pass_attempts": "pass_att",
    "passing_attempts": "pass_att",
    "pass_cmp": "pass_cmp",
    "completions": "pass_cmp",
    "passing_completions": "pass_cmp",
    "rush_yds": "rush_yds",
    "rush_att": "rush_att",
    "rush_attempts": "rush_att",
    "rushing_attempts": "rush_att",
    "rushing_yards": "rush_yds",
    "rush_yards": "rush_yds",
    "rec_yds": "rec_yds",
    "receiving_yards": "rec_yds",
    "rec_yards": "rec_yds",
    "receptions": "receptions",
    "rec": "receptions",
    "pass_rush_yds": "pass_rush_yds",
    "pass_rush_yards": "pass_rush_yds",
    "passing_rushing_yards": "pass_rush_yds",
    "rush_rec_yds": "rush_rec_yds",
    "rush_rec_yards": "rush_rec_yds",
    "rushing_receiving_yards": "rush_rec_yds",
}

MARKET_DISPLAY = {
    "pts": "Points",
    "reb": "Rebounds",
    "ast": "Assists",
    "pra": "PRA",
    "pr": "Pts+Rebs",
    "pa": "Pts+Asts",
    "ra": "Rebs+Asts",
    "3pm": "3PTM",
    "3pa": "3PTA",
    "fgm": "FGM",
    "fga": "FGA",
    "2pm": "2PM",
    "2pa": "2PA",
    "ftm": "FTM",
    "fta": "FTA",
    "tov": "Turnovers",
    "oreb": "OREB",
    "stl": "Steals",
    "blk": "Blocks",
    "blk_stl": "Blks+Stls",
    "qtrs_w_3plus_pts": "Qtrs w/3+ Pts",
}

QUARTER_BOARDS = {"Q1", "Q2", "Q3", "Q4", "1H", "2H", "QTRS"}

# PrizePicks Fantasy Score is NOT registered with a scoring formula.
FANTASY_SCORING_VERSIONS: dict[str, str] = {}


class UnknownMarketError(KeyError):
    """Unknown or unverified market. Fail closed — never nearest-match."""

    def __init__(self, market: str, blocker: str = "UNVERIFIED_MARKET_DEFINITION"):
        super().__init__(market)
        self.market = str(market)
        self.blocker = blocker


def canonicalize_market(market_key: str) -> str | None:
    """Exact alias lookup. Returns None when the key is not registered."""
    raw = str(market_key or "").strip()
    if not raw:
        return None
    key = raw.lower().replace("+", "_").replace("-", "_").replace(" ", "_")
    key = "_".join(p for p in key.split("_") if p)
    return _ALIASES.get(key) or _ALIASES.get(raw) or _GRIDIRON_ALIASES.get(key) or _GRIDIRON_ALIASES.get(raw)


def is_registered(market_key: str) -> bool:
    return canonicalize_market(market_key) is not None


def looks_like_basketball_ledger(stats: dict[str, Any]) -> bool:
    if not isinstance(stats, dict):
        return False
    if "fga" in stats or "twopm" in stats or "tpm" in stats:
        return True
    return "pts" in stats and "reb" in stats and "ast" in stats


def looks_like_gridiron_ledger(stats: dict[str, Any]) -> bool:
    if not isinstance(stats, dict):
        return False
    football = {"pass_yds", "pass_att", "rush_yds", "rush_att", "rec_yds", "receptions", "targets", "dropbacks"}
    return bool(football & set(stats))


def _num(ledger: dict[str, Any], *keys: str) -> float:
    for key in keys:
        if key in ledger and ledger[key] is not None:
            return float(ledger[key])
    raise UnknownMarketError(keys[0], blocker="DERIVED_IDENTITY_FAILURE")


def _formulas() -> dict[str, Callable[[dict[str, Any]], float]]:
    return {
        "pts": lambda L: _num(L, "pts"),
        "reb": lambda L: _num(L, "reb"),
        "ast": lambda L: _num(L, "ast"),
        "pra": lambda L: _num(L, "pts") + _num(L, "reb") + _num(L, "ast"),
        "pr": lambda L: _num(L, "pts") + _num(L, "reb"),
        "pa": lambda L: _num(L, "pts") + _num(L, "ast"),
        "ra": lambda L: _num(L, "reb") + _num(L, "ast"),
        "3pm": lambda L: _num(L, "tpm", "three_pm"),
        "3pa": lambda L: _num(L, "tpa", "three_pa"),
        "fgm": lambda L: _num(L, "fgm"),
        "fga": lambda L: _num(L, "fga"),
        "2pm": lambda L: _num(L, "twopm"),
        "2pa": lambda L: _num(L, "twopa"),
        "ftm": lambda L: _num(L, "ftm"),
        "fta": lambda L: _num(L, "fta"),
        "tov": lambda L: _num(L, "tov"),
        "oreb": lambda L: _num(L, "oreb"),
        "stl": lambda L: _num(L, "stl"),
        "blk": lambda L: _num(L, "blk"),
        "blk_stl": lambda L: _num(L, "blk") + _num(L, "stl"),
        "pass_yds": lambda L: _num(L, "pass_yds"),
        "pass_att": lambda L: _num(L, "pass_att"),
        "pass_cmp": lambda L: _num(L, "pass_cmp"),
        "rush_yds": lambda L: _num(L, "rush_yds"),
        "rush_att": lambda L: _num(L, "rush_att"),
        "rec_yds": lambda L: _num(L, "rec_yds"),
        "receptions": lambda L: _num(L, "receptions"),
        "pass_rush_yds": lambda L: _num(L, "pass_yds") + _num(L, "rush_yds"),
        "rush_rec_yds": lambda L: _num(L, "rush_yds") + _num(L, "rec_yds"),
    }


FORMULAS = _formulas()

GRIDIRON_MARKET_KEYS = frozenset({
    "pass_yds", "pass_att", "pass_cmp", "rush_yds", "rush_att", "rec_yds", "receptions", "pass_rush_yds", "rush_rec_yds",
})
BASKETBALL_MARKET_KEYS = (frozenset(k for k in FORMULAS) | frozenset({"qtrs_w_3plus_pts"})) - GRIDIRON_MARKET_KEYS


def derive_market(ledger: dict[str, Any], market_key: str, board_id: str = "FULL_GAME") -> float:
    """Map a ledger + market key to a scalar. Never independently samples."""
    canon = canonicalize_market(market_key)
    if canon is None:
        raise UnknownMarketError(market_key)
    if canon == "fantasy":
        raise UnknownMarketError("fantasy", blocker="UNVERIFIED_MARKET_DEFINITION")

    board = str(board_id or "FULL_GAME").strip().upper() or "FULL_GAME"

    if canon == "qtrs_w_3plus_pts":
        from dcm.model.quarter_worlds import count_quarters_at_least, require_quarters

        quarters = require_quarters(ledger)
        return float(count_quarters_at_least(quarters, "pts", 3))

    if board in QUARTER_BOARDS:
        from dcm.model.quarter_worlds import derive_board_market

        return derive_board_market(ledger, canon, board)

    fn = FORMULAS.get(canon)
    if fn is None:
        raise UnknownMarketError(market_key)
    return float(fn(ledger))
