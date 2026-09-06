from __future__ import annotations

from dcm.model.parameters import build_parameter_snapshot
from dcm.research.coverage import coverage_report, evaluate_request
from dcm.research.gamelog import (
    CANONICAL_BASKETBALL_FIELDS,
    assert_compatible_basketball_logs,
    normalize_basketball_log,
    normalize_basketball_logs,
)
from dcm.research.role_epoch import RoleEpochBuilder


def _player_request(**extra) -> dict:
    rec = {
        "request_id": "REQ_P",
        "scope": "PLAYER",
        "scope_id": "P1",
        "need": "status_role_logs_opportunity_efficiency",
        "sportFamily": "basketball",
        "league": "WNBA",
    }
    rec.update(extra)
    return rec


def _player_claim(value: dict) -> dict:
    return {"semantic_scope": "PLAYER", "scope_id": "P1", "claim_value": value}


def _base_row(**kwargs) -> dict:
    row = {
        "sportFamily": "basketball",
        "league": "WNBA",
        "eventId": "E",
        "playerId": "P",
        "teamId": "T",
        "projectionId": "X",
        "market": "pts",
        "role": "G",
    }
    row.update(kwargs)
    return row


def _claim(scope: str, scope_id: str, value: dict, h: str = "h") -> dict:
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


def test_br_style_mp_normalizes_minutes_reb_ast():
    got = normalize_basketball_log({"mp": 32, "pts": 11, "reb": 1, "ast": 6}, league="WNBA")
    assert got is not None
    assert got["minutes"] == 32
    assert got["pts"] == 11
    assert got["reb"] == 1
    assert got["ast"] == 6
    assert got["mp_raw"] == 32
    assert "fga" not in got  # do not invent FGA from PTS
    assert "minutes" in CANONICAL_BASKETBALL_FIELDS


def test_mp_clock_string_parses_to_minutes():
    colon = normalize_basketball_log({"MP": "32:00"}, league="WNBA")
    assert colon is not None
    assert colon["minutes"] == 32
    plain = normalize_basketball_log({"MP": "32"}, league="WNBA")
    assert plain is not None
    assert plain["minutes"] == 32
    half = normalize_basketball_log({"mp": "32:30"}, league="WNBA")
    assert half is not None
    assert abs(half["minutes"] - 32.5) < 1e-9
    bad = normalize_basketball_log({"MP": "DNP"}, league="WNBA")
    assert bad is None


def test_normalize_logs_rejects_missing_minutes_without_inventing_fga():
    batch = normalize_basketball_logs(
        [
            {"mp": 32, "pts": 11, "reb": 1, "ast": 6},
            {"pts": 20, "reb": 4, "ast": 3},
            "not-a-row",
        ],
        league="WNBA",
    )
    assert len(batch["logs"]) == 1
    assert batch["logs"][0]["minutes"] == 32
    assert "fga" not in batch["logs"][0]
    assert len(batch["rejected"]) == 2
    assert batch["reasonCounts"]["GAMELOG_MINUTES"] == 1
    assert batch["reasonCounts"]["NOT_A_DICT"] == 1


def test_coverage_mp_plus_ast_is_complete_for_ast_market():
    logs = [{"mp": 32, "pts": 11, "reb": 1, "ast": 6} for _ in range(3)]
    compat = assert_compatible_basketball_logs(logs, market="ast")
    assert compat["valid_n"] == 3
    assert compat["complete"] is True
    report = coverage_report(
        [_player_request(market="ast")],
        [_player_claim({
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": logs,
            "opportunity": {"support_n": 3},
            "efficiency": {"support_n": 3},
        })],
    )
    assert report["complete"] is True
    assert "ROLE_COMPARABLE_GAME_LOGS_MIN_3" not in report["requests"][0]["missing"]
    assert "GAMELOG_MINUTES" not in report["requests"][0]["missing"]
    assert "MARKET_STAT_AST" not in report["requests"][0]["missing"]


def test_coverage_mp_pts_without_ast_misses_market_stat_ast():
    logs = [{"mp": 30, "pts": 18} for _ in range(3)]
    report = coverage_report(
        [_player_request(market="ast")],
        [_player_claim({
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": logs,
            "opportunity": {"support_n": 3},
            "efficiency": {"support_n": 3},
        })],
    )
    assert report["complete"] is False
    assert "MARKET_STAT_AST" in report["requests"][0]["missing"]
    # minutes still normalize from mp
    assert "GAMELOG_MINUTES" not in report["requests"][0]["missing"]


