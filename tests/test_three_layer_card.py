"""Three-layer card: modeled Top 25 + 0-6 PLAYABLE strict card + production-certified."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.runner import run_dcm
from dcm.selection.card_layers import (
    EMPTY_NO_PLAYABLES,
    EMPTY_PORTFOLIO_CONSTRAINT,
    EMPTY_RESEARCH_INCOMPLETE,
    EMPTY_ROOT_NOT_CERTIFIED,
    NOT_PRODUCTION_ROOT_CERTIFIED,
    V6_ROOT_OF_TRUST_MIGRATION_ACCEPTED,
    build_directional_passes,
    is_modeled_playable,
    modeled_empty_card_reason,
    production_certified_rows,
    production_root_accepted,
)
from dcm.selection.portfolio import build_card

CUTOFF = "2026-08-29T00:00:00Z"


def _row(pid: str, event: str, player: str, *, modifier: str = "STANDARD", market: str = "pts") -> dict:
    return {
        "projectionId": pid,
        "playerId": player,
        "playerName": player,
        "eventId": event,
        "teamId": player,
        "team": player,
        "market": market,
        "modifier": modifier,
        "line": 20.5,
    }


def _cand(pid: str, event: str, player: str, *, grade: str, production_selectable: bool = False, blocker=None, modifier="STANDARD") -> dict:
    return {
        "grade": grade,
        "state": "MODELED",
        "blocker": blocker,
        "productionSelectable": production_selectable,
        "modeledPlayable": False,
        "selectedSide": "MORE",
        "evidenceSafeP": 0.62 if grade == "PLAYABLE" else 0.55,
        "rank": 1,
        "row": _row(pid, event, player, modifier=modifier),
    }


def test_v1_hash_and_migration_flag_unchanged():
    from dcm.runtime.schema_root import EXPECTED_SHA256
    assert EXPECTED_SHA256 == "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22"
    assert V6_ROOT_OF_TRUST_MIGRATION_ACCEPTED is False


def test_gate_split_playable_modeled_card_when_production_root_closed():
    ranked = [
        _cand("a", "E1", "A", grade="PLAYABLE", production_selectable=False),
        _cand("b", "E2", "B", grade="PLAYABLE", production_selectable=False),
        _cand("c", "E3", "C", grade="LEAN", production_selectable=False),
        _cand("g", "E4", "G", grade="PLAYABLE", production_selectable=False, modifier="GOBLIN"),
        _cand("s", "E5", "S", grade="PLAYABLE", production_selectable=False, blocker="SHADOW_SUPPORTED_NOT_SELECTABLE"),
    ]
    for p in ranked:
        p["modeledPlayable"] = is_modeled_playable(p)
    qualified = [p for p in ranked if is_modeled_playable(p)]
    assert [p["row"]["projectionId"] for p in qualified] == ["a", "b"]
    card = build_card(qualified)
    assert [p["row"]["projectionId"] for p in card] == ["a", "b"]
    assert all(p["grade"] == "PLAYABLE" for p in card)
    assert all(p["row"]["modifier"] != "GOBLIN" for p in card)
    assert all(not p.get("productionSelectable") for p in card)
    certified = production_certified_rows(card, root_accepted=False)
    assert certified == []
    assert production_root_accepted(global_selection_gate=False, production_selection_ready=False) is False


def test_lean_never_fills_strict_card():
    ranked = [_cand(f"p{i}", f"E{i}", f"P{i}", grade="LEAN") for i in range(8)]
    qualified = [p for p in ranked if is_modeled_playable(p)]
    assert qualified == []
    assert build_card(ranked) == []


def test_empty_reasons_and_directional_passes():
    assert modeled_empty_card_reason(
        modeled_card_size=2, modeled_playable_count=2,
        evidence_coverage_complete=True, research_complete=True,
    ) == ""
    assert modeled_empty_card_reason(
        modeled_card_size=0, modeled_playable_count=0,
        evidence_coverage_complete=True, research_complete=True,
    ) == EMPTY_NO_PLAYABLES
    assert modeled_empty_card_reason(
        modeled_card_size=0, modeled_playable_count=0,
        evidence_coverage_complete=False, research_complete=True,
    ) == EMPTY_RESEARCH_INCOMPLETE
    assert modeled_empty_card_reason(
        modeled_card_size=0, modeled_playable_count=3,
        evidence_coverage_complete=True, research_complete=True,
    ) == EMPTY_PORTFOLIO_CONSTRAINT
    ranked = [
        _cand("a", "E1", "A", grade="PLAYABLE"),
        _cand("c", "E3", "C", grade="LEAN"),
        _cand("d", "E4", "D", grade="PASS"),
    ]
    passes = build_directional_passes(ranked, [{"projectionId": "a"}])
    assert [p["projectionId"] for p in passes] == ["c", "d"]
    assert all(p["grade"] != "PLAYABLE" for p in passes)


def test_synthetic_e2e_writes_layers_with_production_certified_false(tmp_path: Path):
    result = run_dcm(
        input_path=None,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path,
        synthetic=True,
        research="fixture",
    )
    dest = Path(result["dest"])
    freeze = json.loads((dest / "freeze.json").read_text())
    top25 = json.loads((dest / "top25_ranked.json").read_text())
    strict = json.loads((dest / "strict_card.json").read_text())
    certified = json.loads((dest / "production_certified_card.json").read_text())
    directional = json.loads((dest / "directional_passes.json").read_text())
    assert (dest / "top25_ranked.json").is_file()
    assert isinstance(top25, list)
    assert len(top25) >= 1
    assert certified == []
    assert freeze["productionCertified"] is False
    assert freeze["notProductionRootCertified"] is True
    assert freeze["productionRootCertification"] == NOT_PRODUCTION_ROOT_CERTIFIED
    assert freeze["productionEmptyCardReason"] == EMPTY_ROOT_NOT_CERTIFIED
    assert freeze["executionMode"] == "RESEARCHED_MODELED"
    assert freeze["learningRevision"] == "LR000000"
    assert freeze["predictiveClaim"] == "NONE"
    assert freeze["productionSelectionReady"] is False
    assert all(p.get("modifier") != "GOBLIN" for p in strict)
    assert all(p.get("grade") != "LEAN" for p in strict)
    if not strict:
        assert freeze["emptyCardReason"] in {EMPTY_NO_PLAYABLES, EMPTY_RESEARCH_INCOMPLETE}
        assert freeze["runState"] in {"RESEARCHED_MODELED_TOP25", "EMPTY_CARD_COMPLETE"}
    else:
        assert freeze.get("emptyCardReason") in {None, ""}
        assert freeze["runState"] == "RESEARCHED_MODELED_CARD"
    assert isinstance(directional, list)
    assert result["integrity"]["cardSize"] == len(strict)
    assert result["integrity"]["modeledCardSize"] == len(strict)


def test_forced_playable_grades_emit_modeled_card_while_root_closed(tmp_path: Path, monkeypatch):
    import dcm.runner as runner_mod

    monkeypatch.setattr(runner_mod, "grade_of", lambda **kwargs: "PLAYABLE")
    result = run_dcm(
        input_path=None,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path,
        synthetic=True,
        research="fixture",
    )
    dest = Path(result["dest"])
    strict = json.loads((dest / "strict_card.json").read_text())
    certified = json.loads((dest / "production_certified_card.json").read_text())
    freeze = json.loads((dest / "freeze.json").read_text())
    assert len(strict) >= 1
    assert len(strict) <= 6
    assert all(p["grade"] == "PLAYABLE" for p in strict)
    assert all(p["modifier"] != "GOBLIN" for p in strict)
    assert all(not p.get("productionSelectable") for p in strict)
    assert certified == []
    assert freeze["productionCertified"] is False
    assert freeze["notProductionRootCertified"] is True
    assert freeze["executionMode"] == "RESEARCHED_MODELED"
    assert freeze["runState"] == "RESEARCHED_MODELED_CARD"
    assert freeze["modeledCardSize"] == len(strict)
    assert freeze["cardSize"] == len(strict)
    assert "emptyCardReason" not in freeze or freeze["emptyCardReason"] == ""
    assert freeze["productionEmptyCardReason"] == EMPTY_ROOT_NOT_CERTIFIED
    assert freeze["learningRevision"] == "LR000000"


def test_zero_modeled_rows_sets_empty_no_playables(tmp_path: Path):
    rows = [
        {
            "projectionId": "g1", "sportFamily": "basketball", "league": "NBA", "eventId": "E1",
            "eventLabel": "A @ B", "playerId": "G1", "playerName": "Gob", "teamId": "AAA", "team": "AAA",
            "opponent": "BBB", "market": "pts", "marketLabel": "Points", "line": 12.5, "side": "MORE",
            "offeredHigher": True, "offeredLower": False, "modifier": "GOBLIN", "boardId": "FULL_GAME",
            "productType": "PLAYER_PICKS", "role": "G",
        },
        {
            "projectionId": "s1", "sportFamily": "soccer", "league": "EPL", "eventId": "E2",
            "eventLabel": "ARS v MCI", "playerId": "S1", "playerName": "Saka", "teamId": "ARS", "team": "ARS",
            "opponent": "MCI", "market": "shots", "marketLabel": "Shots", "line": 2.5, "side": "MORE",
            "offeredHigher": True, "offeredLower": True, "modifier": "STANDARD", "boardId": "FULL_GAME",
            "productType": "PLAYER_PICKS", "role": "W",
        },
    ]
    har = {
        "_pillars": {"kind": "SYNTHETIC_HAR"},
        "log": {
            "version": "1.2",
            "creator": {"name": "t", "version": "1"},
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
    path = tmp_path / "empty.har.json"
    path.write_text(json.dumps(har), encoding="utf-8")
    result = run_dcm(input_path=path, forecast_cutoff=CUTOFF, output_root=tmp_path / "out", research="fixture")
    dest = Path(result["dest"])
    freeze = json.loads((dest / "freeze.json").read_text())
    strict = json.loads((dest / "strict_card.json").read_text())
    top25 = json.loads((dest / "top25_ranked.json").read_text())
    certified = json.loads((dest / "production_certified_card.json").read_text())
    assert strict == []
    assert top25 == []
    assert certified == []
    assert freeze["cardSize"] == 0
    assert freeze["productionCertified"] is False
    assert freeze["emptyCardReason"] in {EMPTY_NO_PLAYABLES, EMPTY_RESEARCH_INCOMPLETE}
    assert freeze["productionEmptyCardReason"] == EMPTY_ROOT_NOT_CERTIFIED
