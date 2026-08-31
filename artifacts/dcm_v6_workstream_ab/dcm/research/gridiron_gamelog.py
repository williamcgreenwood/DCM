"""Canonical gridiron (NFL/CFB) game-log normalization.

Pro-Football-Reference / Sports-Reference CFB archives emit pass_att/rec/off_pct
style keys. Parameter snapshots must see canonical pass_att/pass_yds/targets/
receptions/rec_yds/snaps (when present) or fail closed — never invent routes
from targets or pass_yds from completions.
"""
from __future__ import annotations

import math
from typing import Any

from dcm.research.gamelog import parse_gs, parse_numeric

CANONICAL_GRIDIRON_FIELDS: tuple[str, ...] = (
    "date",
    "gs",
    "snaps",
    "snap_pct",
    "routes",
    "targets",
    "receptions",
    "rec_yds",
    "rec_td",
    "pass_att",
    "pass_cmp",
    "pass_yds",
    "pass_td",
    "interceptions",
    "rush_att",
    "rush_yds",
    "rush_td",
    "sacks_taken",
    "scramble_att",
    "dropbacks",
    "designed_rush_att",
    "qb_id",
)

# Lowercase alias -> canonical field. Canonical names win when both present.
_ALIASES: dict[str, str] = {
    "snaps": "snaps",
    "off_snaps": "snaps",
    "offsnap": "snaps",
    "offensive_snaps": "snaps",
    "snap_count": "snaps",
    "snap_pct": "snap_pct",
    "off_pct": "snap_pct",
    "offpct": "snap_pct",
    "snap_percentage": "snap_pct",
    "routes": "routes",
    "route": "routes",
    "routes_run": "routes",
    "targets": "targets",
    "tgt": "targets",
    "target": "targets",
    "receptions": "receptions",
    "rec": "receptions",
    "rec_yds": "rec_yds",
    "receiving_yards": "rec_yds",
    "recyds": "rec_yds",
    "rec_td": "rec_td",
    "receiving_td": "rec_td",
    "pass_att": "pass_att",
    "pass_attempts": "pass_att",
    "passing_att": "pass_att",
    "att": "pass_att",
    "pass_cmp": "pass_cmp",
    "cmp": "pass_cmp",
    "completions": "pass_cmp",
    "pass_yds": "pass_yds",
    "passing_yards": "pass_yds",
    "passyds": "pass_yds",
    "pass_td": "pass_td",
    "passing_td": "pass_td",
    "interceptions": "interceptions",
    "pass_int": "interceptions",
    "int": "interceptions",
    "ints": "interceptions",
    "rush_att": "rush_att",
    "rush_attempts": "rush_att",
    "carries": "rush_att",
    "rush_yds": "rush_yds",
    "rushing_yards": "rush_yds",
    "rushyds": "rush_yds",
    "rush_td": "rush_td",
    "sacks_taken": "sacks_taken",
    "sk": "sacks_taken",
    "sacks": "sacks_taken",
    "scramble_att": "scramble_att",
    "scrambles": "scramble_att",
    "dropbacks": "dropbacks",
    "designed_rush_att": "designed_rush_att",
    "gs": "gs",
    "started": "gs",
    "starter": "gs",
    "qb_id": "qb_id",
    "qb": "qb_id",
    "quarterback_id": "qb_id",
}

_OPPORTUNITY_KEYS = (
    "snaps", "snap_pct", "pass_att", "rush_att", "routes", "targets",
    "receptions", "rec_yds", "pass_yds",
)

_MARKET_CODES = {
    "pass_yds": "MARKET_STAT_PASS_YDS",
    "passing_yards": "MARKET_STAT_PASS_YDS",
    "pass_yards": "MARKET_STAT_PASS_YDS",
    "rush_yds": "MARKET_STAT_RUSH_YDS",
    "rushing_yards": "MARKET_STAT_RUSH_YDS",
    "rec_yds": "MARKET_STAT_REC_YDS",
    "receiving_yards": "MARKET_STAT_REC_YDS",
    "receptions": "MARKET_STAT_RECEPTIONS",
    "pass_rush_yds": "MARKET_STAT_PASS_RUSH_YDS",
    "rush_rec_yds": "MARKET_STAT_RUSH_REC_YDS",
}


