"""Evidence -> player/event parameter snapshot.

Opportunity and efficiency are deliberately separate. Production selection
requires non-synthetic evidence, a verified market definition, and support for
both opportunity and efficiency. Small samples shrink toward declared priors.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from dcm.contracts.hashes import content_hash


def _f(v: Any, default: float) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _pairs(claims: list[dict], scope: str, scope_id: str) -> list[tuple[dict, dict]]:
    out = []
    for c in claims:
        if str(c.get("semantic_scope")) == scope and str(c.get("scope_id")) == str(scope_id) and isinstance(c.get("claim_value"), dict):
            out.append((c, c["claim_value"]))
    return sorted(out, key=lambda x: str(x[0].get("observed_at") or ""))


def _merge(pairs: list[tuple[dict, dict]]) -> dict:
    out: dict[str, Any] = {}
    for _, value in pairs:
        out.update(value)
    return out


def _avg(logs: list[dict], key: str) -> tuple[float | None, int]:
    vals = []
    for r in logs:
        try:
            x = float(r[key])
            if math.isfinite(x):
                vals.append(x)
        except (KeyError, TypeError, ValueError):
            pass
    return (mean(vals), len(vals)) if vals else (None, 0)


def _sd(logs: list[dict], key: str, fallback: float) -> float:
    vals = []
    for r in logs:
        try:
            vals.append(float(r[key]))
        except (KeyError, TypeError, ValueError):
            pass
    return pstdev(vals) if len(vals) >= 2 else fallback


def _shrink(sample: float | None, n: int, prior: float, prior_n: float = 5.0) -> float:
    if sample is None or n <= 0:
        return prior
    return (sample * n + prior * prior_n) / (n + prior_n)


def build_parameter_snapshot(row: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    player_pairs = _pairs(claims, "PLAYER", str(row.get("playerId") or ""))
    team_pairs = _pairs(claims, "TEAM", str(row.get("teamId") or ""))
    event_pairs = _pairs(claims, "EVENT", str(row.get("eventId") or ""))
    market_pairs = _pairs(claims, "MARKET", str(row.get("projectionId") or ""))
    player, team, event, market = map(_merge, (player_pairs, team_pairs, event_pairs, market_pairs))
    all_claims = [c for c, _ in player_pairs + team_pairs + event_pairs + market_pairs]
    synthetic = any(str(c.get("source_id") or "").upper().startswith("FIXTURE_") or bool(c.get("synthetic")) for c in all_claims)
    rel = mean([_f(c.get("reliability"), 0.0) for c in all_claims]) if all_claims else 0.0
    fresh = mean([_f(c.get("freshness"), 0.0) for c in all_claims]) if all_claims else 0.0
    logs = player.get("role_epoch_logs") or player.get("game_logs") or []
    logs = [r for r in logs if isinstance(r, dict)] if isinstance(logs, list) else []
    opp = player.get("opportunity") if isinstance(player.get("opportunity"), dict) else {}
    eff = player.get("efficiency") if isinstance(player.get("efficiency"), dict) else {}
    family = str(row.get("sportFamily") or "")
    params: dict[str, Any] = {"family": family}
    opp_n = int(_f(opp.get("support_n"), len(logs)))
    eff_n = int(_f(eff.get("support_n"), len(logs)))

    if family == "basketball":
        minutes, mn = _avg(logs, "minutes")
        fga, fn = _avg(logs, "fga")
        tpa, tn = _avg(logs, "tpa")
        fta, ftan = _avg(logs, "fta")
        reb, rn = _avg(logs, "reb")
        ast, an = _avg(logs, "ast")
        prior_minutes = 34.0 if row.get("league") == "NBA" else 31.0
        mm = _f(opp.get("minutes_mean"), _shrink(minutes, mn, prior_minutes))
        pace = _f(team.get("pace_multiplier"), 1.0) * _f(event.get("pace_multiplier"), 1.0)
        matchup = _f(team.get("matchup_efficiency_multiplier"), 1.0) * _f(event.get("matchup_efficiency_multiplier"), 1.0)
        params.update({
            "minutes_mean": mm * _f(opp.get("role_multiplier"), 1.0),
            "minutes_sd": max(0.75, _f(opp.get("minutes_sd"), _sd(logs, "minutes", 4.5))),
            "fga_per_min": max(0.01, _f(eff.get("fga_per_min"), _shrink(fga / minutes if fga is not None and minutes else None, fn, 0.55)) * pace),
            "three_pa_share": max(0.0, min(1.0, _f(eff.get("three_pa_share"), _shrink(tpa / fga if tpa is not None and fga else None, tn, 0.42)))),
            "two_fg_pct": max(0.05, min(0.95, _f(eff.get("two_fg_pct"), 0.52) * matchup)),
            "three_fg_pct": max(0.05, min(0.80, _f(eff.get("three_fg_pct"), 0.36) * matchup)),
            "fta_per_min": max(0.0, _f(eff.get("fta_per_min"), _shrink(fta / minutes if fta is not None and minutes else None, ftan, 0.18)) * pace),
            "ft_pct": max(0.2, min(1.0, _f(eff.get("ft_pct"), 0.78))),
            "reb_per_min": max(0.0, _f(eff.get("reb_per_min"), _shrink(reb / minutes if reb is not None and minutes else None, rn, 0.23)) * pace),
            "ast_per_min": max(0.0, _f(eff.get("ast_per_min"), _shrink(ast / minutes if ast is not None and minutes else None, an, 0.14)) * pace),
            "stl_per_min": max(0.0, _f(eff.get("stl_per_min"), 0.03) * pace),
            "blk_per_min": max(0.0, _f(eff.get("blk_per_min"), 0.025) * pace),
            "tov_per_min": max(0.0, _f(eff.get("tov_per_min"), 0.08) * pace),
        })
        opp_n = max(opp_n, mn)
        eff_n = max(eff_n, fn, rn, an)
    elif family == "gridiron":
        role = str(player.get("role") or row.get("role") or "QB").upper()
        params["role"] = role
        if role == "QB":
            att, attn = _avg(logs, "pass_att")
            rush, rushn = _avg(logs, "rush_att")
            params.update({
                "pass_att_mean": _f(opp.get("pass_att_mean"), _shrink(att, attn, 34.0)),
                "pass_att_sd": max(1.0, _f(opp.get("pass_att_sd"), _sd(logs, "pass_att", 6.0))),
                "rush_att_mean": _f(opp.get("rush_att_mean"), _shrink(rush, rushn, 5.0)),
                "rush_att_sd": max(0.5, _f(opp.get("rush_att_sd"), _sd(logs, "rush_att", 2.0))),
                "completion_rate": max(0.2, min(0.9, _f(eff.get("completion_rate"), 0.65))),
                "pass_ypa": max(1.0, _f(eff.get("pass_ypa"), 7.1) * _f(team.get("matchup_efficiency_multiplier"), 1.0)),
                "rush_ypa": max(0.0, _f(eff.get("rush_ypa"), 4.4)),
                "sacks_mean": max(0.0, _f(opp.get("sacks_mean"), 2.2)),
            })
            opp_n = max(opp_n, attn, rushn)
            eff_n = max(eff_n, attn)
        else:
            rush, rn = _avg(logs, "rush_att")
            routes, routen = _avg(logs, "routes")
            targets, tn = _avg(logs, "targets")
            rec, recn = _avg(logs, "receptions")
            params.update({
                "rush_att_mean": _f(opp.get("rush_att_mean"), _shrink(rush, rn, 12.0 if role == "RB" else 1.5)),
                "rush_att_sd": max(0.5, _f(opp.get("rush_att_sd"), _sd(logs, "rush_att", 4.0))),
                "routes_mean": _f(opp.get("routes_mean"), _shrink(routes, routen, 22.0 if role in {"WR", "TE"} else 8.0)),
                "routes_sd": max(1.0, _f(opp.get("routes_sd"), _sd(logs, "routes", 5.0))),
                "target_rate": max(0.0, min(1.0, _f(eff.get("target_rate"), targets / routes if targets is not None and routes else 0.28))),
                "catch_rate": max(0.0, min(1.0, _f(eff.get("catch_rate"), rec / targets if rec is not None and targets else 0.68))),
                "rush_ypa": max(0.0, _f(eff.get("rush_ypa"), 4.3)),
                "rec_ypr": max(0.0, _f(eff.get("rec_ypr"), 11.5) * _f(team.get("matchup_efficiency_multiplier"), 1.0)),
            })
            opp_n = max(opp_n, rn, routen)
            eff_n = max(eff_n, tn, recn)
    elif family == "baseball":
        pa, pan = _avg(logs, "PA")
        params.update({
            "pa_mean": _f(opp.get("pa_mean"), _shrink(pa, pan, 4.2)),
            "pa_sd": max(0.2, _f(opp.get("pa_sd"), _sd(logs, "PA", 0.8))),
            "bb_rate": _f(eff.get("bb_rate"), 0.09), "hbp_rate": _f(eff.get("hbp_rate"), 0.01),
            "sf_rate": _f(eff.get("sf_rate"), 0.02), "sh_rate": _f(eff.get("sh_rate"), 0.005),
            "so_rate": _f(eff.get("so_rate"), 0.24), "hr_rate": _f(eff.get("hr_rate"), 0.04),
            "triple_rate": _f(eff.get("triple_rate"), 0.005), "double_rate": _f(eff.get("double_rate"), 0.05),
            "single_rate": _f(eff.get("single_rate"), 0.15), "run_per_pa": _f(eff.get("run_per_pa"), 0.14),
            "rbi_per_pa": _f(eff.get("rbi_per_pa"), 0.12),
        })
        opp_n = max(opp_n, pan)
        eff_n = max(eff_n, len(logs))

    status = str(player.get("status") or "UNKNOWN").strip().upper()
    definition_verified = bool(market.get("definition_verified"))
    active_statuses = {"ACTIVE", "AVAILABLE", "PROBABLE", "EXPECTED_ACTIVE"}
    inactive_statuses = {"OUT", "DNP", "INACTIVE", "SUSPENDED", "IR", "PUP"}
    uncertain_statuses = {"QUESTIONABLE", "GTD", "GAME_TIME_DECISION", "DOUBTFUL", "LIMITED"}
    status_eligible = status in active_statuses
    production_eligible = (
        not synthetic and status_eligible
        and opp_n >= 3 and eff_n >= 3 and definition_verified
    )
    data_quality = max(0.0, min(1.0, rel * 0.65 + fresh * 0.20 + min(1.0, min(opp_n, eff_n) / 10.0) * 0.15))
    ood = max(0.0, min(1.0, _f(player.get("ood_risk"), 0.15 if min(opp_n, eff_n) >= 5 else 0.45)))
    blocker = None
    if synthetic: blocker = "SYNTHETIC_EVIDENCE_NOT_SELECTABLE"
    elif not definition_verified: blocker = "UNVERIFIED_MARKET_DEFINITION"
    elif status in inactive_statuses: blocker = "PLAYER_NOT_ACTIVE"
    elif status in uncertain_statuses: blocker = "PLAYER_STATUS_UNCERTAIN"
    elif status not in active_statuses: blocker = "PLAYER_STATUS_UNKNOWN"
    elif opp_n < 3: blocker = "INSUFFICIENT_OPPORTUNITY_SAMPLE"
    elif eff_n < 3: blocker = "INSUFFICIENT_EFFICIENCY_SAMPLE"

    role = str(player.get("role") or row.get("role") or "UNKNOWN")
    tags = {f"EVENT:{row.get('eventId')}", f"TEAM:{row.get('teamId')}", f"ROLE:{row.get('teamId')}:{role}"}
    if player.get("qb_id"): tags.add(f"QBUNIT:{row.get('teamId')}:{player['qb_id']}")
    if player.get("injury_dependency_id"): tags.add(f"INJURY:{player['injury_dependency_id']}")
    if event.get("weather_state_hash"): tags.add(f"WEATHER:{event['weather_state_hash']}")
    snapshot = {
        "playerId": row.get("playerId"), "eventId": row.get("eventId"), "market": row.get("market"),
        "status": status, "role": role, "opportunity": {"support_n": opp_n}, "efficiency": {"support_n": eff_n},
        "parameters": params, "reliability": rel, "freshness": fresh, "data_quality": data_quality,
        "ood_risk": ood, "synthetic": synthetic, "definition_verified": definition_verified,
        "production_eligible": production_eligible, "blocker": blocker, "dependency_tags": sorted(tags),
        "evidence_hashes": sorted(str(c.get("claim_hash") or "") for c in all_claims if c.get("claim_hash")),
    }
    for key in ("minutes_mean", "minutes_sd", "pass_att_mean", "pass_att_sd", "rush_att_mean", "rush_att_sd", "routes_mean", "routes_sd", "pa_mean", "pa_sd"):
        if key in params:
            snapshot["opportunity"][key] = params[key]
    snapshot["parameter_snapshot_hash"] = content_hash(snapshot)
    return snapshot
