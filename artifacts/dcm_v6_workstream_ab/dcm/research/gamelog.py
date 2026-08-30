"""Canonical basketball game-log normalization.

Basketball-Reference and mixed host archives emit MP/TRB/FG3A-style keys.
Parameter snapshots and coverage must see canonical `minutes`/`fga`/`tpa`/`fta`
or fail closed — never silently treat generic priors as player research.
"""
from __future__ import annotations

import math
from typing import Any


CANONICAL_BASKETBALL_FIELDS: tuple[str, ...] = (
    "minutes",
    "fga",
    "tpa",
    "fta",
    "fgm",
    "tpm",
    "ftm",
    "oreb",
    "dreb",
    "reb",
    "ast",
    "stl",
    "blk",
    "tov",
    "pf",
    "pts",
    "plus",
    "gs",
    "mp_raw",
)

# Lowercase alias -> canonical field. Canonical names are also aliases of themselves.
_ALIASES: dict[str, str] = {
    "minutes": "minutes",
    "min": "minutes",
    "mp": "minutes",
    "fga": "fga",
    "fg_att": "fga",
    "tpa": "tpa",
    "fg3a": "tpa",
    "3pa": "tpa",
    "three_pa": "tpa",
    "tp_att": "tpa",
    "fta": "fta",
    "ft_att": "fta",
    "fgm": "fgm",
    "fg": "fgm",
    "tpm": "tpm",
    "fg3": "tpm",
    "3p": "tpm",
    "three_pm": "tpm",
    "ftm": "ftm",
    "ft": "ftm",
    "reb": "reb",
    "trb": "reb",
    "oreb": "oreb",
    "orb": "oreb",
    "dreb": "dreb",
    "drb": "dreb",
    "ast": "ast",
    "stl": "stl",
    "steal": "stl",
    "steals": "stl",
    "blk": "blk",
    "block": "blk",
    "blocks": "blk",
    "tov": "tov",
    "to": "tov",
    "turnover": "tov",
    "turnovers": "tov",
    "pf": "pf",
    "fouls": "pf",
    "personal_fouls": "pf",
    "pts": "pts",
    "points": "pts",
    "plus": "plus",
    "plus_minus": "plus",
    "+/-": "plus",
    "pm": "plus",
    "gs": "gs",
    "started": "gs",
    "starter": "gs",
}

_TRUTHY = {"1", "true", "yes", "y", "starter", "started", "start"}
_FALSY = {"0", "false", "no", "n", "bench", "reserve", "dnp"}

# Market token -> missing-code and the predicate used on a normalized log.
_MARKET_CODES = {
    "pts": "MARKET_STAT_PTS",
    "points": "MARKET_STAT_PTS",
    "reb": "MARKET_STAT_REB",
    "rebounds": "MARKET_STAT_REB",
    "rebound": "MARKET_STAT_REB",
    "ast": "MARKET_STAT_AST",
    "assists": "MARKET_STAT_AST",
    "assist": "MARKET_STAT_AST",
    "pra": "MARKET_STAT_PRA",
    "3pm": "MARKET_STAT_TPM",
    "threes": "MARKET_STAT_TPM",
    "three": "MARKET_STAT_TPM",
    "3p": "MARKET_STAT_TPM",
    "tpm": "MARKET_STAT_TPM",
    "stl": "MARKET_STAT_STL",
    "steals": "MARKET_STAT_STL",
    "steal": "MARKET_STAT_STL",
    "blk": "MARKET_STAT_BLK",
    "blocks": "MARKET_STAT_BLK",
    "block": "MARKET_STAT_BLK",
    "tov": "MARKET_STAT_TOV",
    "to": "MARKET_STAT_TOV",
    "turnovers": "MARKET_STAT_TOV",
    "turnover": "MARKET_STAT_TOV",
    "pr": "MARKET_STAT_PR",
    "pa": "MARKET_STAT_PA",
    "ra": "MARKET_STAT_RA",
}


def _present(row: dict[str, Any], *keys: str) -> bool:
    return any(row.get(k) is not None for k in keys)


def _market_stat_ok(row: dict[str, Any], market: str) -> bool:
    m = str(market or "").strip().lower()
    if m in {"pts", "points"}:
        return _present(row, "pts", "fga")
    if m in {"reb", "rebounds", "rebound"}:
        return _present(row, "reb")
    if m in {"ast", "assists", "assist"}:
        return _present(row, "ast")
    if m == "pra":
        return _present(row, "pts", "fga") and _present(row, "reb") and _present(row, "ast")
    if m in {"3pm", "threes", "three", "3p", "tpm"}:
        return _present(row, "tpm", "tpa")
    if m in {"stl", "steals", "steal"}:
        return _present(row, "stl")
    if m in {"blk", "blocks", "block"}:
        return _present(row, "blk")
    if m in {"tov", "to", "turnovers", "turnover"}:
        return _present(row, "tov")
    if m == "pr":
        return _present(row, "pts", "fga") and _present(row, "reb")
    if m == "pa":
        return _present(row, "pts", "fga") and _present(row, "ast")
    if m == "ra":
        return _present(row, "reb") and _present(row, "ast")
    return True


