"""MG lookup surface. Implementation lives in payouts.py (hash-keyed tables)."""

from dcm.platform.prizepicks.payouts import (
    DEMO_MG_TABLE_HASH,
    MG_LABELS,
    MG_TABLES,
    minimum_guarantee_return,
    register_minimum_guarantee_table,
)

__all__ = [
    "DEMO_MG_TABLE_HASH",
    "MG_LABELS",
    "MG_TABLES",
    "minimum_guarantee_return",
    "register_minimum_guarantee_table",
]
