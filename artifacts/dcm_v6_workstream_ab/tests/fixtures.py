from dcm.platform.prizepicks.entry_contract import pick
from dcm.platform.prizepicks.payouts import DEMO_MG_TABLE_HASH
from dcm.platform.prizepicks.reboot import ParticipationFacts
from dcm.sports.basketball.minimal import build_basketball_world
from dcm.sports.football.ledger import FootballPlayerSpec, TeamOpportunityPool, build_football_world
from dcm.sports.football.registry import CFB_LEAGUE, NFL_LEAGUE


def nfl_home_pool() -> TeamOpportunityPool:
    return TeamOpportunityPool(
        team_id="HOME",
        off_plays=65,
        pass_att=35,
        designed_rush_att=25,
        sacks_taken=3,
        scramble_att=2,
        targets=35,
    )


def nfl_players() -> list[FootballPlayerSpec]:
    return [
        FootballPlayerSpec("NFL_QB_001", "HOME", "QB", {
            "off_snaps": 65, "routes": 0, "targets": 0, "dropbacks": 40,
            "pass_att": 35, "designed_rush_att": 2, "scramble_att": 2,
        }, {"cmp_rate": 0.65, "ypa": 7.2, "pass_td_rate": 0.05, "int_rate": 0.02, "ypc": 5.0, "scramble_ypc": 7.0, "sack_yds_per": 6.0}),
        FootballPlayerSpec("NFL_WR_001", "HOME", "WR", {
            "off_snaps": 58, "routes": 32, "targets": 10, "dropbacks": 0,
            "pass_att": 0, "designed_rush_att": 0, "scramble_att": 0,
        }, {"catch_rate": 0.6, "ypt": 9.0, "rec_td_rate": 0.08}),
        FootballPlayerSpec("NFL_WR_002", "HOME", "WR", {
            "off_snaps": 50, "routes": 28, "targets": 8, "dropbacks": 0,
            "pass_att": 0, "designed_rush_att": 0, "scramble_att": 0,
        }, {"catch_rate": 0.7, "ypt": 8.0, "rec_td_rate": 0.05}),
        FootballPlayerSpec("NFL_TE_001", "HOME", "TE", {
            "off_snaps": 45, "routes": 20, "targets": 7, "dropbacks": 0,
            "pass_att": 0, "designed_rush_att": 0, "scramble_att": 0,
        }, {"catch_rate": 0.7, "ypt": 7.0, "rec_td_rate": 0.06}),
        FootballPlayerSpec("NFL_RB_001", "HOME", "RB", {
            "off_snaps": 40, "routes": 12, "targets": 6, "dropbacks": 0,
            "pass_att": 0, "designed_rush_att": 21, "scramble_att": 0,
        }, {"catch_rate": 0.8, "ypt": 6.0, "ypc": 4.4, "rush_td_rate": 0.04, "rec_td_rate": 0.02}),
        FootballPlayerSpec("NFL_WR_003", "HOME", "WR", {
            "off_snaps": 20, "routes": 10, "targets": 4, "dropbacks": 0,
            "pass_att": 0, "designed_rush_att": 2, "scramble_att": 0,
        }, {"catch_rate": 0.5, "ypt": 11.0, "ypc": 8.0}),
        FootballPlayerSpec("NFL_K_001", "HOME", "K", {
            "off_snaps": 0, "routes": 0, "targets": 0, "dropbacks": 0,
            "pass_att": 0, "designed_rush_att": 0, "scramble_att": 0,
            "fg_att": 2, "xp_att": 3,
        }, {"fg_rate": 0.8, "xp_rate": 1.0}),
        FootballPlayerSpec("NFL_DEF_001", "HOME", "DEF", {
            "off_snaps": 0, "routes": 0, "targets": 0, "dropbacks": 0,
            "pass_att": 0, "designed_rush_att": 0, "scramble_att": 0,
        }, {"def_tackles": 7.0, "def_sacks": 1.0}),
    ]


def build_nfl_game(event_id="NFL_GAME_1"):
    return build_football_world(
        event_id=event_id,
        league=NFL_LEAGUE,
        teams={"HOME": nfl_home_pool()},
        players=nfl_players(),
    )


def build_cfb_game(event_id="CFB_GAME_1"):
    players = []
    for spec in nfl_players():
        pid = spec.player_id.replace("NFL_", "CFB_")
        if pid == "CFB_WR_002":
            pid = "CFB_WR_UNLISTED"
        players.append(FootballPlayerSpec(pid, spec.team_id, spec.role, spec.opportunity, spec.rates))
    return build_football_world(
        event_id=event_id,
        league=CFB_LEAGUE,
        teams={"HOME": nfl_home_pool()},
        players=players,
    )


def legal_bball_stats():
    # 2PA = FGA-3PA = 12, FGM = 5+3=8, REB=2+6=8, PTS=2*5+3*3+4=10+9+4=23
    return {
        "minutes": 34.0,
        "fga": 18.0,
        "tpa": 6.0,
        "twopa": 12.0,
        "fgm": 8.0,
        "tpm": 3.0,
        "twopm": 5.0,
        "fta": 5.0,
        "ftm": 4.0,
        "oreb": 2.0,
        "dreb": 6.0,
        "reb": 8.0,
        "ast": 6.0,
        "stl": 1.0,
        "blk": 1.0,
        "tov": 2.0,
        "pts": 23.0,
    }


def build_nba_game(event_id="NBA_GAME_1", player_id="NBA_P_001", team_id="BOS"):
    return build_basketball_world(
        event_id=event_id,
        league="NBA",
        player_id=player_id,
        team_id=team_id,
        stats=legal_bball_stats(),
    )


def played(**kwargs) -> ParticipationFacts:
    base = dict(status="PLAYED", role="WR", opportunity_count=50.0)
    base.update(kwargs)
    return ParticipationFacts(**base)


MG_HASH = DEMO_MG_TABLE_HASH


def nfl_pick(pid, player, market, line, side="MORE", modifier="STANDARD", team="HOME", event="NFL_GAME_1"):
    return pick(
        projection_id=pid,
        player_id=player,
        team_id=team,
        event_id=event,
        market=market,
        line=line,
        side=side,
        modifier=modifier,
        league="NFL",
        stat_key=market,
    )
