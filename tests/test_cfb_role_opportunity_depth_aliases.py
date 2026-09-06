"""Opportunity depth_chart / role strings must feed CFB role-state resolver."""

from __future__ import annotations

from dcm.sports.football.cfb_role import resolve_cfb_role_state


def test_starting_qb_opportunity_role_resolves() -> None:
    state = resolve_cfb_role_state(
        {
            "role": "QB",
            "opportunity": {"role": "starting_QB", "pass_att_share": "primary"},
            "game_logs": [{"date": f"2025-09-{i:02d}", "pass_att": 30} for i in range(1, 13)],
        }
    )
    assert state["resolved"] is True
    assert state["primary"] == "RETURNING_STARTER"


def test_featured_rb_depth_chart_rb1() -> None:
    state = resolve_cfb_role_state(
        {
            "role": "RB",
            "opportunity": {"depth_chart": "RB1", "role": "featured_RB"},
            "season2025_observed": {"games": 9, "rushAtt": 101},
            "game_logs": [{"date": f"2025-09-{i:02d}", "rush_att": 12} for i in range(1, 9)],
        }
    )
    assert state["resolved"] is True
    assert state["primary"] == "RETURNING_STARTER"
    assert state["priorSeasonStarts"] == 9.0


def test_wr_rotation_opportunity_role() -> None:
    state = resolve_cfb_role_state(
        {
            "role": "WR",
            "opportunity": {"role": "WR_rotation"},
            "game_logs": [{"date": f"2025-09-{i:02d}", "receptions": 3} for i in range(1, 12)],
        }
    )
    assert state["resolved"] is True
    assert state["primary"] == "RETURNING_ROTATION"


def test_bare_position_still_uncertain() -> None:
    state = resolve_cfb_role_state({"role": "WR", "status": "ACTIVE"})
    assert state["resolved"] is False
    assert state["primary"] == "ROLE_UNCERTAIN"
