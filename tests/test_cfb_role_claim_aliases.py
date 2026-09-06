"""CFB role resolver must read common host claim field aliases."""

from __future__ import annotations

from dcm.sports.football.cfb_role import resolve_cfb_role_state


def test_returning_starter_from_prior_season_and_qb1_opportunity() -> None:
    state = resolve_cfb_role_state(
        {
            "role": "QB",
            "opportunity": {"pass_attempts_role": "QB1", "snap_share_expected": "starter_majority"},
            "priorSeason_2025": {"games": 12, "starts": 12},
        }
    )
    assert state["resolved"] is True
    assert state["primary"] == "RETURNING_STARTER"
    assert state["priorSeasonStarts"] == 12.0


def test_role_alone_stays_uncertain() -> None:
    state = resolve_cfb_role_state({"role": "QB", "status": "ACTIVE"})
    assert state["resolved"] is False
    assert state["primary"] == "ROLE_UNCERTAIN"


def test_game_log_count_can_bound_prior_starts() -> None:
    logs = [{"date": f"2025-09-{i:02d}", "pass_att": 25 + i} for i in range(1, 9)]
    state = resolve_cfb_role_state(
        {
            "role": "QB",
            "opportunity": {"pass_attempts_role": "QB1"},
            "game_logs": logs,
        }
    )
    assert state["priorSeasonStarts"] == 8.0
    assert state["resolved"] is True
    assert state["primary"] in {"RETURNING_STARTER", "PROMOTED_STARTER", "NEW_QB"}
