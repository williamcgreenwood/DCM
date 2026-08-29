"""Event-once primitive worlds. Composites derive from the same draw. Never independent PRA."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from dcm.sports.baseball.pa import conservation as mlb_conservation


def _rng(seed: str) -> random.Random:
    r = random.Random()
    r.seed(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16))
    return r


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def sample_basketball(rng: random.Random, minutes: float) -> dict[str, float]:
    fga = max(0.0, rng.gauss(minutes * 0.55, 3.2))
    tpa = _clip(rng.gauss(fga * 0.42, 1.8), 0.0, fga)
    twopa = fga - tpa
    tpm = _clip(rng.gauss(tpa * 0.36, 1.1), 0.0, tpa)
    twopm = _clip(rng.gauss(twopa * 0.52, 1.4), 0.0, twopa)
    fgm = twopm + tpm
    fta = max(0.0, rng.gauss(minutes * 0.18, 1.4))
    ftm = _clip(rng.gauss(fta * 0.78, 0.9), 0.0, fta)
    oreb = max(0.0, rng.gauss(minutes * 0.05, 0.7))
    dreb = max(0.0, rng.gauss(minutes * 0.18, 1.2))
    reb = oreb + dreb
    ast = max(0.0, rng.gauss(minutes * 0.14, 1.3))
    stl = max(0.0, rng.gauss(minutes * 0.03, 0.5))
    blk = max(0.0, rng.gauss(minutes * 0.025, 0.5))
    tov = max(0.0, rng.gauss(minutes * 0.08, 0.8))
    pts = 2 * twopm + 3 * tpm + ftm
    return {
        "minutes": minutes,
        "fga": fga,
        "tpa": tpa,
        "twopa": twopa,
        "fgm": fgm,
        "tpm": tpm,
        "twopm": twopm,
        "fta": fta,
        "ftm": ftm,
        "oreb": oreb,
        "dreb": dreb,
        "reb": reb,
        "ast": ast,
        "stl": stl,
        "blk": blk,
        "tov": tov,
        "pts": pts,
        "pra": pts + reb + ast,
        "pr": pts + reb,
        "pa": pts + ast,
        "ra": reb + ast,
    }


def sample_football(rng: random.Random, role: str) -> dict[str, float]:
    if role in {"QB", ""}:
        pass_att = max(0.0, rng.gauss(34, 6))
        sacks = max(0.0, rng.gauss(2.2, 1.1))
        scramble = max(0.0, rng.gauss(3.0, 1.5))
        designed = max(0.0, rng.gauss(2.0, 1.2))
        rush_att = designed + scramble
        dropbacks = pass_att + sacks + scramble
        pass_cmp = _clip(rng.gauss(pass_att * 0.65, 3), 0.0, pass_att)
        pass_yds = max(0.0, rng.gauss(pass_att * 7.1, 45))
        rush_yds = max(0.0, rng.gauss(rush_att * 4.4, 18))
        rec_yds = 0.0
        targets = 0.0
        receptions = 0.0
        routes = 0.0
    else:
        pass_att = sacks = scramble = designed = dropbacks = pass_cmp = pass_yds = 0.0
        rush_att = max(0.0, rng.gauss(12 if role == "RB" else 1.5, 4))
        rush_yds = max(0.0, rng.gauss(rush_att * 4.3, 18))
        routes = max(0.0, rng.gauss(22 if role in {"WR", "TE"} else 8, 5))
        targets = _clip(rng.gauss(routes * 0.28, 2), 0.0, routes)
        receptions = _clip(rng.gauss(targets * 0.68, 1.4), 0.0, targets)
        rec_yds = max(0.0, rng.gauss(receptions * 11.5, 18))
    stats = {
        "pass_att": pass_att,
        "pass_cmp": pass_cmp,
        "sacks_taken": sacks,
        "scramble_att": scramble,
        "designed_rush_att": designed,
        "rush_att": rush_att,
        "dropbacks": dropbacks if role in {"QB", ""} else 0.0,
        "pass_yds": pass_yds,
        "rush_yds": rush_yds,
        "rec_yds": rec_yds,
        "receptions": receptions,
        "targets": targets,
        "routes": routes,
        "pass_rush_yds": pass_yds + rush_yds,
        "rush_rec_yds": rush_yds + rec_yds,
    }
    if stats["pass_cmp"] > stats["pass_att"] + 1e-9:
        raise RuntimeError("PRIMITIVE_CONSERVATION_FAILURE: cmp>att")
    if stats["receptions"] > stats["targets"] + 1e-9:
        raise RuntimeError("PRIMITIVE_CONSERVATION_FAILURE: rec>tgt")
    if stats["targets"] > stats["routes"] + 1e-9 and stats["routes"] > 0:
        raise RuntimeError("PRIMITIVE_CONSERVATION_FAILURE: tgt>routes")
    return stats


def sample_baseball_batter(rng: random.Random, pa: float) -> dict[str, float]:
    pa = max(0.0, pa)
    bb = _clip(rng.gauss(pa * 0.09, 0.4), 0.0, pa)
    hbp = _clip(rng.gauss(pa * 0.01, 0.15), 0.0, pa - bb)
    sf = _clip(rng.gauss(pa * 0.02, 0.15), 0.0, pa - bb - hbp)
    sh = _clip(rng.gauss(pa * 0.005, 0.08), 0.0, pa - bb - hbp - sf)
    ab = pa - bb - hbp - sf - sh
    so = _clip(rng.gauss(ab * 0.24, 0.7), 0.0, ab)
    hr = _clip(rng.gauss(ab * 0.04, 0.35), 0.0, ab)
    triple = _clip(rng.gauss(ab * 0.005, 0.08), 0.0, max(0.0, ab - hr))
    double = _clip(rng.gauss(ab * 0.05, 0.35), 0.0, max(0.0, ab - hr - triple))
    single = _clip(rng.gauss(ab * 0.15, 0.55), 0.0, max(0.0, ab - hr - triple - double))
    h = single + double + triple + hr
    tb = 1 * single + 2 * double + 3 * triple + 4 * hr
    stats = {
        "PA": pa,
        "AB": ab,
        "BB": bb,
        "HBP": hbp,
        "SF": sf,
        "SH": sh,
        "SO": so,
        "H": h,
        "1B": single,
        "2B": double,
        "3B": triple,
        "HR": hr,
        "TB": tb,
        "hits_runs_rbi": h + rng.gauss(0.6, 0.5) + rng.gauss(0.5, 0.5),
        "k": so,
        "h": h,
        "tb": tb,
    }
    failed = [c["rule_id"] for c in mlb_conservation(stats) if not c["passed"]]
    if failed:
        raise RuntimeError(f"PRIMITIVE_CONSERVATION_FAILURE: {failed}")
    return stats


MARKET_FROM_STATS = {
    "pts": "pts",
    "reb": "reb",
    "ast": "ast",
    "pra": "pra",
    "pr": "pr",
    "pa": "pa",
    "ra": "ra",
    "3pm": "tpm",
    "stl": "stl",
    "blk": "blk",
    "pass_yds": "pass_yds",
    "rush_yds": "rush_yds",
    "rec_yds": "rec_yds",
    "receptions": "receptions",
    "pass_rush_yds": "pass_rush_yds",
    "rush_rec_yds": "rush_rec_yds",
    "h": "H",
    "tb": "TB",
    "k": "SO",
    "hits_runs_rbi": "hits_runs_rbi",
}


def value_from_stats(market: str, stats: dict[str, float]) -> float:
    if market == "pra":
        return stats["pts"] + stats["reb"] + stats["ast"]
    key = MARKET_FROM_STATS.get(market, market)
    if key not in stats:
        raise KeyError(market)
    return float(stats[key])


def simulate_player_worlds(
    row: dict[str, Any],
    *,
    n: int,
    seed: str,
) -> list[dict[str, float]]:
    rng = _rng(f"{seed}:{row['playerId']}:{row['eventId']}")
    family = row.get("sportFamily")
    worlds = []
    for _ in range(n):
        if family == "basketball":
            minutes = 34.0 if row.get("league") == "NBA" else 31.0
            worlds.append(sample_basketball(rng, minutes))
        elif family == "gridiron":
            worlds.append(sample_football(rng, row.get("role") or "QB"))
        elif family == "baseball":
            worlds.append(sample_baseball_batter(rng, 4.2))
        else:
            raise KeyError(family)
    return worlds
