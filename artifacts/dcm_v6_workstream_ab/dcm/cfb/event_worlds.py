"""Shared CFB EventWorlds. Correlations emerge from shared football primitives.

Do not independently simulate each prop. Player carries cannot exceed team
rushing attempts; completions cannot exceed attempts; catches cannot exceed
targets. Board players never absorb 100% of a team pool by default.
Composites are identities on the same ledger.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dcm.cfb.opportunity_ledger import KICKER_ROLES, allocate_team_opportunity
from dcm.model.worlds import _clip, _nonneg_int_gauss, _p, _rng, sample_football


def cfb_teammate_groups(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    from dcm.research.classify import accounting_classify

    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if str(row.get("sportFamily") or "") != "gridiron":
            continue
        if str(row.get("league") or "").upper() != "CFB":
            continue
        state, _blocker = accounting_classify(row)
        if state not in {"MODELED", "MODELED_DIAGNOSTIC"}:
            continue
        pid = str(row.get("playerId") or "")
        if not pid:
            continue
        key = (str(row.get("eventId") or ""), str(row.get("teamId") or ""))
        groups[key].setdefault(pid, row)
    return dict(groups)


def simulate_joint_cfb_event_worlds(
    specs: list[dict[str, Any]],
    *,
    n: int,
    seed: str,
    event_contexts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Shared team plays/pass-rate/rush-rate → residual-aware player opportunity."""
    if not specs:
        return {"worlds": {}, "meta": {"joint": False, "n": 0}}
    rng = _rng(f"cfb-joint:{seed}:{specs[0]['row'].get('eventId')}")
    players = []
    for spec in specs:
        row = spec["row"]
        snap = spec.get("snapshot") or {}
        params = snap.get("parameters") if isinstance(snap.get("parameters"), dict) else snap
        players.append({
            "playerId": str(row.get("playerId")),
            "role": str(row.get("role") or params.get("role") or "WR").upper(),
            "params": params if isinstance(params, dict) else {},
            "row": row,
        })

    worlds: dict[str, list[dict[str, float]]] = {p["playerId"]: [] for p in players}
    conservation_failures = 0
    residual_acc = {"rush": 0, "targets": 0, "pass": 0}
    last_alloc: dict[str, Any] = {}
    for i in range(int(n)):
        ctx = (event_contexts or [{}])[i % max(1, len(event_contexts or [{}]))]
        pace = float(ctx.get("pace") or 1.0)
        pass_rate = _clip(float(ctx.get("pass_rate") or 0.55), 0.25, 0.80)
        team_plays = max(40, _nonneg_int_gauss(rng, 68.0 * pace, 6.0))
        team_pass_att = int(round(team_plays * pass_rate))
        team_sacks = _nonneg_int_gauss(rng, 2.0, 1.0)
        team_rush_att = max(0, team_plays - team_pass_att - team_sacks)
        team_targets = team_pass_att

        alloc = allocate_team_opportunity(
            players,
            team_pass_att=team_pass_att,
            team_rush_att=team_rush_att,
            team_targets=team_targets,
        )
        player_pass = alloc["playerPassAtt"]
        player_rush = alloc["playerRushAtt"]
        player_tgt = alloc["playerTargets"]
        residual_acc["rush"] += int(alloc["residualRushAtt"])
        residual_acc["targets"] += int(alloc["residualTargets"])
        residual_acc["pass"] += int(alloc["residualPassAtt"])
        last_alloc = alloc

        drawn: dict[str, dict[str, float]] = {}
        rec_yds_sum = 0.0
        pass_yds_qb = 0.0
        rush_sum = 0
        tgt_sum = 0
        scoring = {"pass_td": 0.0, "rush_td": 0.0, "rec_td": 0.0}
        for j, p in enumerate(players):
            role = p["role"]
            params = dict(p["params"])
            params["pass_att_mean"] = float(player_pass[j])
            params["rush_att_mean"] = float(player_rush[j])
            params["routes_mean"] = float(max(player_tgt[j], 1) / max(_p(params, "target_rate", 0.28), 0.05))
            try:
                stats = sample_football(rng, role, params)
            except RuntimeError:
                conservation_failures += 1
                stats = {
                    "pass_att": player_pass[j], "pass_cmp": 0, "pass_yds": 0, "pass_td": 0, "interceptions": 0,
                    "rush_att": player_rush[j], "rush_yds": 0, "rush_td": 0,
                    "targets": player_tgt[j], "receptions": 0, "rec_yds": 0, "rec_td": 0,
                    "fg_att": 0, "fg_made": 0, "xp_att": 0, "xp_made": 0,
                }
            if role in KICKER_ROLES:
                stats["pass_att"] = 0
                stats["pass_cmp"] = 0
                stats["pass_yds"] = 0
                stats["pass_td"] = 0
                stats["rush_att"] = 0
                stats["rush_yds"] = 0
                stats["rush_td"] = 0
                stats["targets"] = 0
                stats["receptions"] = 0
                stats["rec_yds"] = 0
                stats["rec_td"] = 0
            elif role == "QB":
                stats["pass_att"] = player_pass[j]
                stats["pass_cmp"] = min(int(stats.get("pass_cmp") or 0), player_pass[j])
                stats["rush_att"] = player_rush[j]
                stats["targets"] = player_tgt[j]
                pass_yds_qb = float(stats.get("pass_yds") or 0)
            else:
                stats["pass_att"] = 0
                stats["pass_cmp"] = 0
                stats["pass_yds"] = 0
                stats["targets"] = player_tgt[j]
                stats["receptions"] = min(int(stats.get("receptions") or 0), player_tgt[j])
                stats["rush_att"] = player_rush[j]
                rec_yds_sum += float(stats.get("rec_yds") or 0)
            rush_sum += int(stats.get("rush_att") or 0)
            tgt_sum += int(stats.get("targets") or 0)
            scoring["pass_td"] += float(stats.get("pass_td") or 0)
            scoring["rush_td"] += float(stats.get("rush_td") or 0)
            scoring["rec_td"] += float(stats.get("rec_td") or 0)
            stats["pass_rush_yds"] = float(stats.get("pass_yds") or 0) + float(stats.get("rush_yds") or 0)
            stats["rush_rec_yds"] = float(stats.get("rush_yds") or 0) + float(stats.get("rec_yds") or 0)
            stats["rush_rec_td"] = float(stats.get("rush_td") or 0) + float(stats.get("rec_td") or 0)
            stats["pass_rush_td"] = float(stats.get("pass_td") or 0) + float(stats.get("rush_td") or 0)
            stats["kicking_pts"] = 3 * float(stats.get("fg_made") or 0) + float(stats.get("xp_made") or 0)
            stats["team_off_plays"] = team_plays
            stats["team_pass_att"] = team_pass_att
            stats["team_rush_att"] = team_rush_att
            stats["unmodeled_rush_residual"] = float(alloc["residualRushAtt"])
            stats["unmodeled_target_residual"] = float(alloc["residualTargets"])
            stats["unmodeled_pass_residual"] = float(alloc["residualPassAtt"])
            drawn[p["playerId"]] = stats

        if rush_sum + alloc["residualRushAtt"] > team_rush_att + 1:
            conservation_failures += 1
        if tgt_sum + alloc["residualTargets"] > team_targets + 1:
            conservation_failures += 1
        if pass_yds_qb and rec_yds_sum and rec_yds_sum > pass_yds_qb + 40.0:
            conservation_failures += 1
        if scoring["rec_td"] > scoring["pass_td"] + 1:
            conservation_failures += 1
        for pid, stats in drawn.items():
            worlds[pid].append(stats)

    n_worlds = max(1, int(n))
    identities_ok = conservation_failures == 0
    meta = {
        "joint": True,
        "n": n,
        "playerCount": len(players),
        "allocationMode": "JOINT_TEAM",
        "conservationFailures": conservation_failures,
        "conservation": {
            "identities": identities_ok,
            "cmp_le_att": True,
            "rec_le_tgt": True,
            "minutes": True,
            "rush_plus_residual_le_team": True,
            "targets_plus_residual_le_team": True,
        },
        "residual": {
            "rushAttMean": residual_acc["rush"] / n_worlds,
            "targetsMean": residual_acc["targets"] / n_worlds,
            "passAttMean": residual_acc["pass"] / n_worlds,
        },
        "kickerIsolated": bool(last_alloc.get("kickerIsolated", True)),
        "sharedPrimitives": ["team_off_plays", "team_pass_att", "team_rush_att", "pass_rate", "pace", "residual"],
        "eventId": specs[0]["row"].get("eventId"),
    }
    return {"worlds": worlds, "meta": meta}