def parse_pct(value: Any) -> float | None:
    """Parse 71 or '71%' into 0.71. Already-fractional values in [0, 1] stay."""
    if isinstance(value, str) and value.strip().endswith("%"):
        parsed = parse_numeric(value.strip()[:-1])
        return None if parsed is None else parsed / 100.0
    parsed = parse_numeric(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        return parsed / 100.0
    return parsed


def _index_row(row: dict[str, Any]) -> dict[str, list[tuple[str, Any]]]:
    indexed: dict[str, list[tuple[str, Any]]] = {}
    for key, value in row.items():
        indexed.setdefault(str(key).strip().lower(), []).append((str(key), value))
    return indexed


def _present(row: dict[str, Any], *keys: str) -> bool:
    return any(row.get(k) is not None for k in keys)


def _market_stat_ok(row: dict[str, Any], market: str) -> bool:
    m = str(market or "").strip().lower()
    if m in {"pass_yds", "passing_yards", "pass_yards"}:
        return _present(row, "pass_yds", "pass_att")
    if m in {"rush_yds", "rushing_yards"}:
        return _present(row, "rush_yds", "rush_att")
    if m in {"rec_yds", "receiving_yards"}:
        return _present(row, "rec_yds", "receptions", "targets")
    if m == "receptions":
        return _present(row, "receptions", "targets")
    if m == "pass_rush_yds":
        return _present(row, "pass_yds", "pass_att") and _present(row, "rush_yds", "rush_att")
    if m == "rush_rec_yds":
        return _present(row, "rush_yds", "rush_att") and _present(row, "rec_yds", "receptions", "targets")
    return True


def normalize_gridiron_log(row: dict, *, league: str | None = None) -> dict | None:
    """Return a canonical gridiron log, or None if opportunity cannot be resolved.

    Does not invent routes from targets or yards from attempts. Unknown keys
    land under `raw`. Canonical keys win over aliases when both are present.
    """
    if not isinstance(row, dict):
        return None
    indexed = _index_row(row)
    out: dict[str, Any] = {}
    used_lower: set[str] = set()

    def _take(canonical: str) -> Any:
        if canonical.lower() in indexed:
            used_lower.add(canonical.lower())
            return indexed[canonical.lower()][0][1]
        for alias, target in _ALIASES.items():
            if target == canonical and alias in indexed:
                used_lower.add(alias)
                return indexed[alias][0][1]
        return None

    date_raw = None
    for key in ("date", "game_date", "date_game", "gamedate"):
        if key in indexed:
            date_raw = indexed[key][0][1]
            used_lower.add(key)
            break
    if date_raw is not None:
        out["date"] = str(date_raw)

    gs_raw = _take("gs")
    if gs_raw is not None:
        gs = parse_gs(gs_raw)
        if gs is not None:
            out["gs"] = gs

    numeric_fields = (
        "snaps", "routes", "targets", "receptions", "rec_yds", "rec_td",
        "pass_att", "pass_cmp", "pass_yds", "pass_td", "interceptions",
        "rush_att", "rush_yds", "rush_td", "sacks_taken", "scramble_att",
        "dropbacks", "designed_rush_att",
    )
    for field in numeric_fields:
        raw_val = _take(field)
        if raw_val is None:
            continue
        parsed = parse_numeric(raw_val)
        if parsed is not None:
            out[field] = parsed

    snap_pct_raw = _take("snap_pct")
    if snap_pct_raw is not None:
        pct = parse_pct(snap_pct_raw)
        if pct is not None:
            out["snap_pct"] = pct

    qb_raw = _take("qb_id")
    if qb_raw is not None and str(qb_raw).strip():
        out["qb_id"] = str(qb_raw).strip()

    if not any(out.get(k) is not None for k in _OPPORTUNITY_KEYS):
        return None

    # Identities when components are present — never invent missing parts.
    if "dropbacks" not in out:
        if all(k in out for k in ("pass_att", "sacks_taken", "scramble_att")):
            out["dropbacks"] = out["pass_att"] + out["sacks_taken"] + out["scramble_att"]
    if "designed_rush_att" not in out and "rush_att" in out:
        scramble = out.get("scramble_att")
        if scramble is not None:
            out["designed_rush_att"] = max(0.0, out["rush_att"] - scramble)

    raw: dict[str, Any] = {}
    for lower, pairs in indexed.items():
        if lower in used_lower:
            continue
        for orig_key, value in pairs:
            raw[orig_key] = value
    if raw:
        out["raw"] = raw
    if league:
        out["league"] = str(league).upper()
    return out


def normalize_gridiron_logs(logs, *, league: str | None = None) -> dict[str, Any]:
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
        normalized = normalize_gridiron_log(item, league=league)
        if normalized is None:
            reason_counts["GAMELOG_OPPORTUNITY"] = reason_counts.get("GAMELOG_OPPORTUNITY", 0) + 1
            rejected.append({"row": item, "reason": "GAMELOG_OPPORTUNITY"})
            continue
        valid.append(normalized)
    return {"logs": valid, "rejected": rejected, "reasonCounts": reason_counts}


def assert_compatible_gridiron_logs(logs, *, market: str) -> dict[str, Any]:
    """Coverage helper: opportunity-valid logs plus market counting-stat presence."""
    dicts = [x for x in (logs or []) if isinstance(x, dict)] if isinstance(logs, list) else []
    norm = normalize_gridiron_logs(dicts)
    valid = norm["logs"]
    missing: list[str] = []
    if len(valid) < 3:
        missing.append("GAMELOG_OPPORTUNITY")
        missing.append("ROLE_COMPARABLE_GAME_LOGS_MIN_3")
    market_key = str(market or "").strip().lower()
    if market_key and market_key in _MARKET_CODES:
        with_stat = [row for row in valid if _market_stat_ok(row, market_key)]
        if len(with_stat) < 3:
            missing.append(_MARKET_CODES[market_key])
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


def looks_like_gridiron_log(row: dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    keys = {str(k).strip().lower() for k in row}
    football = {
        "pass_att", "pass_yds", "rush_att", "rush_yds", "targets", "receptions",
        "rec", "rec_yds", "off_pct", "snaps", "off_snaps", "routes",
    }
    return bool(keys & football)
