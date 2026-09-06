"""Lineup / on-off effects with shrinkage. Tiny samples cannot drive extremes.

Always store: sample minutes, raw effect, shrunken effect, uncertainty,
maximum allowable adjustment. Missing lineup data is an explicit empty
result, not a silent zero-effect that pretends research happened.
"""
from __future__ import annotations

import math
from typing import Any

from dcm.contracts.hashes import content_hash


LINEUP_VERSION = "lineup-onoff-v1-20260831"
DEFAULT_PRIOR_MINUTES = 200.0
DEFAULT_MAX_ABS = 0.08


def _f(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def shrink_lineup_effect(
    raw_effect: float | None,
    sample_minutes: float | None,
    *,
    prior: float = 0.0,
    prior_minutes: float = DEFAULT_PRIOR_MINUTES,
    max_abs: float = DEFAULT_MAX_ABS,
) -> dict[str, Any]:
    """Hierarchical shrink of a lineup/on-off delta toward 0 (no effect)."""
    raw = _f(raw_effect)
    minutes = _f(sample_minutes) or 0.0
    if minutes < 0:
        minutes = 0.0
    if raw is None or minutes <= 0:
        return {
            "sampleMinutes": minutes,
            "rawEffect": raw,
            "shrunkenEffect": 0.0,
            "uncertainty": max_abs,
            "maxAllowableAdjustment": max_abs,
            "applied": False,
            "reason": "LINEUP_SAMPLE_EMPTY",
            "version": LINEUP_VERSION,
        }
    shrunken = (raw * minutes + prior * prior_minutes) / (minutes + prior_minutes)
    capped = max(-max_abs, min(max_abs, shrunken))
    uncertainty = max_abs * prior_minutes / (minutes + prior_minutes)
    return {
        "sampleMinutes": minutes,
        "rawEffect": raw,
        "shrunkenEffect": capped,
        "uncertainty": uncertainty,
        "maxAllowableAdjustment": max_abs,
        "applied": abs(capped) > 0.0,
        "reason": None,
        "version": LINEUP_VERSION,
        "priorMinutes": prior_minutes,
    }


def build_lineup_effects(
    rows: list[dict[str, Any]] | None,
    *,
    prior_minutes: float = DEFAULT_PRIOR_MINUTES,
    max_abs: float = DEFAULT_MAX_ABS,
) -> dict[str, Any]:
    """Normalize a list of {label, with, without, minutes, rawEffect} rows."""
    effects: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        raw = row.get("rawEffect")
        if raw is None and row.get("with") is not None and row.get("without") is not None:
            a, b = _f(row.get("with")), _f(row.get("without"))
            raw = None if a is None or b is None else a - b
        packed = shrink_lineup_effect(
            raw,
            row.get("minutes") or row.get("sampleMinutes"),
            prior_minutes=prior_minutes,
            max_abs=max_abs,
        )
        packed["label"] = row.get("label") or row.get("teammate") or row.get("context")
        packed["withTeammate"] = row.get("withTeammate") or row.get("with_player")
        packed["withoutTeammate"] = row.get("withoutTeammate") or row.get("without_player")
        effects.append(packed)
    body: dict[str, Any] = {
        "schema": "pillars_dcm.lineup_onoff.v1",
        "version": LINEUP_VERSION,
        "effectCount": len(effects),
        "usableCount": sum(1 for e in effects if e.get("applied")),
        "effects": effects,
        "evidenceUsed": any(e.get("applied") for e in effects),
        "priorUsedAsResearch": False,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