def test_coverage_three_dicts_without_minutes_still_incomplete():
    logs = [{"pts": 11, "reb": 1, "ast": 6} for _ in range(3)]
    report = coverage_report(
        [_player_request(market="pts")],
        [_player_claim({
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": logs,
            "opportunity": {"support_n": 3},
            "efficiency": {"support_n": 3},
        })],
    )
    assert report["complete"] is False
    missing = report["requests"][0]["missing"]
    assert "ROLE_COMPARABLE_GAME_LOGS_MIN_3" in missing or "GAMELOG_MINUTES" in missing
    row = evaluate_request(_player_request(market="pts"), [_player_claim({
        "status": "ACTIVE",
        "role": "starter",
        "game_logs": logs,
        "opportunity": {"support_n": 3},
        "efficiency": {"support_n": 3},
    })])
    assert row["complete"] is False


def _snapshot_for_logs(logs: list[dict], support_n: int | None = None) -> dict:
    opp: dict = {}
    if support_n is not None:
        opp["support_n"] = support_n
    claims = [
        _claim("PLAYER", "P", {
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": logs,
            "opportunity": opp,
            "efficiency": {"support_n": 3},
        }, "p"),
        _claim("TEAM", "T", {"pace_multiplier": 1.0}, "t"),
        _claim("EVENT", "E", {"venue": "X"}, "e"),
        _claim("MARKET", "X", {"definition_verified": True}, "m"),
    ]
    return build_parameter_snapshot(_base_row(), claims)


def test_parameters_mp_logs_drive_minutes_not_wnba_prior():
    with_shots = [
        {"mp": 32, "pts": 11, "reb": 1, "ast": 6, "fga": 10, "tpa": 4, "fta": 2}
        for _ in range(3)
    ]
    snap = _snapshot_for_logs(with_shots)
    support = snap["parameters"]["_log_support"]
    assert support["opportunitySupportFromLogs"] >= 3
    assert support["evidenceUsed"] is True
    assert support["minutesSource"] == "LOGS"
    assert abs(snap["parameters"]["minutes_mean"] - 32.0) < 1e-9
    assert snap["parameters"]["minutes_mean"] != 31.0
    assert snap["opportunity"]["support_n"] >= 3
    # fga present -> not the generic 0.55 prior
    assert abs(snap["parameters"]["fga_per_min"] - 0.55) > 1e-6

    without_shots = [{"mp": 32, "pts": 11, "reb": 1, "ast": 6} for _ in range(3)]
    snap_no = _snapshot_for_logs(without_shots)
    assert abs(snap_no["parameters"]["minutes_mean"] - 32.0) < 1e-9
    assert snap_no["parameters"]["minutes_mean"] != 31.0
    assert snap_no["parameters"]["_log_support"]["opportunitySupportFromLogs"] >= 3
    # fga/tpa/fta absent: efficiency rates stay labeled priors, minutes still from logs
    assert abs(snap_no["parameters"]["fga_per_min"] - 0.55) < 1e-9
    assert abs(snap_no["parameters"]["three_pa_share"] - 0.42) < 1e-9
    assert abs(snap_no["parameters"]["fta_per_min"] - 0.18) < 1e-9


def test_parameters_empty_logs_use_labeled_prior_not_log_support():
    snap = _snapshot_for_logs([], support_n=5)
    support = snap["parameters"]["_log_support"]
    assert support["evidenceUsed"] is False
    assert support["opportunitySupportFromLogs"] == 0
    assert support["minutesSource"] == "PRIOR"
    assert abs(snap["parameters"]["minutes_mean"] - 31.0) < 1e-9
    assert snap["opportunity"]["support_n"] == 0
    assert snap["production_eligible"] is False
    assert snap["blocker"] == "INSUFFICIENT_OPPORTUNITY_SAMPLE"


def test_role_epoch_builder_sees_minutes_after_mp_alias():
    built = RoleEpochBuilder().build({
        "role_epoch_logs": [
            {"mp": 32, "role": "starter"},
            {"mp": 12, "role": "bench"},
            {"mp": 28, "role": "starter", "teammate_out": True},
        ]
    })
    assert built["invented"] is False
    assert built["log_count"] == 3
    starter = built["partitions"]["starter"]
    assert starter and starter[0].get("minutes") == 32
