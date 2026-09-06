"""Phase 11: NumPy EventWorld backend parity + portable reference fallback."""
from __future__ import annotations

import os

import pytest

from dcm.cfb.event_world_backend import (
    RNG_VERSION,
    resolve_event_world_backend,
)
from dcm.cfb.event_worlds import (
    simulate_cfb_event,
    simulate_joint_cfb_event_worlds,
    simulate_joint_cfb_event_worlds_reference,
)
from dcm.cfb.opportunity_ledger import (
    allocate_team_opportunity,
    allocate_team_opportunity_fast,
)
from dcm.model.distributions import from_worlds, from_worlds_reference


def _specs(n_players: int = 8) -> list[dict]:
    templates = [
        ("QB", {"role": "QB", "pass_att_mean": 32.0, "pass_att_sd": 4.0, "completion_rate": 0.62, "ypa": 7.2}),
        ("RB", {"role": "RB", "rush_att_mean": 16.0, "rush_att_sd": 3.0, "ypc": 4.4}),
        ("WR", {"role": "WR", "routes_mean": 9.0, "routes_sd": 2.0, "target_rate": 0.24, "catch_rate": 0.62}),
        ("WR", {"role": "WR", "routes_mean": 7.0, "routes_sd": 1.5, "target_rate": 0.20, "catch_rate": 0.58}),
        ("TE", {"role": "TE", "routes_mean": 5.0, "routes_sd": 1.2, "target_rate": 0.18, "catch_rate": 0.66}),
        ("WR", {"role": "WR", "routes_mean": 5.5, "routes_sd": 1.0, "target_rate": 0.15, "catch_rate": 0.55}),
        ("RB", {"role": "RB", "rush_att_mean": 8.0, "rush_att_sd": 2.0, "ypc": 4.0}),
        ("K", {"role": "K", "fg_att_mean": 1.8, "xp_att_mean": 3.0}),
    ]
    out = []
    for i in range(n_players):
        role, params = templates[i % len(templates)]
        out.append(
            {
                "row": {
                    "playerId": f"{role}_{i}",
                    "eventId": "CFB_PARITY_E0",
                    "teamId": "T00",
                    "role": role,
                    "market": "pass_yds" if role == "QB" else "rush_yds" if role == "RB" else "kicking_pts" if role == "K" else "rec_yds",
                    "sportFamily": "gridiron",
                    "league": "CFB",
                },
                "snapshot": {"parameters": dict(params)},
            }
        )
    return out


def test_resolve_backend_default_numpy():
    prev = os.environ.pop("DCM_EVENTWORLD_BACKEND", None)
    try:
        assert resolve_event_world_backend(None) == "numpy"
        assert resolve_event_world_backend("reference") == "reference"
        assert resolve_event_world_backend("numpy") == "numpy"
    finally:
        if prev is not None:
            os.environ["DCM_EVENTWORLD_BACKEND"] = prev


def test_fast_alloc_matches_full_counts():
    players = []
    for spec in _specs(8):
        players.append(
            {
                "playerId": spec["row"]["playerId"],
                "role": spec["row"]["role"],
                "params": spec["snapshot"]["parameters"],
                "row": spec["row"],
            }
        )
    for pass_a, rush_a, tgt in [(30, 22, 30), (18, 35, 18), (40, 12, 40)]:
        full = allocate_team_opportunity(
            players, team_pass_att=pass_a, team_rush_att=rush_a, team_targets=tgt
        )
        fast = allocate_team_opportunity_fast(
            players, team_pass_att=pass_a, team_rush_att=rush_a, team_targets=tgt
        )
        for key in (
            "playerRushAtt",
            "playerTargets",
            "playerPassAtt",
            "residualRushAtt",
            "residualTargets",
            "residualPassAtt",
            "kickerIsolated",
        ):
            assert full[key] == fast[key]


def test_numpy_vs_reference_bitwise_world_parity():
    specs = _specs(8)
    seed = "phase11-parity-bitwise"
    ref = simulate_joint_cfb_event_worlds(specs, n=96, seed=seed, backend="reference")
    npb = simulate_joint_cfb_event_worlds(specs, n=96, seed=seed, backend="numpy")
    assert ref["worlds"] == npb["worlds"]
    assert ref["meta"]["conservationFailures"] == npb["meta"]["conservationFailures"]
    assert ref["meta"]["residual"] == npb["meta"]["residual"]
    assert ref["meta"]["kickerIsolated"] == npb["meta"]["kickerIsolated"]
    assert ref["meta"]["rngVersion"] == RNG_VERSION
    assert npb["meta"]["rngVersion"] == RNG_VERSION
    assert npb["meta"]["backend"] == "numpy"
    assert ref["meta"]["backend"] == "reference"


def test_reference_function_portable_path():
    out = simulate_joint_cfb_event_worlds_reference(_specs(4), n=12, seed="ref-only")
    assert out["meta"]["backend"] == "reference"
    assert len(out["worlds"]) == 4
    assert all(len(v) == 12 for v in out["worlds"].values())


def test_simulate_cfb_event_alias():
    out = simulate_cfb_event(_specs(3), n=4, seed="alias", backend="reference")
    assert out["meta"]["joint"] is True
    assert out["meta"]["playerCount"] == 3


def test_env_backend_override(monkeypatch):
    monkeypatch.setenv("DCM_EVENTWORLD_BACKEND", "reference")
    out = simulate_joint_cfb_event_worlds(_specs(2), n=3, seed="env")
    assert out["meta"]["backend"] == "reference"
    monkeypatch.setenv("DCM_EVENTWORLD_BACKEND", "numpy")
    out2 = simulate_joint_cfb_event_worlds(_specs(2), n=3, seed="env2")
    assert out2["meta"]["backend"] == "numpy"


def test_distributions_numpy_matches_reference():
    values = [float(i) * 0.37 for i in range(500)]
    line = 40.5
    a = from_worlds(values, line)
    b = from_worlds_reference(values, line)
    assert a["n"] == b["n"]
    assert a["pHigher"] == pytest.approx(b["pHigher"])
    assert a["pLower"] == pytest.approx(b["pLower"])
    assert a["pPush"] == pytest.approx(b["pPush"])
    assert a["mean"] == pytest.approx(b["mean"])


def test_unknown_backend_fails_closed():
    with pytest.raises(ValueError, match="UNKNOWN_EVENTWORLD_BACKEND"):
        resolve_event_world_backend("cuda")
