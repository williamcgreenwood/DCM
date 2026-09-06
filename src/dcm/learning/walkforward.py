"""Chronological walk-forward harness. Train cutoffs must be strictly before test cutoffs.

Evaluates frozen DCM probabilities (selectedP / calibratedP). Optional tiny logistic
challenger is labeled SHADOW and is not a neural net or production model.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

from dcm.contracts.hashes import content_hash
from dcm.learning.dataset import _load_jsonl
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE

LOG_LOSS_CLIP = 1e-12
MIN_CHALLENGER_TRAIN_N = 8
REPORT_SCHEMA = "dcm.walkforward_report.v1-20260830"

class WalkForwardLeakage(RuntimeError):
    """Test fold decisionCutoff is not strictly after every train cutoff."""

def _ts(value: Any) -> str:
    return str(value or "")

def prediction_p(row: dict[str, Any]) -> float | None:
    for key in ("calibratedP", "selectedP", "evidenceSafeP", "forecastP", "rawP"):
        val = row.get(key)
        if val is None:
            continue
        try:
            p = float(val)
        except (TypeError, ValueError):
            continue
        if math.isfinite(p):
            return min(1.0, max(0.0, p))
    return None

def binary_pairs(
    rows: Iterable[dict[str, Any]], *, push: str = "exclude"
) -> tuple[list[float], list[float]]:
    """WIN=1, LOSS=0. PUSH excluded (default) or scored as 0.5."""
    preds: list[float] = []
    y: list[float] = []
    for row in rows:
        if str(row.get("labelSplit") or "supervised") != "supervised":
            continue
        result = str(row.get("result") or row.get("settlement") or "").upper()
        p = prediction_p(row)
        if p is None:
            continue
        if result == "WIN":
            preds.append(p)
            y.append(1.0)
        elif result == "LOSS":
            preds.append(p)
            y.append(0.0)
        elif result == "PUSH":
            if push == "half":
                preds.append(p)
                y.append(0.5)
    return preds, y

def metrics(preds: list[float], y: list[float], *, n_bins: int = 10) -> dict[str, Any]:
    n = len(preds)
    empty = {
        "n": 0,
        "brier": None,
        "logLoss": None,
        "hitRate": None,
        "ece": None,
        "meanPred": None,
        "empiricalRate": None,
    }
    if n == 0:
        return empty
    brier = sum((p - yi) ** 2 for p, yi in zip(preds, y)) / n
    log_loss = 0.0
    hits = 0
    binary_n = 0
    for p, yi in zip(preds, y):
        pc = min(1.0 - LOG_LOSS_CLIP, max(LOG_LOSS_CLIP, p))
        log_loss -= yi * math.log(pc) + (1.0 - yi) * math.log(1.0 - pc)
        if yi in {0.0, 1.0}:
            binary_n += 1
            pred_win = p >= 0.5
            if pred_win and yi == 1.0:
                hits += 1
            elif (not pred_win) and yi == 0.0:
                hits += 1
    log_loss /= n
    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for p, yi in zip(preds, y):
        idx = min(n_bins - 1, max(0, int(p * n_bins)))
        bins[idx].append((p, yi))
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        mean_y = sum(yi for _, yi in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(mean_p - mean_y)
    return {
        "n": n,
        "brier": brier,
        "logLoss": log_loss,
        "hitRate": (hits / binary_n) if binary_n else None,
        "ece": ece,
        "meanPred": sum(preds) / n,
        "empiricalRate": sum(y) / n,
        "pushHandling": "excluded_from_binary_hit_rate",
    }

def assert_no_leakage(train: list[dict[str, Any]], test: list[dict[str, Any]]) -> None:
    train_c = [_ts(r.get("decisionCutoff")) for r in train if _ts(r.get("decisionCutoff"))]
    test_c = [_ts(r.get("decisionCutoff")) for r in test if _ts(r.get("decisionCutoff"))]
    if not train_c or not test_c:
        raise WalkForwardLeakage("WALKFORWARD_LEAKAGE: missing decisionCutoff on train or test")
    max_train = max(train_c)
    min_test = min(test_c)
    if not (max_train < min_test):
        raise WalkForwardLeakage(
            f"WALKFORWARD_LEAKAGE: max(train cutoff)={max_train!r} is not < min(test cutoff)={min_test!r}"
        )
    for row in test:
        c = _ts(row.get("decisionCutoff"))
        if c and c <= max_train:
            raise WalkForwardLeakage(f"WALKFORWARD_LEAKAGE: test cutoff {c!r} <= train max {max_train!r}")

def chronological_folds(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expanding-window folds: unique cutoffs sorted; train all earlier, test the next cutoff."""
    labeled = [r for r in rows if _ts(r.get("decisionCutoff"))]
    cutoffs = sorted({_ts(r.get("decisionCutoff")) for r in labeled})
    folds: list[dict[str, Any]] = []
    for i in range(1, len(cutoffs)):
        train_cut = set(cutoffs[:i])
        test_cut = {cutoffs[i]}
        train = [r for r in labeled if _ts(r.get("decisionCutoff")) in train_cut]
        test = [r for r in labeled if _ts(r.get("decisionCutoff")) in test_cut]
        assert_no_leakage(train, test)
        folds.append(
            {
                "fold": i,
                "trainCutoffs": sorted(train_cut),
                "testCutoffs": sorted(test_cut),
                "trainN": len(train),
                "testN": len(test),
                "train": train,
                "test": test,
            }
        )
    return folds

