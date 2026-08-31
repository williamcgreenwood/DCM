from __future__ import annotations

from dcm.research.coverage import coverage_report


def _claim(scope: str, scope_id: str, value: dict) -> dict:
    return {
        "semantic_scope": scope,
        "scope_id": scope_id,
        "claim_value": value,
    }


def test_player_coverage_requires_status_role_logs_and_model_inputs():
    requests = [{
        "request_id": "REQ_P",
        "scope": "PLAYER",
        "scope_id": "P1",
        "need": "status_role_logs_opportunity_efficiency",
    }]
    bad = coverage_report(requests, [_claim("PLAYER", "P1", {"status": "ACTIVE"})])
    assert bad["complete"] is False
    missing = bad["requests"][0]["missing"]
    assert "PLAYER_ROLE" in missing
    assert "ROLE_COMPARABLE_GAME_LOGS_MIN_3" in missing
    assert "OPPORTUNITY_EVIDENCE" in missing
    assert "EFFICIENCY_EVIDENCE" in missing

    good = coverage_report(
        requests,
        [_claim("PLAYER", "P1", {
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": [{"minutes": 30}, {"minutes": 32}, {"minutes": 34}],
            "opportunity": {"support_n": 3},
            "efficiency": {"support_n": 3},
        })],
    )
    assert good["complete"] is True


def test_market_coverage_requires_verified_definition():
    requests = [{
        "request_id": "REQ_M",
        "scope": "MARKET",
        "scope_id": "M1",
        "need": "definition_line_history",
    }]
    bad = coverage_report(requests, [_claim("MARKET", "M1", {"definition_verified": False})])
    assert bad["complete"] is False
    assert "VERIFIED_MARKET_DEFINITION" in bad["requests"][0]["missing"]

    good = coverage_report(requests, [_claim("MARKET", "M1", {"definition_verified": True})])
    assert good["complete"] is True


def test_player_object_exists_is_not_coverage():
    requests = [{
        "request_id": "REQ_P",
        "scope": "PLAYER",
        "scope_id": "P1",
        "need": "status_role_logs_opportunity_efficiency",
        "sportFamily": "basketball",
        "league": "WNBA",
        "market": "pts",
    }]
    # A PLAYER object / identity shell is not evidence coverage.
    report = coverage_report(requests, [_claim("PLAYER", "P1", {"playerId": "P1", "playerName": "Paige"})])
    assert report["complete"] is False
    missing = report["requests"][0]["missing"]
    assert "PLAYER_STATUS" in missing
    assert "PLAYER_ROLE" in missing
    assert "ROLE_COMPARABLE_GAME_LOGS_MIN_3" in missing


def test_points_market_incomplete_without_fga_or_pts():
    requests = [{
        "request_id": "REQ_P",
        "scope": "PLAYER",
        "scope_id": "P1",
        "need": "status_role_logs_opportunity_efficiency",
        "sportFamily": "basketball",
        "league": "WNBA",
        "market": "pts",
    }]
    logs = [{"minutes": 30, "reb": 4, "ast": 6} for _ in range(3)]
    report = coverage_report(requests, [_claim("PLAYER", "P1", {
        "status": "ACTIVE",
        "role": "starter",
        "game_logs": logs,
        "opportunity": {"support_n": 3},
        "efficiency": {"support_n": 3},
    })])
    assert report["complete"] is False
    assert "MARKET_STAT_PTS" in report["requests"][0]["missing"]

    good_logs = [{"minutes": 30, "pts": 18, "fga": 14, "reb": 4, "ast": 6} for _ in range(3)]
    good = coverage_report(requests, [_claim("PLAYER", "P1", {
        "status": "ACTIVE",
        "role": "starter",
        "game_logs": good_logs,
        "opportunity": {"support_n": 3},
        "efficiency": {"support_n": 3},
    })])
    assert good["complete"] is True


def test_pra_requires_minutes_pts_reb_ast():
    requests = [{
        "request_id": "REQ_P",
        "scope": "PLAYER",
        "scope_id": "P1",
        "need": "status_role_logs_opportunity_efficiency",
        "sportFamily": "basketball",
        "league": "WNBA",
        "market": "pra",
    }]
    incomplete = coverage_report(requests, [_claim("PLAYER", "P1", {
        "status": "ACTIVE",
        "role": "starter",
        "game_logs": [{"minutes": 30, "pts": 18} for _ in range(3)],
        "opportunity": {"support_n": 3},
        "efficiency": {"support_n": 3},
    })])
    assert incomplete["complete"] is False
    assert "MARKET_STAT_PRA" in incomplete["requests"][0]["missing"]

    complete = coverage_report(requests, [_claim("PLAYER", "P1", {
        "status": "ACTIVE",
        "role": "starter",
        "game_logs": [{"minutes": 30, "pts": 18, "reb": 4, "ast": 6} for _ in range(3)],
        "opportunity": {"support_n": 3},
        "efficiency": {"support_n": 3},
    })])
    assert complete["complete"] is True


def test_football_player_path_not_subject_to_basketball_market_codes():
    requests = [{
        "request_id": "REQ_P",
        "scope": "PLAYER",
        "scope_id": "QB1",
        "need": "status_role_logs_opportunity_efficiency",
        "sportFamily": "gridiron",
        "league": "NFL",
        "market": "pass_yds",
    }]
    logs = [{"pass_att": 34, "rush_att": 4} for _ in range(3)]
    report = coverage_report(requests, [_claim("PLAYER", "QB1", {
        "status": "ACTIVE",
        "role": "QB",
        "game_logs": logs,
        "opportunity": {"support_n": 3},
        "efficiency": {"support_n": 3},
    })])
    assert report["complete"] is True
    missing = report["requests"][0]["missing"]
    assert "MARKET_STAT_PTS" not in missing
    assert "GAMELOG_MINUTES" not in missing

