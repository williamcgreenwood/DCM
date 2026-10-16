"""Cutoff-safe empirical outcome distributions for captured Insights offers.

This is an explicitly uncalibrated baseline producer. It derives probabilities
from the captured historical outcome values, never from Outlier's reported
hit-rate field, and preserves discrete outcomes as point masses.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dcm.contracts.hashes import content_hash
from dcm.algorithms.registry import require_algorithm


ALGORITHM_ID = "ALG-ML-PROB-011"


_STAGES = (2000, 1000, 500, 250, 100, 50, 25, 12, 6)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _wilson_lower(successes: int, trials: int, *, z: float = 1.959963984540054) -> float:
    """Two-sided 95% Wilson lower bound for a Bernoulli share."""
    if trials <= 0:
        return 0.0
    p = successes / trials
    z2 = z * z
    den = 1.0 + z2 / trials
    center = p + z2 / (2.0 * trials)
    radius = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * trials)) / trials)
    return max(0.0, (center - radius) / den)


def _offered_sides(claim: Mapping[str, Any]) -> list[str]:
    sides: list[str] = []
    if claim.get("offeredHigher") is True:
        sides.append("HIGHER")
    if claim.get("offeredLower") is True:
        sides.append("LOWER")
    if sides:
        return sides
    direction = str(claim.get("direction") or "").strip().upper()
    direction_class = str(claim.get("directionClass") or "").strip().upper()
    return [direction] if direction_class == "HIGHER_LOWER" and direction in {"HIGHER", "LOWER"} else []


def _policy_exclusion(claim: Mapping[str, Any], line: float) -> str | None:
    counts = claim.get("modifierCounts") if isinstance(claim.get("modifierCounts"), Mapping) else {}
    def has_modifier(name: str) -> bool:
        for key, value in counts.items():
            if str(key).upper() != name:
                continue
            numeric = _number(value)
            if numeric is not None and numeric > 0:
                return True
        return False

    for book in claim.get("books") or []:
        if isinstance(book, Mapping) and str(book.get("modifier") or "").upper() == "GOBLIN":
            return "GREEN_GOBLIN_EXCLUDED"
    if has_modifier("GOBLIN"):
        return "GREEN_GOBLIN_EXCLUDED"

    if abs(line - 0.5) < 1e-9:
        market = " ".join(
            str(claim.get(key) or "")
            for key in ("proposition", "marketLabel", "lineLabel", "propLabel")
        ).upper()
        league = str(claim.get("leagueId") or claim.get("league") or "").upper()
        tokens = set(re.findall(r"[A-Z0-9]+", market))
        interceptions = "INTERCEPTION" in " ".join(tokens) or "INTERCEPTIONS" in tokens or "INT" in tokens
        plus_minus = league == "NHL" and (
            "PLUSMINUS" in "".join(tokens)
            or "PLUS_MINUS" in market.replace(" ", "_")
            or "PLUS/MINUS" in market
        )
        if not interceptions and not plus_minus:
            return "POLICY_LINE_0_5_EXCLUDED"
    return None


def _history_values(
    claim: Mapping[str, Any], cutoff: datetime
) -> tuple[list[tuple[float, str | None, str, str | None]], int]:
    history = claim.get("history") if isinstance(claim.get("history"), Mapping) else {}
    items = history.get("items") if isinstance(history.get("items"), list) else []
    selected: list[tuple[float, str | None, str, str | None]] = []
    seen: set[str] = set()
    excluded_after_cutoff = 0
    for item in items:
        if not isinstance(item, Mapping):
            continue
        observed_at = _time(item.get("date"))
        if observed_at is None:
            continue
        if observed_at > cutoff:
            excluded_after_cutoff += 1
            continue
        value = _number(item.get("value"))
        if value is None:
            value = _number(item.get("stat"))
        if value is None:
            continue
        event_id = str(item.get("eventId") or "").strip()
        identity = event_id or content_hash([observed_at.isoformat(), item.get("matchup"), value])
        if identity in seen:
            continue
        seen.add(identity)
        matchup = str(item.get("matchup") or "").strip() or None
        selected.append((value, event_id or None, observed_at.isoformat().replace("+00:00", "Z"), matchup))
    return selected, excluded_after_cutoff


def _decision(
    claim: Mapping[str, Any], *, cutoff: datetime | None,
    event_date: str | None, event_timezone: str | None,
) -> dict[str, Any]:
    claim_id = str(claim.get("claimId") or claim.get("insightId") or "").strip()
    identity = claim.get("harIdentity") if isinstance(claim.get("harIdentity"), Mapping) else {}
    player = identity.get("player") if isinstance(identity.get("player"), Mapping) else {}
    event_identity = identity.get("event") if isinstance(identity.get("event"), Mapping) else {}
    event = claim.get("event") if isinstance(claim.get("event"), Mapping) else {}
    home = event.get("home") if isinstance(event.get("home"), Mapping) else {}
    away = event.get("away") if isinstance(event.get("away"), Mapping) else {}
    row: dict[str, Any] = {
        "claimId": claim_id,
        "league": str(claim.get("leagueId") or claim.get("league") or "").upper() or None,
        "subjectId": str(claim.get("subjectId") or claim.get("playerId") or "") or None,
        "subjectName": claim.get("subjectName") or player.get("name"),
        "teamId": claim.get("teamId") or player.get("teamId"),
        "eventId": str(claim.get("eventId") or ((claim.get("event") or {}).get("eventId") if isinstance(claim.get("event"), Mapping) else "")) or None,
        "eventScheduledTime": event.get("scheduledTime") or event_identity.get("scheduledTime"),
        "homeTeam": home.get("name") or home.get("alias"),
        "awayTeam": away.get("name") or away.get("alias"),
        "market": str(claim.get("proposition") or claim.get("marketLabel") or "").upper() or None,
        "marketId": claim.get("marketId"),
        "marketOutcomeId": claim.get("marketOutcomeId"),
        "marketDefinitionState": claim.get("marketDefinitionState"),
        "periodLabel": claim.get("periodLabel"),
        "position": claim.get("position"),
        "sourceSnapshotTime": claim.get("sourceSnapshotTime"),
        "modifierCounts": dict(claim.get("modifierCounts") or {})
        if isinstance(claim.get("modifierCounts"), Mapping) else {},
        "line": _number(claim.get("line")),
        "offeredSides": _offered_sides(claim),
        "reportedHitRate": _number(claim.get("reportedHitRate")),
        "reportedLastNCount": int(_number(claim.get("lastNCount")) or 0),
        "reportedLastNHitCount": int(_number(claim.get("lastNHitCount")) or 0),
        "reportedHitRateUsedAsForecast": False,
        "sourceHarSha256": claim.get("sourceHarSha256"),
        "sourceBodyHash": claim.get("sourceBodyHash"),
        "terminalStatus": "UNMODELED",
        "reason": None,
        "probabilityType": "EMPIRICAL_HISTORICAL_RATE_UNCALIBRATED",
        "calibrationStatus": "NOT_CALIBRATED",
    }
    reported_n = row["reportedLastNCount"]
    reported_hits = row["reportedLastNHitCount"]
    computed_reported_rate = reported_hits / reported_n if reported_n > 0 and 0 <= reported_hits <= reported_n else None
    row["reportedLastNComputedRate"] = computed_reported_rate
    reported_rate = row["reportedHitRate"]
    row["reportedRateReconciliation"] = (
        "MATCHED"
        if reported_rate is not None and computed_reported_rate is not None and abs(reported_rate - computed_reported_rate) <= 0.005
        else "DISCREPANCY"
        if reported_rate is not None and computed_reported_rate is not None
        else "NOT_COMPARABLE"
    )
    if claim.get("disposition") != "PLAYER_PROP_CANDIDATE":
        row["reason"] = "NOT_A_PLAYER_PROP_CANDIDATE"
        return row
    if event_date:
        event = claim.get("event") if isinstance(claim.get("event"), Mapping) else {}
        identity = claim.get("harIdentity") if isinstance(claim.get("harIdentity"), Mapping) else {}
        identity_event = identity.get("event") if isinstance(identity.get("event"), Mapping) else {}
        scheduled = _time(event.get("scheduledTime") or identity_event.get("scheduledTime"))
        try:
            local_date = scheduled.astimezone(ZoneInfo(event_timezone or "UTC")).date().isoformat() if scheduled else None
        except ZoneInfoNotFoundError:
            row["reason"] = "EVENT_TIMEZONE_INVALID"
            return row
        if local_date is None:
            row["reason"] = "EVENT_SCHEDULE_TIME_MISSING_OR_INVALID"
            return row
        row["eventLocalDate"] = local_date
        row["eventTimezone"] = event_timezone or "UTC"
        row["runEventDate"] = event_date
        if local_date != event_date:
            row.update({"terminalStatus": "OUT_OF_RUN_SCOPE", "reason": "EVENT_DATE_NOT_TARGET_RUN_DATE"})
            return row
    line = row["line"]
    if line is None:
        row["reason"] = "MISSING_OR_INVALID_LINE"
        return row
    exclusion = _policy_exclusion(claim, line)
    if exclusion:
        row.update({"terminalStatus": "EXCLUDED_BY_POLICY", "reason": exclusion})
        return row
    sides = row["offeredSides"]
    if not sides:
        row["reason"] = "MISSING_OR_UNRESOLVED_OFFERED_SIDE"
        return row
    if cutoff is None:
        row["reason"] = "FORECAST_CUTOFF_MISSING_OR_INVALID"
        return row

    values, excluded_future = _history_values(claim, cutoff)
    if not values:
        row.update({"reason": "NO_VALID_CUTOFF_SAFE_HISTORICAL_OUTCOMES", "excludedAfterCutoffCount": excluded_future})
        return row
    counts: Counter[str] = Counter()
    masses: Counter[str] = Counter()
    for value, _event_id, _observed_at, _matchup in values:
        mass_key = format(value, ".12g")
        masses[mass_key] += 1
        if value > line + 1e-9:
            counts["HIGHER"] += 1
        elif value < line - 1e-9:
            counts["LOWER"] += 1
        else:
            counts["PUSH"] += 1

    n = len(values)
    p_higher = counts["HIGHER"] / n
    p_lower = counts["LOWER"] / n
    p_push = counts["PUSH"] / n
    decisive_n = counts["HIGHER"] + counts["LOWER"]
    probability_by_side = {"HIGHER": p_higher, "LOWER": p_lower}
    offered = sorted(set(sides))
    best_side = max(offered, key=lambda side: (probability_by_side[side], side == "HIGHER"))
    conditional_n = decisive_n
    lower_bound = _wilson_lower(counts[best_side], conditional_n)
    conditional_probability = counts[best_side] / conditional_n if conditional_n else 0.0
    decision = best_side if conditional_probability > 0.5 and lower_bound > 0.5 else "PASS"
    observed_at = [observed for _value, _event_id, observed, _matchup in values]
    history_hash = content_hash({
        "outcomes": sorted(
            ((event_id, value, observed, matchup) for value, event_id, observed, matchup in values),
            key=lambda item: (item[0] or "", item[2], item[1], item[3] or ""),
        ),
        "cutoff": cutoff.isoformat(),
    })
    modifier_counts = claim.get("modifierCounts") if isinstance(claim.get("modifierCounts"), Mapping) else {}
    modifier_state = "GOBLIN_PRESENT" if any(
        str(k).upper() == "GOBLIN" and (_number(v) or 0) > 0 for k, v in modifier_counts.items()
    ) else (
        "STANDARD_OBSERVED" if any(
            str(k).upper() == "STANDARD" and (_number(v) or 0) > 0 for k, v in modifier_counts.items()
        ) else "UNKNOWN"
    )
    row.update({
        "terminalStatus": decision,
        "reason": "EMPIRICAL_DIRECTION_SUPPORTED" if decision in {"HIGHER", "LOWER"} else "DIRECTIONAL_EVIDENCE_NOT_DECISIVE",
        "leanDirection": best_side,
        "offeredSideProbability": probability_by_side[best_side],
        "conditionalDecisionProbability": conditional_probability,
        "conditionalWilsonLower95": lower_bound,
        "pHigher": p_higher,
        "pLower": p_lower,
        "pPush": p_push,
        "outcomeCounts": {key: counts[key] for key in ("HIGHER", "LOWER", "PUSH")},
        "empiricalPointMasses": dict(sorted(masses.items(), key=lambda item: float(item[0]))),
        "massSum": sum(masses.values()) / n,
        "historyObservationCount": n,
        "cutoffSafeHistory": [
            {"observedAt": observed, "eventId": event_id, "matchup": matchup, "value": value}
            for value, event_id, observed, matchup in values
        ],
        "decisiveObservationCount": decisive_n,
        "lowSampleFlag": n < 30,
        "historyLineageHash": history_hash,
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "historyObservedThrough": max(observed_at) if observed_at else None,
        "excludedAfterCutoffCount": excluded_future,
        "modifierState": modifier_state,
        "directionalScore": max(0.0, lower_bound - 0.5) if decision in {"HIGHER", "LOWER"} else 0.0,
    })
    return row


def build_captured_history_decisions(
    claims: Iterable[Mapping[str, Any]], *, forecast_cutoff: str | None,
    event_date: str | None = None, event_timezone: str | None = None,
) -> dict[str, Any]:
    """Model all supplied player-prop claims and emit terminal accounting."""
    algorithm = require_algorithm(ALGORITHM_ID)
    cutoff = _time(forecast_cutoff)
    rows = [
        _decision(claim, cutoff=cutoff, event_date=event_date, event_timezone=event_timezone)
        for claim in claims if isinstance(claim, Mapping)
    ]
    rows.sort(key=lambda row: (str(row.get("claimId") or ""), str(row.get("sourceHarSha256") or "")))
    counts = Counter(str(row.get("terminalStatus") or "UNMODELED") for row in rows)
    model_ranked = [row for row in rows if row.get("terminalStatus") in {"HIGHER", "LOWER", "PASS"}]
    model_ranked.sort(key=lambda row: (
        row.get("terminalStatus") in {"HIGHER", "LOWER"},
        float(row.get("directionalScore") or 0.0),
        abs(float(row.get("conditionalDecisionProbability") or 0.0) - 0.5),
        float(row.get("conditionalWilsonLower95") or 0.0),
        int(row.get("historyObservationCount") or 0),
        str(row.get("claimId") or ""),
    ), reverse=True)
    for index, row in enumerate(model_ranked, 1):
        row["modelRank"] = index
    recommendations = [row for row in model_ranked if row.get("terminalStatus") in {"HIGHER", "LOWER"}]
    recommendations.sort(key=lambda row: (
        float(row.get("directionalScore") or 0.0),
        float(row.get("conditionalDecisionProbability") or 0.0),
        int(row.get("historyObservationCount") or 0),
        str(row.get("claimId") or ""),
    ), reverse=True)
    for index, row in enumerate(recommendations, 1):
        row["directionalRank"] = index
    stages = {
        f"top{limit}": [row.get("claimId") for row in model_ranked[:limit]]
        for limit in _STAGES
    }
    recommendation_stages = {
        f"top{limit}": [row.get("claimId") for row in recommendations[:limit]]
        for limit in _STAGES
    }
    payload: dict[str, Any] = {
        "schema": "pillars_dcm.captured_history_directional_decisions.v1",
        "algorithmId": ALGORITHM_ID,
        "algorithmVersion": algorithm.introduced_version,
        "forecastCutoff": cutoff.isoformat().replace("+00:00", "Z") if cutoff else None,
        "runEventDate": event_date,
        "eventTimezone": event_timezone,
        "probabilityType": "EMPIRICAL_HISTORICAL_RATE_UNCALIBRATED",
        "reportedHitRatesUsedAsForecast": False,
        "baselineScope": "ALL_INPUT_PLAYER_PROP_CLAIMS",
        "inputClaimCount": len(rows),
        "terminalCounts": dict(sorted(counts.items())),
        "modelledClaimCount": len(model_ranked),
        "directionallyRankedCount": len(recommendations),
        "rankStages": stages,
        "recommendationRankStages": recommendation_stages,
        "rows": rows,
        "limits": [
            "Marginal empirical history is not calibrated and is not a production certification.",
            "Sparse history is retained with explicit sample counts and Wilson uncertainty.",
            "Only sides explicitly present in the supplied capture are evaluated.",
            "Discrete outcomes remain exact point masses; no continuous KDE smoothing is applied.",
        ],
    }
    payload["contentHash"] = content_hash(payload)
    return payload


__all__ = ["ALGORITHM_ID", "build_captured_history_decisions"]
