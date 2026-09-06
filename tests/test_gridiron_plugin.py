"""P7 gridiron production plugin: adapters, epochs, models, ledger derivation, gates."""
from __future__ import annotations

from pathlib import Path

import pytest

from dcm.model.gridiron_models import GridironEfficiencyModel, GridironOpportunityModel, TeamEventModel
from dcm.model.market_derive import UnknownMarketError, derive_market
from dcm.model.parameters import build_parameter_snapshot
from dcm.model.worlds import sample_football, value_from_stats
from dcm.research.adapters.pro_football_reference import (
    FootballReferenceGameLogAdapter,
    ProFootballReferenceAdapter,
)
from dcm.research.gridiron_gamelog import (
    looks_like_gridiron_log,
    normalize_gridiron_log,
    normalize_gridiron_logs,
)
from dcm.research.player_packet import build_player_research_packet
from dcm.research.role_epoch import RoleEpochBuilder
from dcm.sports.common.plugin import PRODUCTION, UNSUPPORTED, lookup, selection_state
from dcm.sports.football.ledger import build_football_world
from dcm.sports.football.settlement_map import settle_football_market, settle_football_player
from dcm.sports.football.research_requirements import assess_football_support
from dcm.sports.football.cfb_role import resolve_cfb_role_state
from tests.fixtures import build_cfb_game, build_nfl_game

FIXTURES = Path(__file__).resolve().parent / "research_fixtures"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _claim(scope, scope_id, value, h="h"):
    return {
        "semantic_scope": scope,
        "scope_id": scope_id,
        "claim_value": value,
        "source_id": "OFFICIAL",
        "reliability": 0.95,
        "freshness": 0.95,
        "claim_hash": h,
        "observed_at": "2026-08-28T10:00:00Z",
    }


def _qb_logs(n=8):
    logs = []
    for i in range(n):
        logs.append({
            "game_date": f"2025-09-{(i % 28) + 1:02d}",
            "gs": 1,
            "pass_att": 30 + i,
            "pass_cmp": 20 + (i % 5),
            "pass_yds": 240 + i * 8,
            "pass_td": 2,
            "pass_int": i % 2,
            "sk": 2,
            "rush_att": 4 + (i % 3),
            "rush_yds": 18 + i,
            "off_pct": f"{90 + i % 8}%",
        })
    return logs


def _wr_logs(n=8):
    logs = []
    for i in range(n):
        logs.append({
            "game_date": f"2025-09-{(i % 28) + 1:02d}",
            "gs": 1 if i >= 2 else 0,
            "targets": 8 + (i % 5),
            "rec": 5 + (i % 4),
            "rec_yds": 70 + i * 6,
            "routes": 24 + i,
            "snaps": 50 + i,
            "rush_att": 0,
            "rush_yds": 0,
        })
    return logs


def test_pfr_aliases_normalize_pass_and_receiving():
    qb = normalize_gridiron_log({"pass_att": 35, "pass_yds": 287, "sk": 2, "rush_att": 5, "rush_yds": 22, "gs": 1})
    assert qb is not None
    assert qb["pass_att"] == 35
    assert qb["pass_yds"] == 287
    assert qb["sacks_taken"] == 2
    assert qb["rush_yds"] == 22
    wr = normalize_gridiron_log({"tgt": 11, "rec": 8, "rec_yds": 112, "routes": 32, "snaps": 61})
    assert wr is not None
    assert wr["targets"] == 11
    assert wr["receptions"] == 8
    assert wr["rec_yds"] == 112
    assert wr["routes"] == 32
    assert wr["snaps"] == 61
    # Do not invent routes from targets.
    no_routes = normalize_gridiron_log({"targets": 9, "rec": 6, "rec_yds": 80})
    assert no_routes is not None
    assert "routes" not in no_routes


