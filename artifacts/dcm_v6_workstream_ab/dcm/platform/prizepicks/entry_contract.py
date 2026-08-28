"""Freeze an EntryContract. Displayed payout is captured, never reconstructed."""

from __future__ import annotations

from dcm.contracts.codes import FailureCode
from dcm.contracts.hashes import content_hash
from dcm.contracts.schemas import (
    EntryContract,
    EntryPickContract,
    PickModifier,
    PickSide,
)
from dcm.selection.eligibility import reject_goblin_selection


class EntryContractError(RuntimeError):
    def __init__(self, code: FailureCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


def build_entry_contract(
    *,
    picks: list[EntryPickContract],
    stake: float,
    displayed_leaderboard_payout: float,
    displayed_minimum_guarantee_table_hash: str,
    entry_type: str = "PLAYER_PICKS",
    platform_rule_version: str = "PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1",
    submitted_at: str,
    currency: str = "USD",
    minimum_guarantee_definition_id: str = "PP_MG_V1",
    leaderboard_definition_id: str = "PP_LB_V1",
    allow_goblin_for_analytics: bool = False,
) -> EntryContract:
    if not picks:
        raise EntryContractError(FailureCode.ENTRY_CONTRACT_INCOMPLETE, "no picks")
    if displayed_leaderboard_payout < 0:
        raise EntryContractError(FailureCode.ENTRY_CONTRACT_INCOMPLETE, "leaderboard display missing")
    if not displayed_minimum_guarantee_table_hash:
        raise EntryContractError(FailureCode.ENTRY_CONTRACT_INCOMPLETE, "MG table hash missing")
    for pick in picks:
        if not pick.offered_side_verified:
            raise EntryContractError(FailureCode.OFFERED_SIDE_UNKNOWN, pick.projection_id)
        if pick.modifier == PickModifier.GOBLIN and not allow_goblin_for_analytics:
            reject_goblin_selection(pick)
    display_payload = {
        "stake": stake,
        "lb": displayed_leaderboard_payout,
        "mg_table": displayed_minimum_guarantee_table_hash,
        "picks": [
            {
                "id": p.projection_id,
                "player": p.player_id,
                "market": p.market_definition_id,
                "line": p.line,
                "side": p.side.value,
                "mod": p.modifier.value,
            }
            for p in picks
        ],
        "submitted_at": submitted_at,
        "rule": platform_rule_version,
    }
    return EntryContract(
        platform="PRIZEPICKS",
        platform_rule_version=platform_rule_version,
        submitted_at=submitted_at,
        entry_type=entry_type,
        stake=float(stake),
        currency=currency,
        picks=tuple(picks),
        minimum_guarantee_definition_id=minimum_guarantee_definition_id,
        leaderboard_definition_id=leaderboard_definition_id,
        payout_display_hash=content_hash(display_payload),
        displayed_leaderboard_payout=float(displayed_leaderboard_payout),
        displayed_minimum_guarantee_table_hash=displayed_minimum_guarantee_table_hash,
        source_hashes=(content_hash(display_payload),),
    )


def pick(
    *,
    projection_id: str,
    player_id: str,
    team_id: str,
    event_id: str,
    market: str,
    line: float,
    side: str,
    modifier: str = "STANDARD",
    league: str,
    stat_key: str | None = None,
    offered_side_verified: bool = True,
    reboot_rule_version: str = "PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1",
) -> EntryPickContract:
    weight = {"STANDARD": 1.00, "DEMON": 1.05, "GOBLIN": 0.95, "OTHER": 1.00}[modifier]
    return EntryPickContract(
        projection_id=projection_id,
        player_id=player_id,
        team_id=team_id,
        event_id=event_id,
        market_definition_id=f"PRIZEPICKS|{league}|{market}|PP_FOOTBALL_PRIM_V1_2026-08-27" if league in {"NFL", "CFB", "NFLP"} else f"PRIZEPICKS|{league}|{market}|PP_BBALL_PRIM_V1_2026-08-27",
        line=float(line),
        side=PickSide(side),
        modifier=PickModifier(modifier),
        offered_side_verified=offered_side_verified,
        leaderboard_point_weight=weight,
        reboot_rule_version=reboot_rule_version,
        participation_rule_version="PP_PARTICIPATION_V1_2026-08-25",
        league=league,
        stat_key=stat_key or market,
    )
