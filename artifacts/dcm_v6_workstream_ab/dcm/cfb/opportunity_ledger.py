"""Team opportunity ledger with residual buckets.

Board membership never implies 100% ownership of team opportunity.
Kickers receive no rush attempts or targets.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

KICKER_ROLES = frozenset({"K", "PK"})

# Maximum share of the team pool a single modeled player of this role may
# absorb when teammates are missing from the board.
ROLE_RUSH_CAP = {"QB": 0.18, "RB": 0.55, "WR": 0.10, "TE": 0.06, "FB": 0.12}
ROLE_TARGET_CAP = {"QB": 0.02, "RB": 0.18, "WR": 0.32, "TE": 0.24, "FB": 0.08}
ROLE_PASS_CAP = {"QB": 0.92}

DEFAULT_RUSH_MEAN = {"QB": 6.0, "RB": 14.0, "WR": 1.0, "TE": 0.5, "FB": 4.0}
DEFAULT_TARGET_MEAN = {"QB": 0.2, "RB": 3.5, "WR": 7.0, "TE": 5.0, "FB": 1.5}
DEFAULT_PASS_MEAN = {"QB": 30.0}


def _role(player: Mapping[str, Any]) -> str:
    return str(player.get("role") or (player.get("params") or {}).get("role") or "WR").upper()


def _mean(params: Mapping[str, Any], key: str, default: float) -> float:
    try:
        val = params.get(key)
        if val is None:
            return float(default)
        return max(0.0, float(val))
    except (TypeError, ValueError):
        return float(default)


def allocate_counts(means: Sequence[float], caps: Sequence[float], team_total: int) -> tuple[list[int], int]:
    """Absolute means, capped, never renormalized to 100% of the team pool."""
    total = max(0, int(team_total))
    raw: list[float] = []
    for mean, cap in zip(means, caps):
        capped = min(max(0.0, float(mean)), max(0.0, float(cap)) * total)
        raw.append(capped)
    s = sum(raw)
    if s > total > 0:
        scale = total / s
        raw = [x * scale for x in raw]
    ints = [int(round(x)) for x in raw]
    overflow = sum(ints) - total
    order = sorted(range(len(ints)), key=lambda i: ints[i], reverse=True)
    i = 0
    while overflow > 0 and ints:
        idx = order[i % len(order)]
        if ints[idx] > 0:
            ints[idx] -= 1
            overflow -= 1
        i += 1
        if i > total + len(ints) + 8:
            break
    residual = max(0, total - sum(ints))
    return ints, residual


def allocate_team_opportunity(
    players: Sequence[Mapping[str, Any]],
    *,
    team_pass_att: int,
    team_rush_att: int,
    team_targets: int,
) -> dict[str, Any]:
    """Return per-player counts plus residual buckets.

    Residual is the unmodeled remainder of the team pool. A lone RB on the
    board cannot be assigned every team carry.
    """
    rush_means: list[float] = []
    rush_caps: list[float] = []
    tgt_means: list[float] = []
    tgt_caps: list[float] = []
    pass_means: list[float] = []
    pass_caps: list[float] = []
    kicker_flags: list[bool] = []
    for p in players:
        role = _role(p)
        params = p.get("params") if isinstance(p.get("params"), Mapping) else {}
        is_k = role in KICKER_ROLES
        kicker_flags.append(is_k)
        if is_k:
            rush_means.append(0.0)
            rush_caps.append(0.0)
            tgt_means.append(0.0)
            tgt_caps.append(0.0)
            pass_means.append(0.0)
            pass_caps.append(0.0)
            continue
        rush_means.append(_mean(params, "rush_att_mean", DEFAULT_RUSH_MEAN.get(role, 1.0)))
        rush_caps.append(ROLE_RUSH_CAP.get(role, 0.12))
        tgt_means.append(_mean(params, "routes_mean", 8.0) * _mean(params, "target_rate", DEFAULT_TARGET_MEAN.get(role, 3.0) / 8.0) if params.get("routes_mean") is not None else _mean(params, "targets_mean", DEFAULT_TARGET_MEAN.get(role, 3.0)))
        tgt_caps.append(ROLE_TARGET_CAP.get(role, 0.15))
        pass_means.append(_mean(params, "pass_att_mean", DEFAULT_PASS_MEAN.get(role, 0.0) if role == "QB" else 0.0))
        pass_caps.append(ROLE_PASS_CAP.get(role, 0.0))

    player_rush, residual_rush = allocate_counts(rush_means, rush_caps, team_rush_att)
    player_tgt, residual_tgt = allocate_counts(tgt_means, tgt_caps, team_targets)
    player_pass, residual_pass = allocate_counts(pass_means, pass_caps, team_pass_att)

    for i, is_k in enumerate(kicker_flags):
        if is_k:
            player_rush[i] = 0
            player_tgt[i] = 0
            player_pass[i] = 0

    return {
        "playerRushAtt": player_rush,
        "playerTargets": player_tgt,
        "playerPassAtt": player_pass,
        "residualRushAtt": residual_rush,
        "residualTargets": residual_tgt,
        "residualPassAtt": residual_pass,
        "kickerIsolated": all(player_rush[i] == 0 and player_tgt[i] == 0 for i, k in enumerate(kicker_flags) if k) if any(kicker_flags) else True,
        "modeledRushShare": (sum(player_rush) / team_rush_att) if team_rush_att else 0.0,
        "modeledTargetShare": (sum(player_tgt) / team_targets) if team_targets else 0.0,
        "modeledPassShare": (sum(player_pass) / team_pass_att) if team_pass_att else 0.0,
    }
