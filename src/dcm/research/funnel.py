"""Deterministic board funnel: legal rows -> quota shortlist -> packets.

The HAR is a price-board catalogue, not a labelled outcome dataset.  This
module deliberately performs only structural accounting and attention
allocation.  It never assigns a probability, trains a model, or treats a
PrizePicks modifier as predictive evidence.

The output is an auditable funnel:

``raw rows -> gate receipt -> one primary line per player/game/stat ->
24-row quota shortlist + leftover``

Deep source research happens after this boundary, on game packets selected by
the shortlist.  The implementation is pure Python so it can run on a Mac
without adding a second store or a heavyweight analytics dependency.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from dcm.chat.state import read_json, write_json
from dcm.contracts.hashes import content_hash
from dcm.exclusions import permanent_subject_exclusion


FUNNEL_SCHEMA = "pillars_dcm.research_funnel.v1"
GATES_SCHEMA = "pillars_dcm.research_funnel_gates.v1"
LEFTOVER_SCHEMA = "pillars_dcm.research_funnel_leftover.v1"
SHORTLIST_SCHEMA = "pillars_dcm.research_funnel_shortlist.v1"
ALGORITHM_IDS = (
    "ALG-GROUP-001",  # composite-key grouping / same-line collapse
    "ALG-INDEX-001",  # Python hash-table identity maps
    "ALG-SORT-001",   # deterministic Timsort ordering
    "ALG-SCHED-003",  # deterministic value-density/constraint packing fallback
)

TWO_WAY_LEAGUES = frozenset({"NFL", "MLB"})
FULL_GAME_BOARDS = frozenset({"", "FULL_GAME", "FULL GAME"})
EXCLUDED_MODIFIERS = frozenset({"GOBLIN", "DEMON", "OTHER"})
VOLUME_MARKETS = frozenset(
    {
        "pass_yds", "rush_yds", "rec_yds", "receptions", "targets",
        "rec_targets", "pass_att", "passes_attempted", "pass_cmp", "rush_att",
        "h", "tb", "k",
    }
)
COMBO_MARKETS = frozenset(
    {
        "goal_assist",
        "hits_runs_rbi",
        "pa",
        "pr",
        "pra",
        "pass_rush_yds",
        "pass_rush_rec_tds",
        "rush_rec_yds",
        "rush_rec_td",
        "tackles_ast",
    }
)
EXCLUDED_MARKET_TOKENS = (
    "touchdown", "_td", "td_", "longest", "fantasy", "fantasy_score",
)
_SF_LAR_RE = re.compile(r"\b(?:SF|SFO|SAN\s+FRANCISCO)\b.*\b(?:LAR|LA\s+RAMS|LOS\s+ANGELES)\b|\b(?:LAR|LA\s+RAMS|LOS\s+ANGELES)\b.*\b(?:SF|SFO|SAN\s+FRANCISCO)\b", re.I)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _text(value).upper()


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _iso_timestamp(value: Any) -> float:
    raw = _text(value)
    if not raw:
        return float("inf")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return float("inf")


def _allowed_wager_value(row: Mapping[str, Any]) -> Any:
    if "allowedWagerTypes" in row and _nonempty(row.get("allowedWagerTypes")):
        return row.get("allowedWagerTypes")
    return row.get("allowed_wager_types")


def _side_flags(row: Mapping[str, Any]) -> tuple[bool, bool, bool]:
    """Return (higher, lower, metadata_present) without guessing sides."""
    offered_higher = bool(row.get("offeredHigher") or row.get("offered_higher"))
    offered_lower = bool(row.get("offeredLower") or row.get("offered_lower"))
    raw = _allowed_wager_value(row)
    present = _nonempty(raw)
    values: list[str]
    if isinstance(raw, Mapping):
        values = [_upper(k) for k, v in raw.items() if v]
    elif isinstance(raw, (list, tuple, set)):
        values = [_upper(v) for v in raw]
    else:
        values = [_upper(raw)] if present else []
    awt_higher = awt_lower = False
    recognized = False
    for value in values:
        if value in {"MORE", "OVER", "HIGHER", "OVER_ODDS"}:
            awt_higher = True
            recognized = True
        if value in {"LESS", "UNDER", "LOWER", "UNDER_ODDS"}:
            awt_lower = True
            recognized = True
        if value in {"BOTH", "OVER_UNDER", "UNDER_OR_OVER", "HIGHER_LOWER", "MORE_LESS"}:
            awt_higher = awt_lower = True
            recognized = True
    # A populated AWT field is authoritative.  If it is malformed, fail
    # closed instead of allowing a contradictory convenience boolean to make
    # a side appear.  Exploratory callers can still use offered flags when
    # AWT is genuinely absent.
    if present:
        return (awt_higher, awt_lower, present) if recognized else (False, False, present)
    return offered_higher, offered_lower, present


def _legal_side_class(row: Mapping[str, Any]) -> str:
    higher, lower, _present = _side_flags(row)
    league = _upper(row.get("league"))
    # The current product surface exposes two-sided Higher/Lower only for the
    # NFL and MLB slices.  Do not manufacture a Lower for CFB or another sport.
    lower_legal = lower and league in TWO_WAY_LEAGUES
    if higher and lower_legal:
        return "BOTH"
    if higher:
        return "OVER_ONLY"
    return "NO_SIDE"


def _market_text(row: Mapping[str, Any]) -> str:
    return _text(row.get("market") or row.get("statTypeRaw") or row.get("marketLabel")).lower()


def _market_is_combo(row: Mapping[str, Any]) -> bool:
    market = _market_text(row)
    label = _text(row.get("marketLabel")).lower()
    if bool(row.get("combo")) or _upper(row.get("eventType") or row.get("event_type")) == "COMBO":
        return True
    if market in COMBO_MARKETS or market.endswith("_combo"):
        return True
    # The normalized market key is not guaranteed to carry a ``combo`` flag;
    # labels such as ``Hits+Runs+RBIs`` are still multi-stat offers.
    return "+" in label or " + " in market or " and " in label


def _market_excluded(row: Mapping[str, Any]) -> bool:
    market = _market_text(row)
    label = _text(row.get("marketLabel") or row.get("statTypeRaw")).lower()
    probe = f"{market} {label}"
    return any(token in probe for token in EXCLUDED_MARKET_TOKENS) or bool(re.search(r"\b(?:td|touchdowns?)\b", label))


def _event_key(row: Mapping[str, Any]) -> str:
    return _text(row.get("eventId") or row.get("gameId") or row.get("event_id"))


def _player_key(row: Mapping[str, Any]) -> str:
    return _text(row.get("playerId") or row.get("subjectId") or row.get("player_id"))


def _stat_key(row: Mapping[str, Any]) -> str:
    return _text(row.get("market") or row.get("statTypeRaw") or row.get("marketLabel")).lower()


def _line_value(row: Mapping[str, Any]) -> float | None:
    if isinstance(row.get("line"), bool):
        return None
    try:
        return float(row.get("line"))
    except (TypeError, ValueError):
        return None


def _projection_key(row: Mapping[str, Any]) -> str:
    return _text(row.get("projectionId") or row.get("projection_id"))


def _basic_gate_reasons(
    row: Mapping[str, Any],
    *,
    require_allowed_wager_types: bool = True,
    require_pregame_status: bool = True,
    require_standard_modifier: bool = True,
) -> list[str]:
    reasons: list[str] = []
    status = _upper(row.get("status"))
    if bool(row.get("isLive") or row.get("is_live")) or status in {"IN_PROGRESS", "SUSPENDED", "LIVE"}:
        reasons.append("LIVE_OR_SUSPENDED")
    elif status in {"PRE_GAME", "PREGAME"}:
        pass
    elif not status and not require_pregame_status:
        pass
    elif not status:
        reasons.append("STATUS_UNKNOWN")
    else:
        reasons.append("STATUS_NOT_PREGAME")
    modifier = _upper(row.get("modifier"))
    if modifier in EXCLUDED_MODIFIERS:
        reasons.append(f"MODIFIER_{modifier}")
    elif modifier and modifier != "STANDARD":
        reasons.append("MODIFIER_UNKNOWN")
    elif require_standard_modifier and modifier != "STANDARD":
        reasons.append("MODIFIER_MISSING")
    if (excluded := permanent_subject_exclusion(row)):
        reasons.append(excluded)
    board = _upper(row.get("boardId") or row.get("board_id"))
    if board not in FULL_GAME_BOARDS:
        reasons.append("DURATION_BOARD")
    event_type = _upper(row.get("eventType") or row.get("event_type"))
    if _market_is_combo(row) or event_type == "COMBO":
        reasons.append("COMBO_PROP")
    if not _projection_key(row):
        reasons.append("PROJECTION_ID_UNRESOLVED")
    if not _upper(row.get("league")):
        reasons.append("LEAGUE_UNRESOLVED")
    if not _player_key(row):
        reasons.append("PLAYER_ID_UNRESOLVED")
    if not _event_key(row):
        reasons.append("EVENT_ID_UNRESOLVED")
    if _market_excluded(row):
        reasons.append("TD_LONGEST_OR_FANTASY")
    _higher, _lower, present = _side_flags(row)
    if require_allowed_wager_types and not present:
        reasons.append("MISSING_ALLOWED_WAGER_TYPES")
    if present and not (_higher or _lower):
        reasons.append("UNKNOWN_ALLOWED_WAGER_TYPES")
    if _legal_side_class(row) == "NO_SIDE":
        reasons.append("NO_LEGAL_SIDE")
    return reasons


def _same_line_groups(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str, str, str, float, str, str, bool, str, str], list[dict[str, Any]]]:
    """Group only economically compatible duplicates.

    Outlier captures can contain the same player/stat/line more than once for
    different modifiers or because one outcome has the configured target book
    while another does not.  Collapsing those rows together would let an
    unavailable offer hide an available one (or let a Goblin/other modifier
    contaminate Standard).  Provider, modifier, target-offer presence, period
    and MarketDefinition therefore remain part of the deterministic key.
    """
    groups: dict[tuple[str, str, str, str, float, str, str, bool, str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        line = _line_value(row)
        if line is None:
            continue
        key = (
            _upper(row.get("league")), _event_key(row), _player_key(row), _stat_key(row), line,
            _upper(row.get("modifier") or "OTHER"),
            _upper(row.get("targetBook") or row.get("sourceBook")),
            bool(row.get("targetBookOfferPresent")),
            _upper(row.get("period") or row.get("boardId")),
            _upper(row.get("marketDefinition") or row.get("marketDefinitionId")),
        )
        groups[key].append(row)
    return groups


def _merge_same_line(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted((dict(r) for r in rows), key=lambda r: _projection_key(r))
    merged = dict(ordered[0])
    projection_ids = sorted({_projection_key(r) for r in ordered if _projection_key(r)})
    if projection_ids:
        merged["projectionIds"] = projection_ids
        merged["projectionId"] = projection_ids[0]
    higher = any(_side_flags(r)[0] for r in ordered)
    lower = any(_side_flags(r)[1] for r in ordered)
    merged["offeredHigher"] = higher
    merged["offeredLower"] = lower
    # Preserve a meaningful non-empty AWT value.  The merged side flags are
    # authoritative for this sanitized row; no side is inferred from a line.
    awt_values = [_allowed_wager_value(r) for r in ordered if _nonempty(_allowed_wager_value(r))]
    if awt_values:
        flattened: list[str] = []
        for value in awt_values:
            if isinstance(value, Mapping):
                flattened.extend(_upper(k) for k, enabled in value.items() if enabled)
            elif isinstance(value, (list, tuple, set)):
                flattened.extend(_upper(item) for item in value)
            else:
                flattened.append(_upper(value))
        flattened = sorted({item for item in flattened if item})
        merged["allowedWagerTypes"] = flattened[0] if len(flattened) == 1 else flattened
    merged["sideClass"] = _legal_side_class(merged)
    return merged


def _primary_hint(row: Mapping[str, Any]) -> int:
    return int(bool(row.get("isPrimary") or row.get("is_primary") or row.get("primary") or row.get("primaryLine")))


def _choose_primary(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    values = [v for v in (_line_value(r) for r in rows) if v is not None]
    median = sorted(values)[len(values) // 2] if values else float("inf")
    ordered = sorted(
        (dict(r) for r in rows),
        key=lambda r: (
            -_primary_hint(r),
            -(1 if _legal_side_class(r) == "BOTH" else 0),
            abs((_line_value(r) if _line_value(r) is not None else float("inf")) - median),
            _line_value(r) if _line_value(r) is not None else float("inf"),
            _projection_key(r),
        ),
    )
    primary = ordered[0]
    duplicates: list[dict[str, Any]] = []
    for row in ordered[1:]:
        duplicates.append(
            {
                "projectionId": _projection_key(row),
                "playerId": _player_key(row),
                "eventId": _event_key(row),
                "league": _upper(row.get("league")),
                "market": _stat_key(row),
                "line": _line_value(row),
                "reason": "ALT_LINE_DUPLICATE",
            }
        )
    primary["primaryLine"] = True
    primary["altLineCount"] = len(duplicates)
    return primary, duplicates


def _player_game_stat_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (_upper(row.get("league")), _event_key(row), _player_key(row), _stat_key(row))


def build_legal_universe(
    rows: Sequence[Mapping[str, Any]],
    *,
    require_allowed_wager_types: bool = True,
    require_pregame_status: bool = True,
    require_standard_modifier: bool = True,
) -> dict[str, Any]:
    """Apply structural gates and collapse alt lines to one primary row."""
    line_groups = _same_line_groups(rows)
    merged_rows = [_merge_same_line(group) for _key, group in sorted(line_groups.items(), key=lambda kv: kv[0])]
    gate_exclusions: list[dict[str, Any]] = []
    gate_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    gated: list[dict[str, Any]] = []

    # Do not silently discard malformed rows that cannot be grouped.  Every
    # input row gets either a legal primary/alternate disposition or a gate
    # receipt, which keeps the board accounting auditable.
    for raw in rows:
        if _line_value(raw) is not None:
            continue
        record = {
            "projectionId": _projection_key(raw),
            "playerId": _player_key(raw),
            "eventId": _event_key(raw),
            "league": _upper(raw.get("league")),
            "market": _stat_key(raw),
            "line": None,
            "reason": "LINE_UNRESOLVED",
            "reasons": ["LINE_UNRESOLVED"],
        }
        gate_exclusions.append(record)
        gate_counts["LINE_UNRESOLVED"] += 1
        reason_counts["LINE_UNRESOLVED"] += 1
    for row in merged_rows:
        reasons = _basic_gate_reasons(
            row,
            require_allowed_wager_types=require_allowed_wager_types,
            require_pregame_status=require_pregame_status,
            require_standard_modifier=require_standard_modifier,
        )
        if reasons:
            primary = reasons[0]
            gate_counts[primary] += 1
            for reason in reasons:
                reason_counts[reason] += 1
            gate_exclusions.append(
                {
                    "projectionId": _projection_key(row),
                    "playerId": _player_key(row),
                    "eventId": _event_key(row),
                    "league": _upper(row.get("league")),
                    "market": _stat_key(row),
                    "line": _line_value(row),
                    "reason": primary,
                    "reasons": reasons,
                }
            )
            continue
        row["sideClass"] = _legal_side_class(row)
        gated.append(row)

    by_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in gated:
        by_key[_player_game_stat_key(row)].append(row)
    legal_rows: list[dict[str, Any]] = []
    alt_lines: list[dict[str, Any]] = []
    for key, group in sorted(by_key.items(), key=lambda kv: kv[0]):
        primary, duplicates = _choose_primary(group)
        legal_rows.append(primary)
        alt_lines.extend(duplicates)
    legal_rows.sort(key=lambda r: (_iso_timestamp(r.get("eventStartTime")), _upper(r.get("league")), _event_key(r), _player_key(r), _stat_key(r), _projection_key(r)))
    gate_exclusions.sort(
        key=lambda r: (
            _text(r.get("reason")),
            _upper(r.get("league")),
            _text(r.get("eventId")),
            _text(r.get("playerId")),
            _text(r.get("market")),
            str(r.get("line")),
            _text(r.get("projectionId")),
        )
    )
    side_counts = Counter(_text(r.get("sideClass")) for r in legal_rows)
    return {
        "schema": GATES_SCHEMA,
        "algorithmIds": list(ALGORITHM_IDS),
        "inputRows": len(rows),
        "sameLineRows": len(merged_rows),
        "sameLineCollapsedCount": max(0, len(rows) - sum(1 for raw in rows if _line_value(raw) is None) - len(merged_rows)),
        "legalRows": legal_rows,
        "gateExclusions": gate_exclusions,
        "altLineDuplicates": sorted(alt_lines, key=lambda r: (_upper(r.get("league")), _text(r.get("eventId")), _text(r.get("playerId")), _text(r.get("market")), str(r.get("line")), _text(r.get("projectionId")))),
        "gateCounts": dict(sorted(gate_counts.items())),
        "reasonCounts": dict(sorted(reason_counts.items())),
        "sideCounts": dict(sorted(side_counts.items())),
        "legalCount": len(legal_rows),
        "primaryKeyCount": len(by_key),
        "altLineCount": len(alt_lines),
        "requireAllowedWagerTypes": bool(require_allowed_wager_types),
        "requirePregameStatus": bool(require_pregame_status),
        "requireStandardModifier": bool(require_standard_modifier),
        "unresolvedLineCount": sum(1 for raw in rows if _line_value(raw) is None),
    }


def _is_sf_lar(row: Mapping[str, Any]) -> bool:
    label = " ".join(
        _text(row.get(key))
        for key in ("eventLabel", "event_label", "team", "opponent", "homeTeam", "awayTeam", "home", "away")
    )
    return bool(_SF_LAR_RE.search(label))


def _game_id(row: Mapping[str, Any]) -> str:
    return _event_key(row) or _text(row.get("eventLabel"))


def _stat_family(row: Mapping[str, Any]) -> str:
    market = _stat_key(row)
    if market in {"pass_yds", "pass_att", "pass_cmp", "pass_rush_yds"}:
        return "PASS"
    if market in {"rush_yds", "rush_att", "rush_rec_yds"}:
        return "RUSH"
    if market in {"rec_yds", "receptions", "targets", "rec_att"}:
        return "RECEIVING"
    if market in {"h", "tb", "k"}:
        return "BASEBALL"
    return "OTHER"


def _structural_key(row: Mapping[str, Any], *, must: bool = False) -> tuple[Any, ...]:
    side = _text(row.get("sideClass"))
    market = _stat_key(row)
    return (
        0 if must else 1,
        0 if _is_sf_lar(row) else 1,
        0 if side == "BOTH" else 1,
        0 if market in VOLUME_MARKETS else 1,
        _iso_timestamp(row.get("eventStartTime")),
        0 if _upper(row.get("league")) not in {"NFL"} else 1,
        _stat_family(row),
        _game_id(row),
        _player_key(row),
        _projection_key(row),
    )


def _row_summary(row: Mapping[str, Any], *, reason: str | None = None) -> dict[str, Any]:
    out = {
        "projectionId": _projection_key(row),
        "projectionIds": sorted({_text(v) for v in (row.get("projectionIds") or [_projection_key(row)]) if _text(v)}),
        "playerId": _player_key(row),
        "playerName": _text(row.get("playerName") or row.get("player_name")),
        "eventId": _event_key(row),
        "eventLabel": _text(row.get("eventLabel") or row.get("event_label")),
        "league": _upper(row.get("league")),
        "sportFamily": _text(row.get("sportFamily")),
        "team": _text(row.get("team") or row.get("teamId")),
        "opponent": _text(row.get("opponent")),
        "market": _stat_key(row),
        "marketLabel": _text(row.get("marketLabel")),
        "statFamily": _stat_family(row),
        "line": _line_value(row),
        "sideClass": _text(row.get("sideClass")),
        "offeredHigher": bool(row.get("offeredHigher")),
        "offeredLower": bool(row.get("offeredLower")) and _upper(row.get("league")) in TWO_WAY_LEAGUES,
        "eventStartTime": _text(row.get("eventStartTime")),
        "sfLAR": _is_sf_lar(row),
        "primaryLine": bool(row.get("primaryLine")),
    }
    if reason:
        out["reason"] = reason
    return out


def _quota_state(selected: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    games = {_game_id(r) for r in selected if _game_id(r)}
    leagues = {_upper(r.get("league")) for r in selected if _upper(r.get("league"))}
    players = {_player_key(r) for r in selected if _player_key(r)}
    two_way = sum(_text(r.get("sideClass")) == "BOTH" for r in selected)
    over_only = sum(_text(r.get("sideClass")) == "OVER_ONLY" for r in selected)
    sf_lar = sum(_is_sf_lar(r) for r in selected)
    nfl = sum(_upper(r.get("league")) == "NFL" for r in selected)
    return {
        "rows": len(selected),
        "distinctPlayers": len(players),
        "games": len(games),
        "leagues": len(leagues),
        "twoWay": two_way,
        "overOnly": over_only,
        "nfl": nfl,
        "sfLAR": sf_lar,
    }


def _quota_requirements(state: Mapping[str, Any], *, max_shortlist: int, min_games: int, min_leagues: int, min_two_way: int, max_over_only: int, max_nfl: int, sf_lar_target: int) -> list[dict[str, Any]]:
    checks = [
        ("max_rows", max_shortlist, int(state["rows"]), "<=", int(state["rows"]) <= max_shortlist),
        ("distinct_players", max_shortlist, int(state["distinctPlayers"]), "=", int(state["distinctPlayers"]) == int(state["rows"])),
        ("minimum_games", min_games, int(state["games"]), ">=", int(state["games"]) >= min_games),
        ("minimum_leagues", min_leagues, int(state["leagues"]), ">=", int(state["leagues"]) >= min_leagues),
        ("minimum_two_way", min_two_way, int(state["twoWay"]), ">=", int(state["twoWay"]) >= min_two_way),
        ("maximum_over_only", max_over_only, int(state["overOnly"]), "<=", int(state["overOnly"]) <= max_over_only),
        ("maximum_nfl", max_nfl, int(state["nfl"]), "<=", int(state["nfl"]) <= max_nfl),
        ("sf_lar_exact", sf_lar_target, int(state["sfLAR"]), "=", int(state["sfLAR"]) == sf_lar_target),
    ]
    return [
        {"name": name, "target": target, "actual": actual, "operator": operator, "satisfied": bool(ok)}
        for name, target, actual, operator, ok in checks
    ]


def quota_shortlist(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_shortlist: int = 24,
    max_players_per_game: int = 2,
    min_games: int = 8,
    min_leagues: int = 3,
    min_two_way: int = 12,
    max_over_only: int = 8,
    max_nfl: int = 14,
    sf_lar_target: int = 2,
    must_include: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Greedy, deterministic quota sampler with a visible leftover list.

    This is survey-style attention allocation, not a probability model.  Every
    legal row is either selected or retained in ``leftover`` with a reason.
    """
    pool = [dict(r) for r in rows]
    by_projection = {_projection_key(r): r for r in pool if _projection_key(r)}
    requested_must = {_text(v) for v in (must_include or []) if _text(v)}
    selected: list[dict[str, Any]] = []
    selected_players: set[str] = set()
    game_counts: Counter[str] = Counter()
    must_leftover: list[dict[str, Any]] = []

    def can_add(row: Mapping[str, Any]) -> tuple[bool, str]:
        pid, game, league = _player_key(row), _game_id(row), _upper(row.get("league"))
        side = _text(row.get("sideClass"))
        if not pid:
            return False, "PLAYER_ID_UNRESOLVED"
        if pid in selected_players:
            return False, "DUPLICATE_PLAYER"
        if len(selected) >= max_shortlist:
            return False, "SHORTLIST_CAP"
        if game_counts[game] >= max_players_per_game:
            return False, "GAME_PLAYER_CAP"
        if league == "NFL" and _quota_state(selected)["nfl"] >= max_nfl:
            return False, "NFL_CAP"
        if side == "OVER_ONLY" and _quota_state(selected)["overOnly"] >= max_over_only:
            return False, "OVER_ONLY_CAP"
        if _is_sf_lar(row) and _quota_state(selected)["sfLAR"] >= sf_lar_target:
            return False, "SF_LAR_CAP"
        return True, ""

    def add(row: Mapping[str, Any]) -> bool:
        ok, _reason = can_add(row)
        if not ok:
            return False
        copy = dict(row)
        copy["shortlistRole"] = "MUST_INCLUDE" if _projection_key(copy) in requested_must else "QUOTA"
        selected.append(copy)
        selected_players.add(_player_key(copy))
        game_counts[_game_id(copy)] += 1
        return True

    # Must-include rows are structural flags from a separate injury or
    # consensus screen.  They receive first refusal but still obey hard caps.
    must_rows = sorted((by_projection[pid] for pid in requested_must if pid in by_projection), key=lambda r: _structural_key(r, must=True))
    for row in must_rows:
        if not add(row):
            ok, reason = can_add(row)
            must_leftover.append({**_row_summary(row, reason=reason or "MUST_INCLUDE_CONFLICT"), "mustInclude": True, "feasible": ok})
    for pid in sorted(requested_must - set(by_projection)):
        must_leftover.append({"projectionId": pid, "reason": "MUST_INCLUDE_NOT_IN_LEGAL_UNIVERSE", "mustInclude": True, "feasible": False})

    def add_from(candidates: Iterable[Mapping[str, Any]], *, limit: int | None = None) -> int:
        added = 0
        for row in sorted(candidates, key=lambda r: _structural_key(r)):
            if limit is not None and added >= limit:
                break
            if add(row):
                added += 1
        return added

    # Reserve the exact SF@LAR quota before the broad fill.  If fewer than two
    # rows exist, the final receipt reports QUOTA_INFEASIBLE rather than padding.
    sf_rows = [r for r in pool if _is_sf_lar(r)]
    sf_added = add_from(sf_rows, limit=sf_lar_target)

    # Repair floors in an order that maximizes diversity and two-way coverage.
    while _quota_state(selected)["twoWay"] < min_two_way:
        before = len(selected)
        candidates = [r for r in pool if _text(r.get("sideClass")) == "BOTH" and _player_key(r) not in selected_players]
        candidates.sort(key=lambda r: (0 if _game_id(r) not in game_counts else 1, 0 if _upper(r.get("league")) not in {_upper(x.get("league")) for x in selected} else 1, _structural_key(r)))
        if not candidates or not add(candidates[0]):
            break
        if len(selected) == before:
            break
    while _quota_state(selected)["games"] < min_games:
        before = len(selected)
        candidates = [r for r in pool if _game_id(r) not in game_counts and _player_key(r) not in selected_players]
        candidates.sort(key=lambda r: (0 if _text(r.get("sideClass")) == "BOTH" else 1, _structural_key(r)))
        if not candidates or not add(candidates[0]):
            break
        if len(selected) == before:
            break
    while _quota_state(selected)["leagues"] < min_leagues:
        before = len(selected)
        present = {_upper(x.get("league")) for x in selected}
        candidates = [r for r in pool if _upper(r.get("league")) not in present and _player_key(r) not in selected_players]
        candidates.sort(key=lambda r: (0 if _text(r.get("sideClass")) == "BOTH" else 1, _structural_key(r)))
        if not candidates or not add(candidates[0]):
            break
        if len(selected) == before:
            break

    # Fill the remaining attention budget by the auditable structural key.
    add_from(pool)
    selected_ids = {_projection_key(r) for r in selected}
    leftovers: list[dict[str, Any]] = list(must_leftover)
    for row in sorted(pool, key=lambda r: _structural_key(r)):
        pid = _projection_key(row)
        if pid in selected_ids or pid in requested_must:
            continue
        _ok, reason = can_add(row)
        leftovers.append(_row_summary(row, reason=reason or "NOT_SELECTED"))
    state = _quota_state(selected)
    requirements = _quota_requirements(
        state,
        max_shortlist=max_shortlist,
        min_games=min_games,
        min_leagues=min_leagues,
        min_two_way=min_two_way,
        max_over_only=max_over_only,
        max_nfl=max_nfl,
        sf_lar_target=sf_lar_target,
    )
    infeasible: list[dict[str, Any]] = []
    available_sf = sum(_is_sf_lar(r) for r in pool)
    if available_sf < sf_lar_target:
        infeasible.append({"code": "QUOTA_INFEASIBLE", "name": "sf_lar_exact", "available": available_sf, "target": sf_lar_target})
    available_games = len({_game_id(r) for r in pool if _game_id(r)})
    if available_games < min_games:
        infeasible.append({"code": "QUOTA_INFEASIBLE", "name": "minimum_games", "available": available_games, "target": min_games})
    available_leagues = len({_upper(r.get("league")) for r in pool if _upper(r.get("league"))})
    if available_leagues < min_leagues:
        infeasible.append({"code": "QUOTA_INFEASIBLE", "name": "minimum_leagues", "available": available_leagues, "target": min_leagues})
    if sum(_text(r.get("sideClass")) == "BOTH" for r in pool) < min_two_way:
        infeasible.append({"code": "QUOTA_INFEASIBLE", "name": "minimum_two_way", "available": sum(_text(r.get("sideClass")) == "BOTH" for r in pool), "target": min_two_way})
    return {
        "schema": SHORTLIST_SCHEMA,
        "algorithmIds": list(ALGORITHM_IDS),
        "selectionMethod": "GREEDY_QUOTA_SAMPLER",
        "probabilityHead": False,
        "inputLegalRows": len(pool),
        "selected": [_row_summary(r) | {"shortlistRole": r.get("shortlistRole", "QUOTA")} for r in selected],
        "leftover": leftovers,
        "state": state,
        "requirements": requirements,
        "infeasible": infeasible,
        "available": {
            "sfLAR": available_sf,
            "games": available_games,
            "leagues": available_leagues,
            "twoWay": sum(_text(r.get("sideClass")) == "BOTH" for r in pool),
        },
        "caps": {
            "maxShortlist": max_shortlist,
            "maxPlayersPerGame": max_players_per_game,
            "minGames": min_games,
            "minLeagues": min_leagues,
            "minTwoWay": min_two_way,
            "maxOverOnly": max_over_only,
            "maxNFL": max_nfl,
            "sfLARTarget": sf_lar_target,
        },
        "sfLARRowsReserved": sf_added,
    }