def _sigmoid(z: float) -> float:
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))

def _shadow_features(row: dict[str, Any]) -> list[float] | None:
    p = prediction_p(row)
    if p is None:
        return None

    def f(key: str, default: float = 0.5) -> float:
        val = row.get(key)
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    return [1.0, p, f("lowerBound", p), f("reliability", 0.5)]

def fit_shadow_logistic(train: list[dict[str, Any]], *, steps: int = 250, lr: float = 0.25) -> list[float] | None:
    """Tiny intercept+linear logistic. SHADOW only. No sklearn required. No .pkl."""
    xs: list[list[float]] = []
    ys: list[float] = []
    for row in train:
        result = str(row.get("result") or row.get("settlement") or "").upper()
        if result not in {"WIN", "LOSS"}:
            continue
        feat = _shadow_features(row)
        if feat is None:
            continue
        xs.append(feat)
        ys.append(1.0 if result == "WIN" else 0.0)
    if len(xs) < MIN_CHALLENGER_TRAIN_N:
        return None
    dim = len(xs[0])
    w = [0.0] * dim
    n = len(xs)
    for _ in range(steps):
        grad = [0.0] * dim
        for xi, yi in zip(xs, ys):
            z = sum(wj * xj for wj, xj in zip(w, xi))
            err = _sigmoid(z) - yi
            for j in range(dim):
                grad[j] += err * xi[j]
        for j in range(dim):
            w[j] -= lr * grad[j] / n
    return w

def predict_shadow(w: list[float], row: dict[str, Any]) -> float | None:
    feat = _shadow_features(row)
    if feat is None:
        return None
    return _sigmoid(sum(wj * xj for wj, xj in zip(w, feat)))