def test_off_pct_parses_and_dnp_rejected():
    row = normalize_gridiron_log({"pass_att": 32, "pass_yds": 250, "off_pct": "71%"})
    assert row is not None
    assert abs(row["snap_pct"] - 0.71) < 1e-9
    batch = normalize_gridiron_logs([{"note": "Did Not Play"}, {"pass_att": 20, "pass_yds": 180}])
    assert len(batch["logs"]) == 1
    assert batch["reasonCounts"]["GAMELOG_OPPORTUNITY"] == 1



def test_kicker_only_log_normalizes_and_batch_keeps():
    row = {
        "date": "2025-09-06",
        "fg_att": 3,
        "fg_made": 2,
        "xp_att": 4,
        "xp_made": 4,
        "kicking_pts": 10,
    }
    assert looks_like_gridiron_log(row)
    normalized = normalize_gridiron_log(row, league="CFB")
    assert normalized is not None
    assert normalized["fg_att"] == 3
    assert normalized["fg_made"] == 2
    assert normalized["xp_att"] == 4
    assert normalized["xp_made"] == 4
    assert normalized["kicking_pts"] == 10
    aliased = normalize_gridiron_log({"fga": 2, "fgm": 1, "xpa": 3, "xpm": 3, "kicking_points": 6})
    assert aliased is not None
    assert aliased["fg_att"] == 2
    assert aliased["xp_att"] == 3
    assert aliased["kicking_pts"] == 6
    batch = normalize_gridiron_logs([
        {"note": "Did Not Play"},
        row,
        {"fga": 1, "xp_att": 2, "kicking_pts": 5},
    ], league="CFB")
    assert len(batch["logs"]) == 2
    assert batch["reasonCounts"].get("GAMELOG_OPPORTUNITY") == 1
    assert all("fg_att" in log or "xp_att" in log for log in batch["logs"])


def test_adapter_fixture_nfl_qb_and_cfb_qb():
    nfl = FootballReferenceGameLogAdapter().fetch_normalize({
        "html": _html("pfr_gamelog_qb.html"),
        "league": "NFL",
        "url": "fixture://pro-football-reference/qb",
    })
    assert len(nfl["logs"]) >= 8
    assert all("pass_yds" in r and "pass_att" in r for r in nfl["logs"])
    cfb = ProFootballReferenceAdapter().fetch_normalize({
        "html": _html("cfr_gamelog_qb.html"),
        "league": "CFB",
        "url": "fixture://sports-reference/cfb/qb",
    })
    assert len(cfb["logs"]) >= 8
    assert cfb["logs"][0].get("league") == "CFB"


def test_adapter_fixture_wr_targets_receptions():
    wr = FootballReferenceGameLogAdapter().fetch_normalize({
        "html": _html("pfr_gamelog_wr.html"),
        "league": "NFL",
    })
    assert len(wr["logs"]) >= 8
    assert all("receptions" in r and "rec_yds" in r and "targets" in r for r in wr["logs"])
    assert all(r["receptions"] <= r["targets"] + 1e-9 for r in wr["logs"])


def test_role_epoch_gridiron_starter_depth_and_qb_identity():
    logs = []
    for i in range(6):
        logs.append({"date": f"2025-09-{i+1:02d}", "gs": 0, "snaps": 12, "targets": 2, "rec": 1, "rec_yds": 9, "routes": 8})
    for i in range(8):
        logs.append({"date": f"2025-10-{i+1:02d}", "gs": 1, "snaps": 58, "targets": 9, "rec": 6, "rec_yds": 80, "routes": 30})
    built = RoleEpochBuilder().build(
        {"game_logs": logs, "role": "WR", "sportFamily": "gridiron", "league": "NFL"},
        today_context={"sportFamily": "gridiron", "league": "NFL", "role": "WR"},
    )
    assert built["mode"] == "gridiron"
    assert built["invented"] is False
    assert "stub" not in str(built["builder"]).lower()
    assert built["support_n"] >= 3
    labels = {e["label"] for e in built["epochs"]}
    assert "starter" in labels or "depth" in labels

    qb_logs = _qb_logs(8)
    qb = RoleEpochBuilder().build(
        {"game_logs": qb_logs, "role": "QB", "league": "NFL"},
        today_context={"sportFamily": "gridiron", "league": "NFL", "role": "QB"},
    )
    assert qb["qbIdentity"] is True
    assert (qb.get("projectedRole") or "").startswith("starter") or (qb.get("selected_epoch") or {}).get("label") in {"starter_qb", "starter"}


