"""Sanitized live PrizePicks HAR certification. Replaces REAL_HAR_NOT_SUPPLIED skip."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from dcm.ingest.board import freeze_board
from dcm.ingest.har import ingest_har
from dcm.ingest.prizepicks import parse_prizepicks_payload
from dcm.runner import run_dcm
from dcm.runtime.schema_root import EXPECTED_SHA256

ROOT = Path(__file__).resolve().parents[2] / "artifacts" / "dcm_v6_workstream_ab"
COMPACT = ROOT / "fixtures" / "sanitized_live_har" / "prizepicks_compact.har"
FULL = ROOT / "fixtures" / "sanitized_live_har" / "prizepicks_20260829.sanitized.har"
CUTOFF = "2026-08-29T16:00:00Z"

EXPECTED_FULL = {
    "unique": 11113,
    "league": {"MLB": 4480, "SOCCER": 3104, "CFB": 1568, "WNBA": 1238, "EPL": 580, "KBO": 81, "NPB": 44, "OTD": 8, "CFL": 10},
    "modifier": {"GOBLIN": 1849, "DEMON": 8053, "STANDARD": 1211},
    "status": {"pre_game": 10836, "in_progress": 259, "suspended": 18},
}


def test_compact_har_parses_jsonapi_and_accounts_sides_modifiers(tmp_path: Path):
    ing = ingest_har(COMPACT.read_bytes(), raw_bytes=COMPACT.read_bytes())
    assert ing["adapter"] == "PRIZEPICKS_JSONAPI"
    assert ing["rows"]
    board = freeze_board(ing, mount={"state": "ABSENT_IN_THIS_WORKSPACE"}, cutoff=CUTOFF, asof_policy="account_capture")
    acc = board["accounting"]
    assert acc["unique_offer_rows"] == acc["raw_projection_rows"]
    assert acc["goblin_rows"] >= 1
    assert acc["demon_rows"] >= 1
    assert acc["standard_rows"] >= 1
    assert acc["missing_sides_fail_closed"] == acc["unknown_side_rows"]
    # Goblins extracted (counted) — exclusion is a selection-time rule.
    assert acc["goblin_rows"] == acc["raw_projection_rows"] - acc["standard_rows"] - acc["demon_rows"] - acc["unknown_modifier_rows"]
    ids = {r["projectionId"] for r in board["rows"]}
    assert len(ids) == len(board["rows"])
    for row in board["rows"]:
        if row.get("playerId"):
            assert row["playerId"] != row.get("playerName")
        if not row.get("offeredHigher") and not row.get("offeredLower"):
            assert row.get("side") == "UNKNOWN"


def test_compact_cli_fixture_run_writes_artifacts(tmp_path: Path):
    result = run_dcm(
        input_path=COMPACT,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "RUNS",
        research="fixture",
        workspace=tmp_path,
        account_only=False,
    )
    dest = Path(result["dest"])
    assert result["runState"] in {
        "COMPLETE_FROZEN",
        "INCOMPLETE_CHECKPOINTED",
        "COMPLETE_WITH_UNSUPPORTED_ROWS",
        "EMPTY_CARD_COMPLETE",
        "RESEARCHED_MODELED_CARD",
        "RESEARCHED_MODELED_TOP25",
    }
    for name in (
        "board.json", "population_full.jsonl", "top100.json", "top25_ranked.json",
        "top25_qualified.json", "strict_card.json", "production_certified_card.json",
        "directional_passes.json", "production_readiness.json",
        "evidence_bundle.jsonl", "bundle_manifest.json", "hashes.json", "freeze.json",
        "research_requests.json", "checkpoint.json", "accounting.json",
    ):
        assert (dest / name).exists(), name
    card = json.loads((dest / "strict_card.json").read_text())
    assert all(p.get("modifier") != "GOBLIN" for p in card)
    assert all(not p.get("productionSelectable") for p in card)
    freeze = json.loads((dest / "freeze.json").read_text())
    assert freeze["learningRevision"] == "LR000000"
    assert freeze["predictiveClaim"] == "NONE"
    assert freeze["productionCertified"] is False
    assert freeze.get("notProductionRootCertified") is True


def test_full_sanitized_har_accounts_11113(tmp_path: Path):
    ing = ingest_har(FULL.read_bytes(), raw_bytes=FULL.read_bytes())
    assert ing["adapter"] == "PRIZEPICKS_JSONAPI"
    board = freeze_board(ing, mount={"state": "ABSENT_IN_THIS_WORKSPACE"}, cutoff=CUTOFF, asof_policy="account_capture")
    acc = board["accounting"]
    assert acc["unique_offer_rows"] == EXPECTED_FULL["unique"]
    assert acc["raw_projection_rows"] == EXPECTED_FULL["unique"]
    leagues = acc["by_league"]
    for name, n in EXPECTED_FULL["league"].items():
        assert leagues.get(name) == n, (name, leagues.get(name), n)
    assert acc["goblin_rows"] == EXPECTED_FULL["modifier"]["GOBLIN"]
    assert acc["demon_rows"] == EXPECTED_FULL["modifier"]["DEMON"]
    assert acc["standard_rows"] == EXPECTED_FULL["modifier"]["STANDARD"]
    # missing sides fail-closed
    assert acc["raw_missing_wager_types"] == 1955
    assert acc["raw_over_wager_types"] == 6868
    assert acc["raw_under_or_over_wager_types"] == 2290
    assert acc["missing_sides_fail_closed"] >= 1600
    assert acc["pre_game_rows"] == EXPECTED_FULL["status"]["pre_game"]
    assert acc["in_progress_rows"] == EXPECTED_FULL["status"]["in_progress"]
    assert acc["suspended_rows"] == EXPECTED_FULL["status"]["suspended"]
    assert acc["events"] == 84
    assert acc["players"] == 1358
    result = run_dcm(
        input_path=FULL,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "RUNS",
        research="file",
        workspace=tmp_path,
        account_only=True,
    )
    dest = Path(result["dest"])
    assert result["runState"] in {
        "COMPLETE_FROZEN",
        "INCOMPLETE_CHECKPOINTED",
        "COMPLETE_WITH_UNSUPPORTED_ROWS",
        "EMPTY_CARD_COMPLETE",
    }
    acc2 = json.loads((dest / "accounting.json").read_text())
    assert acc2["unique_offer_rows"] == 11113
    classified = acc2["classified"]
    assert classified["EXCLUDED_GOBLIN"] == 1849
    pop = (dest / "population_full.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(pop) == 11113
    records = [json.loads(line) for line in pop]
    states = Counter(r["state"] for r in records)
    assert states["EXCLUDED_GOBLIN"] == 1849
    # soccer/EPL/KBO/NPB/CFL/OTD fail-closed after accounting (goblins extracted first)
    unsupported_leagues = {"SOCCER", "EPL", "KBO", "NPB", "CFL", "OTD"}
    for r in records:
        if r.get("league") in unsupported_leagues:
            assert r["state"] in {"UNSUPPORTED", "UNRESOLVED", "EXCLUDED_GOBLIN"}
            assert r["state"] != "PLAYABLE"
    mlb = [r for r in records if r.get("league") == "MLB"]
    assert mlb
    assert all(r["state"] in {"MODELED", "UNRESOLVED", "EXCLUDED_GOBLIN", "UNSUPPORTED"} for r in mlb)
    modeled_mlb = [r for r in mlb if r["state"] == "MODELED"]
    assert modeled_mlb
    assert all(r.get("blocker") == "SHADOW_SUPPORTED_NOT_SELECTABLE" for r in modeled_mlb)
    live_rows = [r for r in records if r.get("status") in {"in_progress", "suspended"} or r.get("isLive")]
    assert live_rows
    assert all(r["state"] != "PLAYABLE" for r in live_rows)


def test_v1_expected_hash_unchanged():
    assert EXPECTED_SHA256 == "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22"
