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
