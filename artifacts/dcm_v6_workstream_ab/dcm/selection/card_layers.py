"""Three-layer card contract: ranked Top 25, modeled strict card, production-certified.

The v5/V1 production root must not zero ranking or the modeled 0-6 PLAYABLE card.
Until V6_ROOT_OF_TRUST_MIGRATION is accepted, the production-certified layer stays
empty/false. Do not fill the strict card with LEAN. Goblins never selected.
"""
from __future__ import annotations

import json
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
})


def is_modeled_playable(p: dict[str, Any]) -> bool:
    """PLAYABLE-grade modeled row eligible for the strict card, ignoring production root."""
    row = p.get("row") if isinstance(p.get("row"), dict) else p
    if (row or {}).get("modifier") == "GOBLIN":
        return False
    if p.get("grade") != "PLAYABLE":
        return False
    state = p.get("state")
    if state not in {None, "MODELED"}:
        return False
    if p.get("blocker") in MODELED_CARD_EXCLUDED_BLOCKERS:
        return False
    return True


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
