"""Deterministic research queue for typed Outlier Insights claims.

The queue is an attention allocator, never a probability model.  It consumes
only canonical claims, ranks the complete accounted population, and records
why a row was promoted for research.  A later evidence packet and validated
market definition are required before any row can reach modeling or selection.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable

from dcm.contracts.hashes import content_hash


QUEUE_VERSION = "OUTLIER_INSIGHTS_RESEARCH_QUEUE_V1_2026-09-14"

_PRODUCTION_LEAGUES = {"NFL", "NCAAFB", "CFB", "WNBA"}
_SHADOW_LEAGUES = {"MLB"}
_RESEARCH_ONLY_LEAGUES = {"SOCCER", "NHL", "NBA"}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def wilson_lower_bound(hits: int, n: int, *, z: float = 1.959963984540054) -> float:
    """Wilson 95% lower bound for a historical signal, not a next-game p."""
    if n <= 0:
        return 0.0
    p = min(1.0, max(0.0, hits / n))
    denominator = 1.0 + (z * z / n)
    center = p + (z * z / (2.0 * n))
    radius = z * math.sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n)))
    return max(0.0, min(1.0, (center - radius) / denominator))


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * min(1.0, max(0.0, fraction))
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _history_values(claim: dict[str, Any]) -> list[float]:
    history = claim.get("history") if isinstance(claim.get("history"), dict) else {}
    values: list[float] = []
    for item in history.get("items") or []:
        if not isinstance(item, dict):
            continue
        value = _finite(item.get("value"))
        if value is not None:
            values.append(value)
    return values


def _line_diagnostics(claim: dict[str, Any]) -> dict[str, Any]:
    line = _finite(claim.get("line"))
    values = _history_values(claim)
    q20 = _quantile(values, 0.20)
    q50 = _quantile(values, 0.50)
    q80 = _quantile(values, 0.80)
    period = str(claim.get("periodLabel") or "").upper()
    hit_rate = _finite(claim.get("reportedHitRate"))
    n = int(claim.get("lastNCount") or 0)
    flags: list[str] = []
    if line is None:
        flags.append("MISSING_LINE")
    if period in {"1Q", "2Q", "3Q", "4Q", "1H", "2H"}:
        flags.append("PARTIAL_PERIOD")
    if line is not None and line <= 0.5:
        flags.append("LOW_NUMERIC_LINE_REQUIRES_CONTEXT")
    if hit_rate is not None and hit_rate >= 0.90 and n < 10:
        flags.append("SHORT_PERFECT_OR_NEAR_PERFECT_STREAK")
    if values and line is not None and q20 is not None and q80 is not None:
        direction = str(claim.get("direction") or "")
        inside = q20 <= line <= q80
        if not inside:
            flags.append("HISTORICAL_TAIL_LINE")
        if direction == "HIGHER" and line < q20:
            flags.append("HIGHER_MAY_BE_TOY_LINE")
        if direction == "LOWER" and line > q80:
            flags.append("LOWER_MAY_BE_TOY_LINE")
    return {
        "historicalSample": len(values),
        "historicalQ20": q20,
        "historicalMedian": q50,
        "historicalQ80": q80,
        "flags": sorted(set(flags)),
        "trivialLineSuspect": bool(
            {"LOW_NUMERIC_LINE_REQUIRES_CONTEXT", "SHORT_PERFECT_OR_NEAR_PERFECT_STREAK"} & set(flags)
        ),
    }


def _modifier_state(claim: dict[str, Any]) -> tuple[str, bool, bool]:
    counts = claim.get("modifierCounts") if isinstance(claim.get("modifierCounts"), dict) else {}
    standard = int(counts.get("STANDARD") or 0) > 0
    goblin = int(counts.get("GOBLIN") or 0) > 0
    demon = int(counts.get("DEMON") or 0) > 0
    if demon and standard:
        state = "MIXED_STANDARD_DEMON"
    elif goblin and standard:
        state = "MIXED_STANDARD_GOBLIN"
    elif demon:
        state = "DEMON_ONLY"
    elif goblin:
        state = "GOBLIN_ONLY"
    elif standard:
        state = "STANDARD_PRESENT"
    else:
        state = "NO_EXPLICIT_MODIFIER"
    return state, goblin, demon


def _league_state(claim: dict[str, Any]) -> str:
    league = str(claim.get("leagueId") or "").upper()
    if league in _PRODUCTION_LEAGUES:
        return "PRODUCTION_PATH_RESEARCH_REQUIRED"
    if league in _SHADOW_LEAGUES:
        return "SHADOW_RESEARCH_ONLY"
    if league in _RESEARCH_ONLY_LEAGUES:
        return "RESEARCH_ONLY_NOT_SELECTABLE"
    return "UNKNOWN_SPORT_FAIL_CLOSED"


def score_research_attention(claim: dict[str, Any]) -> dict[str, Any]:
    """Score research value with transparent, bounded components."""
    last_n = int(claim.get("lastNCount") or 0)
    hits = int(claim.get("lastNHitCount") or 0)
    wilson = wilson_lower_bound(hits, last_n)
    n_maturity = min(1.0, math.sqrt(last_n / 20.0)) if last_n else 0.0
    book_count = int(claim.get("bookCount") or 0)
    book_coverage = min(1.0, math.log1p(book_count) / math.log(9.0)) if book_count else 0.0
    modifier_state, goblin, demon = _modifier_state(claim)
    standard_bonus = 1.0 if "STANDARD" in modifier_state else 0.25
    line = _line_diagnostics(claim)
    line_quality = 0.25 if line["trivialLineSuspect"] else 1.0
    league_state = _league_state(claim)
    sport_support = {
        "PRODUCTION_PATH_RESEARCH_REQUIRED": 1.0,
        "SHADOW_RESEARCH_ONLY": 0.65,
        "RESEARCH_ONLY_NOT_SELECTABLE": 0.50,
        "UNKNOWN_SPORT_FAIL_CLOSED": 0.10,
    }[league_state]
    direction_quality = 1.0 if str(claim.get("directionClass")) == "HIGHER_LOWER" else 0.0
    pagination_quality = 1.0 if bool(claim.get("paginationComplete")) else 0.0
    market_active = 1.0 if claim.get("marketActive") is not False else 0.0
    attention = 100.0 * (
        0.26 * wilson
        + 0.14 * n_maturity
        + 0.12 * book_coverage
        + 0.12 * standard_bonus
        + 0.12 * line_quality
        + 0.10 * sport_support
        + 0.08 * direction_quality
        + 0.04 * pagination_quality
        + 0.02 * market_active
    )
    blockers: list[str] = []
    if not pagination_quality:
        blockers.append("PAGINATION_INCOMPLETE")
    if goblin or demon:
        blockers.append("NON_STANDARD_MODIFIER_PRESENT")
    if league_state != "PRODUCTION_PATH_RESEARCH_REQUIRED":
        blockers.append(league_state)
    if line["trivialLineSuspect"]:
        blockers.append("TRIVIAL_LINE_RESEARCH_REQUIRED")
    if claim.get("marketActive") is False:
        blockers.append("MARKET_INACTIVE_AT_CAPTURE")
    if not direction_quality:
        blockers.append("DIRECTION_NOT_HIGHER_OR_LOWER")
    return {
        "attentionScore": round(attention, 8),
        "attentionScoreType": "RESEARCH_PRIORITY_NOT_PROBABILITY",
        "wilsonLowerBound95": round(wilson, 8),
        "nMaturity": round(n_maturity, 8),
        "bookCoverage": round(book_coverage, 8),
        "standardBookBonus": standard_bonus,
        "modifierState": modifier_state,
        "lineDiagnostics": line,
        "leagueState": league_state,
        "blockers": sorted(set(blockers)),
    }


def queue_record(claim: dict[str, Any], *, rank: int) -> dict[str, Any]:
    score = score_research_attention(claim)
    disposition = str(claim.get("disposition") or "")
    eligible_shape = disposition == "PLAYER_PROP_CANDIDATE"
    blocked = list(score["blockers"])
    if not eligible_shape:
        blocked.append("NOT_PLAYER_PROP_CANDIDATE")
    research_state = "RESEARCH_QUEUE" if eligible_shape and not any(
        reason in blocked for reason in ("PAGINATION_INCOMPLETE", "MARKET_INACTIVE_AT_CAPTURE")
    ) else "ACCOUNTED_NOT_QUEUED"
    return {
        "schema": "pillars_dcm.outlier_insight_research_queue_row.v1",
        "rank": int(rank),
        "claimId": claim.get("claimId"),
        "insightId": claim.get("insightId"),
        "sourceHarSha256": claim.get("sourceHarSha256"),
        "sourceBodyHash": claim.get("sourceBodyHash"),
        "leagueId": claim.get("leagueId"),
        "eventId": (claim.get("event") or {}).get("eventId"),
        "scheduledTime": (claim.get("event") or {}).get("scheduledTime"),
        "subjectId": claim.get("subjectId"),
        "subjectName": claim.get("subjectName"),
        "teamId": claim.get("teamId"),
        "marketId": claim.get("marketId"),
        "marketOutcomeId": claim.get("marketOutcomeId"),
        "marketType": claim.get("marketType"),
        "proposition": claim.get("proposition"),
        "periodLabel": claim.get("periodLabel"),
        "line": claim.get("line"),
        "direction": claim.get("direction"),
        "lastNCount": claim.get("lastNCount"),
        "lastNHitCount": claim.get("lastNHitCount"),
        "reportedHitRate": claim.get("reportedHitRate"),
        "bookCount": claim.get("bookCount"),
        "researchState": research_state,
        "productionEligible": False,
        "offerRevalidationRequired": True,
        "probability": None,
        **score,
        "blockers": sorted(set(blocked)),
    }


def _diversified_frontier(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Avoid turning one player/event's correlated props into a fake frontier."""
    selected: list[dict[str, Any]] = []
    event_subject_counts: Counter[tuple[str, str]] = Counter()
    exact_market_counts: Counter[tuple[str, str, str]] = Counter()
    deferred: list[dict[str, Any]] = []
    for row in rows:
        event_subject = (str(row.get("eventId") or ""), str(row.get("subjectId") or ""))
        exact_market = (
            event_subject[0],
            event_subject[1],
            str(row.get("proposition") or ""),
        )
        if event_subject_counts[event_subject] >= 2 or exact_market_counts[exact_market] >= 1:
            deferred.append(row)
            continue
        selected.append(row)
        event_subject_counts[event_subject] += 1
        exact_market_counts[exact_market] += 1
        if len(selected) >= limit:
            return selected
    for row in deferred:
        if len(selected) >= limit:
            break
        event_subject = (str(row.get("eventId") or ""), str(row.get("subjectId") or ""))
        exact_market = (
            event_subject[0],
            event_subject[1],
            str(row.get("proposition") or ""),
        )
        if event_subject_counts[event_subject] >= 2 or exact_market_counts[exact_market] >= 1:
            continue
        selected.append(row)
        event_subject_counts[event_subject] += 1
        exact_market_counts[exact_market] += 1
    if len(selected) < limit:
        for row in deferred:
            if len(selected) >= limit:
                break
            if row not in selected:
                selected.append(row)
    return selected


