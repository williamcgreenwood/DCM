import pytest

from dcm.contracts.codes import FailureCode
from dcm.contracts.schemas import AdministrativeState, ComparisonState, EconomicState, PickModifier
from dcm.platform.prizepicks.entry_contract import EntryContractError, build_entry_contract, pick
from dcm.platform.prizepicks.payouts import DEMO_MG_TABLE_HASH
from dcm.platform.prizepicks.reboot import ParticipationFacts, evaluate_reboot
from dcm.platform.prizepicks.settlement import GroupScoreContext, settle_world_lineup
from dcm.runtime.pipeline import project_and_settle, project_pick
from dcm.selection.eligibility import SelectionForbidden
from tests.fixtures import (
    MG_HASH,
    build_cfb_game,
    build_nba_game,
    build_nfl_game,
    nfl_pick,
    played,
)


def _entry(picks, stake=10.0):
    return build_entry_contract(
        picks=picks,
        stake=stake,
        displayed_leaderboard_payout=250.0,
        displayed_minimum_guarantee_table_hash=MG_HASH,
        submitted_at="2026-08-27T16:00:00Z",
    )


def test_goblin_cannot_enter_production_contract():
    g = nfl_pick("g1", "NFL_WR_001", "rec_yds", 40, modifier="GOBLIN")
    with pytest.raises(SelectionForbidden) as ei:
        _entry([g])
    assert ei.value.code == FailureCode.GOBLIN_SELECTION_FORBIDDEN


def test_goblin_may_be_built_for_analytics_only():
    g = nfl_pick("g1", "NFL_WR_001", "rec_yds", 40, modifier="GOBLIN")
    contract = build_entry_contract(
        picks=[g],
        stake=10.0,
        displayed_leaderboard_payout=25.0,
        displayed_minimum_guarantee_table_hash=MG_HASH,
        submitted_at="2026-08-27T16:00:00Z",
        allow_goblin_for_analytics=True,
    )
    assert contract.picks[0].modifier == PickModifier.GOBLIN


def test_missing_display_hash_impossible():
    # constructor requires payout_display_hash via builder
    with pytest.raises(EntryContractError):
        build_entry_contract(
            picks=[nfl_pick("a", "NFL_WR_001", "rec_yds", 40)],
            stake=10,
            displayed_leaderboard_payout=10,
            displayed_minimum_guarantee_table_hash="",
            submitted_at="2026-08-27T16:00:00Z",
        )


def test_nba_e2e_win_path():
    world_set, world, ledger = build_nba_game()
    # pts=23, reb=8, ast=6, pra=37
    picks = [
        pick(projection_id="n1", player_id="NBA_P_001", team_id="BOS", event_id="NBA_GAME_1",
             market="pts", line=20, side="MORE", league="NBA", stat_key="pts"),
        pick(projection_id="n2", player_id="NBA_P_001", team_id="BOS", event_id="NBA_GAME_1",
             market="pra", line=30, side="MORE", league="NBA", stat_key="pra"),
    ]
    entry = _entry(picks, stake=10)
    facts = {
        "n1": played(role="G", opportunity_count=34),
        "n2": played(role="G", opportunity_count=34),
    }
    out = project_and_settle(ledger=ledger, entry=entry, participation=facts)
    assert out.lineup.win_count == 2
    assert out.lineup.loss_count == 0
    assert out.lineup.original_pick_count == 2
    assert out.lineup.administrative_removed_count == 0
    assert out.lineup.payout_tier_count == 2
    assert out.lineup.eligibility_population_count == 2
    assert out.lineup.minimum_guarantee_return == 3.0
    assert out.lineup.leaderboard_return_status == "UNMODELED"
    assert out.lineup.final_platform_return == 3.0
    assert out.entry_contract_hash == entry.content_hash
    assert out.lineup.settlement_status == "FINAL"
    assert world.valid