def test_opportunity_and_efficiency_qb_vs_skill():
    qb_logs = normalize_gridiron_logs(_qb_logs())["logs"]
    wr_logs = normalize_gridiron_logs(_wr_logs())["logs"]
    qb_opp = GridironOpportunityModel().fit(qb_logs, league="NFL", role="QB")
    qb_eff = GridironEfficiencyModel().fit(qb_logs, league="NFL", role="QB", pass_defense=1.0, rush_defense=1.0)
    assert qb_opp["pass_att_mean"] > 20
    assert qb_eff["pass_ypa"] > 5
    wr_opp = GridironOpportunityModel().fit(wr_logs, league="NFL", role="WR")
    wr_eff = GridironEfficiencyModel().fit(wr_logs, league="NFL", role="WR", pass_defense=1.05)
    assert wr_opp["routes_mean"] > 10
    assert 0 < wr_eff["catch_rate"] <= 1


def test_team_event_missing_defense_fail_closed_for_playable():
    missing = TeamEventModel().fit({"plays": 65, "pass_rate": 0.58}, {"pace": 1.0}, {}, league="NFL", market="pass_yds")
    assert missing["playableBlocker"] == "OPPONENT_PASS_DEFENSE"
    ok = TeamEventModel().fit(
        {"plays": 65, "pass_rate": 0.58, "pace": 1.0},
        {},
        {"pass_defense": 1.0, "rush_defense": 1.0},
        league="NFL",
        market="pass_yds",
    )
    assert ok["playableBlocker"] is None
    assert ok["plays"] == 65


def test_derive_markets_from_primitive_ledger():
    built = build_nfl_game()
    qb = built.ledger.values_for("NFL_QB_001")
    wr = built.ledger.values_for("NFL_WR_001")
    assert derive_market(qb, "pass_yds") == qb["pass_yds"]
    assert derive_market(qb, "Passing Yards") == qb["pass_yds"]
    assert abs(derive_market(qb, "pass_rush_yds") - (qb["pass_yds"] + qb["rush_yds"])) < 1e-9
    assert derive_market(wr, "receptions") == wr["receptions"]
    assert derive_market(wr, "rec_yds") == wr["rec_yds"]
    assert abs(derive_market(wr, "rush_rec_yds") - (wr["rush_yds"] + wr["rec_yds"])) < 1e-9
    settled = settle_football_market(qb, "passing yards")
    assert settled == qb["pass_yds"]
    proj = settle_football_player(built.ledger, player_id="NFL_QB_001", market="pass_yds")
    assert proj.computed_value == qb["pass_yds"]


def test_unknown_football_market_fails_closed():
    built = build_nfl_game()
    qb = built.ledger.values_for("NFL_QB_001")
    with pytest.raises(UnknownMarketError) as ei:
        derive_market(qb, "air_yards")
    assert ei.value.blocker == "UNVERIFIED_MARKET_DEFINITION"
    with pytest.raises(UnknownMarketError):
        settle_football_market(qb, "war")
    with pytest.raises(UnknownMarketError):
        derive_market(qb, "passing_yards_almost")


def test_cfb_pass_yards_from_fixture_ledger():
    built = build_cfb_game()
    qb = built.ledger.values_for("CFB_QB_001")
    yds = derive_market(qb, "pass_yds")
    assert yds == qb["pass_yds"]
    assert yds == settle_football_market(qb, "Pass Yards")


