"""Single call path: ledger markets → projections → WorldLineupOutcome."""

from __future__ import annotations

from dcm.contracts.schemas import EntryContract, PrimitiveStatLedger, WorldLineupOutcome, WorldProjectionResult
from dcm.platform.prizepicks.reboot import ParticipationFacts
from dcm.platform.prizepicks.settlement import GroupScoreContext, settle_world_lineup
from dcm.sports.basketball.minimal import project_basketball_market
from dcm.sports.football.projection import project_football_market


def project_pick(ledger: PrimitiveStatLedger, player_id: str, market: str, world_index: int = 0) -> WorldProjectionResult:
    if ledger.sport == "FOOTBALL":
        return project_football_market(ledger, player_id=player_id, market=market, world_index=world_index)
    if ledger.sport == "BASKETBALL":
        return project_basketball_market(ledger, player_id, market, world_index=world_index)
    raise RuntimeError(f"UNVERIFIED_MARKET_DEFINITION: sport {ledger.sport}")


def project_and_settle(
    *,
    ledger: PrimitiveStatLedger,
    entry: EntryContract,
    participation: dict[str, ParticipationFacts],
    world_index: int = 0,
    group: GroupScoreContext | None = None,
) -> WorldLineupOutcome:
    projections = {}
    for pick in entry.picks:
        projections[pick.projection_id] = project_pick(
            ledger, pick.player_id, pick.stat_key, world_index=world_index,
        )
    return settle_world_lineup(
        entry=entry,
        projections=projections,
        participation=participation,
        world_index=world_index,
        group=group,
    )
