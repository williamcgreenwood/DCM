"""CFB reference implementation. Not a claim that mixed-sport R1 is complete."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ACTIVE_CFB_MARKETS",
    "account_cfb_board",
    "canonicalize_cfb_market",
    "prepare_cfb_research_os",
    "emit_cfb_forecast_artifacts",
    "cfb_top100_row",
    "cfb_top25_final",
    "cfb_playables_final",
]


def __getattr__(name: str) -> Any:
    if name == "ACTIVE_CFB_MARKETS" or name == "canonicalize_cfb_market":
        from dcm.cfb import markets as _markets
        return getattr(_markets, name)
    if name == "account_cfb_board":
        from dcm.cfb.accounting import account_cfb_board
        return account_cfb_board
    if name in {"prepare_cfb_research_os", "emit_cfb_forecast_artifacts"}:
        from dcm.cfb import launch as _launch
        return getattr(_launch, name)
    if name in {"cfb_top100_row", "cfb_top25_final", "cfb_playables_final"}:
        from dcm.cfb import reports as _reports
        return getattr(_reports, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
