"""P6 learning: dataset, walk-forward leakage fence, shadow registry, calibration readiness."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.learning.calibration import (
    INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS,
    evaluate_calibration_readiness,
)
from dcm.learning.dataset import SettlementsMissing, build_dataset, write_dataset
from dcm.learning.failure_class import classify_failure
from dcm.learning.postgame import settle_run
from dcm.learning.registry import propose_promotion, promote, register_challenger
from dcm.learning.sidecar import append_ledger_jsonl
from dcm.learning.walkforward import (
    WalkForwardLeakage,
    assert_no_leakage,
    chronological_folds,
    run_walkforward,
)
from dcm.runtime.freeze import compute_forecast_hash
from dcm.runtime.store import IndexedStore
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE

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


def _write_settleable(
    dest: Path, modeled: list[dict], card_ids: list[str], *, cutoff: str = CUTOFF
) -> Path:
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
        "forecastCutoff": cutoff,
        "boardHash": "board",
        "predictiveClaim": "NONE",
    }
    card = [r for r in modeled if r["projectionId"] in card_ids]
    top25 = list(modeled[:25])
    digest = compute_forecast_hash(freeze_ctx, modeled, card, top25)
    freeze = {**freeze_ctx, "frozenForecastHash": digest, "runState": "COMPLETE_FROZEN"}
    (dest / "frozen_forecast.json").write_text(
        json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (dest / "run_integrity.json").write_text(
        json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (dest / "checkpoint.json").write_text(
        json.dumps({"runId": dest.name, "forecastCutoff": cutoff, "frozenForecastHash": digest}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (dest / "frozen_forecast.sha256").write_text(digest + "\n", encoding="utf-8")
    (dest / "full_population.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in modeled), encoding="utf-8"
    )
    (dest / "population_full.jsonl").write_text(
        (dest / "full_population.jsonl").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (dest / "strict_card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    (dest / "top25_ranked.json").write_text(json.dumps(top25, indent=2) + "\n", encoding="utf-8")
    store = IndexedStore(dest / "index.sqlite")
    from dcm.learning.sidecar import append_record

    append_record(store, "FrozenForecast", cutoff, dest.name, LEARNING_REVISION, {"hash": digest}, source_hash="har")
    store.close()
    append_ledger_jsonl(
        dest,
        "FrozenForecast",
        {"hash": digest},
        cutoff=cutoff,
        run_id=dest.name,
        lr=LEARNING_REVISION,
        source_hash="har",
    )
    return dest


def _settle_nine(dest: Path) -> dict:
    modeled = [
        _row(i, grade="PLAYABLE" if i < 3 else "LEAN", market="pts" if i % 2 == 0 else "reb")
        for i in range(9)
    ]
    dest = _write_settleable(dest, modeled, [r["projectionId"] for r in modeled[:2]])
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
    path = dest.parent / "outcomes.json"
    path.write_text(json.dumps(outcomes) + "\n", encoding="utf-8")
    return settle_run(dest, path)


def test_dataset_builds_n_rows_from_synthetic_settled_run(tmp_path: Path):
    dest = tmp_path / "RUN_DS"
    result = _settle_nine(dest)
    assert len(result["settlements"]) == 9
    assert all("failureClass" in s for s in result["settlements"])
    rows, manifest = build_dataset([dest])
    assert len(rows) == 9
    assert manifest["rowCount"] == 9
    assert manifest["inventedSettlements"] is False
    assert manifest["trainedModel"] is False
    assert manifest["learningRevision"] == "LR000000"
    assert manifest["predictiveClaim"] == "NONE"
    supervised = [r for r in rows if r["labelSplit"] == "supervised"]
    audit = [r for r in rows if r["labelSplit"] == "audit"]
    assert {r["result"] for r in supervised} <= {"WIN", "LOSS", "PUSH"}
    assert "VOID" not in {r["result"] for r in supervised}
    assert "DNP" not in {r["result"] for r in supervised}
    assert "UNKNOWN_PLATFORM_RULE" not in {r["result"] for r in supervised}
    assert "REBOOT" not in {r["result"] for r in supervised}
    assert len(supervised) == 5
    assert len(audit) == 4
    written = write_dataset([dest], dest)
    assert written["rowCount"] == 9
    jsonl = (dest / "training_dataset.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(jsonl) == 9
    assert (dest / "training_dataset_manifest.json").is_file()


def test_dataset_refuses_missing_settlements(tmp_path: Path):
    modeled = [_row(0), _row(1)]
    dest = _write_settleable(tmp_path / "RUN_MISS", modeled, ["proj-0"])
    assert not (dest / "settlements.jsonl").is_file()
    with pytest.raises(SettlementsMissing, match="SETTLEMENTS_MISSING"):
        build_dataset([dest])


def test_walkforward_refuses_leakage(tmp_path: Path):
    early = [{"decisionCutoff": "2026-08-01T00:00:00Z", "result": "WIN", "selectedP": 0.6, "labelSplit": "supervised"}]
    late = [{"decisionCutoff": "2026-08-10T00:00:00Z", "result": "LOSS", "selectedP": 0.4, "labelSplit": "supervised"}]
    assert_no_leakage(early, late)
    with pytest.raises(WalkForwardLeakage, match="WALKFORWARD_LEAKAGE"):
        assert_no_leakage(late, early)
    with pytest.raises(WalkForwardLeakage, match="WALKFORWARD_LEAKAGE"):
        assert_no_leakage(early, early)

    dest_a = _write_settleable(tmp_path / "RUN_A", [_row(0), _row(1)], ["proj-0"], cutoff="2026-08-01T00:00:00Z")
    dest_b = _write_settleable(tmp_path / "RUN_B", [_row(0), _row(1)], ["proj-0"], cutoff="2026-08-10T00:00:00Z")
    (tmp_path / "oa.json").write_text(json.dumps({"proj-0": "WIN", "proj-1": "LOSS"}) + "\n", encoding="utf-8")
    (tmp_path / "ob.json").write_text(json.dumps({"proj-0": "LOSS", "proj-1": "WIN"}) + "\n", encoding="utf-8")
    settle_run(dest_a, tmp_path / "oa.json")
    settle_run(dest_b, tmp_path / "ob.json")
    rows, _ = build_dataset([dest_a, dest_b])
    folds = chronological_folds(rows)
    assert folds
    for fold in folds:
        train_c = fold["trainCutoffs"]
        test_c = fold["testCutoffs"]
        assert max(train_c) < min(test_c)
        assert_no_leakage(fold["train"], fold["test"])
    report = run_walkforward(rows)
    assert report["leakage"] is False
    assert report["learningRevision"] == "LR000000"
    assert report["predictiveClaim"] == "NONE"
    assert report["lrPromoted"] is False
    assert report["shadowChallenger"]["status"] == "SHADOW"
    assert report["shadowChallenger"]["pkl"] is False
    assert report["shadowChallenger"]["trainedNeuralNet"] is False
    (tmp_path / "walkforward_report.json").write_text(json.dumps(report), encoding="utf-8")


def test_challenger_shadow_propose_blocked_promote_refuses_lr(tmp_path: Path, monkeypatch):
    path = tmp_path / "model_registry.json"
    rec = register_challenger(path, model_id="shadow.logistic.v1", feature_schema_hash="feat")
    assert rec["status"] == "SHADOW"
    assert rec["pkl"] is False
    assert rec["production"] is False
    with pytest.raises(RuntimeError, match="CHALLENGER_MUST_REGISTER_AS_SHADOW"):
        register_challenger(path, model_id="bad.prod", status="PRODUCTION")
    proposal = propose_promotion(path, "shadow.logistic.v1")
    assert proposal["status"] == "BLOCKED"
    assert proposal["blocked"] is True
    assert proposal["lrUnchanged"] == "LR000000"
    assert proposal["predictiveClaimUnchanged"] == "NONE"
    assert "LR_AND_PREDICTIVE_CLAIM_PROMOTION_HARD_REFUSED_THIS_PR" in proposal["reasons"]
    monkeypatch.setenv("DCM_ALLOW_LR_PROMOTE", "1")
    refused = promote(path, "shadow.logistic.v1")
    assert refused["ok"] is False
    assert refused["status"] == "REFUSED"
    assert refused["learningRevision"] == "LR000000"
    assert refused["predictiveClaim"] == "NONE"
    assert refused["challengerStatus"] == "SHADOW"
    assert refused["pkl"] is False
    assert LEARNING_REVISION == "LR000000"
    assert PREDICTIVE_CLAIM == "NONE"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["learningRevision"] == "LR000000"
    assert data["predictiveClaim"] == "NONE"
    assert data["champion"]["learningRevision"] == "LR000000"
    assert data["autoPromote"] is False


def test_calibration_readiness_false_on_small_n():
    settlements = [
        {"binaryOutcome": 1, "forecastP": 0.6},
        {"binaryOutcome": 0, "forecastP": 0.4},
    ] * 5
    report = evaluate_calibration_readiness(settlements)
    assert report["n"] == 10
    assert report["ready"] is False
    assert report["activatesCalibration"] is False
    assert report["state"] == INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS
    assert INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS in report["reasons"]
    assert report["learningRevisionUnchanged"] == "LR000000"
    assert report["predictiveClaimUnchanged"] == "NONE"


def test_failure_class_does_not_permanent_patch():
    out = classify_failure(
        predicted_side="MORE",
        outcome="LOSS",
        snapshot_fields={
            "actualMinutes": 10.0,
            "opportunityMean": 32.0,
            "lowerBound": 0.4,
            "direction": "MORE",
        },
    )
    assert out["failureClass"] == "minutes_miss"
    assert out["permanentPatch"] is False
    assert LEARNING_REVISION == "LR000000"


def test_p6_does_not_add_pkl_or_advance_lr():
    assert LEARNING_REVISION == "LR000000"
    assert PREDICTIVE_CLAIM == "NONE"
    root = Path(__file__).resolve().parents[1]
    pkls = [p for p in root.rglob("*.pkl") if ".venv" not in p.parts]
    joblibs = [p for p in root.rglob("*.joblib") if ".venv" not in p.parts]
    assert pkls == []
    assert joblibs == []
