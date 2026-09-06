"""Official football reboot predicates added after the original 41-test slice."""

from dcm.contracts.codes import FailureCode
from dcm.contracts.schemas import AdministrativeState
from dcm.platform.prizepicks.entry_contract import pick
from dcm.platform.prizepicks.reboot import evaluate_reboot
from tests.fixtures import nfl_pick, played


def _cfb(player="CFB_WR_001"):
    return pick(
        projection_id="p1",
        player_id=player,
        team_id="HOME",
        event_id="CFB_GAME_1",
        market="rec_yds",
        line=40,
        side="MORE",
        league="CFB",
        stat_key="rec_yds",
    )


def test_cfb_regular_season_does_not_reboot():
    d = evaluate_reboot(
        _cfb(),
        played(role="WR", status="LEFT_EARLY", left_first_half=True, no_second_half_return=True, game_phase="REGULAR"),
    )
    assert d.applied is False
    assert d.reason_code == FailureCode.CFB_PHASE_NOT_PLAYOFF.value


def test_cfb_bowl_does_not_reboot():
    d = evaluate_reboot(
        _cfb(),
        played(role="WR", status="LEFT_EARLY", left_first_half=True, no_second_half_return=True, game_phase="BOWL"),
    )
    assert d.applied is False
    assert d.reason_code == FailureCode.CFB_PHASE_NOT_PLAYOFF.value


def test_cfb_unknown_phase_unresolved():
    d = evaluate_reboot(
        _cfb(),
        played(role="WR", status="LEFT_EARLY", left_first_half=True, no_second_half_return=True, game_phase="UNSPECIFIED"),
    )
    assert d.administrative_state == AdministrativeState.UNRESOLVED
    assert d.reason_code == FailureCode.CFB_PHASE_NOT_PLAYOFF.value


def test_partial_board_never_reboots_nfl():
    d = evaluate_reboot(
        nfl_pick("a", "NFL_WR_001", "rec_yds", 40),
        played(role="WR", status="LEFT_EARLY", left_first_half=True, no_second_half_return=True, board_id="NFL_1H"),
    )
    assert d.applied is False
    assert d.reason_code == FailureCode.PARTIAL_BOARD_NO_REBOOT.value


def test_third_quarter_exit_is_not_a_reboot():
    d = evaluate_reboot(
        nfl_pick("a", "NFL_WR_001", "rec_yds", 40),
        played(role="WR", status="LEFT_EARLY", left_first_half=False, no_second_half_return=True, left_early=False),
    )
    assert d.applied is False
    assert d.reason_code == "NO_QUALIFYING_EXIT"
