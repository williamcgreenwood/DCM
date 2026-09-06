"""Three-layer card contract: ranked Top 25, modeled strict card, production-certified.

The v5/V1 production root must not zero ranking or the modeled 0-6 PLAYABLE card.
Until V6_ROOT_OF_TRUST_MIGRATION is accepted, the production-certified layer stays
empty/false. Do not fill the strict card with LEAN. Goblins never selected.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Explicit machine-state flag. Do not auto-promote; production-certified card
# remains [] until this is accepted by a future root-of-trust migration.
V6_ROOT_OF_TRUST_MIGRATION_ACCEPTED = False

NOT_PRODUCTION_ROOT_CERTIFIED = "NOT_PRODUCTION_ROOT_CERTIFIED"

EMPTY_NO_PLAYABLES = "EMPTY_NO_PLAYABLES"
EMPTY_RESEARCH_INCOMPLETE = "EMPTY_RESEARCH_INCOMPLETE"
EMPTY_ROOT_NOT_CERTIFIED = "EMPTY_ROOT_NOT_CERTIFIED"
EMPTY_PORTFOLIO_CONSTRAINT = "EMPTY_PORTFOLIO_CONSTRAINT"
EMPTY_ACCOUNT_ONLY = "EMPTY_ACCOUNT_ONLY"

EVENT_ALREADY_STARTED = "EVENT_ALREADY_STARTED"
PLAYER_STATUS_UNCERTAIN = "PLAYER_STATUS_UNCERTAIN"
PLAYER_NOT_ACTIVE = "PLAYER_NOT_ACTIVE"
PLAYER_STATUS_UNKNOWN = "PLAYER_STATUS_UNKNOWN"

# Row blockers that are not the production root. These still keep a row off
# the modeled strict card even when grade is PLAYABLE.
MODELED_CARD_EXCLUDED_BLOCKERS = frozenset({
    "RESEARCH_ONLY_NOT_SELECTABLE",
    "SHADOW_SUPPORTED_NOT_SELECTABLE",
    "LIVE_OR_IN_PROGRESS_NOT_PRODUCTION",
    "UNKNOWN_STATUS_FAIL_CLOSED",
    "GOBLIN_SELECTION_FORBIDDEN",
    "UNSUPPORTED_FAIL_CLOSED",
    "OFFERED_SIDE_UNKNOWN",
    "PRIMITIVE_CONSERVATION_FAILURE",
    "MODIFIER_UNKNOWN",
    "PLAYER_ID_UNRESOLVED_NO_NAME_INFERENCE",
    "HALF_LINE_AVOID_BASEBALL_HRRBI_0_5",
    PLAYER_STATUS_UNCERTAIN,
    PLAYER_NOT_ACTIVE,
    PLAYER_STATUS_UNKNOWN,
    EVENT_ALREADY_STARTED,
})

# Status/start hard gates. Always applied to modeled PLAYABLE, including synthetic.
# ParameterSnapshot PLAYER_STATUS_UNCERTAIN forces modeledPlayable=false.
STATUS_START_HARD_BLOCKERS = frozenset({
    PLAYER_STATUS_UNCERTAIN,
    PLAYER_NOT_ACTIVE,
    PLAYER_STATUS_UNKNOWN,
    EVENT_ALREADY_STARTED,
    "LIVE_OR_IN_PROGRESS_NOT_PRODUCTION",
    "UNKNOWN_STATUS_FAIL_CLOSED",
})

# HAR/player status OUT/INACTIVE/SUSPENDED cannot be modeled PLAYABLE.
HARD_EXCLUDE_PLAYER_STATUSES = frozenset({
    "OUT", "INACTIVE", "SUSPENDED", "DNP", "IR", "PUP",
})
# P2: availability mixture with no PLAYABLE promotion when uncertainty is
# excessive. P0: hard-exclude QUESTIONABLE/DOUBTFUL from PLAYABLE.
UNCERTAIN_PLAYER_STATUSES = frozenset({
    "QUESTIONABLE", "GTD", "GAME_TIME_DECISION", "DOUBTFUL", "LIMITED",
})
LIVE_EVENT_STATUSES = frozenset({"in_progress", "suspended"})


def _parse_utc(value: Any) -> datetime | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _snapshot_of(p: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(snapshot, dict):
        return snapshot
    for key in ("parameterSnapshot", "snapshot"):
        value = p.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _player_status(p: dict[str, Any], row: dict[str, Any], snap: dict[str, Any]) -> str:
    for value in (snap.get("status"), p.get("playerStatus"), row.get("playerStatus")):
        s = str(value or "").strip().upper()
        if s:
            return s
    return ""


def _tags(p: dict[str, Any], row: dict[str, Any]) -> list[Any]:
    tags = p.get("dependencyTags") or row.get("dependencyTags") or []
    return list(tags) if isinstance(tags, (list, tuple, set)) else []


def _role_tag_excludes_playable(tag: Any) -> bool:
    s = str(tag or "")
    if not s.upper().startswith("ROLE:"):
        return False
    role = s.split(":")[-1].strip().lower().replace(" ", "_")
    return role in {
        "questionable", "doubtful", "gtd", "game_time_decision", "limited",
        "out", "inactive", "suspended", "dnp",
    }


def event_started_before_cutoff(row: dict[str, Any] | None, cutoff: str | None) -> bool:
    """True when the event is live/suspended or start <= forecastDecisionCutoff."""
    row = row or {}
    status = str(row.get("status") or "").strip().lower()
    if row.get("isLive") or status in LIVE_EVENT_STATUSES:
        return True
    start = _parse_utc(
        row.get("eventStartTime") or row.get("startTime") or row.get("scheduledStart")
    )
    cut = _parse_utc(cutoff)
    if start is None or cut is None:
        return False
    return start <= cut


def started_event_blocker(row: dict[str, Any] | None, cutoff: str | None) -> str | None:
    row = row or {}
    if not event_started_before_cutoff(row, cutoff):
        return None
    status = str(row.get("status") or "").strip().lower()
    if row.get("isLive") or status in LIVE_EVENT_STATUSES:
        return "LIVE_OR_IN_PROGRESS_NOT_PRODUCTION"
    return EVENT_ALREADY_STARTED


def status_start_hard_blocker(
    p: dict[str, Any],
    *,
    cutoff: str | None = None,
    snapshot: dict[str, Any] | None = None,
) -> str | None:
    """Return the status/start blocker that keeps a row off modeled PLAYABLE."""
    row = p.get("row") if isinstance(p.get("row"), dict) else p
    row = row if isinstance(row, dict) else {}
    snap = _snapshot_of(p, snapshot)
    blocker = p.get("blocker") or snap.get("blocker")
    if blocker in MODELED_CARD_EXCLUDED_BLOCKERS:
        return str(blocker)
    status = _player_status(p, row, snap)
    if status in HARD_EXCLUDE_PLAYER_STATUSES:
        return PLAYER_NOT_ACTIVE
    if status in UNCERTAIN_PLAYER_STATUSES:
        return PLAYER_STATUS_UNCERTAIN
    if status == "UNKNOWN":
        return PLAYER_STATUS_UNKNOWN
    if any(_role_tag_excludes_playable(tag) for tag in _tags(p, row)):
        return PLAYER_STATUS_UNCERTAIN
    cut = cutoff or p.get("forecastCutoff") or p.get("forecastDecisionCutoff")
    return started_event_blocker(row, cut)


def is_modeled_playable(
    p: dict[str, Any],
    *,
    cutoff: str | None = None,
    snapshot: dict[str, Any] | None = None,
) -> bool:
    """PLAYABLE-grade modeled row eligible for the strict card, ignoring production root.

    P0 status/start hard gates (cannot be modeledPlayable / cannot be on strict_card):
    1. player status in {OUT, INACTIVE, SUSPENDED} — hard exclude
    2. ParameterSnapshot / row blocker PLAYER_STATUS_UNCERTAIN
    3. event already started / in_progress / suspended vs forecastDecisionCutoff
    4. QUESTIONABLE/DOUBTFUL — hard exclude from PLAYABLE (availability mixture is P2)
    """
    row = p.get("row") if isinstance(p.get("row"), dict) else p
    if (row or {}).get("modifier") == "GOBLIN":
        return False
    if p.get("grade") != "PLAYABLE":
        return False
    state = p.get("state")
    if state not in {None, "MODELED"}:
        return False
    if status_start_hard_blocker(p, cutoff=cutoff, snapshot=snapshot):
        return False
    return True


def apply_pre_freeze_status_start_gates(
    ranked: list[dict[str, Any]],
    *,
    cutoff: str | None,
) -> list[dict[str, Any]]:
    """Final status/start strip immediately before portfolio freeze.

    Late OUT / UNCERTAIN / started-event rows are forced off modeledPlayable
    and cannot enter the PLAYABLE card. Must run after ranking, before build_card.
    """
    qualified: list[dict[str, Any]] = []
    for p in ranked:
        snap = p.get("parameterSnapshot") if isinstance(p.get("parameterSnapshot"), dict) else None
        gate = status_start_hard_blocker(p, cutoff=cutoff, snapshot=snap)
        if gate:
            p["blocker"] = p.get("blocker") or gate
            p["modeledPlayable"] = False
            continue
        playable = is_modeled_playable(p, cutoff=cutoff, snapshot=snap)
        p["modeledPlayable"] = playable
        if playable:
            qualified.append(p)
    return qualified


def production_root_accepted(*, global_selection_gate: bool, production_selection_ready: bool) -> bool:
    return bool(
        V6_ROOT_OF_TRUST_MIGRATION_ACCEPTED
        and global_selection_gate
        and production_selection_ready
    )


def production_certified_rows(
    strict_card: list[dict[str, Any]],
    *,
    root_accepted: bool,
) -> list[dict[str, Any]]:
    if not root_accepted:
        return []
    return [row for row in strict_card if row.get("productionSelectable")]


def modeled_empty_card_reason(
    *,
    modeled_card_size: int,
    modeled_playable_count: int,
    evidence_coverage_complete: bool,
    research_complete: bool,
    account_only: bool = False,
) -> str:
    if modeled_card_size > 0:
        return ""
    if account_only:
        return EMPTY_ACCOUNT_ONLY
    if not research_complete or not evidence_coverage_complete:
        return EMPTY_RESEARCH_INCOMPLETE
    if modeled_playable_count > 0:
        return EMPTY_PORTFOLIO_CONSTRAINT
    return EMPTY_NO_PLAYABLES


def layer_run_state(
    *,
    root_accepted: bool,
    modeled_card_size: int,
    ranked_size: int,
    unsupported: int,
) -> str:
    if not root_accepted:
        if modeled_card_size > 0:
            return "RESEARCHED_MODELED_CARD"
        if ranked_size > 0:
            return "RESEARCHED_MODELED_TOP25"
        return "EMPTY_CARD_COMPLETE"
    if modeled_card_size == 0:
        return "EMPTY_CARD_COMPLETE"
    if unsupported:
        return "COMPLETE_WITH_UNSUPPORTED_ROWS"
    return "COMPLETE_FROZEN"


def compact_directional_row(p: dict[str, Any]) -> dict[str, Any]:
    row = p.get("row") if isinstance(p.get("row"), dict) else {}
    line = row.get("line") if "line" in row else p.get("line")
    return {
        "rank": p.get("rank"),
        "player": row.get("playerName") or p.get("player"),
        "team": row.get("team") or p.get("team"),
        "market": row.get("market") or p.get("market"),
        "line": line,
        "direction": p.get("selectedSide") or p.get("direction"),
        "grade": p.get("grade"),
        "evidenceSafeP": p.get("evidenceSafeP"),
        "projectionId": row.get("projectionId") or p.get("projectionId"),
    }


def build_directional_passes(
    ranked: list[dict[str, Any]],
    strict_card: list[dict[str, Any]],
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Strongest side for modeled non-PLAYABLE candidates not on the strict card."""
    card_ids = {
        str(p.get("projectionId") or (p.get("row") or {}).get("projectionId") or "")
        for p in strict_card
    }
    out: list[dict[str, Any]] = []
    for p in ranked:
        row = p.get("row") if isinstance(p.get("row"), dict) else p
        pid = str(row.get("projectionId") or p.get("projectionId") or "")
        if pid in card_ids:
            continue
        if p.get("grade") == "PLAYABLE":
            continue
        if (row or {}).get("modifier") == "GOBLIN":
            continue
        out.append(compact_directional_row(p))
        if len(out) >= limit:
            break
    return out


def write_card_layer_files(
    dest: Path,
    *,
    top25_ranked: list[dict[str, Any]],
    strict_card: list[dict[str, Any]],
    production_certified: list[dict[str, Any]],
    directional_passes: list[dict[str, Any]],
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "top25_ranked.json").write_text(json.dumps(top25_ranked, indent=2) + "\n", encoding="utf-8")
    (dest / "strict_card.json").write_text(json.dumps(strict_card, indent=2) + "\n", encoding="utf-8")
    (dest / "production_certified_card.json").write_text(
        json.dumps(production_certified, indent=2) + "\n", encoding="utf-8"
    )
    (dest / "directional_passes.json").write_text(
        json.dumps(directional_passes, indent=2) + "\n", encoding="utf-8"
    )
