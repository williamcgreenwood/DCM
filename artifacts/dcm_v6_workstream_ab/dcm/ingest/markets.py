"""Stat-type and league identity maps. Unknown labels stay unknown — no nearest match."""

from __future__ import annotations

import re

_STAT = {
    "points": "pts",
    "pts": "pts",
    "rebounds": "reb",
    "reb": "reb",
    "assists": "ast",
    "ast": "ast",
    "pra": "pra",
    "pts rebs asts": "pra",
    "pts reb ast": "pra",
    "points rebounds assists": "pra",
    "pts rebs ast": "pra",
    "3 pt made": "3pm",
    "3pm": "3pm",
    "threes": "3pm",
    "three pointers made": "3pm",
    "3 pointers made": "3pm",
    "steals": "stl",
    "stl": "stl",
    "blocks": "blk",
    "blk": "blk",
    "blocked shots": "blk",
    "turnovers": "to",
    "to": "to",
    "passing yards": "pass_yds",
    "pass yds": "pass_yds",
    "pass yards": "pass_yds",
    "rushing yards": "rush_yds",
    "rush yds": "rush_yds",
    "receiving yards": "rec_yds",
    "rec yds": "rec_yds",
    "receptions": "receptions",
    "passing rushing yards": "pass_rush_yds",
    "pass rush yds": "pass_rush_yds",
    "pass rush yards": "pass_rush_yds",
    "rush rec yds": "rush_rec_yds",
    "rushing receiving yards": "rush_rec_yds",
    "field goals made": "fg_made",
    "fg made": "fg_made",
    "tackles": "def_tackles",
    "def tackles": "def_tackles",
    "hits": "h",
    "h": "h",
    "total bases": "tb",
    "tb": "tb",
    "pitcher strikeouts": "k",
    "strikeouts": "k",
    "ks": "k",
    "k": "k",
    "hits runs rbis": "hits_runs_rbi",
    "hits runs rbi": "hits_runs_rbi",
    "h r rbi": "hits_runs_rbi",
    "hits runs and rbis": "hits_runs_rbi",
    "hitter strikeouts": "k",
    "pitching outs": "pitching_outs",
    "pitches thrown": "pitches_thrown",
    "player touchdowns": "player_td",
    "pass tds": "pass_td",
    "fg attempted": "fg_att",
    "fantasy score": "fantasy",
    "pitcher fantasy score": "fantasy",
    "significant strikes": "sig_strikes",
    "sig strikes": "sig_strikes",
    "sig strikes landed": "sig_strikes",
    "shots": "shots",
    "shots on goal": "sog",
    "sog": "sog",
    "aces": "aces",
    "punches landed": "punches_landed",
    "runs": "runs",
    "strokes": "strokes",
    "kills": "kills",
}

_LABEL = {
    "pts": "Points",
    "reb": "Rebounds",
    "ast": "Assists",
    "pra": "Pts+Reb+Ast",
    "3pm": "3-PT Made",
    "stl": "Steals",
    "pass_yds": "Passing Yards",
    "rush_yds": "Rushing Yards",
    "rec_yds": "Receiving Yards",
    "receptions": "Receptions",
    "pass_rush_yds": "Pass+Rush Yds",
    "rush_rec_yds": "Rush+Rec Yds",
    "fg_made": "FG Made",
    "def_tackles": "Tackles",
    "h": "Hits",
    "tb": "Total Bases",
    "k": "Strikeouts",
    "hits_runs_rbi": "Hits+Runs+RBIs",
    "sig_strikes": "Sig. Strikes",
    "shots": "Shots",
    "sog": "Shots on Goal",
    "aces": "Aces",
    "punches_landed": "Punches Landed",
    "runs": "Runs",
    "strokes": "Strokes",
    "kills": "Kills",
}

_LEAGUE = {
    "nba": ("NBA", "basketball"),
    "wnba": ("WNBA", "basketball"),
    "nfl": ("NFL", "gridiron"),
    "nflp": ("NFLP", "gridiron"),
    "nfl preseason": ("NFLP", "gridiron"),
    "ncaaf": ("CFB", "gridiron"),
    "cfb": ("CFB", "gridiron"),
    "ncaa football": ("CFB", "gridiron"),
    "college football": ("CFB", "gridiron"),
    "ncaafb": ("CFB", "gridiron"),
    "cfl": ("CFL", "gridiron"),
    "mlb": ("MLB", "baseball"),
    "kbo": ("KBO", "baseball"),
    "npb": ("NPB", "baseball"),
    "nhl": ("NHL", "hockey"),
    "ufc": ("UFC", "combat"),
    "mma": ("UFC", "combat"),
    "boxing": ("BOXING", "combat"),
    "pga": ("PGA", "golf"),
    "atp": ("ATP", "racket"),
    "wta": ("WTA", "racket"),
    "epl": ("EPL", "soccer"),
    "soccer": ("SOCCER", "soccer"),
    "t20": ("T20", "cricket"),
    "cricket": ("T20", "cricket"),
    "cs2": ("CS2", "esports"),
    "otd": ("OTD", "unknown"),
}

_SPORT_FAMILY = {
    "basketball": "basketball",
    "football": "gridiron",
    "gridiron": "gridiron",
    "baseball": "baseball",
    "hockey": "hockey",
    "mma": "combat",
    "combat": "combat",
    "golf": "golf",
    "tennis": "racket",
    "racket": "racket",
    "soccer": "soccer",
    "cricket": "cricket",
    "esports": "esports",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def map_stat(label: str | None) -> tuple[str, str]:
    """Return (market_key, market_label). Unknown keys stay as a slug — fail closed later."""
    if not label:
        return ("unknown", "UNKNOWN")
    key = _STAT.get(_norm(label))
    if key:
        return key, _LABEL.get(key, label)
    slug = _norm(label).replace(" ", "_")
    return slug or "unknown", label


def map_league(name: str | None, sport: str | None = None) -> tuple[str, str]:
    raw = _norm(name or "")
    if raw in _LEAGUE:
        return _LEAGUE[raw]
    sport_fam = _SPORT_FAMILY.get(_norm(sport or ""), "unknown")
    if raw:
        return raw.upper()[:12], sport_fam
    if sport_fam != "unknown":
        return sport_fam.upper(), sport_fam
    return "UNKNOWN", "unknown"


def market_label(market: str, fallback: str = "") -> str:
    return _LABEL.get(market, fallback or market)
