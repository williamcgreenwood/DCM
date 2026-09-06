"""P5 settlement: full modeled population, card-only subset, append-only ledger."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.learning.postgame import settle_run
from dcm.learning.sidecar import append_ledger_jsonl, mutate_forecast, read_ledger_jsonl
from dcm.runtime.freeze import compute_forecast_hash
from dcm.runtime.store import IndexedStore
from dcm.version import LEARNING_REVISION, SOFTWARE

CUTOFF = "2026-08-29T00:00:00Z"


def _row(i: int, *, grade: str = "PLAYABLE", market: str = "pts") -> dict:
    return {
        "projectionId": f"proj-{i}",
        "player": f"Player {i}",
        "market": market,
        "line": 20.5 + i,
        "direction": "MORE",
        "state": "MODELED",
        "grade": grade,
        "selectedP": 0.58,
        "evidenceSafeP": 0.55,
        "lowerBound": 0.4,
        "sportFamily": "basketball",
        "league": "WNBA",
        "modifier": "STANDARD",
        "offeredHigher": True,
        "offeredLower": True,
    }


def _write_settleable(dest: Path, modeled: list[dict], card_ids: list[str]) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    freeze_ctx = {
        "runId": dest.name,
        "dcmVersion": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "schemaId": "PHASE_BC_SCHEMA_V2_2026-08-29",
        "schemaHash": "schema",
        "modelConfigHash": "model",
        "calibrationStateHash": "cal",
        "harSha256": "har",
        "forecastCutoff": CUTOFF,
        "boardHash": "board",
        "predictiveClaim": "NONE",
    }
    card = [r for r in modeled if r["projectionId"] in card_ids]
    top25 = list(modeled[:25])
    digest = compute_forecast_hash(freeze_ctx, modeled, card, top25)
    freeze = {**freeze_ctx, "frozenForecastHash": digest, "runState": "COMPLETE_FROZEN"}
    (dest / "frozen_forecast.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "run_integrity.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "checkpoint.json").write_text(
        json.dumps({"runId": dest.name, "forecastCutoff": CUTOFF, "frozenForecastHash": digest}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (dest / "frozen_forecast.sha256").write_text(digest + "\n", encoding="utf-8")
    (dest / "full_population.jsonl").write_text("".join(json.dumps(r) + "\n" for r in modeled), encoding="utf-8")
    (dest / "population_full.jsonl").write_text((dest / "full_population.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    (dest / "strict_card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    (dest / "top25_ranked.json").write_text(json.dumps(top25, indent=2) + "\n", encoding="utf-8")
    store = IndexedStore(dest / "index.sqlite")
    from dcm.learning.sidecar import append_record

    append_record(store, "FrozenForecast", CUTOFF, dest.name, LEARNING_REVISION, {"hash": digest}, source_hash="har")
    store.close()
    append_ledger_jsonl(
        dest,
        "FrozenForecast",
        {"hash": digest},
        cutoff=CUTOFF,
        run_id=dest.name,
        lr=LEARNING_REVISION,
        source_hash="har",
    )
    return dest


def test_settle_full_modeled_population_n_records(tmp_path: Path):
    n = 9
    modeled = [_row(i, grade="PLAYABLE" if i < 3 else "LEAN", market="pts" if i % 2 == 0 else "reb") for i in range(n)]
    dest = _write_settleable(tmp_path / "RUN_FULL", modeled, [r["projectionId"] for r in modeled[:2]])
    outcomes = {
        "outcomes": [
            {"projectionId": "proj-0", "result": "WIN"},
            {"projectionId": "proj-1", "result": "LOSS"},
            {"projectionId": "proj-2", "result": "PUSH"},
            {"projectionId": "proj-3", "result": "VOID"},
            {"projectionId": "proj-4", "result": "DNP"},
            {"projectionId": "proj-5", "result": "REBOOT"},
            {"projectionId": "proj-6", "result": "UNKNOWN_PLATFORM_RULE"},
            {"projectionId": "proj-7", "officialStatValue": 40.0},
            {"projectionId": "proj-8", "officialStatValue": 10.0},
        ]
    }
    path = tmp_path / "outcomes.json"
    path.write_text(json.dumps(outcomes) + "\n", encoding="utf-8")
    result = settle_run(dest, path)
    assert len(result["settlements"]) == n
    by_id = {s["projectionId"]: s for s in result["settlements"]}
    assert by_id["proj-0"]["result"] == "WIN"
    assert by_id["proj-1"]["result"] == "LOSS"
    assert by_id["proj-2"]["result"] == "PUSH"
    assert by_id["proj-3"]["result"] == "VOID"
    assert by_id["proj-4"]["result"] == "DNP"
    assert by_id["proj-5"]["result"] == "REBOOT"
    assert by_id["proj-6"]["result"] == "UNKNOWN_PLATFORM_RULE"
    assert by_id["proj-7"]["result"] == "WIN"
    assert by_id["proj-8"]["result"] == "LOSS"
    summary = json.loads((dest / "settlement_summary.json").read_text(encoding="utf-8"))
    assert summary["modeledSettled"] == n
    assert summary["byResult"]["WIN"] == 2
    assert summary["byResult"]["LOSS"] == 2
    assert "pts" in summary["byMarket"]
    assert "PLAYABLE" in summary["byGrade"]
    lines = (dest / "settlements.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == n


def test_settle_card_only_subset(tmp_path: Path):
    modeled = [_row(i) for i in range(5)]
    card_ids = ["proj-0", "proj-1"]
    dest = _write_settleable(tmp_path / "RUN_CARD", modeled, card_ids)
    outcomes = {"proj-0": "WIN", "proj-1": "LOSS", "proj-2": "PUSH", "proj-3": "WIN", "proj-4": "LOSS"}
    path = tmp_path / "outcomes.json"
    path.write_text(json.dumps(outcomes) + "\n", encoding="utf-8")
    result = settle_run(dest, path, card_only=True)
    assert len(result["settlements"]) == 2
    assert {s["projectionId"] for s in result["settlements"]} == set(card_ids)
    assert result["summary"]["cardOnly"] is True


def test_settle_missing_outcome_is_unknown_platform_rule(tmp_path: Path):
    modeled = [_row(0), _row(1)]
    dest = _write_settleable(tmp_path / "RUN_MISS", modeled, ["proj-0"])
    path = tmp_path / "outcomes.json"
    path.write_text('{"outcomes": [{"projectionId": "proj-0", "result": "WIN"}]}\n', encoding="utf-8")
    result = settle_run(dest, path)
    by_id = {s["projectionId"]: s for s in result["settlements"]}
    assert by_id["proj-0"]["result"] == "WIN"
    assert by_id["proj-1"]["result"] == "UNKNOWN_PLATFORM_RULE"
    assert by_id["proj-1"]["reason"] == "OUTCOME_MISSING"


def test_ledger_append_does_not_rewrite_frozen_forecast(tmp_path: Path):
    modeled = [_row(i) for i in range(3)]
    dest = _write_settleable(tmp_path / "RUN_LEDGER", modeled, ["proj-0"])
    freeze_before = (dest / "frozen_forecast.json").read_bytes()
    ledger_before = [r for r in read_ledger_jsonl(dest) if r.get("kind") == "FrozenForecast"]
    assert len(ledger_before) == 1
    store = IndexedStore(dest / "index.sqlite")
    cur = store.conn.execute("SELECT payload FROM records WHERE kind='FrozenForecast' ORDER BY id")
    sqlite_before = [row[0] for row in cur.fetchall()]
    store.close()
    path = tmp_path / "outcomes.json"
    path.write_text(json.dumps({"proj-0": "WIN", "proj-1": "LOSS", "proj-2": "PUSH"}) + "\n", encoding="utf-8")
    settle_run(dest, path)
    assert (dest / "frozen_forecast.json").read_bytes() == freeze_before
    ledger_after = read_ledger_jsonl(dest)
    frozen_after = [r for r in ledger_after if r.get("kind") == "FrozenForecast"]
    assert frozen_after == ledger_before
    settled = [r for r in ledger_after if r.get("kind") == "Settlement"]
    assert len(settled) == 3
    store = IndexedStore(dest / "index.sqlite")
    cur = store.conn.execute("SELECT payload FROM records WHERE kind='FrozenForecast' ORDER BY id")
    sqlite_after = [row[0] for row in cur.fetchall()]
    store.close()
    assert sqlite_after == sqlite_before
    with pytest.raises(RuntimeError, match="APPEND_ONLY"):
        mutate_forecast(dest / "frozen_forecast.json")