def build_board_funnel(
    rows: Sequence[Mapping[str, Any]],
    *,
    must_include: Sequence[str] | None = None,
    require_allowed_wager_types: bool = True,
    require_pregame_status: bool = True,
    require_standard_modifier: bool = True,
    max_shortlist: int = 24,
    max_players_per_game: int = 2,
    min_games: int = 8,
    min_leagues: int = 3,
    min_two_way: int = 12,
    max_over_only: int = 8,
    max_nfl: int = 14,
    sf_lar_target: int = 2,
) -> dict[str, Any]:
    gates = build_legal_universe(
        rows,
        require_allowed_wager_types=require_allowed_wager_types,
        require_pregame_status=require_pregame_status,
        require_standard_modifier=require_standard_modifier,
    )
    shortlist = quota_shortlist(
        gates["legalRows"],
        max_shortlist=max_shortlist,
        max_players_per_game=max_players_per_game,
        min_games=min_games,
        min_leagues=min_leagues,
        min_two_way=min_two_way,
        max_over_only=max_over_only,
        max_nfl=max_nfl,
        sf_lar_target=sf_lar_target,
        must_include=must_include,
    )
    summary = {
        "schema": FUNNEL_SCHEMA,
        "algorithmIds": list(ALGORITHM_IDS),
        "algorithm": "deterministic_gate_primary_line_greedy_quota",
        "inputRows": len(rows),
        "sameLineRows": gates["sameLineRows"],
        "sameLineCollapsedCount": gates["sameLineCollapsedCount"],
        "legalRows": gates["legalCount"],
        "gateExcludedRows": len(gates["gateExclusions"]),
        "altLineDuplicates": gates["altLineCount"],
        "unresolvedLineRows": gates["unresolvedLineCount"],
        "shortlistRows": len(shortlist["selected"]),
        "leftoverRows": len(shortlist["leftover"]),
        "gateCounts": gates["gateCounts"],
        "sideCounts": gates["sideCounts"],
        "shortlistState": shortlist["state"],
        "quotaRequirements": shortlist["requirements"],
        "quotaInfeasible": shortlist["infeasible"],
        "mustIncludeRequested": len(must_include or []),
        "predictiveClaim": "NONE",
        "probabilityHead": False,
        "outcomesUsed": False,
        "trainingPerformed": False,
        "productionSelectionPermitted": False,
        "contentHash": None,
    }
    summary["contentHash"] = content_hash({k: v for k, v in summary.items() if k != "contentHash"})
    return {
        **summary,
        "gates": gates,
        "shortlist": shortlist,
    }


