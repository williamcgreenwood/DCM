"""Frozen payout tables keyed by display hash. No nearest-match. No card-size inference."""

from __future__ import annotations

from dcm.contracts.hashes import content_hash


def register_minimum_guarantee_table(rows: dict[tuple[int, int], float], *, label: str) -> str:
    """rows maps (payout_tier_count, win_count) -> return amount (not multiplier)."""
    payload = {
        "label": label,
        "rows": [{"tier": k[0], "wins": k[1], "amount": v} for k, v in sorted(rows.items())],
    }
    table_hash = content_hash(payload)
    MG_TABLES[table_hash] = dict(rows)
    MG_LABELS[table_hash] = label
    return table_hash


MG_TABLES: dict[str, dict[tuple[int, int], float]] = {}
MG_LABELS: dict[str, str] = {}


# Captured example used by fixtures. Binding is the hash, not "6-pick flex".
DEMO_FLEX_ROWS = {
    (6, 6): 250.0,
    (6, 5): 20.0,
    (6, 4): 2.5,
    (6, 3): 0.0,
    (6, 2): 0.0,
    (6, 1): 0.0,
    (6, 0): 0.0,
    (5, 5): 100.0,
    (5, 4): 10.0,
    (5, 3): 0.0,
    (4, 4): 50.0,
    (4, 3): 5.0,
    (3, 3): 25.0,
    (2, 2): 3.0,
    (2, 1): 1.5,  # documented 2-pick special-case row lives in the frozen table
    (2, 0): 0.0,
    (1, 1): 0.0,
}
DEMO_MG_TABLE_HASH = register_minimum_guarantee_table(DEMO_FLEX_ROWS, label="PP_MG_FIXTURE_CAPTURED_V1")


def minimum_guarantee_return(table_hash: str, payout_tier_count: int, win_count: int) -> float | None:
    table = MG_TABLES.get(table_hash)
    if table is None:
        return None
    return table.get((payout_tier_count, win_count))