def test_nfl_and_cfb_row_reaches_modeled_path_with_fixture():
    nfl_html = _html("pfr_gamelog_qb.html")
    packet = build_player_research_packet(
        identity={"playerId": "NFL_QB_001", "playerName": "QB", "league": "NFL", "sportFamily": "gridiron", "eventId": "E1"},
        status="ACTIVE",
        role_hints={"role": "QB"},
        gamelog_html=nfl_html,
        as_of="2026-08-30T12:00:00Z",
        league="NFL",
    )
    assert packet["gameLogCount"] >= 8
    assert packet["evidenceUsed"] is True
    logs = packet["gameLogs"]
    row = {
        "sportFamily": "gridiron", "league": "NFL", "eventId": "E1", "playerId": "NFL_QB_001",
        "teamId": "KC", "projectionId": "pp-pass", "market": "pass_yds", "role": "QB",
    }
    claims = [
        _claim("PLAYER", "NFL_QB_001", {
            "status": "ACTIVE", "role": "QB", "game_logs": logs,
            "opportunity": {"support_n": len(logs)}, "efficiency": {"support_n": len(logs)},
        }),
        _claim("TEAM", "KC", {
            "plays": 65, "pass_rate": 0.58, "pace": 1.0,
            "pass_defense": 1.0, "rush_defense": 1.0,
            "matchup_efficiency_multiplier": 1.0,
        }),
        _claim("EVENT", "E1", {
            "scheduled_start": "2026-09-07T17:00:00Z", "environment": "outdoor",
            "pass_defense": 1.0, "rush_defense": 1.0,
        }),
        _claim("MARKET_DEFINITION", "prizepicks|NFL|pass_yds|FULL_GAME", {"definition_verified": True}),
        _claim("OFFER", "pp-pass", {"offer_recorded": True}),
    ]
    snap = build_parameter_snapshot(row, claims)
    assert snap["blocker"] is None
    assert snap["production_eligible"] is True
    assert snap["parameters"]["pass_att_mean"] > 20
    assert snap["role_epoch"]["mode"] == "gridiron"

    cfb_html = _html("cfr_gamelog_qb.html")
    cfb_packet = build_player_research_packet(
        identity={"playerId": "CFB_QB_001", "league": "CFB", "sportFamily": "gridiron", "eventId": "C1"},
        status="ACTIVE",
        role_hints={"role": "QB"},
        gamelog_html=cfb_html,
        as_of="2026-08-30T12:00:00Z",
        league="CFB",
    )
    cfb_row = {
        "sportFamily": "gridiron", "league": "CFB", "eventId": "C1", "playerId": "CFB_QB_001",
        "teamId": "OSU", "projectionId": "cfb-pass", "market": "pass_yds", "role": "QB",
    }
    cfb_claims = [
        _claim("PLAYER", "CFB_QB_001", {
            "status": "ACTIVE", "role": "QB", "depth_chart_role": "starter", "prior_season_starts": 8,
            "game_logs": cfb_packet["gameLogs"],
            "opportunity": {"support_n": cfb_packet["gameLogCount"]},
            "efficiency": {"support_n": cfb_packet["gameLogCount"]},
        }),
        _claim("TEAM", "OSU", {"plays": 70, "pass_rate": 0.55, "pace": 1.0, "pass_defense": 0.98, "rush_defense": 1.02}),
        _claim("EVENT", "C1", {"scheduled_start": "2026-09-06T19:00:00Z", "environment": "outdoor", "pass_defense": 0.98, "rush_defense": 1.02}),
        _claim("MARKET_DEFINITION", "prizepicks|CFB|pass_yds|FULL_GAME", {"definition_verified": True}),
        _claim("OFFER", "cfb-pass", {"offer_recorded": True}),
    ]
    cfb_snap = build_parameter_snapshot(cfb_row, cfb_claims)
    assert cfb_snap["production_eligible"] is True
    assert cfb_snap["blocker"] is None


