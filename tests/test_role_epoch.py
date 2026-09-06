"""P2 RoleEpochBuilder: change-points, comparable sample, hierarchical shrink."""
from __future__ import annotations

from dcm.model.parameters import build_parameter_snapshot
from dcm.research.role_epoch import BUILDER_ID, RoleEpochBuilder, detect_change_points, shrinkage_weights


def _bench_to_starter_logs(n_bench=20, n_starter=17):
    logs = []
    for i in range(n_bench):
        logs.append({
            "date": f"2026-05-{(i % 28) + 1:02d}",
            "minutes": 12.0,
            "gs": 0,
            "role": "bench",
            "pts": 4,
            "reb": 1,
            "ast": 1,
            "fga": 4,
            "tpa": 1,
            "fta": 1,
        })
    for i in range(n_starter):
        logs.append({
            "date": f"2026-06-{(i % 28) + 1:02d}",
            "minutes": 32.0,
            "gs": 1,
            "role": "starter",
            "pts": 18,
            "reb": 5,
            "ast": 4,
            "fga": 14,
            "tpa": 5,
            "fta": 3,
        })
    return logs


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


def _row(**kwargs):
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


def test_builder_id_is_not_stub():
    assert "stub" not in BUILDER_ID.lower()
    assert "stub" not in RoleEpochBuilder.builder.lower()
    built = RoleEpochBuilder().build({"game_logs": [{"minutes": 30, "gs": 1}] * 5, "role": "starter"})
    assert built["builder"] == BUILDER_ID
    assert "stub" not in built["builder"].lower()
    assert built["invented"] is False


def test_change_point_bench_to_starter_37():
    minutes = [12.0] * 20 + [32.0] * 17
    assert len(minutes) == 37
    cuts = detect_change_points(minutes)
    assert 0 in cuts
    assert 20 in cuts
    logs = _bench_to_starter_logs(20, 17)
    assert len(logs) == 37
    built = RoleEpochBuilder().build(
        {"game_logs": logs, "role": "starter", "league": "WNBA"},
        today_context={"role": "starter", "league": "WNBA"},
    )
    assert built["invented"] is False
    assert built["log_count"] == 37
    labels = [e["label"] for e in built["epochs"]]
    assert "bench" in labels
    assert "starter" in labels
    starter_epochs = [e for e in built["epochs"] if e["label"] == "starter"]
    assert starter_epochs
    assert starter_epochs[-1]["n"] == 17
    assert starter_epochs[-1]["start"] == 20
    assert starter_epochs[-1]["end"] == 37
    assert built["selected_epoch"]["label"] == "starter"
    assert built["support_n"] == 17
    assert abs(sum(r["minutes"] for r in built["comparable_logs"]) / 17 - 32.0) < 1e-9
    assert built["shrinkage"]["priorWeight"] < shrinkage_weights(3, 3)["priorWeight"]
    assert built["shrinkage"]["roleWeight"] > shrinkage_weights(3, 37)["roleWeight"]


def test_thin_support_raises_prior_weight():
    thin = shrinkage_weights(3, 3)
    thick = shrinkage_weights(30, 30)
    assert thin["priorWeight"] > thick["priorWeight"]
    assert thick["roleWeight"] > thin["roleWeight"]
    assert abs(thin["roleWeight"] + thin["seasonWeight"] + thin["priorWeight"] - 1.0) < 1e-12
    logs = [{"minutes": 32.0, "gs": 1, "role": "starter"} for _ in range(2)]
    built = RoleEpochBuilder().build({"game_logs": logs, "role": "starter"}, today_context={"role": "starter"})
    assert built["support_n"] == 2
    assert built["shrinkage"]["priorWeight"] > shrinkage_weights(17, 37)["priorWeight"]


def test_parameters_use_role_comparable_minutes_when_epochs_exist():
    logs = _bench_to_starter_logs(20, 17)
    claims = [
        _claim("PLAYER", "P", {
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": logs,
            "opportunity": {"support_n": 17},
            "efficiency": {"support_n": 17},
        }, "p"),
        _claim("TEAM", "T", {"pace_multiplier": 1.0}, "t"),
        _claim("EVENT", "E", {"venue": "X"}, "e"),
        _claim("MARKET", "X", {"definition_verified": True}, "m"),
    ]
    snap = build_parameter_snapshot(_row(), claims)
    assert snap["parameters"]["_log_support"]["evidenceUsed"] is True
    assert snap["parameters"]["_log_support"]["opportunitySupportFromLogs"] == 17
    assert abs(snap["parameters"]["minutes_mean"] - 32.0) < 1e-9
    # Mixed-season mean would be (20*12 + 17*32)/37 ≈ 21.19 — must not use that.
    mixed = (20 * 12.0 + 17 * 32.0) / 37.0
    assert abs(snap["parameters"]["minutes_mean"] - mixed) > 5.0
    assert snap["role_epoch"]["builder"] == BUILDER_ID
    assert "stub" not in snap["role_epoch"]["builder"].lower()
    assert snap["roleWeight"] > 0
    assert snap["priorWeight"] >= 0
    assert abs(snap["roleWeight"] + snap["playerWeight"] + snap["priorWeight"] - 1.0) < 1e-9


def test_thin_role_sample_does_not_set_evidence_used():
    logs = (
        [{"minutes": 12.0, "gs": 0, "role": "bench", "fga": 4, "reb": 1, "ast": 1} for _ in range(30)]
        + [{"minutes": 30.0, "gs": 1, "role": "starter", "fga": 12, "reb": 4, "ast": 3} for _ in range(2)]
    )
    claims = [
        _claim("PLAYER", "P", {
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": logs,
            "opportunity": {"support_n": 32},
            "efficiency": {"support_n": 32},
        }, "p"),
        _claim("TEAM", "T", {"pace_multiplier": 1.0}, "t"),
        _claim("EVENT", "E", {"venue": "X"}, "e"),
        _claim("MARKET", "X", {"definition_verified": True}, "m"),
    ]
    snap = build_parameter_snapshot(_row(), claims)
    assert snap["parameters"]["_log_support"]["opportunitySupportFromLogs"] == 2
    assert snap["parameters"]["_log_support"]["evidenceUsed"] is False
    assert snap["priorWeight"] > snap["roleWeight"]
    thick = build_parameter_snapshot(_row(), [
        _claim("PLAYER", "P", {
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": _bench_to_starter_logs(5, 30),
            "opportunity": {},
            "efficiency": {},
        }, "p"),
        _claim("TEAM", "T", {"pace_multiplier": 1.0}, "t"),
        _claim("EVENT", "E", {"venue": "X"}, "e"),
        _claim("MARKET", "X", {"definition_verified": True}, "m"),
    ])
    assert thick["parameters"]["_log_support"]["evidenceUsed"] is True
    assert snap["priorWeight"] > thick["priorWeight"]


def test_does_not_invent_logs():
    built = RoleEpochBuilder().build({"role": "starter"})
    assert built["invented"] is False
    assert built["comparable_logs"] == []
    assert built["support_n"] == 0
    assert built["log_count"] == 0
    assert built["shrinkage"]["priorWeight"] == 1.0
