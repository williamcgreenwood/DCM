"""WorldProjection × EntryContract → WorldLineupOutcome. Fail closed on unknown state."""

from __future__ import annotations

from dataclasses import dataclass

from dcm.contracts.codes import FailureCode
from dcm.contracts.hashes import content_hash
from dcm.contracts.schemas import (
    AdministrativeState,
    ComparisonState,
    EconomicState,
    EntryContract,
    EntryPickContract,
    LineupSettlement,
    PickSide,
    WorldLineupOutcome,
    WorldPickState,
    WorldProjectionResult,
)
from dcm.platform.prizepicks.payouts import minimum_guarantee_return
from dcm.platform.prizepicks.reboot import ParticipationFacts, RebootDecision, evaluate_reboot


SETTLEMENT_RULE_VERSION = "PP_SETTLEMENT_ADAPTER_V1_2026-08-27"
SETTLEMENT_RULE_HASH = content_hash({
    "version": SETTLEMENT_RULE_VERSION,
    "snapshot": "PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1",
    "final": "max(LB, MG)",
})


@dataclass(frozen=True)
class GroupScoreContext:
    """Optional. Without this, Leaderboard return is UNMODELED."""
    group_size: int
    user_is_sole_or_tied_max: bool
    tied_top_scorers: int


class SettlementError(RuntimeError):
    def __init__(self, code: FailureCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


def compare(value: float, line: float, side: PickSide) -> ComparisonState:
    if abs(value - line) < 1e-12:
        return ComparisonState.TIE
    more = value > line
    if side == PickSide.MORE:
        return ComparisonState.WIN if more else ComparisonState.LOSS
    return ComparisonState.WIN if not more else ComparisonState.LOSS


def _economic(admin: AdministrativeState, comparison: ComparisonState) -> EconomicState:
    if admin == AdministrativeState.UNRESOLVED:
        return EconomicState.UNRESOLVED
    if admin in {AdministrativeState.DNP, AdministrativeState.REBOOT, AdministrativeState.CANCELLED}:
        return EconomicState.REMOVED
    if admin == AdministrativeState.INVALID_MARKET:
        return EconomicState.UNRESOLVED
    if comparison == ComparisonState.WIN:
        return EconomicState.COUNTS_AS_WIN
    if comparison == ComparisonState.LOSS:
        return EconomicState.COUNTS_AS_LOSS
    if comparison == ComparisonState.TIE:
        return EconomicState.TIER_REDUCTION
    return EconomicState.UNRESOLVED


def _pick_state(
    pick: EntryPickContract,
    projection: WorldProjectionResult,
    facts: ParticipationFacts,
) -> WorldPickState:
    decision: RebootDecision = evaluate_reboot(pick, facts)
    admin = decision.administrative_state
    if admin == AdministrativeState.UNRESOLVED:
        comparison = ComparisonState.NOT_APPLICABLE
    elif admin in {AdministrativeState.DNP, AdministrativeState.REBOOT, AdministrativeState.CANCELLED}:
        comparison = ComparisonState.NOT_APPLICABLE
    else:
        comparison = compare(projection.computed_value, pick.line, pick.side)
    economic = _economic(admin, comparison)
    return WorldPickState(
        projection_id=pick.projection_id,
        administrative_state=admin,
        comparison_state=comparison,
        economic_state=economic,
        official_stat_value=projection.computed_value,
        comparison_line=pick.line,
        reboot_applied=decision.applied,
        reason_code=decision.reason_code,
    )


def settle_world_lineup(
    *,
    entry: EntryContract,
    projections: dict[str, WorldProjectionResult],
    participation: dict[str, ParticipationFacts],
    world_index: int = 0,
    group: GroupScoreContext | None = None,
    world_projection_hash: str | None = None,
) -> WorldLineupOutcome:
    if not entry.payout_display_hash or not entry.picks:
        raise SettlementError(FailureCode.ENTRY_CONTRACT_INCOMPLETE, "missing display hash or picks")

    states: list[WorldPickState] = []
    for pick in entry.picks:
        if pick.projection_id not in projections:
            raise SettlementError(FailureCode.PLATFORM_SETTLEMENT_UNRESOLVED, f"missing projection {pick.projection_id}")
        if pick.projection_id not in participation:
            raise SettlementError(FailureCode.UNKNOWN_PARTICIPATION_RULE, f"missing participation {pick.projection_id}")
        states.append(_pick_state(pick, projections[pick.projection_id], participation[pick.projection_id]))

    if any(s.administrative_state == AdministrativeState.UNRESOLVED or s.economic_state == EconomicState.UNRESOLVED for s in states):
        lineup = LineupSettlement(
            original_pick_count=len(entry.picks),
            administrative_removed_count=sum(1 for s in states if s.economic_state == EconomicState.REMOVED),
            tie_count=sum(1 for s in states if s.comparison_state == ComparisonState.TIE),
            payout_tier_count=0,
            eligibility_population_count=0,
            distinct_remaining_team_count=0,
            win_count=0,
            loss_count=0,
            push_count=0,
            minimum_guarantee_return=0.0,
            leaderboard_score=0.0,
            leaderboard_return=0.0,
            leaderboard_return_status="UNMODELED",
            final_platform_return=0.0,
            net_return=-entry.stake,
            settlement_status="UNRESOLVED",
        )
        return _outcome(world_index, states, lineup, entry, projections, world_projection_hash)

    removed = [s for s in states if s.economic_state == EconomicState.REMOVED]
    active = [s for s in states if s.economic_state != EconomicState.REMOVED]
    wins = [s for s in active if s.comparison_state == ComparisonState.WIN]
    losses = [s for s in active if s.comparison_state == ComparisonState.LOSS]
    pushes = [s for s in active if s.comparison_state == ComparisonState.TIE]

    if len(removed) + len(active) != len(entry.picks):
        raise SettlementError(FailureCode.ENTRY_CONTRACT_INCOMPLETE, "pick accounting hole")
    if len(wins) + len(losses) + len(pushes) != len(active):
        raise SettlementError(FailureCode.ENTRY_CONTRACT_INCOMPLETE, "active accounting hole")

    # Ties stay in eligibility; DNP/Reboot do not.
    payout_tier_count = len(active)  # remaining after admin removal; ties still occupy a tier slot
    eligibility_population_count = len(active)
    # payout tier steps down for ties AND voids; remaining result count for MG lookup
    # uses active picks as the card that still exists. Wins are compared inside that card.
    remaining_pick_ids = {s.projection_id for s in active}
    remaining_teams = {
        p.team_id for p in entry.picks if p.projection_id in remaining_pick_ids
    }
    distinct_remaining_team_count = len(remaining_teams)

    settlement_status = "FINAL"
    mg_return = 0.0
    if active and distinct_remaining_team_count == 1 and removed:
        # Same-team after administrative removal → refund.
        settlement_status = "REFUND"
        mg_return = entry.stake
        final_return = entry.stake
        lb_score = 0.0
        lb_return = 0.0
        lb_status = "NOT_APPLICABLE"
    elif not active:
        settlement_status = "REFUND"
        mg_return = entry.stake
        final_return = entry.stake
        lb_score = 0.0
        lb_return = 0.0
        lb_status = "NOT_APPLICABLE"
    else:
        looked = minimum_guarantee_return(entry.displayed_minimum_guarantee_table_hash, payout_tier_count, len(wins))
        if looked is None:
            raise SettlementError(
                FailureCode.UNKNOWN_PLATFORM_RULE,
                f"no MG row for tier={payout_tier_count} wins={len(wins)} hash={entry.displayed_minimum_guarantee_table_hash[:12]}",
            )
        mg_return = float(looked)
        pick_by_id = {p.projection_id: p for p in entry.picks}
        lb_score = 0.0
        for s in wins:
            pick = pick_by_id[s.projection_id]
            lb_score += pick.leaderboard_point_weight
        if group is None:
            lb_return = 0.0
            lb_status = "UNMODELED"
            final_return = mg_return  # lower bound: max(unmodeled LB, MG) cannot be less than MG
        else:
            if group.user_is_sole_or_tied_max and group.tied_top_scorers >= 1:
                lb_return = entry.displayed_leaderboard_payout / group.tied_top_scorers
            else:
                lb_return = 0.0
            lb_status = "MODELED"
            final_return = max(lb_return, mg_return)

    lineup = LineupSettlement(
        original_pick_count=len(entry.picks),
        administrative_removed_count=len(removed),
        tie_count=len(pushes),
        payout_tier_count=payout_tier_count,
        eligibility_population_count=eligibility_population_count,
        distinct_remaining_team_count=distinct_remaining_team_count,
        win_count=len(wins),
        loss_count=len(losses),
        push_count=len(pushes),
        minimum_guarantee_return=mg_return,
        leaderboard_score=lb_score if settlement_status == "FINAL" else 0.0,
        leaderboard_return=lb_return if settlement_status == "FINAL" else 0.0,
        leaderboard_return_status=lb_status if settlement_status == "FINAL" else "NOT_APPLICABLE",
        final_platform_return=final_return,
        net_return=final_return - entry.stake,
        settlement_status=settlement_status,
    )
    return _outcome(world_index, states, lineup, entry, projections, world_projection_hash)


def _outcome(world_index, states, lineup, entry, projections, world_projection_hash) -> WorldLineupOutcome:
    proj_hash = world_projection_hash or content_hash(sorted(p.content_hash for p in projections.values()))
    return WorldLineupOutcome(
        world_index=world_index,
        pick_states=tuple(states),
        lineup=lineup,
        world_projection_hash=proj_hash,
        entry_contract_hash=entry.content_hash,
        settlement_rule_hash=SETTLEMENT_RULE_HASH,
        source_hashes=(proj_hash, entry.content_hash, SETTLEMENT_RULE_HASH),
    )
