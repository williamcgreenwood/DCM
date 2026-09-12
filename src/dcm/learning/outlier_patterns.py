"""Prospective Outlier observation and guarded segment analysis.

Historical line/odds/hit-rate patterns can produce challenger hypotheses only.
Single legs and correlated slips are intentionally analyzed as separate units.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Any, Iterable, Mapping

REQUIRED_OBSERVATION_FIELDS = frozenset({"observationId", "decisionCutoff", "projectionId", "line", "side", "modifier", "targetBook", "selected", "selectionState"})


@dataclass(frozen=True)
class SegmentSummary:
    segment: tuple[tuple[str, str], ...]
    n: int
    wins: int
    losses: int
    posterior_mean: float
    wilson_lower: float
    state: str

    def as_dict(self) -> dict[str, Any]:
        return {"segment": dict(self.segment), "n": self.n, "wins": self.wins, "losses": self.losses,
                "posteriorMean": self.posterior_mean, "wilsonLower": self.wilson_lower, "state": self.state,
                "promotionForbidden": True}


def validate_observation(row: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    missing = tuple(sorted(key for key in REQUIRED_OBSERVATION_FIELDS if row.get(key) in (None, "")))
    if str(row.get("modifier") or "").upper() == "GOBLIN":
        return False, tuple(sorted(set(missing) | {"GOBLIN_SELECTION_FORBIDDEN"}))
    return not missing, missing


def _wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    radius = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - radius) / denom)


def summarize_leg_segments(rows: Iterable[Mapping[str, Any]], *, by: tuple[str, ...], minimum_n: int) -> list[SegmentSummary]:
    """Summarize settled independent legs only; any slip lineage is excluded."""
    groups: dict[tuple[tuple[str, str], ...], list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if str(row.get("entryUnit") or "LEG").upper() != "LEG" or row.get("slipId"):
            continue
        result = str(row.get("result") or row.get("settlement") or "").upper()
        if result not in {"WIN", "LOSS"}:
            continue
        key = tuple((name, str(row.get(name) or "")) for name in by)
        groups[key][0] += 1
        groups[key][1] += result == "WIN"
    return [SegmentSummary(key, n, wins, n - wins, (wins + 1) / (n + 2), _wilson_lower(wins, n), "CHALLENGER_REQUIRES_FUTURE_HOLDOUT")
            for key, (n, wins) in sorted(groups.items()) if n >= minimum_n]
