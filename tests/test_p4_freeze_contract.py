"""P4: line surfaces on slim, explanations, freeze binds, probability contract, joint worlds."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.model.market_derive import derive_market
from dcm.model.uncertainty import PROBABILITY_CONTRACT_KEYS
from dcm.model.worlds import sample_basketball, value_from_stats
from dcm.runner import run_dcm
from dcm.selection.card_layers import (
    PLAYER_NOT_ACTIVE,
    apply_pre_freeze_status_start_gates,
    is_modeled_playable,
)

CUTOFF = "2026-08-29T00:00:00Z"


def _row(**kwargs):
    base = {
        "projectionId": "p0",
        "sportFamily": "basketball",
        "league": "WNBA",
        "eventId": "DAL-CON",
        "eventLabel": "DAL vs CON",
        "playerId": "PAIGE",
        "playerName": "Paige Bueckers",
        "teamId": "DAL",
        "team": "DAL",
        "opponent": "CON",
        "market": "pts",
        "marketLabel": "Points",
        "line": 21.5,
        "side": "MORE",
        "offeredHigher": True,
        "offeredLower": True,
        "modifier": "STANDARD",
        "boardId": "FULL_GAME",
        "productType": "PLAYER_PICKS",
        "role": "G",
        "status": "pre_game",
    }
    base.update(kwargs)
    return base


def _har(rows):
    return {
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
                    "content": {"mimeType": "application/json", "text": json.dumps({"data": rows})},
                },
            }],
        },
    }


def test_slim_probability_contract_keys_are_separate(tmp_path: Path):
    result = run_dcm(
        input_path=None,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path,
        synthetic=True,
        research="fixture",
    )
    dest = Path(result["dest"])
    freeze = json.loads((dest / "frozen_forecast.json").read_text())
    contract = freeze["probabilityContract"]
    assert contract["reliabilityIsNotProbability"] is True
    assert set(contract["separateKeys"]) == set(PROBABILITY_CONTRACT_KEYS)
    assert "not a probability" in contract["note"].lower()
    binds = freeze["freezeBinds"]
    for key in (
        "software", "schemaHash", "featureStoreHash", "harSha256", "boardHash",
        "evidenceGraphHash", "parameterSnapshotHashes", "modelConfigHash",
        "calibrationStateHash", "forecastDecisionCutoff", "top25Hash", "cardHash",
        "explanationsHash",
    ):
        assert key in binds, key
    assert freeze.get("gitCommit") == binds.get("gitCommit")
    ranked = json.loads((dest / "top25_ranked.json").read_text())
    assert ranked, "synthetic board must rank at least one modeled row"
    for row in ranked:
        for key in PROBABILITY_CONTRACT_KEYS:
            assert key in row, key
        # Separate keys: reliability is not selectedP even if numeric values coincide.
        assert "reliability" in row and "selectedP" in row and "reliability" != "selectedP"
    explanations = (dest / "prop_explanations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert explanations
    obj = json.loads(explanations[0])
    for key in ("player", "market", "line", "direction", "topPositiveDrivers", "topNegativeDrivers",
                "primaryFailurePaths", "featureHashes", "evidenceHashes", "parameterSnapshotHash",
                "modelIds", "simulationHash"):
        assert key in obj, key
    assert isinstance(obj["topPositiveDrivers"], list)
    assert isinstance(obj["topNegativeDrivers"], list)


def test_line_surface_fields_on_playable_or_lean_slim(tmp_path: Path):
    rows = [
        _row(projectionId="p1", playerId="PAIGE", playerName="Paige Bueckers", line=8.5),
        _row(projectionId="p2", playerId="OGU", playerName="Arike Ogunbowale", line=8.5),
    ]
    path = tmp_path / "board.har.json"
    path.write_text(json.dumps(_har(rows)), encoding="utf-8")
    result = run_dcm(input_path=path, forecast_cutoff=CUTOFF, output_root=tmp_path / "out", research="fixture")
    dest = Path(result["dest"])
    ranked = json.loads((dest / "top25_ranked.json").read_text())
    serious = [r for r in ranked if r.get("grade") in {"PLAYABLE", "LEAN"}]
    assert serious, "fixture minutes/priors should produce PLAYABLE or LEAN on a soft 8.5 line"
    for row in serious:
        for key in (
            "offered_line", "break_even_line", "playable_break_line",
            "true_unclamped_line_tolerance", "edge_elasticity", "robustness_area",
        ):
            assert key in row, key
        assert row["true_unclamped_line_tolerance"] is not None
        if row["grade"] == "PLAYABLE":
            assert float(row["true_unclamped_line_tolerance"]) >= 0


def test_joint_worlds_engaged_on_multi_teammate_board(tmp_path: Path):
    rows = [
        _row(projectionId="p1", playerId="PAIGE", playerName="Paige Bueckers", line=21.5),
        _row(projectionId="p2", playerId="OGU", playerName="Arike Ogunbowale", line=18.5),
        _row(projectionId="p3", playerId="PAIGE", playerName="Paige Bueckers", market="pra", marketLabel="PRA", line=32.0),
    ]
    path = tmp_path / "two.har.json"
    path.write_text(json.dumps(_har(rows)), encoding="utf-8")
    result = run_dcm(input_path=path, forecast_cutoff=CUTOFF, output_root=tmp_path / "out", research="fixture")
    dest = Path(result["dest"])
    meta = json.loads((dest / "event_worlds_meta.json").read_text())
    freeze = json.loads((dest / "frozen_forecast.json").read_text())
    assert meta["allocationMode"] != "INDEPENDENT"
    assert meta["allocationMode"] in {"JOINT_TEAM", "MIXED"}
    assert freeze.get("eventWorldAllocation") == meta["allocationMode"]
    expl_path = dest / "prop_explanations.jsonl"
    assert expl_path.is_file()


def test_derive_market_used_for_pra_in_simulation_path(monkeypatch):
    calls: list[str] = []
    orig = derive_market

    def spy(ledger, market_key, board_id="FULL_GAME"):
        calls.append(str(market_key))
        return orig(ledger, market_key, board_id=board_id)

    monkeypatch.setattr("dcm.model.market_derive.derive_market", spy)
    rng = __import__("random").Random(9)
    w = sample_basketball(rng, 32.0)
    w["pra"] = 9999.0  # identity corruption: precomputed field must not win
    value = value_from_stats("pra", w)
    assert value == w["pts"] + w["reb"] + w["ast"]
    assert value != 9999.0
    assert any(str(c).lower() in {"pra", "pts_reb_ast"} or "pra" in str(c).lower() for c in calls)


def test_pre_freeze_gates_strip_late_out():
    healthy = {
        "grade": "PLAYABLE",
        "state": "MODELED",
        "blocker": None,
        "modeledPlayable": True,
        "row": _row(eventStartTime="2026-08-30T23:00:00Z", projectionId="ok"),
        "parameterSnapshot": {"status": "ACTIVE", "blocker": None},
        "forecastCutoff": "2026-08-30T19:00:00Z",
        "dependencyTags": ["ROLE:DAL:starter"],
    }
    late_out = {
        "grade": "PLAYABLE",
        "state": "MODELED",
        "blocker": None,
        "modeledPlayable": True,
        "row": _row(eventStartTime="2026-08-30T23:00:00Z", projectionId="out1", playerId="OUTP"),
        "parameterSnapshot": {"status": "OUT", "blocker": PLAYER_NOT_ACTIVE},
        "playerStatus": "OUT",
        "forecastCutoff": "2026-08-30T19:00:00Z",
        "dependencyTags": ["ROLE:DAL:out"],
    }
    qualified = apply_pre_freeze_status_start_gates(
        [healthy, late_out], cutoff="2026-08-30T19:00:00Z"
    )
    assert [p["row"]["projectionId"] for p in qualified] == ["ok"]
    assert late_out["modeledPlayable"] is False
    assert is_modeled_playable(late_out, cutoff="2026-08-30T19:00:00Z") is False
