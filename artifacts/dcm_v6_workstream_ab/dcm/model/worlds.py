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


def _nonneg_int_gauss(rng: random.Random, mean: float, sd: float) -> int:
    return max(0, int(round(rng.gauss(mean, max(0.01, sd)))))


def _binomial(rng: random.Random, n: int, p: float) -> int:
    p = _clip(float(p), 0.0, 1.0)
    return sum(1 for _ in range(max(0, int(n))) if rng.random() < p)


def _poisson(rng: random.Random, lam: float) -> int:
    lam = max(0.0, float(lam))
    if lam <= 0.0:
        return 0
    # Knuth is efficient for the small per-player lambdas used here.
    threshold = __import__("math").exp(-lam)
    k = 0
    product = 1.0
    while product > threshold:
        k += 1
        product *= rng.random()
    return k - 1


def _categorical_counts(
    rng: random.Random,
    n: int,
    probabilities: dict[str, float],
) -> dict[str, int]:
    clean = {key: max(0.0, float(value)) for key, value in probabilities.items()}
    total = sum(clean.values())
    # Reserve at least 2% probability for an ordinary out when supplied rates
    # are overly aggressive rather than allowing impossible >100% mass.
    if total > 0.98:
        scale = 0.98 / total
        clean = {key: value * scale for key, value in clean.items()}
    keys = list(clean)
    counts = {key: 0 for key in keys}
    for _ in range(max(0, int(n))):
        u = rng.random()
        cumulative = 0.0
        for key in keys:
            cumulative += clean[key]
            if u < cumulative:
                counts[key] += 1
                break
    return counts


