"""Joint EventWorld: team minutes, FGA residual, ledger identities."""
from __future__ import annotations

from dcm.model.event_world_joint import (
    reconcile_team_minutes,
    simulate_joint_team_worlds,
    team_minute_target,
)
from dcm.model.market_derive import derive_market
from dcm.model.worlds import as_primitive_ledger, sample_basketball, simulate_player_worlds, value_from_stats


def _spec(pid: str, minutes_mean: float, fga_pm: float = 0.55, league: str = "WNBA"):
    return {
        "row": {
            "playerId": pid,
            "eventId": "WNBA_DAL_CON",
            "teamId": "DAL",
            "sportFamily": "basketball",
            "league": league,
            "market": "pts",
        },
        "snapshot": {
            "parameters": {
                "minutes_mean": minutes_mean,
                "minutes_sd": 2.5,
                "fga_per_min": fga_pm,
                "three_pa_share": 0.40,
                "two_fg_pct": 0.50,
                "three_fg_pct": 0.34,
                "fta_per_min": 0.16,
                "ft_pct": 0.80,
                "reb_per_min": 0.20,
                "ast_per_min": 0.12,
            }
        },
    }


def test_five_wnba_teammates_minutes_sum_near_200():
    players = [_spec(f"P{i}", 32.0 + i, 0.50 + 0.02 * i) for i in range(5)]
    out = simulate_joint_team_worlds(players, n=128, seed="joint-min-200")
    sums = []
    for i in range(128):
        s = sum(out["worlds"][f"P{k}"][i]["minutes"] for k in range(5))
        sums.append(s)
        assert abs(s - 200.0) < 1.5
    assert abs(sum(sums) / len(sums) - 200.0) < 1.0
    assert out["meta"]["allocationMode"] == "JOINT_TEAM"
    assert abs(out["meta"]["teamMinuteSumMean"] - 200.0) < 1.0
    assert abs(team_minute_target("WNBA") - 200.0) < 1e-9


def test_two_teammates_team_total_including_residual_near_200():
    players = [_spec("A", 34.0, 0.70), _spec("B", 28.0, 0.45)]
    out = simulate_joint_team_worlds(players, n=96, seed="joint-two")
    assert out["meta"]["allocationMode"] == "JOINT_TEAM"
    assert abs(out["meta"]["teamMinuteSumMean"] - 200.0) < 2.0
    assert out["meta"]["modeledMinuteSumMean"] < 120.0  # two players, not inflated to 200
    assert out["meta"]["residualMinuteSumMean"] > 50.0


def test_nba_five_teammates_minutes_sum_near_240():
    players = [
        _spec(f"N{i}", 30.0 + i, 0.50, league="NBA") for i in range(5)
    ]
    for p in players:
        p["row"]["eventId"] = "NBA_BOS_NYK"
        p["row"]["teamId"] = "BOS"
        p["row"]["league"] = "NBA"
    out = simulate_joint_team_worlds(players, n=64, seed="joint-nba-240")
    assert abs(out["meta"]["teamMinuteSumMean"] - 240.0) < 1.5


def _corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx > 0 and dy > 0 else 0.0


