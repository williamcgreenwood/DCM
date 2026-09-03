"""Quarter-state modeling from full-game primitive totals.

Full-game points and minutes are split into four quarter draws that SUM to the
game totals (Dirichlet shares + largest-remainder integer allocation). Quarter
props are never inferred from a full-game Gaussian alone. If the board is
quarter-based and this plugin cannot derive the requested stat, fail closed.
"""
from __future__ import annotations

import random
from typing import Any

QUARTER_PLUGIN_VERSION = "BBALL_QUARTERS_V1_2026-08-30"
N_QUARTERS = 4
# Mild concentration around equal quarters (mean 0.25) with real between-period variance.
DIRICHLET_ALPHA = 3.0

QUARTER_INDEX = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3}
HALF_SLICES = {"1H": (0, 2), "2H": (2, 4)}
# Stats this plugin actually splits. Anything else on a quarter/half board fails closed.
SPLIT_STATS = {"pts", "minutes"}


class QuarterPluginIncomplete(RuntimeError):
    blocker = "QUARTER_PLUGIN_INCOMPLETE"

    def __init__(self, message: str = "QUARTER_PLUGIN_INCOMPLETE"):
        super().__init__(message)
        self.blocker = "QUARTER_PLUGIN_INCOMPLETE"


def dirichlet_shares(rng: random.Random, k: int = N_QUARTERS, alpha: float = DIRICHLET_ALPHA) -> list[float]:
    draws = [rng.gammavariate(max(1e-3, float(alpha)), 1.0) for _ in range(k)]
    total = sum(draws)
    if total <= 0:
        return [1.0 / k] * k
    return [d / total for d in draws]


def allocate_int(total: int, shares: list[float]) -> list[int]:
    """Largest-remainder so allocated integers sum exactly to total."""
    total = max(0, int(total))
    k = len(shares)
    if k == 0:
        return []
    if total == 0:
        return [0] * k
    raw = [max(0.0, float(s)) * total for s in shares]
    floors = [int(x) for x in raw]
    rem = total - sum(floors)
    order = sorted(range(k), key=lambda i: (raw[i] - floors[i], -i), reverse=True)
    for i in order[: max(0, rem)]:
        floors[i] += 1
    return floors


def allocate_float(total: float, shares: list[float]) -> list[float]:
    total = float(total)
    k = len(shares)
    if k == 0:
        return []
    out = [max(0.0, float(s)) * total for s in shares]
    drift = total - sum(out)
    if k and abs(drift) > 1e-12:
        out[-1] += drift
    return out


def split_game_to_quarters(
    rng: random.Random,
    *,
    pts: float,
    minutes: float,
    n_quarters: int = N_QUARTERS,
) -> dict[str, Any]:
    """Split full-game pts/minutes into n quarters that sum to the game totals."""
    pts_i = max(0, int(round(float(pts))))
    minutes_f = max(0.0, float(minutes))
    min_shares = dirichlet_shares(rng, n_quarters)
    # Points shares are a second Dirichlet draw so scoring is not a deterministic
    # scale of minutes (still sums to game points).
    pts_shares = dirichlet_shares(rng, n_quarters)
    q_pts = allocate_int(pts_i, pts_shares)
    q_min = allocate_float(minutes_f, min_shares)
    return {
        "pts": q_pts,
        "minutes": q_min,
        "pts_shares": pts_shares,
        "minutes_shares": min_shares,
        "pluginVersion": QUARTER_PLUGIN_VERSION,
    }


def attach_quarter_state(world: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    world["_quarters"] = split_game_to_quarters(
        rng,
        pts=float(world.get("pts") or 0.0),
        minutes=float(world.get("minutes") or 0.0),
    )
    return world


def require_quarters(ledger: dict[str, Any]) -> dict[str, Any]:
    q = ledger.get("_quarters")
    if not isinstance(q, dict) or not q.get("pts"):
        raise QuarterPluginIncomplete("QUARTER_PLUGIN_INCOMPLETE")
    return q


def count_quarters_at_least(quarters: dict[str, Any], stat: str, threshold: float) -> int:
    values = quarters.get(stat) or []
    return sum(1 for v in values if float(v) + 1e-12 >= float(threshold))


def derive_board_market(ledger: dict[str, Any], canon_market: str, board_id: str) -> float:
    """Derive a quarter/half board market from the attached quarter split.

    Only pts (and minutes) are split. Other stats on 1H/2H/Qn boards fail closed
    rather than faking a full-game Gaussian scaled by 1/4.
    """
    board = str(board_id or "").upper()
    if canon_market not in SPLIT_STATS:
        raise QuarterPluginIncomplete(f"QUARTER_PLUGIN_INCOMPLETE:{canon_market}:{board}")
    q = require_quarters(ledger)
    values = [float(v) for v in (q.get(canon_market) or [])]
    if len(values) < N_QUARTERS:
        raise QuarterPluginIncomplete("QUARTER_PLUGIN_INCOMPLETE")
    if board in QUARTER_INDEX:
        return float(values[QUARTER_INDEX[board]])
    if board in HALF_SLICES:
        lo, hi = HALF_SLICES[board]
        return float(sum(values[lo:hi]))
    if board == "QTRS":
        raise QuarterPluginIncomplete(f"QUARTER_PLUGIN_INCOMPLETE:QTRS:{canon_market}")
    raise QuarterPluginIncomplete(f"QUARTER_PLUGIN_INCOMPLETE:{board}")