def test_skill_receptions_path_from_fixture():
    wr = FootballReferenceGameLogAdapter().fetch_normalize({"html": _html("pfr_gamelog_wr.html"), "league": "NFL"})
    row = {
        "sportFamily": "gridiron", "league": "NFL", "eventId": "E1", "playerId": "NFL_WR_001",
        "teamId": "KC", "projectionId": "pp-rec", "market": "receptions", "role": "WR",
    }
    claims = [
        _claim("PLAYER", "NFL_WR_001", {
            "status": "ACTIVE", "role": "WR", "game_logs": wr["logs"],
            "opportunity": {"support_n": len(wr["logs"])}, "efficiency": {"support_n": len(wr["logs"])},
        }),
        _claim("TEAM", "KC", {"plays": 65, "pass_rate": 0.6, "pace": 1.0, "pass_defense": 1.0, "rush_defense": 1.0}),
        _claim("EVENT", "E1", {"pass_defense": 1.0, "rush_defense": 1.0, "scheduled_start": "2026-09-07T17:00:00Z"}),
        _claim("MARKET_DEFINITION", "prizepicks|NFL|receptions|FULL_GAME", {"definition_verified": True}),
        _claim("OFFER", "pp-rec", {"offer_recorded": True}),
    ]
    snap = build_parameter_snapshot(row, claims)
    assert snap["production_eligible"] is True
    assert snap["parameters"]["catch_rate"] > 0
    worlds_rng = __import__("random").Random(7)
    world = sample_football(worlds_rng, "WR", snap["parameters"])
    assert value_from_stats("receptions", world) == world["receptions"]
    assert value_from_stats("rec_yds", world) == world["rec_yds"]


def test_production_capable_only_full_path_markets():
    active_19 = (
        "pass_yds", "pass_att", "pass_cmp", "pass_td", "interceptions",
        "rush_yds", "rush_att", "rush_td", "rec_yds", "receptions", "rec_td",
        "targets", "pass_rush_yds", "rush_rec_yds", "rush_rec_td", "pass_rush_td",
        "fg_made", "xp_made", "kicking_pts",
    )
    for league in ("NFL", "CFB"):
        for market in active_19:
            assert selection_state("gridiron", league, market) == PRODUCTION
        assert selection_state("gridiron", league, "def_tackles") == UNSUPPORTED
        assert selection_state("gridiron", league, "air_yards") == UNSUPPORTED
    assert selection_state("gridiron", "CFL", "pass_yds") == UNSUPPORTED
    assert selection_state("gridiron", "NFLP", "pass_yds") != PRODUCTION
    manifest = lookup("gridiron")
    assert manifest.plugin_version == "1.3.0"
    assert "CFL_REBOOT" in manifest.known_unsupported
    assert "LONGEST_PLAY_MARKETS" in manifest.known_unsupported
    assert "FANTASY_UNVERSIONED" in manifest.known_unsupported


def test_missing_opponent_defense_blocks_playable_snapshot():
    logs = normalize_gridiron_logs(_qb_logs())["logs"]
    row = {
        "sportFamily": "gridiron", "league": "NFL", "eventId": "E1", "playerId": "NFL_QB_001",
        "teamId": "KC", "projectionId": "pp-pass", "market": "pass_yds", "role": "QB",
    }
    claims = [
        _claim("PLAYER", "NFL_QB_001", {
            "status": "ACTIVE", "role": "QB", "game_logs": logs,
            "opportunity": {"support_n": 8}, "efficiency": {"support_n": 8},
        }),
        _claim("TEAM", "KC", {"plays": 65, "pass_rate": 0.58, "pace": 1.0}),
        _claim("EVENT", "E1", {"scheduled_start": "2026-09-07T17:00:00Z"}),
        _claim("MARKET_DEFINITION", "prizepicks|NFL|pass_yds|FULL_GAME", {"definition_verified": True}),
        _claim("OFFER", "pp-pass", {"offer_recorded": True}),
    ]
    snap = build_parameter_snapshot(row, claims)
    assert snap["production_eligible"] is False
    assert snap["blocker"] == "OPPONENT_PASS_DEFENSE"


