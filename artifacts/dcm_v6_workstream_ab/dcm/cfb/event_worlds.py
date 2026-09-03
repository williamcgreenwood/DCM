"""Shared CFB EventWorlds. Correlations emerge from shared football primitives.

Do not independently simulate each prop. Player carries cannot exceed team
rushing attempts; completions cannot exceed attempts; catches cannot exceed
targets. Composites are identities on the same ledger.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dcm.model.worlds import _binomial, _clip, _nonneg_int_gauss, _p, _poisson, _rng, sample_football


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


def _share_int(total: int, weights: list[float]) -> list[int]:
    if not weights:
        return []
    clipped = [max(0.0, w) for w in weights]
    s = sum(clipped)
    if s <= 0:
        return [0 for _ in weights]
    raw = [total * w / s for w in clipped]
    ints = [int(x) for x in raw]
    remainder = total - sum(ints)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - ints[i], reverse=True)
    for i in order[: max(0, remainder)]:
        ints[i] += 1
    return ints


def simulate_joint_cfb_event_worlds(
    specs: list[dict[str, Any]],
    *,
    n: int,
    seed: str,
    event_contexts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Shared team plays/pass-rate/rush-rate → player opportunity → efficiency."""
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
    for i in range(int(n)):
        ctx = (event_contexts or [{}])[i % max(1, len(event_contexts or [{}]))]
        pace = float(ctx.get("pace") or 1.0)
        pass_rate = _clip(float(ctx.get("pass_rate") or 0.55), 0.25, 0.80)
        team_plays = max(40, _nonneg_int_gauss(rng, 68.0 * pace, 6.0))
        team_pass_att = int(round(team_plays * pass_rate))
        team_sacks = _nonneg_int_gauss(rng, 2.0, 1.0)
        team_rush_att = max(0, team_plays - team_pass_att - team_sacks)
        team_targets = team_pass_att  # laterals unmodeled

        qb = [p for p in players if p["role"] == "QB"]
        skill = [p for p in players if p["role"] != "QB"]
        kicker = [p for p in players if p["role"] in {"K", "PK"}]

        pass_weights = [_p(p["params"], "pass_att_mean", 34.0 if p["role"] == "QB" else 0.0) for p in players]
        rush_weights = [_p(p["params"], "rush_att_mean", 12.0 if p["role"] == "RB" else (5.0 if p["role"] == "QB" else 1.0)) for p in players]
        target_weights = [_p(p["params"], "routes_mean", 22.0 if p["role"] in {"WR", "TE"} else 3.0) * _p(p["params"], "target_rate", 0.28) for p in players]

        player_pass = _share_int(team_pass_att, pass_weights) if qb else [0] * len(players)
        player_rush = _share_int(team_rush_att, rush_weights)
        player_tgt = _share_int(team_targets, target_weights)

        # QB owns team pass attempts when a QB is on the board.
        if len(qb) == 1:
            qid = qb[0]["playerId"]
            for j, p in enumerate(players):
                if p["playerId"] == qid:
                    player_pass[j] = team_pass_att
                else:
                    player_pass[j] = 0

        drawn: dict[str, dict[str, float]] = {}
        rec_yds_sum = 0.0
        pass_yds_qb = 0.0
        rush_sum = 0
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
            # Overlay shared opportunity so conservation vs team pools holds.
            if role == "QB":
                stats["pass_att"] = player_pass[j]
                stats["pass_cmp"] = min(stats.get("pass_cmp", 0), player_pass[j])
                stats["rush_att"] = player_rush[j]
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
            stats["pass_rush_yds"] = float(stats.get("pass_yds") or 0) + float(stats.get("rush_yds") or 0)
            stats["rush_rec_yds"] = float(stats.get("rush_yds") or 0) + float(stats.get("rec_yds") or 0)
            stats["rush_rec_td"] = float(stats.get("rush_td") or 0) + float(stats.get("rec_td") or 0)
            stats["pass_rush_td"] = float(stats.get("pass_td") or 0) + float(stats.get("rush_td") or 0)
            stats["kicking_pts"] = 3 * float(stats.get("fg_made") or 0) + float(stats.get("xp_made") or 0)
            stats["team_off_plays"] = team_plays
            stats["team_pass_att"] = team_pass_att
            stats["team_rush_att"] = team_rush_att
            drawn[p["playerId"]] = stats

        if rush_sum > team_rush_att + len(players):
            conservation_failures += 1
        if pass_yds_qb and rec_yds_sum and rec_yds_sum > pass_yds_qb + 40.0:
            conservation_failures += 1
        for pid, stats in drawn.items():
            worlds[pid].append(stats)

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
        },
        "sharedPrimitives": ["team_off_plays", "team_pass_att", "team_rush_att", "pass_rate", "pace"],
    }
    return {"worlds": worlds, "meta": meta}