def test_nba_reboot_1h_leave_and_already_achieved():
    p = pick(projection_id="n1", player_id="NBA_P_001", team_id="BOS", event_id="NBA_GAME_1",
             market="pts", line=20, side="MORE", league="NBA", stat_key="pts")
    left = played(role="G", opportunity_count=16, status="LEFT_EARLY", left_first_half=True, no_second_half_return=True)
    d = evaluate_reboot(p, left)
    assert d.administrative_state == AdministrativeState.REBOOT
    achieved = played(role="G", opportunity_count=16, status="LEFT_EARLY", left_first_half=True, no_second_half_return=True, achieved_before_exit=True)
    d2 = evaluate_reboot(p, achieved)
    assert d2.administrative_state == AdministrativeState.ACTIVE
    less = pick(projection_id="n1", player_id="NBA_P_001", team_id="BOS", event_id="NBA_GAME_1",
                market="pts", line=20, side="LESS", league="NBA", stat_key="pts")
    d3 = evaluate_reboot(less, left)
    assert d3.applied is False


def test_nfl_e2e_combo_derived_from_same_world():
    built = build_nfl_game()
    wr = built.ledger.values_for("NFL_WR_001")
    combo = project_pick(built.ledger, "NFL_WR_001", "rush_rec_yds")
    assert abs(combo.computed_value - (wr["rush_yds"] + wr["rec_yds"])) < 1e-9
    picks = [
        nfl_pick("a", "NFL_WR_001", "rec_yds", wr["rec_yds"] - 1),
        nfl_pick("b", "NFL_WR_001", "rush_rec_yds", combo.computed_value - 1),
        nfl_pick("c", "NFL_QB_001", "pass_yds", 1000, side="LESS"),  # should win LESS
        nfl_pick("d", "NFL_RB_001", "rush_yds", 1000),  # likely loss
        nfl_pick("e", "NFL_TE_001", "receptions", 0),
        nfl_pick("f", "NFL_WR_002", "targets", 1000, side="LESS"),
    ]
    entry = _entry(picks, stake=10)
    facts = {pid: played(role=role) for pid, role in [
        ("a", "WR"), ("b", "WR"), ("c", "QB"), ("d", "RB"), ("e", "TE"), ("f", "WR")
    ]}
    out = project_and_settle(ledger=built.ledger, entry=entry, participation=facts)
    assert out.lineup.original_pick_count == 6
    assert out.lineup.win_count + out.lineup.loss_count + out.lineup.push_count == out.lineup.payout_tier_count
    assert out.lineup.administrative_removed_count == 0
    assert out.lineup.leaderboard_return_status == "UNMODELED"
    assert out.lineup.final_platform_return == out.lineup.minimum_guarantee_return


def test_nfl_defense_excluded_from_reboot():
    p = nfl_pick("d1", "NFL_DEF_001", "def_tackles", 5)
    facts = played(role="DEF", status="LEFT_EARLY", left_early=True, did_not_return=True)
    d = evaluate_reboot(p, facts)
    assert d.applied is False
    assert d.reason_code == "DEFENSE_EXCLUDED"


def test_nfl_reboot_qualifying_and_same_team_refund():
    built = build_nfl_game()
    picks = [
        nfl_pick("a", "NFL_WR_001", "rec_yds", 1, team="HOME"),
        nfl_pick("b", "NFL_WR_002", "rec_yds", 1, team="HOME"),
    ]
    entry = _entry(picks, stake=10)
    facts = {
        "a": played(role="WR", status="LEFT_EARLY", left_early=True, did_not_return=True),
        "b": played(role="WR"),
    }
    out = project_and_settle(ledger=built.ledger, entry=entry, participation=facts)
    assert out.pick_states[0].administrative_state == AdministrativeState.REBOOT
    assert out.pick_states[0].economic_state == EconomicState.REMOVED
    assert out.lineup.administrative_removed_count == 1
    assert out.lineup.distinct_remaining_team_count == 1
    assert out.lineup.settlement_status == "REFUND"
    assert out.lineup.final_platform_return == entry.stake
    assert out.lineup.net_return == 0.0


def test_tie_stays_in_eligibility_not_removed():
    built = build_nfl_game()
    rec = built.ledger.values_for("NFL_WR_001")["receptions"]
    picks = [
        nfl_pick("a", "NFL_WR_001", "receptions", rec),  # exact → tie
        nfl_pick("b", "NFL_WR_002", "receptions", -1),   # win MORE
    ]
    entry = _entry(picks, stake=10)
    facts = {"a": played(role="WR"), "b": played(role="WR")}
    out = project_and_settle(ledger=built.ledger, entry=entry, participation=facts)
    assert out.pick_states[0].comparison_state == ComparisonState.TIE
    assert out.pick_states[0].economic_state == EconomicState.TIER_REDUCTION
    assert out.lineup.tie_count == 1
    assert out.lineup.administrative_removed_count == 0
    assert out.lineup.eligibility_population_count == 2
    assert out.lineup.payout_tier_count == 2