def _p(params: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def generate_event_contexts(
    family: str,
    event_id: str,
    *,
    n: int,
    seed: str,
) -> list[dict[str, float]]:
    """Create deterministic latent event states shared by every player.

    The event stream is keyed only by forecast seed + sport family + event ID,
    never by player identity. This preserves cross-player event dependence while
    player-specific RNG remains independent conditional on the event state.
    """
    rng = _rng(f"{seed}:EVENT:{family}:{event_id}")
    out = []
    for _ in range(n):
        out.append({
            "tempo": _clip(rng.gauss(1.0, 0.055), 0.84, 1.16),
            "efficiency": _clip(rng.gauss(1.0, 0.045), 0.86, 1.14),
            "opportunity": _clip(rng.gauss(1.0, 0.045), 0.86, 1.14),
            "environment": _clip(rng.gauss(1.0, 0.035), 0.88, 1.12),
        })
    return out


def _contextualize(
    params: dict[str, Any],
    family: str,
    context: dict[str, float],
) -> dict[str, Any]:
    p = dict(params)
    tempo = float(context["tempo"])
    eff = float(context["efficiency"])
    opp = float(context["opportunity"])
    env = float(context["environment"])

    if family == "basketball":
        if "minutes_mean" in p:
            p["minutes_mean"] = _p(p, "minutes_mean", 34.0) * opp
        for key in ("fga_per_min", "fta_per_min", "reb_per_min", "ast_per_min", "stl_per_min", "blk_per_min", "tov_per_min"):
            if key in p:
                p[key] = _p(p, key, 0.0) * tempo
        for key in ("two_fg_pct", "three_fg_pct"):
            if key in p:
                p[key] = _p(p, key, 0.5) * eff
    elif family == "gridiron":
        for key in ("pass_att_mean", "rush_att_mean", "routes_mean"):
            if key in p:
                p[key] = _p(p, key, 0.0) * opp
        for key in ("pass_ypa", "rush_ypa", "rec_ypr"):
            if key in p:
                p[key] = _p(p, key, 0.0) * eff * env
    elif family == "baseball":
        if "pa_mean" in p:
            p["pa_mean"] = _p(p, "pa_mean", 4.2) * opp
        for key in ("single_rate", "double_rate", "triple_rate", "hr_rate", "run_per_pa", "rbi_per_pa"):
            if key in p:
                p[key] = _p(p, key, 0.0) * eff * env
        if "so_rate" in p:
            p["so_rate"] = _p(p, "so_rate", 0.24) / max(0.75, eff)
    return p


LEDGER_KEYS = (
    "minutes", "fgm", "fga", "tpm", "three_pm", "tpa", "three_pa",
    "twopm", "twopa", "ftm", "fta", "oreb", "dreb", "reb", "ast",
    "stl", "blk", "tov", "pf", "pts",
)


def assert_ledger_identities(ledger: dict[str, Any]) -> None:
    """Fail closed when a world violates basketball counting identities."""
    three_pa = float(ledger.get("three_pa", ledger.get("tpa", 0)))
    three_pm = float(ledger.get("three_pm", ledger.get("tpm", 0)))
    twopa = float(ledger["twopa"])
    twopm = float(ledger["twopm"])
    fga = float(ledger["fga"])
    fgm = float(ledger["fgm"])
    oreb = float(ledger["oreb"])
    dreb = float(ledger["dreb"])
    reb = float(ledger["reb"])
    pts = float(ledger["pts"])
    ftm = float(ledger["ftm"])
    failed = []
    if abs(twopa - (fga - three_pa)) > 1e-9:
        failed.append("2PA")
    if abs(twopm - (fgm - three_pm)) > 1e-9:
        failed.append("2PM")
    if abs(fgm - (twopm + three_pm)) > 1e-9:
        failed.append("FGM")
    if abs(reb - (oreb + dreb)) > 1e-9:
        failed.append("REB")
    if abs(pts - (2 * twopm + 3 * three_pm + ftm)) > 1e-9:
        failed.append("PTS")
    if fgm > fga + 1e-9:
        failed.append("MADE_FGA")
    if three_pm > three_pa + 1e-9:
        failed.append("MADE_TPA")
    if float(ledger.get("ftm", 0)) > float(ledger.get("fta", 0)) + 1e-9:
        failed.append("MADE_FTA")
    if failed:
        raise RuntimeError(f"PRIMITIVE_CONSERVATION_FAILURE:{failed}")


def as_primitive_ledger(stats: dict[str, Any]) -> dict[str, float]:
    """Canonical PrimitiveStatLedger dict. Applies oreb/dreb split if only reb is present."""
    out = dict(stats)
    if "tpa" not in out and "three_pa" in out:
        out["tpa"] = out["three_pa"]
    if "tpm" not in out and "three_pm" in out:
        out["tpm"] = out["three_pm"]
    if "three_pa" not in out and "tpa" in out:
        out["three_pa"] = out["tpa"]
    if "three_pm" not in out and "tpm" in out:
        out["three_pm"] = out["tpm"]
    if "reb" in out and ("oreb" not in out or "dreb" not in out):
        reb = max(0, int(round(float(out["reb"]))))
        share = float(out.get("oreb_share") or 0.22)
        oreb = int(round(reb * share))
        oreb = min(max(0, oreb), reb)
        out["oreb"] = oreb
        out["dreb"] = reb - oreb
        out["reb"] = reb
    if "pf" not in out:
        out["pf"] = 0
    if "twopa" not in out and "fga" in out:
        out["twopa"] = float(out["fga"]) - float(out.get("tpa") or 0)
    if "twopm" not in out and "fgm" in out:
        out["twopm"] = float(out["fgm"]) - float(out.get("tpm") or 0)
    ledger = {k: float(out[k]) for k in LEDGER_KEYS if k in out}
    for k in LEDGER_KEYS:
        if k not in ledger:
            raise RuntimeError(f"PRIMITIVE_CONSERVATION_FAILURE:missing:{k}")
    assert_ledger_identities(ledger)
    return ledger


def sample_basketball(
    rng: random.Random,
    minutes: float,
    parameters: dict[str, Any] | None = None,
    *,
    allocated_fga: int | None = None,
) -> dict[str, float]:
    p = parameters or {}
    if allocated_fga is None:
        fga_mean = minutes * max(0.01, _p(p, "fga_per_min", 0.55))
        fga = _nonneg_int_gauss(rng, fga_mean, max(1.0, fga_mean ** 0.5))
    else:
        fga = max(0, int(allocated_fga))
    tpa = _binomial(rng, fga, _p(p, "three_pa_share", 0.42))
    twopa = fga - tpa
    tpm = _binomial(rng, tpa, _p(p, "three_fg_pct", 0.36))
    twopm = _binomial(rng, twopa, _p(p, "two_fg_pct", 0.52))
    fgm = twopm + tpm

    fta_mean = minutes * max(0.0, _p(p, "fta_per_min", 0.18))
    fta = _nonneg_int_gauss(rng, fta_mean, max(0.75, fta_mean ** 0.5))
    ftm = _binomial(rng, fta, _p(p, "ft_pct", 0.78))

    reb_mean = minutes * max(0.0, _p(p, "reb_per_min", 0.23))
    reb = _nonneg_int_gauss(rng, reb_mean, max(0.75, reb_mean ** 0.5))
    oreb = _binomial(rng, reb, _p(p, "oreb_share", 0.22))
    dreb = reb - oreb

    ast_mean = minutes * max(0.0, _p(p, "ast_per_min", 0.14))
    stl_mean = minutes * max(0.0, _p(p, "stl_per_min", 0.03))
    blk_mean = minutes * max(0.0, _p(p, "blk_per_min", 0.025))
    tov_mean = minutes * max(0.0, _p(p, "tov_per_min", 0.08))
    pf_mean = minutes * max(0.0, _p(p, "pf_per_min", 0.07))
    ast = _nonneg_int_gauss(rng, ast_mean, max(0.65, ast_mean ** 0.5))
    stl = _poisson(rng, stl_mean)
    blk = _poisson(rng, blk_mean)
    tov = _nonneg_int_gauss(rng, tov_mean, max(0.55, tov_mean ** 0.5))
    pf = _nonneg_int_gauss(rng, pf_mean, max(0.45, pf_mean ** 0.5))

    pts = 2 * twopm + 3 * tpm + ftm
    # Composites are derived from this ledger, never independently sampled.
    stats = {
        "minutes": minutes, "fga": fga, "tpa": tpa, "three_pa": tpa, "twopa": twopa,
        "fgm": fgm, "tpm": tpm, "three_pm": tpm, "twopm": twopm, "fta": fta, "ftm": ftm,
        "oreb": oreb, "dreb": dreb, "reb": reb, "ast": ast, "stl": stl, "blk": blk,
        "tov": tov, "pf": pf, "pts": pts,
        "pra": pts + reb + ast, "pr": pts + reb, "pa": pts + ast, "ra": reb + ast,
    }
    assert_ledger_identities(stats)
    return stats

def sample_football(rng: random.Random, role: str, parameters: dict[str, Any] | None = None) -> dict[str, float]:
    p = parameters or {}
    role = (role or "QB").upper()
    if role == "QB":
        pass_att = _nonneg_int_gauss(rng, _p(p, "pass_att_mean", 34.0), max(1.0, _p(p, "pass_att_sd", 6.0)))
        sacks = _nonneg_int_gauss(rng, _p(p, "sacks_mean", 2.2), 1.1)
        rush_att = _nonneg_int_gauss(rng, _p(p, "rush_att_mean", 5.0), max(0.5, _p(p, "rush_att_sd", 2.0)))
        scramble = _binomial(rng, rush_att, 0.60)
        designed = rush_att - scramble
        pass_cmp = _binomial(rng, pass_att, _p(p, "completion_rate", 0.65))
        pass_yds = int(round(rng.gauss(pass_att * max(1.0, _p(p, "pass_ypa", 7.1)), 42.0)))
        rush_yds = int(round(rng.gauss(rush_att * _p(p, "rush_ypa", 4.4), 16.0)))
        routes = targets = receptions = rec_yds = 0
        dropbacks = pass_att + sacks + scramble
    else:
        pass_att = pass_cmp = sacks = scramble = designed = pass_yds = dropbacks = 0
        rush_att = _nonneg_int_gauss(
            rng,
            _p(p, "rush_att_mean", 12.0 if role == "RB" else 1.5),
            max(0.5, _p(p, "rush_att_sd", 4.0)),
        )
        rush_yds = int(round(rng.gauss(rush_att * _p(p, "rush_ypa", 4.3), 17.0)))
        routes = _nonneg_int_gauss(
            rng,
            _p(p, "routes_mean", 22.0 if role in {"WR", "TE"} else 8.0),
            max(1.0, _p(p, "routes_sd", 5.0)),
        )
        targets = _binomial(rng, routes, _p(p, "target_rate", 0.28))
        receptions = _binomial(rng, targets, _p(p, "catch_rate", 0.68))
        rec_yds = int(round(rng.gauss(receptions * max(0.0, _p(p, "rec_ypr", 11.5)), 17.0)))
    snaps = max(dropbacks if role == "QB" else (routes or rush_att), pass_att, rush_att, routes)
    stats = {
        "pass_att": pass_att, "pass_cmp": pass_cmp, "sacks_taken": sacks, "scramble_att": scramble,
        "designed_rush_att": designed, "rush_att": rush_att, "dropbacks": dropbacks,
        "pass_yds": pass_yds, "rush_yds": rush_yds, "rec_yds": rec_yds,
        "receptions": receptions, "targets": targets, "routes": routes,
        "snaps": snaps, "off_snaps": snaps,
        "pass_rush_yds": pass_yds + rush_yds, "rush_rec_yds": rush_yds + rec_yds,
    }
    if stats["pass_cmp"] > stats["pass_att"] or stats["receptions"] > stats["targets"] or stats["targets"] > stats["routes"]:
        raise RuntimeError("PRIMITIVE_CONSERVATION_FAILURE")
    return stats

def sample_baseball_batter(rng: random.Random, pa: float, parameters: dict[str, Any] | None = None) -> dict[str, float]:
    p = parameters or {}
    pa_i = max(0, int(round(pa)))

    # Non-AB plate appearance outcomes are allocated sequentially so the exact
    # identity PA = AB + BB + HBP + SF + SH holds in every world.
    bb = _binomial(rng, pa_i, _p(p, "bb_rate", 0.09))
    remaining = pa_i - bb
    hbp = _binomial(rng, remaining, _p(p, "hbp_rate", 0.01))
    remaining -= hbp
    sf = _binomial(rng, remaining, _p(p, "sf_rate", 0.02))
    remaining -= sf
    sh = _binomial(rng, remaining, _p(p, "sh_rate", 0.005))
    ab = remaining - sh

    outcomes = _categorical_counts(
        rng,
        ab,
        {
            "SO": _p(p, "so_rate", 0.24),
            "HR": _p(p, "hr_rate", 0.04),
            "3B": _p(p, "triple_rate", 0.005),
            "2B": _p(p, "double_rate", 0.05),
            "1B": _p(p, "single_rate", 0.15),
        },
    )
    so = outcomes["SO"]
    hr = outcomes["HR"]
    triple = outcomes["3B"]
    double = outcomes["2B"]
    single = outcomes["1B"]
    h = single + double + triple + hr
    tb = single + 2 * double + 3 * triple + 4 * hr

    runs = _poisson(rng, pa_i * max(0.0, _p(p, "run_per_pa", 0.14)))
    rbi = _poisson(rng, pa_i * max(0.0, _p(p, "rbi_per_pa", 0.12)))
    stats = {
        "PA": pa_i, "AB": ab, "BB": bb, "HBP": hbp, "SF": sf, "SH": sh,
        "SO": so, "H": h, "1B": single, "2B": double, "3B": triple, "HR": hr,
        "TB": tb, "R": runs, "RBI": rbi, "hits_runs_rbi": h + runs + rbi,
        "k": so, "h": h, "tb": tb,
    }
    failed = [check["rule_id"] for check in mlb_conservation(stats) if not check["passed"]]
    if failed:
        raise RuntimeError(f"PRIMITIVE_CONSERVATION_FAILURE:{failed}")
    return stats

MARKET_FROM_STATS = {
    "pts": "pts", "reb": "reb", "ast": "ast", "pra": "pra", "pr": "pr", "pa": "pa", "ra": "ra",
    "3pm": "tpm", "stl": "stl", "blk": "blk", "pass_yds": "pass_yds", "pass_att": "pass_att",
    "pass_cmp": "pass_cmp", "rush_yds": "rush_yds", "rush_att": "rush_att",
    "rec_yds": "rec_yds", "receptions": "receptions", "pass_rush_yds": "pass_rush_yds",
    "rush_rec_yds": "rush_rec_yds", "h": "H", "tb": "TB", "k": "SO", "hits_runs_rbi": "hits_runs_rbi",
}


def value_from_stats(market: str, stats: dict[str, float], board_id: str = "FULL_GAME") -> float:
    from dcm.model.market_derive import (
        UnknownMarketError,
        derive_market,
        looks_like_basketball_ledger,
        looks_like_gridiron_ledger,
    )

    if looks_like_basketball_ledger(stats):
        return derive_market(stats, market, board_id=board_id)
    if looks_like_gridiron_ledger(stats):
        try:
            return derive_market(stats, market, board_id=board_id)
        except UnknownMarketError:
            raise KeyError(market)
    if market == "pra" and "pts" in stats and "reb" in stats and "ast" in stats:
        return float(stats["pts"]) + float(stats["reb"]) + float(stats["ast"])
    key = MARKET_FROM_STATS.get(market, market)
    if key not in stats:
        raise KeyError(market)
    return float(stats[key])


def simulate_player_worlds(
    row: dict[str, Any],
    *,
    n: int,
    seed: str,
    parameter_snapshot: dict[str, Any] | None = None,
    event_contexts: list[dict[str, float]] | None = None,
) -> list[dict[str, float]]:
    family = str(row.get("sportFamily") or "")
    rng = _rng(f"{seed}:PLAYER:{row['playerId']}:{row['eventId']}")
    params = (parameter_snapshot or {}).get("parameters") if isinstance(parameter_snapshot, dict) else {}
    params = params if isinstance(params, dict) else {}
    contexts = event_contexts or generate_event_contexts(
        family, str(row.get("eventId") or ""), n=n, seed=seed
    )
    if len(contexts) < n:
        raise ValueError("EVENT_CONTEXT_WORLD_COUNT_TOO_SMALL")

    worlds = []
    mix = (parameter_snapshot or {}).get("availabilityMixture") if isinstance(parameter_snapshot, dict) else None
    try:
        p_play = float((mix or {}).get("pPlay")) if isinstance(mix, dict) and mix.get("pPlay") is not None else 1.0
    except (TypeError, ValueError):
        p_play = 1.0
    # ACTIVE (~0.99) is not mixed. PROBABLE/QUESTIONABLE draw PLAY vs SIT per world.
    mix_worlds = p_play < 0.97
    for idx in range(n):
        world_params = _contextualize(params, family, contexts[idx])
        if family == "basketball":
            sit = mix_worlds and rng.random() > p_play
            mean_minutes = _p(world_params, "minutes_mean", 34.0 if row.get("league") == "NBA" else 31.0)
            sd_minutes = max(0.5, _p(world_params, "minutes_sd", 4.5))
            regulation = 48.0 if row.get("league") == "NBA" else 40.0
            minutes = 0.0 if sit else _clip(rng.gauss(mean_minutes, sd_minutes), 0.0, regulation + 10.0)
            world = sample_basketball(rng, minutes, world_params)
            from dcm.model.quarter_worlds import attach_quarter_state
            q_rng = _rng(f"{seed}:QUARTER:{row['playerId']}:{row['eventId']}:{idx}")
            attach_quarter_state(world, q_rng)
            if sit:
                world["_availabilityState"] = "SIT"
            worlds.append(world)
        elif family == "gridiron":
            worlds.append(
                sample_football(
                    rng,
                    str(world_params.get("role") or row.get("role") or "QB"),
                    world_params,
                )
            )
        elif family == "baseball":
            pa = _nonneg_int_gauss(
                rng,
                _p(world_params, "pa_mean", 4.2),
                max(0.2, _p(world_params, "pa_sd", 0.8)),
            )
            worlds.append(sample_baseball_batter(rng, pa, world_params))
        else:
            raise KeyError(family)
    return worlds
