"""Team opportunity ledger with residual buckets.

Board membership never implies 100% ownership of team opportunity.
Kickers receive no rush attempts or targets.
Role caps are fallback priors only. Evidence-backed shares are not recapped.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from dcm.contracts.hashes import content_hash

KICKER_ROLES = frozenset({"K", "PK"})

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


def _support_n(params: Mapping[str, Any]) -> int:
    for key in ("support_n", "opportunity_support_n", "log_support_n"):
        try:
            n = int(params.get(key) or 0)
            if n:
                return n
        except (TypeError, ValueError):
            continue
    logs = params.get("comparable_logs") or params.get("game_logs") or []
    if isinstance(logs, list):
        return len([r for r in logs if isinstance(r, dict)])
    return 0


def estimate_opportunity_share(
    player: Mapping[str, Any],
    *,
    pool: str,
    team_total: float,
) -> dict[str, Any]:
    """Evidence-driven share of a team opportunity pool.

    Hierarchy: current role-epoch logs → season mean → archetype prior → static role cap.
    A known full-game starting QB is not blindly capped at 92%.
    """
    role = _role(player)
    params = player.get("params") if isinstance(player.get("params"), Mapping) else {}
    is_k = role in KICKER_ROLES
    total = max(0.0, float(team_total))
    support = _support_n(params)
    if is_k or pool not in {"rush", "targets", "pass"}:
        body = {
            "subject": player.get("playerId") or player.get("subject"),
            "role": role,
            "pool": pool,
            "estimatedShare": 0.0,
            "residualShare": 1.0 if total else 0.0,
            "mean": 0.0,
            "support_n": support,
            "method": "KICKER_ISOLATED" if is_k else "NOT_APPLICABLE",
            "fallback": False,
            "priorUsed": False,
        }
        body["contentHash"] = content_hash(body)
        return body
    if pool == "rush":
        mean = _mean(params, "rush_att_mean", DEFAULT_RUSH_MEAN.get(role, 1.0))
        cap = ROLE_RUSH_CAP.get(role, 0.12)
        prior_mean = DEFAULT_RUSH_MEAN.get(role, 1.0)
    elif pool == "targets":
        if params.get("routes_mean") is not None:
            mean = _mean(params, "routes_mean", 8.0) * _mean(params, "target_rate", DEFAULT_TARGET_MEAN.get(role, 3.0) / 8.0)
        else:
            mean = _mean(params, "targets_mean", DEFAULT_TARGET_MEAN.get(role, 3.0))
        cap = ROLE_TARGET_CAP.get(role, 0.15)
        prior_mean = DEFAULT_TARGET_MEAN.get(role, 3.0)
    else:
        mean = _mean(params, "pass_att_mean", DEFAULT_PASS_MEAN.get(role, 0.0) if role == "QB" else 0.0)
        cap = ROLE_PASS_CAP.get(role, 0.0)
        prior_mean = DEFAULT_PASS_MEAN.get(role, 0.0) if role == "QB" else 0.0

    starter = str(params.get("projected_role") or params.get("starter") or player.get("starter") or "").lower()
    is_starter = starter in {"1", "true", "starter", "starter_qb", "starting"} or (
        role == "QB" and support >= 3 and mean >= 0.85 * max(total, 1.0)
    )
    fallback = False
    method = "ROLE_EPOCH_LOGS"
    if support >= 3 and total > 0:
        share = min(1.0, max(0.0, mean / total))
        # Removal/backup residual: never assign 100% even to a starter.
        if is_starter and role == "QB" and pool == "pass":
            share = min(share, 0.99)
        method = "ROLE_EPOCH_LOGS"
    elif support > 0 and total > 0:
        share = min(1.0, max(0.0, mean / total))
        method = "THIN_SAMPLE"
    else:
        share = float(cap)
        mean = cap * total
        fallback = True
        method = "ROLE_CAP_FALLBACK"
        if total > 0 and prior_mean:
            # Archetype prior sits above the static cap when both exist; cap still binds.
            arch = min(cap, prior_mean / total) if total else cap
            share = arch
            mean = share * total
            method = "ARCHETYPE_PRIOR_THEN_CAP"
    residual = max(0.0, 1.0 - share) if total else 0.0
    body = {
        "subject": player.get("playerId") or player.get("subject"),
        "role": role,
        "pool": pool,
        "estimatedShare": share,
        "residualShare": residual,
        "mean": mean,
        "support_n": support,
        "method": method,
        "fallback": fallback,
        "priorUsed": fallback,
        "capApplied": fallback,
        "cap": cap if fallback else None,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def allocate_counts(means: Sequence[float], caps: Sequence[float], team_total: int) -> tuple[list[int], int]:
    """Absolute means, capped, never renormalized to 100% of the team pool."""
    total = max(0, int(team_total))
    raw: list[float] = []
    for mean, cap in zip(means, caps):
        cap_f = float(cap)
        if cap_f >= 0.999:
            capped = max(0.0, float(mean))
        else:
            capped = min(max(0.0, float(mean)), max(0.0, cap_f) * total)
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
    share_rows: list[dict[str, Any]] = []
    for p in players:
        role = _role(p)
        is_k = role in KICKER_ROLES
        kicker_flags.append(is_k)
        rush_est = estimate_opportunity_share(p, pool="rush", team_total=team_rush_att)
        tgt_est = estimate_opportunity_share(p, pool="targets", team_total=team_targets)
        pass_est = estimate_opportunity_share(p, pool="pass", team_total=team_pass_att)
        share_rows.append({"rush": rush_est, "targets": tgt_est, "pass": pass_est})
        if is_k:
            rush_means.append(0.0)
            rush_caps.append(0.0)
            tgt_means.append(0.0)
            tgt_caps.append(0.0)
            pass_means.append(0.0)
            pass_caps.append(0.0)
            continue
        rush_means.append(float(rush_est["mean"]))
        rush_caps.append(1.0 if not rush_est["fallback"] else ROLE_RUSH_CAP.get(role, 0.12))
        tgt_means.append(float(tgt_est["mean"]))
        tgt_caps.append(1.0 if not tgt_est["fallback"] else ROLE_TARGET_CAP.get(role, 0.15))
        pass_means.append(float(pass_est["mean"]))
        pass_caps.append(1.0 if not pass_est["fallback"] else ROLE_PASS_CAP.get(role, 0.0))

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
        "shareEstimates": share_rows,
    }


def _pool_mean_cap_for_total(
    player: Mapping[str, Any],
    *,
    pool: str,
    team_total: float,
) -> tuple[float, float, bool]:
    """Return (mean, allocate_cap, fallback) matching estimate_opportunity_share math.

    Skips content_hash / audit body construction for hot EventWorld loops.
    """
    role = _role(player)
    params = player.get("params") if isinstance(player.get("params"), Mapping) else {}
    is_k = role in KICKER_ROLES
    total = max(0.0, float(team_total))
    if is_k or pool not in {"rush", "targets", "pass"}:
        return 0.0, 0.0, False
    if pool == "rush":
        mean = _mean(params, "rush_att_mean", DEFAULT_RUSH_MEAN.get(role, 1.0))
        cap = ROLE_RUSH_CAP.get(role, 0.12)
        prior_mean = DEFAULT_RUSH_MEAN.get(role, 1.0)
    elif pool == "targets":
        if params.get("routes_mean") is not None:
            mean = _mean(params, "routes_mean", 8.0) * _mean(
                params, "target_rate", DEFAULT_TARGET_MEAN.get(role, 3.0) / 8.0
            )
        else:
            mean = _mean(params, "targets_mean", DEFAULT_TARGET_MEAN.get(role, 3.0))
        cap = ROLE_TARGET_CAP.get(role, 0.15)
        prior_mean = DEFAULT_TARGET_MEAN.get(role, 3.0)
    else:
        mean = _mean(params, "pass_att_mean", DEFAULT_PASS_MEAN.get(role, 0.0) if role == "QB" else 0.0)
        cap = ROLE_PASS_CAP.get(role, 0.0)
        prior_mean = DEFAULT_PASS_MEAN.get(role, 0.0) if role == "QB" else 0.0

    support = _support_n(params)
    starter = str(params.get("projected_role") or params.get("starter") or player.get("starter") or "").lower()
    is_starter = starter in {"1", "true", "starter", "starter_qb", "starting"} or (
        role == "QB" and support >= 3 and mean >= 0.85 * max(total, 1.0)
    )
    if support >= 3 and total > 0:
        share = min(1.0, max(0.0, mean / total))
        if is_starter and role == "QB" and pool == "pass":
            share = min(share, 0.99)
        mean = share * total
        fallback = False
    elif support > 0 and total > 0:
        share = min(1.0, max(0.0, mean / total))
        mean = share * total
        fallback = False
    else:
        share = float(cap)
        mean = cap * total
        fallback = True
        if total > 0 and prior_mean:
            arch = min(cap, prior_mean / total) if total else cap
            share = arch
            mean = share * total
    allocate_cap = 1.0 if not fallback else float(cap)
    if is_k:
        return 0.0, 0.0, False
    return float(mean), float(allocate_cap), bool(fallback)


def allocate_team_opportunity_fast(
    players: Sequence[Mapping[str, Any]],
    *,
    team_pass_att: int,
    team_rush_att: int,
    team_targets: int,
) -> dict[str, Any]:
    """Hot-path allocation without per-call content_hash / shareEstimates bodies.

    Counts and residuals match ``allocate_team_opportunity``; audit share rows are omitted.
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
        rm, rc, _ = _pool_mean_cap_for_total(p, pool="rush", team_total=team_rush_att)
        tm, tc, _ = _pool_mean_cap_for_total(p, pool="targets", team_total=team_targets)
        pm, pc, _ = _pool_mean_cap_for_total(p, pool="pass", team_total=team_pass_att)
        rush_means.append(rm)
        rush_caps.append(rc)
        tgt_means.append(tm)
        tgt_caps.append(tc)
        pass_means.append(pm)
        pass_caps.append(pc)

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
        "kickerIsolated": all(
            player_rush[i] == 0 and player_tgt[i] == 0 for i, k in enumerate(kicker_flags) if k
        )
        if any(kicker_flags)
        else True,
        "modeledRushShare": (sum(player_rush) / team_rush_att) if team_rush_att else 0.0,
        "modeledTargetShare": (sum(player_tgt) / team_targets) if team_targets else 0.0,
        "modeledPassShare": (sum(player_pass) / team_pass_att) if team_pass_att else 0.0,
        "shareEstimates": [],
    }