def write_funnel_artifacts(
    run_dir: Path,
    *,
    input_path: Path | None = None,
    must_include_path: Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run the funnel against a sanitized ``board.json`` and persist receipts."""
    run_dir = Path(run_dir)
    source = Path(input_path) if input_path else run_dir / "board.json"
    doc = read_json(source)
    rows = doc.get("rows") if isinstance(doc, Mapping) else doc
    if not isinstance(rows, list):
        raise ValueError("BOARD_ROWS_REQUIRED")
    must: list[str] = []
    if must_include_path is not None:
        raw = read_json(Path(must_include_path))
        if isinstance(raw, Mapping):
            raw = raw.get("projectionIds") or raw.get("mustInclude") or raw.get("rows") or []
        if isinstance(raw, list):
            must = [_text(v.get("projectionId") if isinstance(v, Mapping) else v) for v in raw if _text(v.get("projectionId") if isinstance(v, Mapping) else v)]
    result = build_board_funnel(rows, must_include=must, **kwargs)
    gates = dict(result["gates"])
    shortlist = dict(result["shortlist"])
    # Keep full board rows local; Drive sync should copy only these sanitized
    # receipts, never the HAR or response bodies.
    write_json(run_dir / "research_funnel.json", result)
    write_json(run_dir / "gates.json", {
        "schema": GATES_SCHEMA,
        "algorithmIds": list(ALGORITHM_IDS),
        "contentHash": content_hash(gates),
        "inputRows": gates["inputRows"],
        "sameLineRows": gates["sameLineRows"],
        "sameLineCollapsedCount": gates["sameLineCollapsedCount"],
        "legalCount": gates["legalCount"],
        "gateCounts": gates["gateCounts"],
        "reasonCounts": gates["reasonCounts"],
        "sideCounts": gates["sideCounts"],
        "gateExclusions": gates["gateExclusions"],
        "altLineDuplicates": gates["altLineDuplicates"],
        "unresolvedLineCount": gates["unresolvedLineCount"],
    })
    write_json(run_dir / "leftover.json", {
        "schema": LEFTOVER_SCHEMA,
        "algorithmIds": list(ALGORITHM_IDS),
        "contentHash": content_hash(shortlist["leftover"]),
        "count": len(shortlist["leftover"]),
        "rows": shortlist["leftover"],
        "gateExcludedCount": len(gates["gateExclusions"]),
        "predictiveClaim": "NONE",
    })
    write_json(run_dir / "shortlist.json", {
        "schema": SHORTLIST_SCHEMA,
        "algorithmIds": list(ALGORITHM_IDS),
        "contentHash": content_hash(shortlist),
        "rows": shortlist["selected"],
        "state": shortlist["state"],
        "requirements": shortlist["requirements"],
        "infeasible": shortlist["infeasible"],
        "predictiveClaim": "NONE",
    })
    return {
        **{k: v for k, v in result.items() if k not in {"gates", "shortlist"}},
        "runDir": str(run_dir),
        "artifacts": ["research_funnel.json", "gates.json", "leftover.json", "shortlist.json"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a deterministic legal-board funnel and quota shortlist.")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--input", type=Path, default=None, help="Sanitized board JSON; defaults to <run>/board.json")
    parser.add_argument("--must-include", type=Path, default=None, help="JSON list of projection IDs from an optional external screen")
    parser.add_argument("--max-shortlist", type=int, default=24)
    parser.add_argument("--min-games", type=int, default=8)
    parser.add_argument("--min-leagues", type=int, default=3)
    parser.add_argument("--min-two-way", type=int, default=12)
    parser.add_argument("--max-over-only", type=int, default=8)
    parser.add_argument("--max-nfl", type=int, default=14)
    parser.add_argument("--sf-lar-target", type=int, default=2)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = write_funnel_artifacts(
        args.run,
        input_path=args.input,
        must_include_path=args.must_include,
        max_shortlist=max(1, int(args.max_shortlist)),
        min_games=max(0, int(args.min_games)),
        min_leagues=max(0, int(args.min_leagues)),
        min_two_way=max(0, int(args.min_two_way)),
        max_over_only=max(0, int(args.max_over_only)),
        max_nfl=max(0, int(args.max_nfl)),
        sf_lar_target=max(0, int(args.sf_lar_target)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FUNNEL_SCHEMA",
    "GATES_SCHEMA",
    "LEFTOVER_SCHEMA",
    "SHORTLIST_SCHEMA",
    "ALGORITHM_IDS",
    "build_board_funnel",
    "build_legal_universe",
    "quota_shortlist",
    "write_funnel_artifacts",
]