def test_dnp_removes_from_eligibility():
    built = build_nfl_game()
    picks = [
        nfl_pick("a", "NFL_WR_001", "rec_yds", 1),
        nfl_pick("b", "NFL_WR_002", "rec_yds", 1),
    ]
    entry = _entry(picks, stake=10)
    facts = {
        "a": played(role="WR", status="DNP", opportunity_count=0),
        "b": played(role="WR"),
    }
    out = project_and_settle(ledger=built.ledger, entry=entry, participation=facts)
    assert out.pick_states[0].administrative_state == AdministrativeState.DNP
    assert out.lineup.administrative_removed_count == 1


def test_kicker_zero_opportunity_path():
    p = nfl_pick("k1", "NFL_K_001", "fg_made", 1.5)
    facts = played(role="K", opportunity_count=0, specialist_attempts=0, status="PLAYED")
    d = evaluate_reboot(p, facts)
    assert d.applied is True
    assert d.reason_code == "KP_ZERO_OPPORTUNITY"


def test_nfl_preseason_unresolved():
    p = pick(
        projection_id="p1", player_id="NFL_QB_001", team_id="HOME", event_id="PRE",
        market="pass_yds", line=200, side="MORE", league="NFLP", stat_key="pass_yds",
    )
    d = evaluate_reboot(p, played(role="QB", status="LEFT_EARLY", left_early=True, did_not_return=True))
    assert d.administrative_state == AdministrativeState.UNRESOLVED
    assert d.reason_code == FailureCode.PRESEASON_RULE_UNVERIFIED.value


def test_cfb_unlisted_player_unresolved():
    p = pick(
        projection_id="p1", player_id="CFB_WR_UNLISTED", team_id="HOME", event_id="CFB_GAME_1",
        market="rec_yds", line=40, side="MORE", league="CFB", stat_key="rec_yds",
    )
    d = evaluate_reboot(p, played(role="WR", status="LEFT_EARLY", left_early=True, did_not_return=True))
    assert d.administrative_state == AdministrativeState.UNRESOLVED
    assert d.reason_code == FailureCode.CFB_PLAYER_NOT_IN_REBOOT_REGISTRY.value


def test_cfb_registered_player_can_reboot():
    p = pick(
        projection_id="p1", player_id="CFB_WR_001", team_id="HOME", event_id="CFB_GAME_1",
        market="rec_yds", line=40, side="MORE", league="CFB", stat_key="rec_yds",
    )
    d = evaluate_reboot(
        p,
        played(
            role="WR",
            status="LEFT_EARLY",
            left_first_half=True,
            no_second_half_return=True,
            game_phase="CFP_PLAYOFF",
            board_id="FULL_GAME",
        ),
    )
    assert d.applied is True
    assert d.reason_code == "CFB_REGISTERED_PLAYER_REBOOT"


def test_cfb_e2e_path_uses_same_adapter():
    built = build_cfb_game()
    rec = built.ledger.values_for("CFB_WR_001")["rec_yds"]
    picks = [
        pick(projection_id="a", player_id="CFB_WR_001", team_id="HOME", event_id="CFB_GAME_1",
             market="rec_yds", line=rec - 1, side="MORE", league="CFB", stat_key="rec_yds"),
        pick(projection_id="b", player_id="CFB_QB_001", team_id="HOME", event_id="CFB_GAME_1",
             market="pass_yds", line=10, side="MORE", league="CFB", stat_key="pass_yds"),
    ]
    entry = _entry(picks, stake=10)
    facts = {"a": played(role="WR"), "b": played(role="QB")}
    out = project_and_settle(ledger=built.ledger, entry=entry, participation=facts)
    assert out.lineup.original_pick_count == 2
    assert out.lineup.settlement_status in {"FINAL", "UNRESOLVED"}
    assert out.lineup.win_count == 2