def build_research_queue(claims: Iterable[dict[str, Any]], *, top_n: int = 100, top_preview: int = 25) -> dict[str, Any]:
    """Account the full claim universe, then emit Top-100/Top-25 attention lists."""
    records = [dict(claim) for claim in claims if isinstance(claim, dict)]
    scored = [queue_record(claim, rank=0) for claim in records]
    scored.sort(
        key=lambda row: (
            0 if row["researchState"] == "RESEARCH_QUEUE" else 1,
            -float(row.get("attentionScore") or 0.0),
            -int(row.get("bookCount") or 0),
            -int(row.get("lastNCount") or 0),
            str(row.get("leagueId") or ""),
            str(row.get("scheduledTime") or ""),
            str(row.get("claimId") or ""),
        )
    )
    for index, row in enumerate(scored, 1):
        row["rank"] = index
    queued = [row for row in scored if row["researchState"] == "RESEARCH_QUEUE"]
    top100 = queued[: max(0, int(top_n))]
    top25 = top100[: max(0, int(top_preview))]
    production_blockers = {
        "PAGINATION_INCOMPLETE",
        "NON_STANDARD_MODIFIER_PRESENT",
        "MARKET_INACTIVE_AT_CAPTURE",
        "DIRECTION_NOT_HIGHER_OR_LOWER",
        "TRIVIAL_LINE_RESEARCH_REQUIRED",
    }
    production_queue = [
        row for row in queued
        if row.get("leagueState") == "PRODUCTION_PATH_RESEARCH_REQUIRED"
        and not production_blockers.intersection(row.get("blockers") or [])
    ]
    top100_production = production_queue[: max(0, int(top_n))]
    top25_production = top100_production[: max(0, int(top_preview))]
    diversified_top25 = _diversified_frontier(top100, max(0, int(top_preview)))
    diversified_production_top25 = _diversified_frontier(
        top100_production,
        max(0, int(top_preview)),
    )
    counts = Counter(str(row.get("researchState") or "UNKNOWN") for row in scored)
    league_counts = Counter(str(row.get("leagueId") or "UNKNOWN") for row in queued)
    accounting = {
        "inputClaimCount": len(records),
        "queuedClaimCount": len(queued),
        "top100Count": len(top100),
        "top25Count": len(top25),
        "productionQueueCount": len(production_queue),
        "productionTop100Count": len(top100_production),
        "productionTop25Count": len(top25_production),
        "diversifiedTop25Count": len(diversified_top25),
        "diversifiedProductionTop25Count": len(diversified_production_top25),
        "states": dict(sorted(counts.items())),
        "queuedByLeague": dict(sorted(league_counts.items())),
        "probabilityStatus": "NONE",
        "selectionStatus": "RESEARCH_ONLY",
        "contentHash": content_hash(
            [
                {
                    "claimId": row.get("claimId"),
                    "attentionScore": row.get("attentionScore"),
                    "rank": row.get("rank"),
                    "researchState": row.get("researchState"),
                    "leagueState": row.get("leagueState"),
                    "blockers": row.get("blockers"),
                }
                for row in scored
            ]
        ),
    }
    return {
        "schema": "pillars_dcm.outlier_insights_research_queue.v1",
        "queueVersion": QUEUE_VERSION,
        "accounting": accounting,
        "rows": scored,
        "top100": top100,
        "top25": top25,
        "diversifiedTop25": diversified_top25,
        "productionTop100": top100_production,
        "productionTop25": top25_production,
        "diversifiedProductionTop25": diversified_production_top25,
    }
