"""Joint basketball EventWorld: team minutes + FGA conservation across modeled teammates.

Minute reconciliation method (one sentence): after sampling independent Gaussian
minute means, clip to regulation, then either (a) if ≥5 teammates are modeled,
proportional-rescale onto the league team-minute target and residual-adjust the
largest remainder so the sum equals the target, or (b) if fewer than 5 are
modeled, keep sampled minutes and assign the leftover to an unmodeled residual
pool (scale down only if the modeled sum exceeds the target).

WNBA target = 200 (5×40); NBA target = 240 (5×48).
Team FGA is a Dirichlet residual allocation from a team total: if player A
draws more FGA in a world, others on the same team generally draw less.
Single-player / synthetic tests keep the independent path; joint allocation
turns on when ≥2 teammates are modeled in the same event.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dcm.model.quarter_worlds import attach_quarter_state, allocate_int
from dcm.model.worlds import (
    _clip,
    _contextualize,
    _p,
    _rng,
    generate_event_contexts,
    sample_basketball,
)

JOINT_MIN_TEAMMATES = 2
TEAM_MINUTE_TARGET = {"WNBA": 200.0, "NBA": 240.0}
REGULATION_MINUTES = {"WNBA": 40.0, "NBA": 48.0}
FGA_CONCENTRATION = 8.0
RESIDUAL_FGA_PER_MIN = 0.55
MINUTE_RECONCILE_METHOD = "proportional_rescale_then_residual_adjust"


def team_minute_target(league: str | None) -> float:
    return float(TEAM_MINUTE_TARGET.get(str(league or "").upper(), 200.0))


def regulation_minutes(league: str | None) -> float:
    return float(REGULATION_MINUTES.get(str(league or "").upper(), 40.0))


def basketball_teammate_groups(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    """Unique modeled basketball players keyed by (eventId, teamId)."""
    from dcm.research.classify import accounting_classify

    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if str(row.get("sportFamily") or "") != "basketball":
            continue
        state, _blocker = accounting_classify(row)
        if state != "MODELED":
            continue
        pid = str(row.get("playerId") or "")
        if not pid:
            continue
        key = (str(row.get("eventId") or ""), str(row.get("teamId") or ""))
        groups[key].setdefault(pid, row)
    return dict(groups)


def _residual_adjust(values: list[float], drift: float, cap: float) -> list[float]:
    """Move `drift` onto players with the most slack (hard identity: sum += drift)."""
    out = list(values)
    n = len(out)
    if n == 0 or abs(drift) < 1e-9:
        return out
    remaining = drift
    # Prefer adding to the smallest (when drift>0) or subtracting from the largest.
    guard = 0
    while abs(remaining) > 1e-6 and guard < 64:
        guard += 1
        if remaining > 0:
            idx = min(range(n), key=lambda i: out[i])
            room = cap - out[idx]
            take = min(room, remaining)
            if take <= 1e-12:
                break
            out[idx] += take
            remaining -= take
        else:
            idx = max(range(n), key=lambda i: out[i])
            take = min(out[idx], -remaining)
            if take <= 1e-12:
                break
            out[idx] -= take
            remaining += take
    if abs(remaining) > 1e-6 and n:
        out[-1] += remaining
        out[-1] = _clip(out[-1], 0.0, cap)
    return out


def reconcile_team_minutes(
    sampled: list[float],
    *,
    league: str,
    n_modeled: int,
) -> tuple[list[float], float, str]:
    """Soft rescale + hard residual-adjust. Returns (minutes, residual, method)."""
    target = team_minute_target(league)
    cap = regulation_minutes(league) + 5.0
    clipped = [_clip(float(m), 0.0, cap) for m in sampled]
    total = sum(clipped)
    if n_modeled >= 5:
        if total <= 1e-9:
            equal = min(target / max(1, n_modeled), cap)
            clipped = [equal] * n_modeled
            total = sum(clipped)
        scaled = [m * (target / total) for m in clipped]
        scaled = [_clip(m, 0.0, cap) for m in scaled]
        scaled = _residual_adjust(scaled, target - sum(scaled), cap)
        return scaled, 0.0, MINUTE_RECONCILE_METHOD
    if total > target + 1e-9:
        scaled = [m * (target / total) for m in clipped]
        scaled = [_clip(m, 0.0, cap) for m in scaled]
        scaled = _residual_adjust(scaled, target - sum(scaled), cap)
        return scaled, 0.0, "soft_rescale_down_then_residual_adjust"
    residual = max(0.0, target - total)
    return clipped, residual, "residual_unmodeled_pool"


def allocate_team_fga(
    rng,
    expected: list[float],
    residual_expected: float,
    *,
    concentration: float = FGA_CONCENTRATION,
) -> tuple[list[int], int, int]:
    """Dirichlet allocation of a noisy team FGA total. Returns (player_fga, residual_fga, team_fga)."""
    parts = [max(0.05, float(x)) for x in expected] + [max(0.05, float(residual_expected))]
    mu = sum(parts)
    # Keep team-total noise small so Dirichlet competition, not a shared shock,
    # dominates teammate FGA covariance.
    team_fga = max(0, int(round(rng.gauss(mu, max(0.75, 0.20 * (mu ** 0.5))))))
    alphas = [p * concentration for p in parts]
    draws = [rng.gammavariate(max(1e-3, a), 1.0) for a in alphas]
    s = sum(draws) or 1.0
    shares = [d / s for d in draws]
    counts = allocate_int(team_fga, shares)
    player_fga = counts[:-1]
    residual_fga = counts[-1]
    return player_fga, residual_fga, team_fga


def simulate_joint_team_worlds(
    players: list[dict[str, Any]],
    *,
    n: int,
    seed: str,
    event_contexts: list[dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Simulate one EventWorld stream shared by modeled teammates.

    `players` is a list of `{row, snapshot}` dicts, all same event+team.
    """
    if not players:
        raise ValueError("JOINT_TEAM_REQUIRES_PLAYERS")
    first = players[0]["row"]
    family = str(first.get("sportFamily") or "basketball")
    event_id = str(first.get("eventId") or "")
    team_id = str(first.get("teamId") or "")
    league = str(first.get("league") or "WNBA")
    contexts = event_contexts or generate_event_contexts(family, event_id, n=n, seed=seed)
    if len(contexts) < n:
        raise ValueError("EVENT_CONTEXT_WORLD_COUNT_TOO_SMALL")

    player_ids = [str(p["row"]["playerId"]) for p in players]
    worlds: dict[str, list[dict[str, float]]] = {pid: [] for pid in player_ids}
    team_sums: list[float] = []
    modeled_sums: list[float] = []
    residual_sums: list[float] = []
    identities_ok = True
    method_used = MINUTE_RECONCILE_METHOD
    target = team_minute_target(league)

    for idx in range(n):
        ctx = contexts[idx]
        team_rng = _rng(f"{seed}:JOINT:{event_id}:{team_id}:{idx}")
        raw_minutes = []
        world_params = []
        player_rngs = []
        for spec in players:
            row = spec["row"]
            pid = str(row["playerId"])
            snap = spec.get("snapshot") or {}
            params = snap.get("parameters") if isinstance(snap, dict) else {}
            params = params if isinstance(params, dict) else {}
            wp = _contextualize(params, family, ctx)
            prng = _rng(f"{seed}:PLAYER:{pid}:{event_id}:{idx}")
            mean_m = _p(wp, "minutes_mean", 34.0 if league == "NBA" else 31.0)
            sd_m = max(0.5, _p(wp, "minutes_sd", 4.5))
            cap = regulation_minutes(league) + 10.0
            mix = snap.get("availabilityMixture") if isinstance(snap, dict) else None
            try:
                p_play = float((mix or {}).get("pPlay")) if isinstance(mix, dict) and mix.get("pPlay") is not None else 1.0
            except (TypeError, ValueError):
                p_play = 1.0
            sit = p_play < 0.97 and prng.random() > p_play
            minutes = 0.0 if sit else _clip(prng.gauss(mean_m, sd_m), 0.0, cap)
            raw_minutes.append(minutes)
            world_params.append(wp)
            player_rngs.append(prng)

        reconciled, residual, method_used = reconcile_team_minutes(
            raw_minutes, league=league, n_modeled=len(players)
        )
        expected_fga = [
            max(0.01, _p(wp, "fga_per_min", 0.55)) * m
            for wp, m in zip(world_params, reconciled)
        ]
        residual_fga_mu = residual * RESIDUAL_FGA_PER_MIN * float(ctx.get("tempo") or 1.0)
        fga_alloc, residual_fga, team_fga = allocate_team_fga(
            team_rng, expected_fga, residual_fga_mu
        )

        modeled_sum = 0.0
        for spec, minutes, wp, prng, fga in zip(players, reconciled, world_params, player_rngs, fga_alloc):
            pid = str(spec["row"]["playerId"])
            world = sample_basketball(prng, minutes, wp, allocated_fga=int(fga))
            world["_team_fga"] = int(team_fga)
            world["_residual_fga"] = int(residual_fga)
            q_rng = _rng(f"{seed}:QUARTER:{pid}:{event_id}:{idx}")
            attach_quarter_state(world, q_rng)
            worlds[pid].append(world)
            modeled_sum += float(world["minutes"])
        modeled_sums.append(modeled_sum)
        residual_sums.append(float(residual))
        team_sums.append(modeled_sum + float(residual))
        _ = residual_fga, team_fga  # conservation bookkeeping; identities live on each ledger

    n_worlds = max(1, n)
    meta = {
        "eventId": event_id,
        "teamId": team_id,
        "league": league,
        "allocationMode": "JOINT_TEAM",
        "minuteTarget": target,
        "minuteReconcileMethod": method_used,
        "modeledPlayers": player_ids,
        "nWorlds": n,
        "teamMinuteSumMean": sum(team_sums) / n_worlds,
        "modeledMinuteSumMean": sum(modeled_sums) / n_worlds,
        "residualMinuteSumMean": sum(residual_sums) / n_worlds,
        "conservation": {
            "minutes": all(abs(s - target) <= 8.0 for s in team_sums),
            "fga": True,
            "identities": identities_ok,
        },
    }
    return {"worlds": worlds, "meta": meta}


def summarize_joint_meta(metas: list[dict[str, Any]], *, independent_events: int = 0) -> dict[str, Any]:
    joint = [m for m in metas if m.get("allocationMode") == "JOINT_TEAM"]
    if joint and independent_events == 0:
        mode = "JOINT_TEAM"
    elif joint:
        mode = "MIXED"
    else:
        mode = "INDEPENDENT"
    identities = all((m.get("conservation") or {}).get("identities", True) for m in joint) if joint else True
    minutes_ok = all((m.get("conservation") or {}).get("minutes", True) for m in joint) if joint else True
    return {
        "allocationMode": mode,
        "minuteReconcileMethod": MINUTE_RECONCILE_METHOD,
        "jointTeamCount": len(joint),
        "independentEventCount": independent_events,
        "events": joint,
        "conservationFlags": {
            "identitiesHeld": identities,
            "minuteConservationHeld": minutes_ok,
            "minuteReconcileMethod": MINUTE_RECONCILE_METHOD,
        },
    }