def evaluate_folds(folds: list[dict[str, Any]]) -> dict[str, Any]:
    base_preds: list[float] = []
    base_y: list[float] = []
    chal_preds: list[float] = []
    chal_y: list[float] = []
    fold_reports: list[dict[str, Any]] = []
    for fold in folds:
        train, test = fold["train"], fold["test"]
        assert_no_leakage(train, test)
        p_base, y_base = binary_pairs(test, push="exclude")
        base_m = metrics(p_base, y_base)
        w = fit_shadow_logistic(train)
        chal_m: dict[str, Any] | None
        if w is None:
            chal_m = {
                "n": 0,
                "skipped": True,
                "reason": "INSUFFICIENT_TRAIN_N_FOR_SHADOW_LOGISTIC",
                "status": "SHADOW",
            }
        else:
            cp: list[float] = []
            cy: list[float] = []
            for row in test:
                result = str(row.get("result") or row.get("settlement") or "").upper()
                if result not in {"WIN", "LOSS"}:
                    continue
                pr = predict_shadow(w, row)
                if pr is None:
                    continue
                cp.append(pr)
                cy.append(1.0 if result == "WIN" else 0.0)
            chal_m = metrics(cp, cy)
            chal_m["status"] = "SHADOW"
            chal_m["trainedNeuralNet"] = False
            chal_m["pkl"] = False
            chal_preds.extend(cp)
            chal_y.extend(cy)
        base_preds.extend(p_base)
        base_y.extend(y_base)
        fold_reports.append(
            {
                "fold": fold["fold"],
                "trainCutoffs": fold["trainCutoffs"],
                "testCutoffs": fold["testCutoffs"],
                "trainN": fold["trainN"],
                "testN": fold["testN"],
                "leakage": False,
                "baseline": base_m,
                "shadowLogistic": chal_m,
            }
        )
    return {
        "folds": fold_reports,
        "baselinePooled": metrics(base_preds, base_y),
        "shadowLogisticPooled": metrics(chal_preds, chal_y) if chal_preds else {"n": 0, "status": "SHADOW", "skipped": True},
    }

def run_walkforward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    folds = chronological_folds(rows)
    if not folds:
        report = {
            "schema": REPORT_SCHEMA,
            "status": "INSUFFICIENT_CHRONOLOGICAL_CUTOFFS",
            "leakage": False,
            "foldCount": 0,
            "note": "Need ≥2 distinct decisionCutoff values. Random/shuffled splits are refused.",
            "baseline": {
                "model": "frozen_dcm_calibratedP_or_selectedP",
                "role": "CHAMPION_PROBABILITY_PATH",
                "trained": False,
                "pkl": False,
            },
            "shadowChallenger": {
                "model": "logistic_linear_shadow",
                "status": "SHADOW",
                "trainedNeuralNet": False,
                "pkl": False,
                "skipped": True,
                "reason": "INSUFFICIENT_CHRONOLOGICAL_CUTOFFS",
            },
            "learningRevision": LEARNING_REVISION,
            "predictiveClaim": PREDICTIVE_CLAIM,
            "software": SOFTWARE,
        }
        report["contentHash"] = content_hash(report)
        return report
    evaluated = evaluate_folds(folds)
    report = {
        "schema": REPORT_SCHEMA,
        "status": "COMPLETE",
        "leakage": False,
        "foldCount": len(evaluated["folds"]),
        "folds": evaluated["folds"],
        "baseline": {
            "model": "frozen_dcm_calibratedP_or_selectedP",
            "role": "CHAMPION_PROBABILITY_PATH",
            "trained": False,
            "pkl": False,
            "metrics": evaluated["baselinePooled"],
        },
        "shadowChallenger": {
            "model": "logistic_linear_shadow",
            "status": "SHADOW",
            "trainedNeuralNet": False,
            "pkl": False,
            "metrics": evaluated["shadowLogisticPooled"],
            "note": "Honest linear logistic on frozen features. Not a neural net. Not production.",
        },
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "software": SOFTWARE,
        "lrPromoted": False,
    }
    report["contentHash"] = content_hash({k: v for k, v in report.items() if k != "contentHash"})
    return report

def write_walkforward_report(dataset_path: Path, out_path: Path) -> dict[str, Any]:
    rows = _load_jsonl(Path(dataset_path))
    report = run_walkforward(rows)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Chronological walk-forward of frozen DCM probabilities.")
    p.add_argument("--dataset", type=Path, required=True, help="training_dataset.jsonl")
    p.add_argument("--out", type=Path, default=None, help="walkforward_report.json (default: beside dataset)")
    args = p.parse_args(argv)
    out = args.out or (Path(args.dataset).resolve().parent / "walkforward_report.json")
    try:
        report = write_walkforward_report(args.dataset, out)
    except WalkForwardLeakage as exc:
        print(str(exc))
        return 2
    print(json.dumps({k: report[k] for k in ("schema", "status", "foldCount", "leakage", "learningRevision", "predictiveClaim") if k in report}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
