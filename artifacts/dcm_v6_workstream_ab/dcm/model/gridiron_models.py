"""Gridiron opportunity, efficiency, and team/event models.

QB vs skill vs kicker paths are explicit. Opportunity (snaps/routes/targets/
dropbacks/carries/FG-XP attempts) is fit separately from efficiency (YPA/
catch-rate/YPR/TD-INT rates/make rates). Opponent pass/rush defense is a
required placeholder for PLAYABLE on relevant markets — missing values fail
closed rather than defaulting to 1.0 silently.

No pickled models. Deterministic hashes of inputs only. Shrinkage is the
stdlib Empirical Bayes primitive (ALG-ML-PROB-001).
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from dcm.algorithms.ml_families import empirical_bayes_shrink
from dcm.contracts.hashes import content_hash

OPP_VERSION = "GRIDIRON_OPP_V1_2026-08-30"
EFF_VERSION = "GRIDIRON_EFF_V1_2026-08-30"
TEAM_EVENT_VERSION = "GRIDIRON_TEAM_EVENT_V2_CFB_REGIMES_2026-09-02"

QB_ROLES = frozenset({"QB", "QUARTERBACK"})
SKILL_ROLES = frozenset({"WR", "TE", "RB", "FB", "HB", "SLOT", "WR1", "WR2"})
KICKER_ROLES = frozenset({"K", "PK", "KICKER"})

LEAGUE_PRIORS: dict[str, dict[str, float]] = {
    "NFL": {
        "pass_att_mean": 34.0, "pass_att_sd": 6.0,
        "rush_att_mean_qb": 5.0, "rush_att_sd_qb": 2.0,
        "rush_att_mean_rb": 14.0, "rush_att_mean_skill": 1.5, "rush_att_sd": 4.0,
        "routes_mean_wr": 28.0, "routes_mean_te": 20.0, "routes_mean_rb": 10.0, "routes_sd": 5.0,
        "snaps_mean_qb": 64.0, "snaps_mean_wr": 55.0, "snaps_sd": 8.0,
        "sacks_mean": 2.2, "completion_rate": 0.65, "pass_ypa": 7.1,
        "rush_ypa_qb": 4.4, "rush_ypa": 4.3, "target_rate": 0.28,
        "catch_rate": 0.68, "rec_ypr": 11.5,
        "pass_td_rate": 0.045, "int_rate": 0.025, "rush_td_rate": 0.055, "rec_td_rate": 0.055,
        "fg_att_mean": 1.7, "xp_att_mean": 2.4, "fg_rate": 0.84, "xp_rate": 0.94,
        "plays": 65.0, "pass_rate": 0.58, "rush_rate": 0.42, "pace": 1.0,
    },
    "CFB": {
        "pass_att_mean": 32.0, "pass_att_sd": 7.0,
        "rush_att_mean_qb": 8.0, "rush_att_sd_qb": 3.0,
        "rush_att_mean_rb": 16.0, "rush_att_mean_skill": 1.2, "rush_att_sd": 5.0,
        "routes_mean_wr": 26.0, "routes_mean_te": 18.0, "routes_mean_rb": 8.0, "routes_sd": 6.0,
        "snaps_mean_qb": 68.0, "snaps_mean_wr": 50.0, "snaps_sd": 10.0,
        "sacks_mean": 2.0, "completion_rate": 0.62, "pass_ypa": 7.8,
        "rush_ypa_qb": 5.2, "rush_ypa": 4.8, "target_rate": 0.26,
        "catch_rate": 0.64, "rec_ypr": 13.0,
        "pass_td_rate": 0.050, "int_rate": 0.028, "rush_td_rate": 0.070, "rec_td_rate": 0.065,
        "fg_att_mean": 1.8, "xp_att_mean": 3.2, "fg_rate": 0.78, "xp_rate": 0.93,
        "plays": 70.0, "pass_rate": 0.54, "rush_rate": 0.46, "pace": 1.0,
    },
}
_DEFAULT = LEAGUE_PRIORS["NFL"]

PASS_MARKETS = frozenset({
    "pass_yds", "pass_rush_yds", "receptions", "rec_yds", "pass_att", "pass_cmp",
    "pass_td", "interceptions", "rec_td", "targets", "rush_rec_yds", "rush_rec_td", "pass_rush_td",
})
RUSH_MARKETS = frozenset({
    "rush_yds", "pass_rush_yds", "rush_rec_yds", "rush_att", "rush_td", "rush_rec_td", "pass_rush_td",
})
REC_MARKETS = frozenset({
    "receptions", "rec_yds", "rush_rec_yds", "rec_td", "targets", "rush_rec_td",
})
KICK_MARKETS = frozenset({"fg_made", "xp_made", "kicking_pts", "fg_att"})


def _f(v: Any, default: float | None = None) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _avg(logs: list[dict[str, Any]], key: str) -> tuple[float | None, int]:
    vals = []
    for row in logs:
        x = _f(row.get(key))
        if x is not None:
            vals.append(x)
    return (mean(vals), len(vals)) if vals else (None, 0)


def _sd(logs: list[dict[str, Any]], key: str, fallback: float) -> float:
    vals = []
    for row in logs:
        x = _f(row.get(key))
        if x is not None:
            vals.append(x)
    return pstdev(vals) if len(vals) >= 2 else fallback


def _blend(role_val: float | None, season_val: float | None, prior: float, weights: dict[str, float]) -> float:
    rw = float(weights.get("roleWeight") or 0.0)
    sw = float(weights.get("seasonWeight") or 0.0)
    pw = float(weights.get("priorWeight") or 0.0)
    parts: list[tuple[float, float]] = []
    if role_val is not None:
        parts.append((rw, role_val))
    if season_val is not None and (role_val is None or abs(season_val - role_val) > 1e-12):
        parts.append((sw, season_val))
    parts.append((pw if pw > 0 else 1.0, prior))
    wsum = sum(w for w, _ in parts)
    if wsum <= 0:
        return prior
    return sum(w * v for w, v in parts) / wsum


def _rate(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def league_priors(league: str | None) -> dict[str, float]:
    key = str(league or "").strip().upper()
    return dict(LEAGUE_PRIORS.get(key) or _DEFAULT)


def _role_bucket(role: str | None) -> str:
    text = str(role or "").strip().upper()
    if text in QB_ROLES or text == "QB":
        return "QB"
    if text in KICKER_ROLES:
        return "K"
    if text in {"RB", "FB", "HB"}:
        return "RB"
    if text in {"TE"}:
        return "TE"
    return "WR"


def _eb(sample: float | None, n: int, prior: float, *, prior_n: float = 8.0, weights: dict[str, float] | None = None) -> float:
    """Empirical Bayes shrink toward the declared prior. Never uses outcomes."""
    if sample is None or n <= 0:
        return prior
    w = weights or {}
    rw = float(w.get("roleWeight") or 0.0)
    pw = float(w.get("priorWeight") or 0.0)
    pn = float(prior_n)
    if pw + rw > 0:
        pn = max(1.0, float(prior_n) * (pw / max(rw, 1e-9) if rw > 0 else 1.0))
    return empirical_bayes_shrink(float(sample), float(n), float(prior), pn)


class GridironOpportunityModel:
    """Snaps / dropbacks / routes / targets / carries / kicking attempts from role-comparable logs."""

    definition_version = OPP_VERSION

    def fit(
        self,
        comparable_logs: list[dict[str, Any]],
        *,
        season_logs: list[dict[str, Any]] | None = None,
        pace: float = 1.0,
        shrinkage: dict[str, float] | None = None,
        league: str | None = None,
        role: str | None = None,
        support_n: int | None = None,
        team_plays: float | None = None,
        pass_rate: float | None = None,
        participation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        role_logs = [r for r in (comparable_logs or []) if isinstance(r, dict)]
        season = [r for r in (season_logs or role_logs) if isinstance(r, dict)]
        priors = league_priors(league)
        bucket = _role_bucket(role)
        role_n = int(support_n) if support_n is not None else len(role_logs)
        weights = dict(shrinkage or {})
        if not weights:
            from dcm.research.role_epoch import shrinkage_weights
            weights = shrinkage_weights(role_n, len(season))
        pace_m = float(_f(pace, 1.0) or 1.0)
        plays = _f(team_plays, priors["plays"]) or priors["plays"]
        prate = _f(pass_rate, priors["pass_rate"]) or priors["pass_rate"]

        snaps, sn = _avg(role_logs, "snaps")
        s_snaps, _ = _avg(season, "snaps")
        pass_att, pan = _avg(role_logs, "pass_att")
        s_pass, _ = _avg(season, "pass_att")
        rush_att, rn = _avg(role_logs, "rush_att")
        s_rush, _ = _avg(season, "rush_att")
        routes, routen = _avg(role_logs, "routes")
        s_routes, _ = _avg(season, "routes")
        targets, tn = _avg(role_logs, "targets")
        s_tgt, _ = _avg(season, "targets")

        snap_prior = priors["snaps_mean_qb"] if bucket == "QB" else priors["snaps_mean_wr"]
        if isinstance(participation, dict) and participation.get("mean") is not None:
            snaps_mean = float(participation["mean"]) * pace_m
        else:
            snaps_mean = _blend(snaps, s_snaps, snap_prior, weights) * pace_m
        body: dict[str, Any] = {
            "role": bucket,
            "snaps_mean": snaps_mean,
            "snaps_sd": max(2.0, _sd(role_logs if role_logs else season, "snaps", priors["snaps_sd"])),
            "support_n": max(sn, pan, rn, routen, tn, len(role_logs)),
            "shrinkage": {
                "roleWeight": float(weights.get("roleWeight") or 0.0),
                "seasonWeight": float(weights.get("seasonWeight") or 0.0),
                "priorWeight": float(weights.get("priorWeight") or 0.0),
            },
            "definition_version": OPP_VERSION,
            "team_plays": plays * pace_m,
            "pass_rate": max(0.0, min(1.0, prate)),
            "logSupport": {
                "snaps_n": sn, "pass_att_n": pan, "rush_att_n": rn,
                "routes_n": routen, "targets_n": tn,
            },
        }
        if bucket == "QB":
            body["pass_att_mean"] = _blend(pass_att, s_pass, priors["pass_att_mean"], weights) * pace_m
            body["pass_att_sd"] = max(1.0, _sd(role_logs if role_logs else season, "pass_att", priors["pass_att_sd"]))
            body["rush_att_mean"] = _blend(rush_att, s_rush, priors["rush_att_mean_qb"], weights) * pace_m
            body["rush_att_sd"] = max(0.5, _sd(role_logs if role_logs else season, "rush_att", priors["rush_att_sd_qb"]))
            body["sacks_mean"] = max(0.0, priors["sacks_mean"])
            body["opportunity_from"] = "dropbacks_pass_att"
        else:
            rush_prior = priors["rush_att_mean_rb"] if bucket == "RB" else priors["rush_att_mean_skill"]
            route_prior = {
                "WR": priors["routes_mean_wr"],
                "TE": priors["routes_mean_te"],
                "RB": priors["routes_mean_rb"],
            }.get(bucket, priors["routes_mean_wr"])
            body["rush_att_mean"] = _blend(rush_att, s_rush, rush_prior, weights) * pace_m
            body["rush_att_sd"] = max(0.5, _sd(role_logs if role_logs else season, "rush_att", priors["rush_att_sd"]))
            body["routes_mean"] = _blend(routes, s_routes, route_prior, weights) * pace_m
            body["routes_sd"] = max(1.0, _sd(role_logs if role_logs else season, "routes", priors["routes_sd"]))
            body["targets_mean"] = _blend(targets, s_tgt, (body["routes_mean"] * priors["target_rate"]), weights)
            body["opportunity_from"] = "routes_targets" if routen > 0 else "targets_or_snaps"
        if bucket == "K":
            fg_att, fgn = _avg(role_logs, "fg_att")
            s_fg, _ = _avg(season, "fg_att")
            xp_att, xpn = _avg(role_logs, "xp_att")
            s_xp, _ = _avg(season, "xp_att")
            body["fg_att_mean"] = _blend(fg_att, s_fg, priors["fg_att_mean"], weights) * pace_m
            body["xp_att_mean"] = _blend(xp_att, s_xp, priors["xp_att_mean"], weights) * pace_m
            body["opportunity_from"] = "kicking_attempts"
            body["logSupport"]["fg_att_n"] = fgn
            body["logSupport"]["xp_att_n"] = xpn
            body["support_n"] = max(int(body["support_n"]), fgn, xpn)
        body["inputHash"] = content_hash({
            "logs": [{
                "snaps": r.get("snaps"), "pass_att": r.get("pass_att"), "rush_att": r.get("rush_att"),
                "routes": r.get("routes"), "targets": r.get("targets"),
                "fg_att": r.get("fg_att"), "xp_att": r.get("xp_att"),
            } for r in role_logs],
            "pace": pace_m, "league": league, "role": bucket,
            "shrinkage": body["shrinkage"], "version": OPP_VERSION,
        })
        return body


class GridironEfficiencyModel:
    """YPA / completion / catch-rate / YPR / TD-INT / FG-XP rates from comparable logs.

    Never invents opportunity. Rates are Empirical-Bayes shrunk toward league priors.
    """

    definition_version = EFF_VERSION

    def fit(
        self,
        comparable_logs: list[dict[str, Any]],
        *,
        matchup: float = 1.0,
        shrinkage: dict[str, float] | None = None,
        league: str | None = None,
        role: str | None = None,
        pass_defense: float | None = None,
        rush_defense: float | None = None,
    ) -> dict[str, Any]:
        logs = [r for r in (comparable_logs or []) if isinstance(r, dict)]
        priors = league_priors(league)
        weights = dict(shrinkage or {})
        bucket = _role_bucket(role)
        match = float(_f(matchup, 1.0) or 1.0)
        pass_def = _f(pass_defense)
        rush_def = _f(rush_defense)
        pass_mul = match * (pass_def if pass_def is not None else 1.0)
        rush_mul = match * (rush_def if rush_def is not None else 1.0)

        def _sum_rate(num_key: str, den_key: str) -> tuple[float | None, int]:
            num = 0.0
            den = 0.0
            n = 0
            for row in logs:
                a = _f(row.get(num_key))
                b = _f(row.get(den_key))
                if a is None or b is None or b <= 0:
                    continue
                num += a
                den += b
                n += 1
            if n <= 0 or den <= 0:
                return (None, 0)
            return (num / den, n)

        cmp_rate, cmp_n = _sum_rate("pass_cmp", "pass_att")
        ypa, ypa_n = _sum_rate("pass_yds", "pass_att")
        rush_ypa, rypa_n = _sum_rate("rush_yds", "rush_att")
        catch, catch_n = _sum_rate("receptions", "targets")
        ypr, ypr_n = _sum_rate("rec_yds", "receptions")
        tgt_rate, tgt_n = _sum_rate("targets", "routes")
        ptd_rate, ptd_n = _sum_rate("pass_td", "pass_att")
        int_rate, int_n = _sum_rate("interceptions", "pass_att")
        rtd_rate, rtd_n = _sum_rate("rush_td", "rush_att")
        rec_td_rate, rec_td_n = _sum_rate("rec_td", "targets")
        fg_rate, fg_n = _sum_rate("fg_made", "fg_att")
        xp_rate, xp_n = _sum_rate("xp_made", "xp_att")

        def _b(sample: float | None, n: int, prior: float) -> float:
            return _eb(sample, n, prior, weights=weights)

        body: dict[str, Any] = {
            "role": bucket,
            "completion_rate": max(0.2, min(0.9, _b(cmp_rate, cmp_n, priors["completion_rate"]))),
            "pass_ypa": max(1.0, _b(ypa, ypa_n, priors["pass_ypa"]) * pass_mul),
            "rush_ypa": max(0.0, _b(rush_ypa, rypa_n, priors["rush_ypa_qb"] if bucket == "QB" else priors["rush_ypa"]) * rush_mul),
            "target_rate": max(0.0, min(1.0, _b(tgt_rate, tgt_n, priors["target_rate"]))),
            "catch_rate": max(0.0, min(1.0, _b(catch, catch_n, priors["catch_rate"]))),
            "rec_ypr": max(0.0, _b(ypr, ypr_n, priors["rec_ypr"]) * pass_mul),
            "pass_td_rate": max(0.0, min(0.25, _b(ptd_rate, ptd_n, priors["pass_td_rate"]))),
            "int_rate": max(0.0, min(0.20, _b(int_rate, int_n, priors["int_rate"]))),
            "rush_td_rate": max(0.0, min(0.35, _b(rtd_rate, rtd_n, priors["rush_td_rate"]))),
            "rec_td_rate": max(0.0, min(0.35, _b(rec_td_rate, rec_td_n, priors["rec_td_rate"]))),
            "fg_rate": max(0.4, min(0.99, _b(fg_rate, fg_n, priors["fg_rate"]))),
            "xp_rate": max(0.7, min(0.999, _b(xp_rate, xp_n, priors["xp_rate"]))),
            "support_n": max(cmp_n, ypa_n, rypa_n, catch_n, ypr_n, tgt_n, ptd_n, int_n, rtd_n, rec_td_n, fg_n, xp_n, len(logs)),
            "makesAttemptedSupport": {
                "cmp_n": cmp_n, "ypa_n": ypa_n, "rush_ypa_n": rypa_n,
                "catch_n": catch_n, "ypr_n": ypr_n, "target_rate_n": tgt_n,
                "pass_td_n": ptd_n, "int_n": int_n, "rush_td_n": rtd_n,
                "rec_td_n": rec_td_n, "fg_n": fg_n, "xp_n": xp_n,
            },
            "passDefenseApplied": pass_def is not None,
            "rushDefenseApplied": rush_def is not None,
            "shrinkage": {
                "roleWeight": float(weights.get("roleWeight") or 0.0),
                "seasonWeight": float(weights.get("seasonWeight") or 0.0),
                "priorWeight": float(weights.get("priorWeight") or 0.0),
                "method": "empirical_bayes_shrink",
            },
            "definition_version": EFF_VERSION,
        }
        body["inputHash"] = content_hash({
            "logs": [{
                "pass_att": r.get("pass_att"), "pass_cmp": r.get("pass_cmp"), "pass_yds": r.get("pass_yds"),
                "pass_td": r.get("pass_td"), "interceptions": r.get("interceptions"),
                "rush_att": r.get("rush_att"), "rush_yds": r.get("rush_yds"), "rush_td": r.get("rush_td"),
                "targets": r.get("targets"), "receptions": r.get("receptions"), "rec_yds": r.get("rec_yds"),
                "rec_td": r.get("rec_td"), "fg_att": r.get("fg_att"), "fg_made": r.get("fg_made"),
                "xp_att": r.get("xp_att"), "xp_made": r.get("xp_made"),
            } for r in logs],
            "matchup": match, "pass_defense": pass_def, "rush_defense": rush_def,
            "league": league, "role": bucket, "shrinkage": body["shrinkage"], "version": EFF_VERSION,
        })
        return body


class TeamEventModel:
    """Team plays / pass-rate / rush-rate / pace plus opponent pass/rush defense.

    Opponent defense is a required placeholder for PLAYABLE on pass/rush/receiving
    markets. Kicking markets do not require opponent defense. Absence is a
    blocker (`OPPONENT_PASS_DEFENSE` / `OPPONENT_RUSH_DEFENSE`), not a silent 1.0.
    """

    definition_version = TEAM_EVENT_VERSION

    def fit(
        self,
        team: dict[str, Any] | None = None,
        event: dict[str, Any] | None = None,
        opponent: dict[str, Any] | None = None,
        *,
        league: str | None = None,
        market: str | None = None,
    ) -> dict[str, Any]:
        team = team if isinstance(team, dict) else {}
        event = event if isinstance(event, dict) else {}
        opponent = opponent if isinstance(opponent, dict) else {}
        priors = league_priors(league)

        def _first(*keys: str, sources: tuple[dict, ...] | None = None) -> Any:
            srcs = sources or (team, event, opponent)
            for src in srcs:
                for key in keys:
                    if key in src and src.get(key) is not None:
                        return src.get(key)
            return None

        plays = _f(_first("plays", "off_plays", "team_off_plays", "pace_plays"))
        pass_rate = _f(_first("pass_rate", "passRate"))
        rush_rate = _f(_first("rush_rate", "rushRate"))
        pace = _f(_first("pace", "pace_multiplier"))
        pass_def = _f(_first(
            "pass_defense", "opp_pass_def", "pass_defense_multiplier",
            "matchup_pass_defense", sources=(opponent, team, event),
        ))
        rush_def = _f(_first(
            "rush_defense", "opp_rush_def", "rush_defense_multiplier",
            "matchup_rush_defense", sources=(opponent, team, event),
        ))
        spread = _f(_first("consensus_spread", "spread", "closing_spread", sources=(event, team)))
        total = _f(_first("game_total", "consensus_total", "total", sources=(event, team)))
        # CFB guarded-launch regime prior. These are conservative workload-state
        # weights, not a calibrated win probability and never a prop direction.
        regime = {"competitive": 0.80, "controlled_lead": 0.15, "blowout": 0.05}
        if str(league or "").upper() == "CFB" and spread is not None:
            margin = abs(spread)
            if margin > 21:
                regime = {"competitive": 0.35, "controlled_lead": 0.30, "blowout": 0.35}
            elif margin > 14:
                regime = {"competitive": 0.50, "controlled_lead": 0.30, "blowout": 0.20}
            elif margin > 7:
                regime = {"competitive": 0.65, "controlled_lead": 0.25, "blowout": 0.10}
        missing: list[str] = []
        if plays is None and pace is None:
            missing.append("FOOTBALL_TEAM_PLAYS_OR_PACE")
        mkt = str(market or "").strip().lower()
        if mkt not in KICK_MARKETS:
            if (not mkt or mkt in PASS_MARKETS or mkt in REC_MARKETS) and pass_def is None:
                missing.append("OPPONENT_PASS_DEFENSE")
            if (not mkt or mkt in RUSH_MARKETS) and rush_def is None:
                missing.append("OPPONENT_RUSH_DEFENSE")

        body = {
            "plays": plays if plays is not None else priors["plays"],
            "playsObserved": plays is not None,
            "pass_rate": pass_rate if pass_rate is not None else priors["pass_rate"],
            "passRateObserved": pass_rate is not None,
            "rush_rate": rush_rate if rush_rate is not None else (1.0 - (pass_rate if pass_rate is not None else priors["pass_rate"])),
            "rushRateObserved": rush_rate is not None,
            "pace": pace if pace is not None else priors["pace"],
            "paceObserved": pace is not None,
            "pass_defense": pass_def,
            "rush_defense": rush_def,
            "consensus_spread": spread,
            "game_total": total,
            "event_regime_weights": regime,
            "starter_curtailment": {"controlled_lead": 0.90, "blowout": 0.72},
            "missing": missing,
            "playableBlocker": missing[0] if missing else None,
            "definition_version": TEAM_EVENT_VERSION,
        }
        body["inputHash"] = content_hash({
            "plays": plays, "pass_rate": pass_rate, "rush_rate": rush_rate, "pace": pace,
            "pass_defense": pass_def, "rush_defense": rush_def, "spread": spread, "total": total,
            "event_regime_weights": regime, "league": league, "market": mkt,
            "version": TEAM_EVENT_VERSION,
        })
        return body