def test_fga_negative_correlation_or_residual():
    """Players compete for a team FGA pool (Dirichlet shares). Shared pace can
    lift raw counts together; competition is in the shares / residual pool."""
    five = [_spec(f"P{i}", 32.0, 0.45 + 0.08 * (i == 0)) for i in range(5)]
    out5 = simulate_joint_team_worlds(five, n=256, seed="joint-fga-five")
    fa = [w["fga"] for w in out5["worlds"]["P0"]]
    fb = [w["fga"] for w in out5["worlds"]["P1"]]
    team = [w["_team_fga"] for w in out5["worlds"]["P0"]]
    sa = [a / t for a, t in zip(fa, team) if t]
    sb = [b / t for b, t in zip(fb, team) if t]
    assert _corr(sa, sb) < 0.0
    mid = sorted(sa)[len(sa) // 2]
    high_b = [b for a, b in zip(sa, sb) if a >= mid]
    low_b = [b for a, b in zip(sa, sb) if a < mid]
    assert sum(high_b) / len(high_b) < sum(low_b) / len(low_b)

    two = [_spec("A", 36.0, 0.80), _spec("B", 30.0, 0.55)]
    out2 = simulate_joint_team_worlds(two, n=192, seed="joint-fga-two")
    fa = [w["fga"] for w in out2["worlds"]["A"]]
    team = [w["_team_fga"] for w in out2["worlds"]["A"]]
    residual_share = [(t - a) / t for a, t in zip(fa, team) if t]
    sa = [a / t for a, t in zip(fa, team) if t]
    assert residual_share
    assert _corr(sa, residual_share) < 0.0
    mid = sorted(sa)[len(sa) // 2]
    high_rem = [r for a, r in zip(sa, residual_share) if a >= mid]
    low_rem = [r for a, r in zip(sa, residual_share) if a < mid]
    assert sum(high_rem) / len(high_rem) < sum(low_rem) / len(low_rem)


def test_single_player_path_still_independent():
    row = _spec("SOLO", 31.0)["row"]
    worlds = simulate_player_worlds(row, n=16, seed="solo")
    assert len(worlds) == 16
    for w in worlds:
        as_primitive_ledger(w)


def test_reconcile_method_documented():
    mins, residual, method = reconcile_team_minutes([32.0, 33.0, 31.0, 30.0, 34.0], league="WNBA", n_modeled=5)
    assert abs(sum(mins) - 200.0) < 1e-6
    assert residual == 0.0
    assert "rescale" in method and "residual" in method
    two, residual2, method2 = reconcile_team_minutes([34.0, 28.0], league="WNBA", n_modeled=2)
    assert abs(sum(two) + residual2 - 200.0) < 1e-6
    assert residual2 > 0
    assert "residual" in method2


def test_runner_two_teammates_writes_joint_meta(tmp_path):
    import json
    from pathlib import Path as P
    from dcm.runner import run_dcm

    def row(pid, name, proj, line=18.5):
        return {
            "projectionId": proj,
            "sportFamily": "basketball",
            "league": "WNBA",
            "eventId": "DAL-CON",
            "eventLabel": "DAL vs CON",
            "playerId": pid,
            "playerName": name,
            "teamId": "DAL",
            "team": "DAL",
            "opponent": "CON",
            "market": "pts",
            "marketLabel": "Points",
            "line": line,
            "side": "MORE",
            "offeredHigher": True,
            "offeredLower": True,
            "modifier": "STANDARD",
            "boardId": "FULL_GAME",
            "productType": "PLAYER_PICKS",
            "role": "G",
            "status": "pre_game",
        }

    har = {
        "_pillars": {"kind": "SYNTHETIC_HAR"},
        "log": {
            "version": "1.2",
            "creator": {"name": "pillars-test", "version": "1"},
            "entries": [{
                "startedDateTime": "2026-08-28T16:00:00.000Z",
                "request": {"method": "GET", "url": "https://api.prizepicks.com/projections", "headers": []},
                "response": {
                    "status": 200,
                    "headers": [{"name": "Content-Type", "value": "application/json"}],
                    "content": {"mimeType": "application/json", "text": json.dumps({"data": [
                        row("PAIGE", "Paige Bueckers", "p1", 21.5),
                        row("OGU", "Arike Ogunbowale", "p2", 18.5),
                    ]})},
                },
            }],
        },
    }
    path = tmp_path / "two.har.json"
    path.write_text(json.dumps(har), encoding="utf-8")
    result = run_dcm(input_path=path, forecast_cutoff="2026-08-29T00:00:00Z", output_root=tmp_path / "out", research="fixture")
    dest = P(result["dest"])
    meta = json.loads((dest / "event_worlds_meta.json").read_text())
    freeze = json.loads((dest / "frozen_forecast.json").read_text())
    assert meta["allocationMode"] in {"JOINT_TEAM", "MIXED"}
    assert meta["jointTeamCount"] >= 1
    assert freeze.get("eventWorldAllocation") in {"JOINT_TEAM", "MIXED"}
    team = meta["events"][0]
    assert abs(team["minuteTarget"] - 200.0) < 1e-9
    assert abs(team["teamMinuteSumMean"] - 200.0) < 8.0
    assert freeze.get("conservationFailures", 0) == 0