def parse_numeric(value: Any) -> float | None:
    """Parse a counting stat or minutes value. MM:SS -> minutes as a float.

    Unparseable strings (including malformed clock values) return None rather
    than 0, so callers can reject instead of silently treating them as zero.
    """
    if value is None or value is False:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    text = str(value).strip()
    if not text:
        return None
    if ":" in text:
        parts = text.split(":")
        try:
            nums = [float(p) for p in parts]
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(n) for n in nums):
            return None
        if len(nums) == 2:
            return nums[0] + nums[1] / 60.0
        if len(nums) == 3:
            return nums[0] * 60.0 + nums[1] + nums[2] / 60.0
        return None
    try:
        x = float(text)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def parse_gs(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            return None
        return 1 if float(value) else 0
    text = str(value).strip().lower()
    if text in _TRUTHY:
        return 1
    if text in _FALSY:
        return 0
    return None


def _index_row(row: dict[str, Any]) -> dict[str, list[tuple[str, Any]]]:
    """Map lowercase key -> list of (original_key, value) in insertion order."""
    indexed: dict[str, list[tuple[str, Any]]] = {}
    for key, value in row.items():
        indexed.setdefault(str(key).strip().lower(), []).append((str(key), value))
    return indexed


def normalize_basketball_log(row: dict, *, league: str | None = None) -> dict | None:
    """Return a canonical basketball log, or None if minutes cannot be resolved.

    Does not invent FGA/TPA/FTA from PTS. Unknown keys land under `raw`.
    Canonical keys win over aliases when both are present.
    """
    if not isinstance(row, dict):
        return None
    indexed = _index_row(row)
    out: dict[str, Any] = {}
    used_lower: set[str] = set()

    def _take(canonical: str) -> Any:
        # Canonical key first (case-insensitive), then any alias that maps here.
        if canonical.lower() in indexed:
            used_lower.add(canonical.lower())
            return indexed[canonical.lower()][0][1]
        for alias, target in _ALIASES.items():
            if target == canonical and alias in indexed:
                used_lower.add(alias)
                return indexed[alias][0][1]
        return None

    minutes_raw = _take("minutes")
    minutes = parse_numeric(minutes_raw)
    if minutes is None:
        return None
    out["minutes"] = minutes
    out["mp_raw"] = minutes_raw

    for field in CANONICAL_BASKETBALL_FIELDS:
        if field in {"minutes", "mp_raw", "gs"}:
            continue
        raw_val = _take(field)
        if raw_val is None:
            continue
        parsed = parse_numeric(raw_val)
        if parsed is not None:
            out[field] = parsed

    gs_raw = _take("gs")
    if gs_raw is not None:
        gs = parse_gs(gs_raw)
        if gs is not None:
            out["gs"] = gs

    raw: dict[str, Any] = {}
    for lower, pairs in indexed.items():
        if lower in used_lower:
            continue
        for orig_key, value in pairs:
            raw[orig_key] = value
    if raw:
        out["raw"] = raw
    _ = league  # reserved for league-specific aliases
    return out


def normalize_basketball_logs(logs, *, league: str | None = None) -> dict[str, Any]:
    """Split a log list into valid canonical rows and rejected originals."""
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reason_counts: dict[str, int] = {}
    rows = logs if isinstance(logs, list) else []
    for item in rows:
        if not isinstance(item, dict):
            reason_counts["NOT_A_DICT"] = reason_counts.get("NOT_A_DICT", 0) + 1
            rejected.append({"row": item, "reason": "NOT_A_DICT"})
            continue
        normalized = normalize_basketball_log(item, league=league)
        if normalized is None:
            reason_counts["GAMELOG_MINUTES"] = reason_counts.get("GAMELOG_MINUTES", 0) + 1
            rejected.append({"row": item, "reason": "GAMELOG_MINUTES"})
            continue
        valid.append(normalized)
    return {"logs": valid, "rejected": rejected, "reasonCounts": reason_counts}


def assert_compatible_basketball_logs(logs, *, market: str) -> dict[str, Any]:
    """Coverage helper: minutes-valid logs plus market counting-stat presence."""
    dicts = [x for x in (logs or []) if isinstance(x, dict)] if isinstance(logs, list) else []
    norm = normalize_basketball_logs(dicts)
    valid = norm["logs"]
    missing: list[str] = []
    if len(valid) < 3:
        missing.append("GAMELOG_MINUTES")
        missing.append("ROLE_COMPARABLE_GAME_LOGS_MIN_3")
    market_key = str(market or "").strip().lower()
    if market_key and market_key in _MARKET_CODES:
        with_stat = [row for row in valid if _market_stat_ok(row, market_key)]
        if len(with_stat) < 3:
            missing.append(_MARKET_CODES[market_key])
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for code in missing:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return {
        "complete": not ordered,
        "missing": ordered,
        "valid_n": len(valid),
    }
