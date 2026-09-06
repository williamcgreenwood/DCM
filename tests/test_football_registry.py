from dcm.contracts.codes import FailureCode
from dcm.sports.football.conservation import evaluate_football_conservation, football_conservation_rules
from dcm.sports.football.ledger import ConservationError, corrupt_stat
from dcm.sports.football.projection import project_football_market
from dcm.sports.football.registry import (
    CFB_LEAGUE,
    CFB_PLAYER_REBOOT_ELIGIBLE,
    NFL_LEAGUE,
    NFLP_LEAGUE,
    football_market_definitions,
    football_primitive_keys,
    football_stat_reboot_eligibility,
    lookup_market,
)
from dcm.validation.conservation_harness import run_football_harness
from tests.fixtures import build_cfb_game, build_nfl_game


def test_nfl_and_cfb_share_primitive_keys():
    keys = football_primitive_keys()
    assert "pass_yds" in keys and "targets" in keys and "team_off_plays" in keys
    nfl = {m.market for m in football_market_definitions(NFL_LEAGUE)}
    cfb = {m.market for m in football_market_definitions(CFB_LEAGUE)}
    assert nfl == cfb
    assert "pass_rush_yds" in nfl
    assert "rush_rec_yds" in nfl


def test_conservation_rules_exist_for_nfl_cfb_nflp():
    rules = football_conservation_rules()
    leagues = {r.league for r in rules}
    assert leagues == {NFL_LEAGUE, CFB_LEAGUE, NFLP_LEAGUE}


def test_valid_nfl_world_conserves():
    built = build_nfl_game()
    assert built.world.valid
    assert built.world.primitive_ledger_hash == built.ledger.content_hash
    results = evaluate_football_conservation(built.ledger)
    assert all(r.passed for r in results)


def test_valid_cfb_world_conserves():
    built = build_cfb_game()
    assert built.ledger.league == CFB_LEAGUE
    assert built.world.valid


def test_snap_sum_is_not_required_to_equal_plays():
    built = build_nfl_game()
    snaps = sum(built.ledger.values_for(e.entity_id)["off_snaps"] for e in built.ledger.entries if e.entity_type == "PLAYER" and e.stat_key == "off_snaps")
    plays = built.ledger.team_values("HOME")["team_off_plays"]
    assert snaps != plays
    snap_rules = [r for r in evaluate_football_conservation(built.ledger) if r.rule_id == "NO_SNAP_EQ_PLAYS"]
    assert snap_rules and snap_rules[0].passed


def test_qb_dropback_identity():
    built = build_nfl_game()
    v = built.ledger.values_for("NFL_QB_001")
    assert v["dropbacks"] == v["pass_att"] + v["sacks_taken"] + v["scramble_att"]
    assert v["rush_att"] == v["designed_rush_att"] + v["scramble_att"]


def test_receptions_cannot_exceed_targets():
    built = build_nfl_game()
    bad = corrupt_stat(built.ledger, "NFL_WR_001", "receptions", 99)
    failed = [r for r in evaluate_football_conservation(bad) if not r.passed]
    assert any(r.rule_id == "REC_LE_TGT" for r in failed)


def test_builder_fail_closed_on_pass_rec_mismatch():
    from dcm.sports.football.ledger import FootballPlayerSpec, TeamOpportunityPool, build_football_world
    from tests.fixtures import nfl_home_pool, nfl_players
    try:
        build_football_world(
            event_id="X",
            league=NFL_LEAGUE,
            teams={"HOME": nfl_home_pool()},
            players=nfl_players(),
            extra_team_stats={"HOME": {
                "team_pass_yds": 12,
                "team_rec_yds": 400,
                "team_off_plays": 65,
                "team_pass_att": 35,
                "team_rush_att": 27,
                "team_sacks_taken": 3,
                "team_designed_rush_att": 25,
                "team_dropbacks": 40,
                "team_targets": 35,
                "team_rush_yds": 10,
            }},
        )
        assert False, "expected ConservationError"
    except ConservationError as exc:
        assert exc.code == FailureCode.PRIMITIVE_CONSERVATION_FAILURE


def test_derived_combo_matches_components():
    built = build_nfl_game()
    wr = built.ledger.values_for("NFL_WR_001")
    proj = project_football_market(built.ledger, player_id="NFL_WR_001", market="rush_rec_yds")
    assert abs(proj.computed_value - (wr["rush_yds"] + wr["rec_yds"])) < 1e-9
    assert proj.primitive_ledger_hash == built.ledger.content_hash


def test_unverified_market_fail_closed():
    built = build_nfl_game()
    try:
        project_football_market(built.ledger, player_id="NFL_WR_001", market="war")
        assert False
    except Exception as exc:
        assert "UNVERIFIED_MARKET_DEFINITION" in str(exc)


def test_defense_stat_not_reboot_eligible():
    assert football_stat_reboot_eligibility(NFL_LEAGUE, "def_tackles", "DEF") == "VERIFIED_FALSE"
    assert football_stat_reboot_eligibility(NFL_LEAGUE, "pass_yds", "QB") == "VERIFIED_TRUE"
    assert football_stat_reboot_eligibility(NFLP_LEAGUE, "pass_yds", "QB") == "UNKNOWN"


def test_cfb_player_registry_is_explicit():
    assert "CFB_QB_001" in CFB_PLAYER_REBOOT_ELIGIBLE
    assert "CFB_WR_UNLISTED" not in CFB_PLAYER_REBOOT_ELIGIBLE


def test_unknown_stat_eligibility_is_unknown():
    assert football_stat_reboot_eligibility(NFL_LEAGUE, "air_yards", "WR") == "UNKNOWN"


def test_harness_valid_and_corrupt():
    cases = {c.name: c for c in run_football_harness()}
    assert cases["valid_world_builds"].passed
    assert cases["corrupt_rec_gt_tgt_fails"].passed
    assert cases["corrupt_team_plays_fails"].passed
    assert cases["builder_rejects_pass_rec_mismatch"].passed


def test_ledger_hash_changes_on_corruption():
    built = build_nfl_game()
    bad = corrupt_stat(built.ledger, "NFL_WR_001", "rec_yds", 0.0)
    assert bad.content_hash != built.ledger.content_hash


def test_market_definition_key_is_exact_tuple():
    md = lookup_market(NFL_LEAGUE, "pass_yds")
    assert md.key() == ("PRIZEPICKS", "NFL", "pass_yds", md.definition_version)
    assert md.verified