def test_fixture_pass_yards_offer_derived_from_primitive_ledger():
    """One-line demo: a fixture NFL pass-yards offer equals ledger pass_yds."""
    built = build_nfl_game()
    assert derive_market(built.ledger.values_for("NFL_QB_001"), "pass_yds") == built.ledger.values_for("NFL_QB_001")["pass_yds"]


def test_cfb_attempt_markets_are_opportunity_only_for_model_support():
    logs = normalize_gridiron_logs(_qb_logs(2))["logs"]
    support = assess_football_support(
        market="pass_att",
        role="QB",
        status="ACTIVE",
        logs=logs,
        definition_verified=True,
        team_event={
            "playsObserved": True,
            "paceObserved": True,
            "pass_defense": None,
            "rush_defense": None,
        },
    )
    assert support["modelable"] is True
    assert support["efficiencyFields"] == []
    assert support["playableSupport"] is False
    assert "PLAYABLE_OPPORTUNITY_SUPPORT_LT3" in support["playableBlockers"]


def test_cfb_yardage_market_can_model_thin_but_not_playable():
    logs = normalize_gridiron_logs(_qb_logs(1))["logs"]
    support = assess_football_support(
        market="pass_yds",
        role="QB",
        status="ACTIVE",
        logs=logs,
        definition_verified=True,
        team_event={
            "playsObserved": True,
            "paceObserved": True,
            "pass_defense": 1.0,
            "rush_defense": 1.0,
        },
    )
    assert support["modelable"] is True
    assert support["playableSupport"] is False
    assert support["opportunitySupportN"] == 1
    assert support["efficiencySupportN"] == 1


def test_cfb_market_support_holds_zero_history_for_research():
    support = assess_football_support(
        market="rush_yds",
        role="RB",
        status="ACTIVE",
        logs=[],
        definition_verified=True,
        team_event={
            "playsObserved": True,
            "paceObserved": True,
            "pass_defense": 1.0,
            "rush_defense": 1.0,
        },
    )
    assert support["modelable"] is False
    assert "MINIMUM_OPPORTUNITY_SUPPORT_MISSING" in support["modelBlockers"]


def test_cfb_blowout_regime_is_explicit_not_directional():
    model = TeamEventModel().fit(
        {"plays": 72, "pass_rate": 0.55, "pace": 1.0},
        {"spread": -28.5, "game_total": 55.5},
        {"pass_defense": 0.98, "rush_defense": 1.02},
        league="CFB",
        market="pass_yds",
    )
    weights = model["event_regime_weights"]
    assert set(weights) == {"competitive", "controlled_lead", "blowout"}
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert weights["blowout"] > 0.05
    assert model["starter_curtailment"]["blowout"] < 1.0


def test_cfb_role_state_transfer_and_promoted_are_not_returning_starters():
    transfer = resolve_cfb_role_state({
        "role": "QB",
        "depth_chart_role": "starter",
        "previous_school": "OLD",
        "prior_season_starts": 10,
    }, role="QB")
    assert transfer["primary"] == "TRANSFER_STARTER"
    assert transfer["transferOpportunityCarryoverAllowed"] is False

    promoted = resolve_cfb_role_state({
        "role": "RB",
        "depth_chart_role": "starter",
        "prior_role": "backup",
        "prior_season_starts": 1,
    }, role="RB")
    assert promoted["primary"] == "PROMOTED_STARTER"

    unknown = resolve_cfb_role_state({"role": "WR"}, role="WR")
    assert unknown["primary"] == "ROLE_UNCERTAIN"
    assert unknown["resolved"] is False
