"""Cutoff-safe, abstention-first audit for manual/production direction proposals.

This is not a probability model. Its role is to prevent weak recent-trend
narratives from silently overruling the pre-event observed base rate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
from typing import Literal, Sequence

Side = Literal["HIGHER", "LOWER"]


@dataclass(frozen=True)
class HistoricalObservation:
    event_id: str
    completed_at_utc: str
    value: float


@dataclass(frozen=True)
class InverseGateResult:
    status: str
    side: Side
    line: float
    eligible: int
    successes: int
    failures: int
    pushes: int
    empirical_hit_rate: float | None
    beta22_diagnostic: float | None
    opposing_hit_rate: float | None
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def _as_aware_datetime(text: str) -> datetime:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("UTC_OFFSET_REQUIRED")
    return dt


def audit_direction(
    *,
    side: Side,
    line: float,
    observations: Sequence[HistoricalObservation],
    cutoff_utc: str,
    exact_offer_verified: bool,
    verified_regime_evidence_ids: Sequence[str] = (),
    minimum_games: int = 5,
) -> InverseGateResult:
    """Evaluate a candidate direction; never convert hit rate into calibrated p.

    Role-change overrides require auditable independent evidence. This gate
    cannot certify playability by itself, and its results must be consumed by
    the canonical eligibility and ranking pipeline.
    """
    if side not in {"HIGHER", "LOWER"}:
        raise ValueError("INVALID_SIDE")
    if not isfinite(float(line)):
        raise ValueError("INVALID_LINE")
    if minimum_games < 3:
        raise ValueError("MINIMUM_GAMES_TOO_SMALL")
    cutoff = _as_aware_datetime(cutoff_utc)
    seen: set[str] = set()
    wins = losses = pushes = 0
    for obs in observations:
        if not obs.event_id or obs.event_id in seen:
            raise ValueError("DUPLICATE_OR_EMPTY_EVENT_ID")
        seen.add(obs.event_id)
        if _as_aware_datetime(obs.completed_at_utc) >= cutoff:
            raise ValueError("POST_CUTOFF_GAME_LOG")
        if not isfinite(float(obs.value)):
            raise ValueError("INVALID_OBSERVATION")
        if obs.value == line:
            pushes += 1
        elif (obs.value > line) == (side == "HIGHER"):
            wins += 1
        else:
            losses += 1
    n = wins + losses
    p = wins / n if n else None
    opp = losses / n if n else None
    shrink = (wins + 2) / (n + 4) if n else None
    reasons: list[str] = []
    if not exact_offer_verified:
        reasons.append("EXACT_PLATFORM_OFFER_UNVERIFIED")
    if n < minimum_games:
        reasons.append("INSUFFICIENT_COMPARABLE_GAMES")
    if n and opp is not None and opp >= 0.75:
        if not verified_regime_evidence_ids:
            reasons.append("CONTRADICTS_PRE_EVENT_BASE_RATE_NO_REGIME_EVIDENCE")
        else:
            reasons.append("INVERSE_REQUIRES_INDEPENDENT_REGIME_VALIDATION")
    if pushes:
        reasons.append("PUSH_RULES_MUST_BE_VERIFIED")
    if not exact_offer_verified:
        status = "BLOCKED_UNVERIFIED_OFFER"
    elif n < minimum_games:
        status = "BLOCKED_INSUFFICIENT_EVIDENCE"
    elif "CONTRADICTS_PRE_EVENT_BASE_RATE_NO_REGIME_EVIDENCE" in reasons:
        status = "BLOCKED_UNSUPPORTED_INVERSE"
    elif "INVERSE_REQUIRES_INDEPENDENT_REGIME_VALIDATION" in reasons:
        status = "CHALLENGER_ONLY"
    elif pushes:
        status = "BLOCKED_UNKNOWN_PUSH_RULES"
    else:
        status = "SHADOW_DIRECTION_ONLY"
    return InverseGateResult(
        status=status, side=side, line=float(line), eligible=n,
        successes=wins, failures=losses, pushes=pushes,
        empirical_hit_rate=p, beta22_diagnostic=shrink,
        opposing_hit_rate=opp, reasons=tuple(reasons),
    )
