"""Optional RFECV shadow challenger with nested chronological evaluation.

This module is deliberately outside the production probability path. Every
transform is inside an sklearn Pipeline, and all feature selection happens
inside an outer training window using event-disjoint chronological inner folds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from dcm.contracts.hashes import content_hash
from dcm.learning.walkforward import chronological_folds


def evaluate_rfecv_shadow(
    rows: Sequence[dict[str, Any]],
    feature_names: Sequence[str],
    *,
    min_train_rows: int = 12,
) -> dict[str, Any]:
    """Run one outer chronological RFECV comparison on explicit numeric features.

    Rows must contain numeric `features` keyed by ``feature_names``, a WIN/LOSS
    `result`, eventId, decisionCutoff, and labelAvailableAt. The final distinct
    cutoff is held out; RFECV's inner folds are built from outer-train rows only.
    """
    try:
        import numpy as np
        import sklearn
        from sklearn.feature_selection import RFECV
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import log_loss
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:  # optional runtime dependency
        raise RuntimeError("RFECV_EXTRA_REQUIRED: install pillars-dcm[rfecv]") from exc

    names = [str(name) for name in feature_names]
    if len(names) < 2 or len(names) != len(set(names)):
        raise ValueError("RFECV_FEATURE_NAMES_INVALID")
    material = [dict(row) for row in rows]
    if any(not row.get("eventId") for row in material):
        raise ValueError("RFECV_EVENT_ID_REQUIRED")
    if any(str(row.get("result", "")).upper() not in {"WIN", "LOSS"} for row in material):
        raise ValueError("RFECV_BINARY_LABELS_REQUIRED")
    parsed = []
    for row in material:
        try:
            raw = str(row["decisionCutoff"])
            value = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError
            parsed.append(value.astimezone(timezone.utc))
        except (KeyError, TypeError, ValueError):
            raise ValueError("RFECV_TIMEZONE_AWARE_CUTOFF_REQUIRED") from None
    final_cutoff = max(parsed)
    test_indices = [i for i, value in enumerate(parsed) if value == final_cutoff]
    train_indices = [i for i, value in enumerate(parsed) if value < final_cutoff]
    test_events = {str(material[i]["eventId"]) for i in test_indices}
    train_indices = [i for i in train_indices if str(material[i]["eventId"]) not in test_events]
    if len(train_indices) < min_train_rows or not test_indices:
        return {"status": "BLOCKED", "blocker": "INSUFFICIENT_OUTER_CHRONOLOGICAL_ROWS", "sklearnVersion": sklearn.__version__}

    train_cutoff = final_cutoff
    eligible_train = []
    for i in train_indices:
        available = material[i].get("labelAvailableAt")
        if not available:
            continue
        try:
            dt = datetime.fromisoformat(str(available).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is not None and dt.astimezone(timezone.utc) < train_cutoff:
            eligible_train.append(i)
    train_indices = eligible_train
    train_rows = [material[i] for i in train_indices]
    inner = chronological_folds(train_rows)
    if len(inner) < 2:
        return {"status": "BLOCKED", "blocker": "INSUFFICIENT_EVENT_DISJOINT_INNER_FOLDS", "innerFoldCount": len(inner), "sklearnVersion": sklearn.__version__}

    def matrix(indices: list[int]):
        return np.asarray([[material[i].get("features", {}).get(name, np.nan) for name in names] for i in indices], dtype=float)

    X_train, X_test = matrix(train_indices), matrix(test_indices)
    if not np.isfinite(X_train[~np.isnan(X_train)]).all() or np.isinf(X_train).any() or np.isinf(X_test).any():
        raise ValueError("RFECV_FEATURES_MUST_BE_FINITE_OR_NAN")
    y_train = np.asarray([1 if str(material[i]["result"]).upper() == "WIN" else 0 for i in train_indices])
    y_test = np.asarray([1 if str(material[i]["result"]).upper() == "WIN" else 0 for i in test_indices])
    if len(np.unique(y_train)) != 2 or len(np.unique(y_test)) != 2:
        return {"status": "BLOCKED", "blocker": "BOTH_LABEL_CLASSES_REQUIRED_IN_TRAIN_AND_TEST", "innerFoldCount": len(inner), "sklearnVersion": sklearn.__version__}

    pos = {id(row): local for local, row in enumerate(train_rows)}
    cv = []
    for fold in inner:
        fit_idx = [pos[id(row)] for row in fold["train"] if id(row) in pos]
        val_idx = [pos[id(row)] for row in fold["test"] if id(row) in pos]
        if fit_idx and val_idx and len(set(y_train[fit_idx])) == 2:
            cv.append((np.asarray(fit_idx), np.asarray(val_idx)))
    if len(cv) < 2:
        return {"status": "BLOCKED", "blocker": "INSUFFICIENT_VALID_RFECV_SPLITS", "innerFoldCount": len(cv), "sklearnVersion": sklearn.__version__}

    estimator = Pipeline([
        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scale", StandardScaler()),
        ("logit", LogisticRegression(random_state=0, max_iter=1000, class_weight="balanced")),
    ])
    selector = RFECV(
        estimator=estimator,
        step=1,
        min_features_to_select=1,
        cv=cv,
        scoring="neg_log_loss",
        importance_getter="named_steps.logit.coef_",
        n_jobs=1,
    )
    selector.fit(X_train, y_train)
    probabilities = selector.predict_proba(X_test)[:, 1]
    baseline = Pipeline([
        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scale", StandardScaler()),
        ("logit", LogisticRegression(random_state=0, max_iter=1000, class_weight="balanced")),
    ])
    baseline.fit(X_train, y_train)
    baseline_probabilities = baseline.predict_proba(X_test)[:, 1]
    selected = [name for name, keep in zip(names, selector.support_) if bool(keep)]
    selected_log_loss = float(log_loss(y_test, probabilities, labels=[0, 1]))
    baseline_log_loss = float(log_loss(y_test, baseline_probabilities, labels=[0, 1]))
    return {
        "status": "SHADOW_ONLY",
        "sklearnVersion": sklearn.__version__,
        "inputHash": content_hash(material),
        "featureNames": names,
        "selectedFeatures": selected,
        "featureCount": len(selected),
        "outerTrainN": len(train_indices),
        "outerTestN": len(test_indices),
        "outerTrainEventN": len({material[i]["eventId"] for i in train_indices}),
        "outerTestEventN": len(test_events),
        "eventDisjoint": not bool({material[i]["eventId"] for i in train_indices} & test_events),
        "innerFoldCount": len(cv),
        "outerTestLogLoss": selected_log_loss,
        "allFeatureBaselineLogLoss": baseline_log_loss,
        "logLossDifferenceVsAllFeatureBaseline": selected_log_loss - baseline_log_loss,
        "outerTestPredictions": probabilities.tolist(),
        "preprocessingFitScope": "each inner training fold; final selector fit restricted to outer training rows",
        "productionProbabilityAuthority": False,
        "predictiveClaim": "NONE",
    }
