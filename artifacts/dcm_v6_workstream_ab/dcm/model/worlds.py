"""Evidence-parameterized shared primitive worlds.

Opportunity is sampled before conditional efficiency. Composite markets derive
from the same world. Generic priors remain development fallbacks only; runner
selection gates prevent them from becoming production PLAYABLEs.
"""
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


def _p(params: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def sample_basketball(rng: random.Random, minutes: float, parameters: dict[str, Any] | None = None) -> dict[str, float]:
    p = parameters or {}
    fga = max(0.0, rng.gauss(minutes * max(0.01, _p(p, "fga_per_min", 0.55)), 3.0))
    tpa = _clip(rng.gauss(fga * _clip(_p(p, "three_pa_share", 0.42), 0.0, 1.0), 1.6), 0.0, fga)
    twopa = fga - tpa
    tpm = _clip(rng.gauss(tpa * _clip(_p(p, "three_fg_pct", 0.36), 0.05, 0.8), 1.0), 0.0, tpa)
    twopm = _clip(rng.gauss(twopa * _clip(_p(p, "two_fg_pct", 0.52), 0.05, 0.95), 1.3), 0.0, twopa)
    fgm = twopm + tpm
    fta = max(0.0, rng.gauss(minutes * max(0.0, _p(p, "fta_per_min", 0.18)), 1.3))
    ftm = _clip(rng.gauss(fta * _clip(_p(p, "ft_pct", 0.78), 0.2, 1.0), 0.8), 0.0, fta)
    reb = max(0.0, rng.gauss(minutes * max(0.0, _p(p, "reb_per_min", 0.23)), 1.4))
    oreb = _clip(rng.gauss(reb * _clip(_p(p, "oreb_share", 0.22), 0.0, 1.0), 0.5), 0.0, reb)
    dreb = reb - oreb
    ast = max(0.0, rng.gauss(minutes * max(0.0, _p(p, "ast_per_min", 0.14)), 1.2))
    stl = max(0.0, rng.gauss(minutes * max(0.0, _p(p, "stl_per_min", 0.03)), 0.5))
    blk = max(0.0, rng.gauss(minutes * max(0.0, _p(p, "blk_per_min", 0.025)), 0.5))
    tov = max(0.0, rng.gauss(minutes * max(0.0, _p(p, "tov_per_min", 0.08)), 0.8))
    pts = 2 * twopm + 3 * tpm + ftm
    return {
        "minutes": minutes, "fga": fga, "tpa": tpa, "twopa": twopa, "fgm": fgm,
        "tpm": tpm, "twopm": twopm, "fta": fta, "ftm": ftm, "oreb": oreb,
        "dreb": dreb, "reb": reb, "ast": ast, "stl": stl, "blk": blk, "tov": tov,
        "pts": pts, "pra": pts + reb + ast, "pr": pts + reb, "pa": pts + ast, "ra": reb + ast,
    }


def sample_football(rng: random.Random, role: str, parameters: dict[str, Any] | None = None) -> dict[str, float]:
    p = parameters or {}
    role = (role or "QB").upper()
    if role == "QB":
        pass_att = max(0.0, rng.gauss(_p(p, "pass_att_mean", 34.0), max(1.0, _p(p, "pass_att_sd", 6.0))))
        sacks = max(0.0, rng.gauss(_p(p, "sacks_mean", 2.2), 1.1))
        rush_att = max(0.0, rng.gauss(_p(p, "rush_att_mean", 5.0), max(0.5, _p(p, "rush_att_sd", 2.0))))
        scramble = min(rush_att, max(0.0, rng.gauss(rush_att * 0.6, 0.8)))
        designed = max(0.0, rush_att - scramble)
        pass_cmp = _clip(rng.gauss(pass_att * _clip(_p(p, "completion_rate", 0.65), 0.2, 0.9), 2.5), 0.0, pass_att)
        pass_yds = max(0.0, rng.gauss(pass_att * max(1.0, _p(p, "pass_ypa", 7.1)), 42.0))
        rush_yds = max(0.0, rng.gauss(rush_att * max(0.0, _p(p, "rush_ypa", 4.4)), 16.0))
        routes = targets = receptions = rec_yds = 0.0
        dropbacks = pass_att + sacks + scramble
    else:
        pass_att = pass_cmp = sacks = scramble = designed = pass_yds = dropbacks = 0.0
        rush_att = max(0.0, rng.gauss(_p(p, "rush_att_mean", 12.0 if role == "RB" else 1.5), max(0.5, _p(p, "rush_att_sd", 4.0))))
        rush_yds = max(0.0, rng.gauss(rush_att * max(0.0, _p(p, "rush_ypa", 4.3)), 17.0))
        routes = max(0.0, rng.gauss(_p(p, "routes_mean", 22.0 if role in {"WR", "TE"} else 8.0), max(1.0, _p(p, "routes_sd", 5.0))))
        targets = _clip(rng.gauss(routes * _clip(_p(p, "target_rate", 0.28), 0.0, 1.0), 1.8), 0.0, routes)
        receptions = _clip(rng.gauss(targets * _clip(_p(p, "catch_rate", 0.68), 0.0, 1.0), 1.2), 0.0, targets)
        rec_yds = max(0.0, rng.gauss(receptions * max(0.0, _p(p, "rec_ypr", 11.5)), 17.0))
    stats = {
        "pass_att": pass_att, "pass_cmp": pass_cmp, "sacks_taken": sacks, "scramble_att": scramble,
        "designed_rush_att": designed, "rush_att": rush_att, "dropbacks": dropbacks,
        "pass_yds": pass_yds, "rush_yds": rush_yds, "rec_yds": rec_yds,
        "receptions": receptions, "targets": targets, "routes": routes,
        "pass_rush_yds": pass_yds + rush_yds, "rush_rec_yds": rush_yds + rec_yds,
    }
    if stats["pass_cmp"] > stats["pass_att"] + 1e-9 or stats["receptions"] > stats["targets"] + 1e-9:
        raise RuntimeError("PRIMITIVE_CONSERVATION_FAILURE")
    return stats


def sample_baseball_batter(rng: random.Random, pa: float, parameters: dict[str, Any] | None = None) -> dict[str, float]:
    p = parameters or {}
    pa = max(0.0, pa)
    bb = _clip(rng.gauss(pa * _clip(_p(p, "bb_rate", 0.09), 0, 0.6), 0.35), 0, pa)
    hbp = _clip(rng.gauss(pa * _clip(_p(p, "hbp_rate", 0.01), 0, 0.2), 0.12), 0, pa - bb)
    sf = _clip(rng.gauss(pa * _clip(_p(p, "sf_rate", 0.02), 0, 0.2), 0.12), 0, pa - bb - hbp)
    sh = _clip(rng.gauss(pa * _clip(_p(p, "sh_rate", 0.005), 0, 0.1), 0.07), 0, pa - bb - hbp - sf)
    ab = max(0.0, pa - bb - hbp - sf - sh)
    so = _clip(rng.gauss(ab * _clip(_p(p, "so_rate", 0.24), 0, 0.8), 0.65), 0, ab)
    hr = _clip(rng.gauss(ab * _clip(_p(p, "hr_rate", 0.04), 0, 0.3), 0.30), 0, ab)
    triple = _clip(rng.gauss(ab * _clip(_p(p, "triple_rate", 0.005), 0, 0.1), 0.07), 0, max(0, ab - hr))
    double = _clip(rng.gauss(ab * _clip(_p(p, "double_rate", 0.05), 0, 0.4), 0.32), 0, max(0, ab - hr - triple))
    single = _clip(rng.gauss(ab * _clip(_p(p, "single_rate", 0.15), 0, 0.7), 0.50), 0, max(0, ab - hr - triple - double))
    h = single + double + triple + hr
    tb = single + 2 * double + 3 * triple + 4 * hr
    runs = max(0.0, rng.gauss(pa * max(0.0, _p(p, "run_per_pa", 0.14)), 0.45))
    rbi = max(0.0, rng.gauss(pa * max(0.0, _p(p, "rbi_per_pa", 0.12)), 0.45))
    stats = {"PA": pa, "AB": ab, "BB": bb, "HBP": hbp, "SF": sf, "SH": sh, "SO": so,
             "H": h, "1B": single, "2B": double, "3B": triple, "HR": hr, "TB": tb,
             "R": runs, "RBI": rbi, "hits_runs_rbi": h + runs + rbi, "k": so, "h": h, "tb": tb}
    failed = [c["rule_id"] for c in mlb_conservation(stats) if not c["passed"]]
    if failed:
        raise RuntimeError(f"PRIMITIVE_CONSERVATION_FAILURE:{failed}")
    return stats


MARKET_FROM_STATS = {
    "pts": "pts", "reb": "reb", "ast": "ast", "pra": "pra", "pr": "pr", "pa": "pa", "ra": "ra",
    "3pm": "tpm", "stl": "stl", "blk": "blk", "pass_yds": "pass_yds", "rush_yds": "rush_yds",
    "rec_yds": "rec_yds", "receptions": "receptions", "pass_rush_yds": "pass_rush_yds",
    "rush_rec_yds": "rush_rec_yds", "h": "H", "tb": "TB", "k": "SO", "hits_runs_rbi": "hits_runs_rbi",
}


def value_from_stats(market: str, stats: dict[str, float]) -> float:
    if market == "pra":
        return stats["pts"] + stats["reb"] + stats["ast"]
    key = MARKET_FROM_STATS.get(market, market)
    if key not in stats:
        raise KeyError(market)
    return float(stats[key])


def simulate_player_worlds(row: dict[str, Any], *, n: int, seed: str, parameter_snapshot: dict[str, Any] | None = None) -> list[dict[str, float]]:
    rng = _rng(f"{seed}:{row['playerId']}:{row['eventId']}")
    params = (parameter_snapshot or {}).get("parameters") if isinstance(parameter_snapshot, dict) else {}
    params = params if isinstance(params, dict) else {}
    worlds = []
    for _ in range(n):
        if row.get("sportFamily") == "basketball":
            mean_minutes = _p(params, "minutes_mean", 34.0 if row.get("league") == "NBA" else 31.0)
            sd_minutes = max(0.5, _p(params, "minutes_sd", 4.5))
            regulation = 48.0 if row.get("league") == "NBA" else 40.0
            minutes = _clip(rng.gauss(mean_minutes, sd_minutes), 0.0, regulation + 10.0)
            worlds.append(sample_basketball(rng, minutes, params))
        elif row.get("sportFamily") == "gridiron":
            worlds.append(sample_football(rng, str(params.get("role") or row.get("role") or "QB"), params))
        elif row.get("sportFamily") == "baseball":
            pa = max(0.0, rng.gauss(_p(params, "pa_mean", 4.2), max(0.2, _p(params, "pa_sd", 0.8))))
            worlds.append(sample_baseball_batter(rng, pa, params))
        else:
            raise KeyError(row.get("sportFamily"))
    return worlds
