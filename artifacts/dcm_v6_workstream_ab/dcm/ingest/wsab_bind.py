"""Bind normalized board rows to WSAB football/basketball plugins. No LR promotion."""

from __future__ import annotations

import json
from pathlib import Path

from dcm.sports.football.registry import (
    CFB_LEAGUE,
    DERIVED_SPECS,
    NFL_LEAGUE,
    NFLP_LEAGUE,
    PRIMITIVE_SPECS,
    football_stat_reboot_eligibility,
)

_CFB_NAMES_PATH = Path(__file__).resolve().parents[2] / "configs" / "cfb_player_reboot_eligible.json"


def _cfb_official_names() -> set[str]:
    if not _CFB_NAMES_PATH.is_file():
        return set()
    data = json.loads(_CFB_NAMES_PATH.read_text(encoding="utf-8"))
    return {str(n).casefold() for n in data.get("official_listed_names_2026-08-27") or []}


_CFB_OFFICIAL = _cfb_official_names()

_FOOTBALL_MARKETS = set(PRIMITIVE_SPECS) | set(DERIVED_SPECS)
_BASKETBALL_MARKETS = {"pts", "reb", "ast", "pra", "3pm", "stl"}


def annotate_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        league = str(item.get("league") or "")
        market = str(item.get("market") or "")
        role = str(item.get("role") or "")
        name = str(item.get("playerName") or "")
        item["cfbOfficialNameListed"] = name.casefold() in _CFB_OFFICIAL
        item["cfbOfficialPlayerId"] = None
        if league in {NFL_LEAGUE, CFB_LEAGUE, NFLP_LEAGUE}:
            bound = market in _FOOTBALL_MARKETS
            item["wsabPlugin"] = "football" if bound else None
            item["wsabMarketBound"] = bound
            item["rebootEligibility"] = football_stat_reboot_eligibility(league, market, role) if bound else "UNKNOWN"
        elif league in {"NBA", "WNBA"} and market in _BASKETBALL_MARKETS:
            item["wsabPlugin"] = "basketball"
            item["wsabMarketBound"] = True
            item["rebootEligibility"] = "VERIFIED_TRUE" if league in {"NBA", "WNBA"} else "UNKNOWN"
        else:
            item["wsabPlugin"] = None
            item["wsabMarketBound"] = False
            item["rebootEligibility"] = "UNKNOWN"
        out.append(item)
    return out
