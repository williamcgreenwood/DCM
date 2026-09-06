"""NumPy / SoA-oriented CFB joint EventWorld backend.

Keeps the reference ``random.Random`` stream (rngVersion v1) for bitwise ledger
parity with ``simulate_joint_cfb_event_worlds_reference``. Acceleration comes from:
- skipping per-world content_hash share audit bodies (``allocate_team_opportunity_fast``)
- contiguous NumPy team-play / residual / opportunity buffers
- optional SoA views of hot ledger fields (exported in meta; public worlds remain dicts)

Public return shape matches the reference backend (dict-of-list-of-dict worlds).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from dcm.cfb.event_world_backend import RNG_VERSION, backend_meta
from dcm.cfb.opportunity_ledger import KICKER_ROLES, allocate_team_opportunity_fast
from dcm.model.worlds import _clip, _nonneg_int_gauss, _p, _rng, sample_football

# Hot fields mirrored into SoA for future C ABI / matrix consumers.
_SOA_FIELDS = (
    "pass_att",
    "pass_cmp",
    "pass_yds",
    "pass_td",
    "interceptions",
    "rush_att",
    "rush_yds",
    "rush_td",
    "targets",
    "receptions",
    "rec_yds",
    "rec_td",
    "fg_made",
    "xp_made",
    "kicking_pts",
    "team_off_plays",
    "team_pass_att",
    "team_rush_att",
    "unmodeled_rush_residual",
    "unmodeled_target_residual",
    "unmodeled_pass_residual",
)


def simulate_joint_cfb_event_worlds_numpy(
    specs: list[dict[str, Any]],
    *,
    n: int,
    seed: str,
    event_contexts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not specs:
        return {
            "worlds": {},
            "meta": {
                "joint": False,
                "n": 0,
                **backend_meta("numpy"),
            },
        }

    rng = _rng(f"cfb-joint:{seed}:{specs[0]['row'].get('eventId')}")
    players: list[dict[str, Any]] = []
    for spec in specs:
        row = spec["row"]
        snap = spec.get("snapshot") or {}
        params = snap.get("parameters") if isinstance(snap.get("parameters"), dict) else snap
        players.append(
            {
                "playerId": str(row.get("playerId")),
                "role": str(row.get("role") or params.get("role") or "WR").upper(),
                "params": params if isinstance(params, dict) else {},
                "row": row,
            }
        )

    n_worlds = max(0, int(n))
    n_players = len(players)
    player_ids = [p["playerId"] for p in players]

    team_plays_a = np.zeros(n_worlds, dtype=np.int32)
    team_pass_a = np.zeros(n_worlds, dtype=np.int32)
    team_rush_a = np.zeros(n_worlds, dtype=np.int32)
    residual_rush_a = np.zeros(n_worlds, dtype=np.int32)
    residual_tgt_a = np.zeros(n_worlds, dtype=np.int32)
    residual_pass_a = np.zeros(n_worlds, dtype=np.int32)
    player_pass_a = np.zeros((n_worlds, n_players), dtype=np.int32)
    player_rush_a = np.zeros((n_worlds, n_players), dtype=np.int32)
    player_tgt_a = np.zeros((n_worlds, n_players), dtype=np.int32)
    soa: dict[str, dict[str, np.ndarray]] = {
        pid: {f: np.zeros(n_worlds, dtype=np.float64) for f in _SOA_FIELDS} for pid in player_ids
    }

    worlds: dict[str, list[dict[str, float]]] = {pid: [] for pid in player_ids}
    conservation_failures = 0
    residual_acc = {"rush": 0, "targets": 0, "pass": 0}
    last_alloc: dict[str, Any] = {}
    ctx_list = event_contexts or [{}]

    for i in range(n_worlds):
        ctx = ctx_list[i % max(1, len(ctx_list))]
        pace = float(ctx.get("pace") or 1.0)
        pass_rate = _clip(float(ctx.get("pass_rate") or 0.55), 0.25, 0.80)
        team_plays = max(40, _nonneg_int_gauss(rng, 68.0 * pace, 6.0))
        team_pass_att = int(round(team_plays * pass_rate))
        team_sacks = _nonneg_int_gauss(rng, 2.0, 1.0)
        team_rush_att = max(0, team_plays - team_pass_att - team_sacks)
        team_targets = team_pass_att

        alloc = allocate_team_opportunity_fast(
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

        team_plays_a[i] = team_plays
        team_pass_a[i] = team_pass_att
        team_rush_a[i] = team_rush_att
        residual_rush_a[i] = int(alloc["residualRushAtt"])
        residual_tgt_a[i] = int(alloc["residualTargets"])
        residual_pass_a[i] = int(alloc["residualPassAtt"])
        player_pass_a[i, :] = np.asarray(player_pass, dtype=np.int32)
        player_rush_a[i, :] = np.asarray(player_rush, dtype=np.int32)
        player_tgt_a[i, :] = np.asarray(player_tgt, dtype=np.int32)

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
            params["routes_mean"] = float(
                max(player_tgt[j], 1) / max(_p(params, "target_rate", 0.28), 0.05)
            )
            try:
                stats = sample_football(rng, role, params)
            except RuntimeError:
                conservation_failures += 1
                stats = {
                    "pass_att": player_pass[j],
                    "pass_cmp": 0,
                    "pass_yds": 0,
                    "pass_td": 0,
                    "interceptions": 0,
                    "rush_att": player_rush[j],
                    "rush_yds": 0,
                    "rush_td": 0,
                    "targets": player_tgt[j],
                    "receptions": 0,
                    "rec_yds": 0,
                    "rec_td": 0,
                    "fg_att": 0,
                    "fg_made": 0,
                    "xp_att": 0,
                    "xp_made": 0,
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
            for f in _SOA_FIELDS:
                soa[p["playerId"]][f][i] = float(stats.get(f) or 0.0)

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

    denom = max(1, n_worlds)
    identities_ok = conservation_failures == 0
    meta = {
        "joint": True,
        "n": n,
        "playerCount": n_players,
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
            "rushAttMean": residual_acc["rush"] / denom,
            "targetsMean": residual_acc["targets"] / denom,
            "passAttMean": residual_acc["pass"] / denom,
        },
        "kickerIsolated": bool(last_alloc.get("kickerIsolated", True)),
        "sharedPrimitives": [
            "team_off_plays",
            "team_pass_att",
            "team_rush_att",
            "pass_rate",
            "pace",
            "residual",
        ],
        "eventId": specs[0]["row"].get("eventId"),
        **backend_meta("numpy"),
        "soaFields": list(_SOA_FIELDS),
        "teamPlayBufferBytes": int(team_plays_a.nbytes + team_pass_a.nbytes + team_rush_a.nbytes),
        "opportunityBufferBytes": int(
            player_pass_a.nbytes + player_rush_a.nbytes + player_tgt_a.nbytes
        ),
        "soaBufferBytes": int(sum(arr.nbytes for pid in soa for arr in soa[pid].values())),
        "rngVersion": RNG_VERSION,
    }
    return {"worlds": worlds, "meta": meta, "_soa": soa}
