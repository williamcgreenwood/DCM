"""Permanent subject exclusions that apply at every DCM selection boundary.

These are operator policy inputs, not predictive features.  A row is still
accounted for before the exclusion is applied, but an excluded subject cannot
enter research, modeling, ranking, a card, or the learning ledger.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


# The IDs are the stable subject IDs observed in the supplied CFB Outlier
# capture.  Names remain as a defensive fallback for another provider/export
# that omits the ID or formats punctuation differently.
PERMANENT_EXCLUDED_PLAYER_IDS: dict[str, str] = {
    "280607d805dbc22af844820dec5f5aa0091431dd": "PLAYER_BRENNAN_PARACHEK_PERMANENTLY_EXCLUDED",
    "cecb9ae4f4ec5111f807d65da0fcdb529ae00d24": "PLAYER_CJ_CARR_PERMANENTLY_EXCLUDED",
}

PERMANENT_EXCLUDED_PLAYER_NAMES: dict[str, str] = {
    "BRENNANPARACHEK": "PLAYER_BRENNAN_PARACHEK_PERMANENTLY_EXCLUDED",
    "CJCARR": "PLAYER_CJ_CARR_PERMANENTLY_EXCLUDED",
}


def normalize_subject_name(value: Any) -> str:
    """Normalize punctuation/spacing without fuzzy matching or name invention."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def permanent_subject_exclusion(row: Mapping[str, Any] | None) -> str | None:
    """Return a terminal exclusion code for an exact configured subject."""
    record = row if isinstance(row, Mapping) else {}
    player_id = str(record.get("playerId") or record.get("player_id") or "").strip().lower()
    if player_id in PERMANENT_EXCLUDED_PLAYER_IDS:
        return PERMANENT_EXCLUDED_PLAYER_IDS[player_id]
    name = normalize_subject_name(record.get("playerName") or record.get("player_name") or record.get("player"))
    return PERMANENT_EXCLUDED_PLAYER_NAMES.get(name)


def is_permanently_excluded_subject(row: Mapping[str, Any] | None) -> bool:
    return permanent_subject_exclusion(row) is not None

