"""Valid worlds pass; corrupted worlds fail closed before settlement."""

from __future__ import annotations

from dataclasses import dataclass

from dcm.sports.football.conservation import evaluate_football_conservation
from dcm.sports.football.ledger import (
    ConservationError,
    FootballPlayerSpec,
    TeamOpportunityPool,
    build_football_world,
    corrupt_stat,
)
from dcm.sports.football.registry import NFL_LEAGUE


@dataclass(frozen=True)
class HarnessCase:
    name: str
    passed: bool
    detail: str


def _valid_spec() -> tuple[dict[str, TeamOpportunityPool], list[FootballPlayerSpec]]:
    home = TeamOpportunityPool(
        team_id="HOME",
        off_plays=65,
        pass_att=35,
        designed_rush_att=25,
        sacks_taken=3,
        scramble_att=2,
        targets=35,
    )
    qb = FootballPlayerSpec(
        player_id="NFL_QB_001",
        team_id="HOME",
        role="QB",
        opportunity={
            "off_snaps": 65,
            "routes": 0,
            "targets": 0,
            "dropbacks": 40,  # 35 att + 3 sacks + 2 scrambles
            "pass_att": 35,
            "designed_rush_att": 2,
            "scramble_att": 2,
        },
        rates={
            "cmp_rate": 0.65,
            "ypa": 7.2,
            "pass_td_rate": 0.05,
            "int_rate": 0.02,
            "ypc": 5.0,
            "scramble_ypc": 7.0,
            "sack_yds_per": 6.0,
        },
    )
    wr1 = FootballPlayerSpec(
        player_id="NFL_WR_001",
        team_id="HOME",
        role="WR",
        opportunity={
            "off_snaps": 58,
            "routes": 32,
            "targets": 10,
            "dropbacks": 0,
            "pass_att": 0,
            "designed_rush_att": 0,
            "scramble_att": 0,
        },
        rates={"catch_rate": 0.6, "ypt": 9.0, "rec_td_rate": 0.08},
    )
    wr2 = FootballPlayerSpec(
        player_id="NFL_WR_002",
        team_id="HOME",
        role="WR",
        opportunity={
            "off_snaps": 50,
            "routes": 28,
            "targets": 8,
            "dropbacks": 0,
            "pass_att": 0,
            "designed_rush_att": 0,
            "scramble_att": 0,
        },
        rates={"catch_rate": 0.7, "ypt": 8.0, "rec_td_rate": 0.05},
    )
    te = FootballPlayerSpec(
        player_id="NFL_TE_001",
        team_id="HOME",
        role="TE",
        opportunity={
            "off_snaps": 45,
            "routes": 20,
            "targets": 7,
            "dropbacks": 0,
            "pass_att": 0,
            "designed_rush_att": 0,
            "scramble_att": 0,
        },
        rates={"catch_rate": 0.7, "ypt": 7.0, "rec_td_rate": 0.06},
    )
    rb = FootballPlayerSpec(
        player_id="NFL_RB_001",
        team_id="HOME",
        role="RB",
        opportunity={
            "off_snaps": 40,
            "routes": 12,
            "targets": 6,
            "dropbacks": 0,
            "pass_att": 0,
            "designed_rush_att": 21,
            "scramble_att": 0,
        },
        rates={"catch_rate": 0.8, "ypt": 6.0, "ypc": 4.4, "rush_td_rate": 0.04, "rec_td_rate": 0.02},
    )
    wr3 = FootballPlayerSpec(
        player_id="NFL_WR_003",
        team_id="HOME",
        role="WR",
        opportunity={
            "off_snaps": 20,
            "routes": 10,
            "targets": 4,
            "dropbacks": 0,
            "pass_att": 0,
            "designed_rush_att": 2,
            "scramble_att": 0,
        },
        rates={"catch_rate": 0.5, "ypt": 11.0, "ypc": 8.0},
    )
    return {"HOME": home}, [qb, wr1, wr2, te, rb, wr3]


def run_football_harness() -> tuple[HarnessCase, ...]:
    cases: list[HarnessCase] = []
    teams, players = _valid_spec()
    built = build_football_world(event_id="NFL_HARNESS", league=NFL_LEAGUE, teams=teams, players=players)
    cases.append(HarnessCase("valid_world_builds", built.world.valid, built.ledger.content_hash))

    # Corruption: receptions > targets
    bad = corrupt_stat(built.ledger, "NFL_WR_001", "receptions", 99)
    results = evaluate_football_conservation(bad)
    failed = [r for r in results if not r.passed]
    cases.append(HarnessCase("corrupt_rec_gt_tgt_fails", any(r.rule_id == "REC_LE_TGT" for r in failed), str(len(failed))))

    # Corruption: team plays identity
    bad_plays = corrupt_stat(built.ledger, "HOME", "team_off_plays", 1)
    results = evaluate_football_conservation(bad_plays)
    failed = [r for r in results if not r.passed]
    cases.append(HarnessCase("corrupt_team_plays_fails", any(r.rule_id == "TEAM_PLAYS" for r in failed), str(len(failed))))

    # Corruption must not be silently accepted by builder when allow_invalid=False
    try:
        build_football_world(
            event_id="NFL_BAD",
            league=NFL_LEAGUE,
            teams=teams,
            players=players,
            extra_team_stats={"HOME": {"team_pass_yds": 9999, "team_rec_yds": 1, "team_off_plays": 65, "team_pass_att": 35, "team_rush_att": 27, "team_sacks_taken": 3, "team_designed_rush_att": 25, "team_dropbacks": 40, "team_targets": 35, "team_rush_yds": 0}},
        )
        cases.append(HarnessCase("builder_rejects_pass_rec_mismatch", False, "should have raised"))
    except ConservationError:
        cases.append(HarnessCase("builder_rejects_pass_rec_mismatch", True, "raised ConservationError"))

    return tuple(cases)