def test_unknown_mg_row_fail_closed():
    built = build_nfl_game()
    picks = [nfl_pick("a", "NFL_WR_001", "rec_yds", 1) for _ in range(3)]
    # rebuild ids
    picks = [
        nfl_pick("a", "NFL_WR_001", "rec_yds", 1),
        nfl_pick("b", "NFL_WR_002", "rec_yds", 1),
        nfl_pick("c", "NFL_TE_001", "rec_yds", 1),
    ]
    entry = build_entry_contract(
        picks=picks,
        stake=10,
        displayed_leaderboard_payout=50,
        displayed_minimum_guarantee_table_hash="not_a_real_table_hash",
        submitted_at="2026-08-27T16:00:00Z",
    )
    facts = {k: played(role="WR") for k in ("a", "b", "c")}
    with pytest.raises(Exception) as ei:
        project_and_settle(ledger=built.ledger, entry=entry, participation=facts)
    assert "UNKNOWN_PLATFORM_RULE" in str(ei.value)


def test_leaderboard_modeled_when_group_supplied():
    world_set, world, ledger = build_nba_game()
    picks = [
        pick(projection_id="n1", player_id="NBA_P_001", team_id="BOS", event_id="NBA_GAME_1",
             market="pts", line=20, side="MORE", league="NBA", stat_key="pts"),
        pick(projection_id="n2", player_id="NBA_P_001", team_id="BOS", event_id="NBA_GAME_1",
             market="pra", line=30, side="MORE", league="NBA", stat_key="pra"),
    ]
    entry = _entry(picks, stake=10)
    facts = {"n1": played(role="G", opportunity_count=34), "n2": played(role="G", opportunity_count=34)}
    out = project_and_settle(
        ledger=ledger,
        entry=entry,
        participation=facts,
        group=GroupScoreContext(group_size=10, user_is_sole_or_tied_max=True, tied_top_scorers=2),
    )
    assert out.lineup.leaderboard_return_status == "MODELED"
    assert out.lineup.leaderboard_return == 125.0  # 250 / 2
    assert out.lineup.final_platform_return == max(125.0, out.lineup.minimum_guarantee_return)
    assert abs(out.lineup.leaderboard_score - 2.0) < 1e-9


def test_payout_gt_zero_is_not_net_gt_zero():
    world_set, world, ledger = build_nba_game()
    picks = [
        pick(projection_id="n1", player_id="NBA_P_001", team_id="BOS", event_id="NBA_GAME_1",
             market="pts", line=20, side="MORE", league="NBA", stat_key="pts"),
        pick(projection_id="n2", player_id="NBA_P_001", team_id="BOS", event_id="NBA_GAME_1",
             market="pra", line=30, side="MORE", league="NBA", stat_key="pra"),
    ]
    entry = _entry(picks, stake=10)
    facts = {"n1": played(role="G"), "n2": played(role="G")}
    out = project_and_settle(ledger=ledger, entry=entry, participation=facts)
    assert out.lineup.final_platform_return > 0
    # 2-pick 2-win table pays 3.0 on a 10 stake → net negative
    assert out.lineup.net_return < 0


def test_hashes_are_stable_and_bound():
    built = build_nfl_game()
    again = build_nfl_game()
    assert built.ledger.content_hash == again.ledger.content_hash
    assert built.world_set.content_hash == again.world_set.content_hash


def test_preseason_e2e_unresolved_does_not_guess_payout():
    from dcm.sports.football.ledger import build_football_world
    from tests.fixtures import nfl_home_pool, nfl_players
    built = build_football_world(
        event_id="PRE1",
        league="NFLP",
        teams={"HOME": nfl_home_pool()},
        players=nfl_players(),
    )
    p = pick(
        projection_id="a", player_id="NFL_WR_001", team_id="HOME", event_id="PRE1",
        market="rec_yds", line=1, side="MORE", league="NFLP", stat_key="rec_yds",
    )
    entry = _entry([p], stake=10)
    out = project_and_settle(
        ledger=built.ledger,
        entry=entry,
        participation={"a": played(role="WR", status="LEFT_EARLY", left_early=True, did_not_return=True)},
    )
    assert out.lineup.settlement_status == "UNRESOLVED"
    assert out.lineup.final_platform_return == 0.0
