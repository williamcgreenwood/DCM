"""Auditable advanced-modeling execution receipts for the canonical runner.

This layer deliberately orchestrates existing DCM producers/consumers. KDE and
SVD are diagnostic-only; neither may manufacture or replace a forecast
probability. Missing historical, calibration, or payout evidence is represented
as a typed blocker in the receipt.
"""
from __future__ import annotations

import math
import re
import time
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from dcm.contracts.hashes import content_hash
from dcm.algorithms.computation_law import computation_law_identity
from dcm.learning.calibration import evaluate_calibration_readiness
from dcm.algorithms.registry import algorithm_registry_sha256, load_algorithm_registry, require_algorithm

ADVANCED_EXECUTION_SCHEMA = "pillars_dcm.advanced_modeling_execution.v1"
MIN_KDE_SAMPLE = 30
MAX_KDE_SAMPLE = 500
MIN_SVD_ROWS = 8
MAX_SVD_ROWS = 10_000
MAX_SVD_COLUMNS = 512

CAPABILITY_DAG = (
    ("SVD", "FEATURES", "PARAMETERS"),
    ("MONTE_CARLO", "EVENTWORLD", "PROBABILITY"),
    ("KDE", "EVENTWORLD", "PROBABILITY_DIAGNOSTIC"),
    ("CALIBRATION", "PROBABILITY", "PORTFOLIO"),
    ("PORTFOLIO_CORRELATION", "PROBABILITY", "PORTFOLIO"),
    ("PAYOUT_EV", "PORTFOLIO", "FREEZE"),
)
CAPABILITY_DEPENDENCIES = {
    "SVD": ("ALGORITHM_GRAPH",),
    "MONTE_CARLO": ("ALGORITHM_GRAPH",),
    "KDE": ("ALGORITHM_GRAPH",),
    "CALIBRATION": ("MONTE_CARLO",),
    "PORTFOLIO_CORRELATION": ("MONTE_CARLO", "CALIBRATION"),
    "PAYOUT_EV": ("PORTFOLIO_CORRELATION",),
}
CAPABILITY_INPUT_REQUIREMENTS = {
    "SVD": ("CUTOFF_SAFE_ROLE_OPPONENT_FEATURE_MATRIX",),
    "MONTE_CARLO": ("PARAMETER_SNAPSHOT", "SUPPORTED_EVENTWORLD_BACKEND"),
    "KDE": ("COMPARABLE_CUTOFF_SAFE_CONTINUOUS_HISTORY",),
    "CALIBRATION": ("CHRONOLOGICAL_FORECAST_OUTCOME_PAIRS",),
    "PORTFOLIO_CORRELATION": ("ALIGNED_SHARED_EVENT_OUTCOMES",),
    "PAYOUT_EV": ("VERIFIED_ENTRY_CONTRACT", "COMPLETE_PAYOUT_RULES", "CALIBRATED_JOINT_OUTCOMES"),
}
CAPABILITY_INPUT_PRODUCERS = {
    "ALGORITHM_GRAPH": ("CANONICAL_ALGORITHM_REGISTRY",),
    "KDE": ("CUTOFF_SAFE_COMPARABLE_STAT_HISTORY", "OBSERVED_MARKET_DEFINITION_AND_LINE"),
    "SVD": ("FROZEN_CUTOFF_SAFE_FEATURE_HISTORY", "CHRONOLOGICAL_TRAINING_ROWS.numericFeatures"),
    "MONTE_CARLO": ("SPORT_PARAMETER_SNAPSHOTS", "SPORT_SPECIFIC_SHARED_EVENTWORLD_BACKEND"),
    "CALIBRATION": ("FROZEN_PREGAME_FORECASTS", "AUTHORITATIVE_LATER_SETTLEMENTS"),
    "PORTFOLIO_CORRELATION": ("ALIGNED_SHARED_EVENT_SELECTION_OUTCOMES",),
    "PAYOUT_EV": ("OBSERVED_ENTRY_CONTRACT", "COMPLETE_DATED_PAYOUT_RULES", "CALIBRATED_JOINT_OUTCOMES"),
}
CAPABILITY_ALGORITHMS = {
    "ALGORITHM_GRAPH": "ALG-CTRL-001",
    "KDE": "ALG-ML-PROB-009",
    "SVD": "ALG-ML-TABULAR-013",
    "MONTE_CARLO": "ALG-MC-001",
    "CALIBRATION": "ALG-CAL-001",
    "PORTFOLIO_CORRELATION": "ALG-PORT-001",
    "PAYOUT_EV": "ALG-EV-001",
}


def _deterministic_hash_payload(value: Any) -> Any:
    """Remove observational timings recursively from deterministic hashes."""
    if isinstance(value, Mapping):
        return {str(k): _deterministic_hash_payload(v) for k, v in value.items()
                if k not in {"executionDurationMs", "contentHash"}}
    if isinstance(value, (list, tuple)):
        return [_deterministic_hash_payload(item) for item in value]
    return value


def compile_advanced_execution_dag() -> dict[str, Any]:
    """Compile and validate the bounded modeling DAG against the live registry."""
    nodes = [{
        "nodeId": "ALGORITHM_GRAPH",
        "algorithmId": CAPABILITY_ALGORITHMS["ALGORITHM_GRAPH"],
        "lifecycle": require_algorithm(CAPABILITY_ALGORITHMS["ALGORITHM_GRAPH"]).lifecycle,
        "producer": "dcm.algorithms.registry",
        "consumer": "canonical seven-capability execution controller",
        "dependsOn": [],
        "requiredInputs": ["CANONICAL_RUN_CONTEXT"],
    }]
    node_ids = {"ALGORITHM_GRAPH", *(capability for capability, _producer, _consumer in CAPABILITY_DAG)}
    seen: set[str] = {"ALGORITHM_GRAPH"}
    for capability, producer, consumer in CAPABILITY_DAG:
        algorithm_id = CAPABILITY_ALGORITHMS[capability]
        record = require_algorithm(algorithm_id)
        dependencies = CAPABILITY_DEPENDENCIES[capability]
        if capability in dependencies or any(dep in node_ids and dep not in seen for dep in dependencies):
            raise ValueError(f"ADVANCED_MODEL_DAG_CYCLE_OR_FORWARD_EDGE:{capability}")
        node = {
            "nodeId": capability,
            "algorithmId": algorithm_id,
            "lifecycle": record.lifecycle,
            "producer": producer,
            "consumer": consumer,
            "dependsOn": list(dependencies),
            "requiredInputs": list(CAPABILITY_INPUT_REQUIREMENTS[capability]),
        }
        nodes.append(node)
        seen.add(capability)
    law = computation_law_identity()
    return {"schema": "pillars_dcm.advanced_modeling_dag.v1", "version": "1.2.0",
            "computationLawVersion": law["version"], "computationLawSha256": law["sha256"],
            "nodes": nodes, "validated": True}


def _receipt(capability: str, state: str, *, producer: str, consumer: str,
             blockers: Sequence[str] = (), details: Mapping[str, Any] | None = None,
             run_id: str = "UNAVAILABLE", forecast_cutoff: str = "",
             input_hashes: Sequence[str] = (), event_ids: Sequence[str] = (),
             market_ids: Sequence[str] = (), duration_ms: float | None = None,
             applicability: str = "EVALUATED") -> dict[str, Any]:
    algorithm_id = CAPABILITY_ALGORITHMS[capability]
    record = require_algorithm(algorithm_id)
    law = computation_law_identity()
    body = {
        "computationLawVersion": law["version"],
        "computationLawSha256": law["sha256"],
        "capability": capability,
        "algorithmId": algorithm_id,
        "algorithmVersion": record.introduced_version,
        "algorithmLifecycle": record.lifecycle,
        "fallbackAlgorithmId": record.fallback_algorithm_id,
        "requirementIds": list(record.requirement_trace_ids),
        "testReferences": list(record.test_ids),
        "benchmarkReferences": list(record.benchmark_ids),
        "runId": run_id,
        "modelId": "DCM_CANONICAL",
        "modelVersion": "UNAVAILABLE",
        "inputDatasetIds": [],
        "inputDatasetLineageState": "NOT_PROVIDED_BY_CANONICAL_RUNNER",
        "featureSnapshotIds": [],
        "parameterSnapshotIds": [],
        "snapshotLineageState": "RECORDED_IN_INPUT_CONTENT_HASHES_WHEN_PRESENT",
        "eventIds": list(dict.fromkeys(str(x) for x in event_ids if x)),
        "marketIds": list(dict.fromkeys(str(x) for x in market_ids if x)),
        "evidenceCutoff": forecast_cutoff or None,
        "inputContentHashes": list(dict.fromkeys(str(x) for x in input_hashes if x)),
        "applicabilityVerdict": applicability,
        "state": state,
        "executionMethod": record.implementation_module + "." + record.implementation_symbol,
        "randomSeed": (details or {}).get("randomSeed"),
        "rngVersion": (details or {}).get("rngVersion"),
        "executionDurationMs": duration_ms,
        "outputHash": None,
        "numericalDiagnostics": (details or {}).get("diagnostics") or (details or {}).get("diagnostic") or {},
        "producer": producer,
        "consumer": consumer,
        "fallbackDetails": None,
        "blockers": list(blockers),
        "details": dict(details or {}),
    }
    # Duration is audit telemetry. It must not perturb deterministic output or
    # restart-equivalence hashes for identical model inputs.
    body["outputHash"] = content_hash({
        k: v for k, v in body.items() if k not in {"outputHash", "executionDurationMs"}
    })
    return body


def _timestamp_at_or_before(value: Any, cutoff: str) -> bool:
    raw = str(value or "").strip()
    if not raw or not cutoff:
        return False
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
        cutoff_dt = datetime.fromisoformat(cutoff[:-1] + "+00:00" if cutoff.endswith("Z") else cutoff)
    except ValueError:
        return False
    if parsed.tzinfo is None or cutoff_dt.tzinfo is None:
        return False
    return parsed.astimezone(timezone.utc) <= cutoff_dt.astimezone(timezone.utc)


def _aware_utc_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def gaussian_kde_diagnostic(values: Sequence[float], *, min_n: int = MIN_KDE_SAMPLE) -> dict[str, Any]:
    """Select bandwidth by deterministic leave-one-out likelihood.

    The returned density is explicitly diagnostic and has no probability-field
    or calibration interface. Sparse samples abstain.
    """
    try:
        xs = [float(x) for x in values]
    except (TypeError, ValueError, OverflowError):
        return {"state": "BLOCKED_INVALID_DENSITY_INPUT", "n": 0,
                "blocker": "NON_NUMERIC_OBSERVATION", "forecastProbability": None}
    if any(not math.isfinite(x) for x in xs):
        return {"state": "BLOCKED_INVALID_DENSITY_INPUT", "n": len(xs),
                "blocker": "NONFINITE_OBSERVATION", "forecastProbability": None}
    if len(xs) < min_n:
        return {"state": "INACTIVE_INSUFFICIENT_DATA", "n": len(xs),
                "blocker": f"INSUFFICIENT_SAMPLE:{len(xs)}<{min_n}", "forecastProbability": None}
    original_n = len(xs)
    if original_n > MAX_KDE_SAMPLE:
        # Deterministic evenly spaced thinning bounds O(n^2) LOO work while
        # retaining the observed range; the result remains diagnostic-only.
        xs = [xs[round(i * (original_n - 1) / (MAX_KDE_SAMPLE - 1))]
              for i in range(MAX_KDE_SAMPLE)]
    mean = sum(xs) / len(xs)
    variance = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    sigma = math.sqrt(max(variance, 1e-12))
    base = 1.06 * sigma * len(xs) ** (-0.2)
    candidates = [base * factor for factor in (0.5, 0.75, 1.0, 1.5, 2.0)]
    root_2pi = math.sqrt(2.0 * math.pi)
    best_h, best_score = candidates[0], -math.inf
    candidate_scores = []
    for h in candidates:
        score = 0.0
        for i, point in enumerate(xs):
            density = sum(math.exp(-0.5 * ((point - other) / h) ** 2)
                          for j, other in enumerate(xs) if i != j)
            density /= (len(xs) - 1) * h * root_2pi
            score += math.log(max(density, 1e-300))
        score /= len(xs)
        candidate_scores.append({"bandwidth": h, "looLogLikelihood": score})
        if score > best_score:
            best_h, best_score = h, score
    density_se = math.sqrt(max(0.0, 1.0 / (len(xs) * best_h * root_2pi)))
    lower, upper = min(xs) - 3.0 * best_h, max(xs) + 3.0 * best_h
    grid = [lower + (upper - lower) * i / 100 for i in range(101)]
    density = [sum(math.exp(-0.5 * ((point - x) / best_h) ** 2) for x in xs)
               / (len(xs) * best_h * root_2pi) for point in grid]
    integral = sum((density[i] + density[i + 1]) * (grid[i + 1] - grid[i]) / 2
                   for i in range(len(grid) - 1))
    result = {
        "state": "SHADOW_DIAGNOSTIC",
        "algorithmVersion": "KDE-LOO-GAUSSIAN-v1",
        "n": len(xs),
        "inputN": original_n,
        "sampleCap": MAX_KDE_SAMPLE,
        "sampleReduction": "EVEN_SPACED_DETERMINISTIC" if original_n > MAX_KDE_SAMPLE else "NONE",
        "bandwidth": best_h,
        "looLogLikelihood": best_score,
        "bandwidthCandidates": candidate_scores,
        "densityGrid": [{"x": x, "density": y} for x, y in zip(grid, density)],
        "gridIntegralDiagnostic": integral,
        "densityNormalization": "ANALYTIC_GAUSSIAN_KERNEL_MIXTURE",
        "densityUncertaintyDiagnostic": density_se,
        "effectiveSampleSize": len(xs),
        "forecastProbability": None,
        "probabilityAuthority": "NONE_DIAGNOSTIC_ONLY",
    }
    result["inputContentHash"] = content_hash({"values": xs, "algorithmVersion": result["algorithmVersion"]})
    result["snapshotHash"] = content_hash({k: v for k, v in result.items() if k != "snapshotHash"})
    return result


def normalized_svd_diagnostic(
    matrix: Sequence[Sequence[float]], *, observed_at: Sequence[str] | None = None,
    forecast_cutoff: str | None = None, min_rows: int = MIN_SVD_ROWS,
) -> dict[str, Any]:
    """Validate chronology, normalize columns, and report a NumPy SVD rank.

    This reports structure only. It intentionally returns no forecast values.
    """
    rows = [[float(x) for x in row] for row in matrix]
    if not rows:
        return {"state": "BLOCKED_HISTORICAL_FEATURE_MATRIX_MISSING",
                "forecastProbability": None}
    if any(not all(math.isfinite(x) for x in row) for row in rows):
        return {"state": "BLOCKED_INVALID_FEATURE_MATRIX", "forecastProbability": None}
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        return {"state": "BLOCKED_INVALID_FEATURE_MATRIX", "forecastProbability": None}
    if observed_at is None or len(observed_at) != len(rows) or not forecast_cutoff:
        return {"state": "BLOCKED_TEMPORAL_METADATA_MISSING", "forecastProbability": None}
    if any(not _timestamp_at_or_before(ts, forecast_cutoff) for ts in observed_at):
        return {"state": "BLOCKED_POST_CUTOFF_FEATURE", "forecastProbability": None}
    timestamps = [_aware_utc_timestamp(ts) for ts in observed_at]
    if any(ts is None for ts in timestamps):
        return {"state": "BLOCKED_TEMPORAL_METADATA_INVALID", "forecastProbability": None}
    if timestamps != sorted(timestamps):
        return {"state": "BLOCKED_NONCHRONOLOGICAL_FEATURE_MATRIX", "forecastProbability": None}
    if len(rows) < min_rows or width < 2:
        return {"state": "INACTIVE_INSUFFICIENT_DATA", "rows": len(rows), "columns": width,
                "blocker": "INSUFFICIENT_FEATURE_MATRIX", "forecastProbability": None}
    if len(rows) > MAX_SVD_ROWS or width > MAX_SVD_COLUMNS:
        return {"state": "BLOCKED_RESOURCE_LIMIT", "rows": len(rows), "columns": width,
                "limits": {"maxRows": MAX_SVD_ROWS, "maxColumns": MAX_SVD_COLUMNS},
                "forecastProbability": None}
    try:
        import numpy as np
    except ImportError:
        return {"state": "FALLBACK_UNAVAILABLE", "blocker": "NUMPY_REQUIRED_FOR_SVD", "forecastProbability": None}
    array = np.asarray(rows, dtype=np.float64)
    means = array.mean(axis=0)
    scales = array.std(axis=0)
    scales[scales < 1e-12] = 1.0
    normalized = (array - means) / scales
    singular = np.linalg.svd(normalized, compute_uv=False)
    if singular.size == 0 or float(singular[0]) <= 1e-12:
        rank = 0
    else:
        rank = int(np.sum(singular > max(normalized.shape) * np.finfo(float).eps * singular[0]))
    fold_ranks: list[int] = []
    # Chronological prefix/suffix rank stability is a diagnostic only; neither
    # fold may contain rows after the forecast evidence cutoff.
    split = len(rows) // 2
    for fold in (rows[:split], rows[split:]):
        if len(fold) < 4:
            continue
        fold_array = np.asarray(fold, dtype=np.float64)
        fold_scales = fold_array.std(axis=0)
        fold_scales[fold_scales < 1e-12] = 1.0
        fold_normalized = (fold_array - fold_array.mean(axis=0)) / fold_scales
        fold_singular = np.linalg.svd(fold_normalized, compute_uv=False)
        threshold = max(fold_normalized.shape) * np.finfo(float).eps * (float(fold_singular[0]) if fold_singular.size else 0.0)
        fold_ranks.append(int(np.sum(fold_singular > threshold)))
    stability = "RANK_STABLE" if len(fold_ranks) == 2 and fold_ranks[0] == fold_ranks[1] else "RANK_UNSTABLE_OR_UNAVAILABLE"
    return {
        "state": "SHADOW_DIAGNOSTIC", "rows": len(rows), "columns": width,
        "algorithmVersion": "SVD-ZSCORE-CHRONOLOGICAL-v1",
        "inputMatrixHash": content_hash(rows),
        "rank": rank, "singularValues": [float(x) for x in singular],
        "normalization": "COLUMN_ZSCORE", "chronologicalFoldRanks": fold_ranks,
        "stability": stability,
        "forecastProbability": None,
        "probabilityAuthority": "NONE_DIAGNOSTIC_ONLY",
    }


def build_cutoff_safe_svd_matrix(
    rows: Sequence[Mapping[str, Any]], *, forecast_cutoff: str,
    min_rows: int = MIN_SVD_ROWS,
) -> dict[str, Any]:
    """Build an SVD matrix from numeric features frozen with prior forecasts.

    Training-dataset labels are used only to establish that the frozen row had
    settled by the current cutoff. Feature values themselves come only from
    the original frozen ``numericFeatures`` payload, never from settlement
    records. Rows without stable event/time identity or finite feature values
    are excluded and counted.
    """
    cutoff_dt = _aware_utc_timestamp(forecast_cutoff)
    if cutoff_dt is None:
        return {"state": "BLOCKED_VALID_FORECAST_CUTOFF_MISSING", "matrix": [],
                "featureNames": [], "sourceRowCount": 0, "excludedRows": len(rows)}
    eligible: list[tuple[datetime, str, str, dict[str, float]]] = []
    excluded_after_cutoff = 0
    excluded_invalid = 0
    for raw in rows:
        if not isinstance(raw, Mapping):
            excluded_invalid += 1
            continue
        decision = _aware_utc_timestamp(raw.get("decisionCutoff"))
        available = _aware_utc_timestamp(raw.get("labelAvailableAt"))
        event_id = str(raw.get("eventId") or "").strip()
        pid = str(raw.get("projectionId") or "").strip()
        features_raw = raw.get("numericFeatures")
        if decision and decision <= cutoff_dt and available and available <= cutoff_dt:
            pass
        elif decision and available and decision <= cutoff_dt and available > cutoff_dt:
            excluded_after_cutoff += 1
            continue
        else:
            excluded_invalid += 1
            continue
        if not event_id or not pid or decision >= available or not isinstance(features_raw, Mapping):
            excluded_invalid += 1
            continue
        features: dict[str, float] = {}
        valid = True
        for key, value in features_raw.items():
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                valid = False
                break
            if not math.isfinite(number):
                valid = False
                break
            features[str(key)] = number
        if not valid or len(features) < 2:
            excluded_invalid += 1
            continue
        eligible.append((decision, event_id, pid, features))
    eligible.sort(key=lambda item: (item[0], item[1], item[2]))
    if len(eligible) < min_rows:
        return {"state": "BLOCKED_HISTORICAL_FEATURE_MATRIX_MISSING", "matrix": [],
                "featureNames": [], "sourceRowCount": len(eligible),
                "excludedAfterCutoffRows": excluded_after_cutoff,
                "excludedInvalidRows": excluded_invalid,
                "blocker": f"INSUFFICIENT_FROZEN_FEATURE_ROWS:{len(eligible)}<{min_rows}"}
    feature_names = sorted(set.intersection(*(set(item[3]) for item in eligible)))
    if len(feature_names) < 2:
        return {"state": "BLOCKED_HISTORICAL_FEATURE_MATRIX_MISSING", "matrix": [],
                "featureNames": feature_names, "sourceRowCount": len(eligible),
                "excludedAfterCutoffRows": excluded_after_cutoff,
                "excludedInvalidRows": excluded_invalid,
                "blocker": "FEWER_THAN_TWO_SHARED_NUMERIC_FEATURES"}
    matrix = [[item[3][name] for name in feature_names] for item in eligible]
    observed_at = [item[0].isoformat().replace("+00:00", "Z") for item in eligible]
    lineage = [{"eventId": item[1], "projectionId": item[2], "decisionCutoff": observed_at[i]}
               for i, item in enumerate(eligible)]
    return {
        "state": "MATRIX_BUILT_FROM_FROZEN_FEATURES",
        "matrix": matrix,
        "observedAt": observed_at,
        "featureNames": feature_names,
        "sourceRowCount": len(eligible),
        "excludedAfterCutoffRows": excluded_after_cutoff,
        "excludedInvalidRows": excluded_invalid,
        "sourceLineageHash": content_hash(lineage),
        "inputMatrixHash": content_hash({"featureNames": feature_names, "matrix": matrix,
                                          "observedAt": observed_at, "lineage": lineage}),
        "source": "FROZEN_CHRONOLOGICAL_TRAINING_ROWS.numericFeatures",
    }


def empirical_discrete_distribution_diagnostic(
    values: Sequence[float], *, min_n: int = MIN_KDE_SAMPLE,
) -> dict[str, Any]:
    """Bounded empirical fallback for discrete/count outcomes.

    Gaussian KDE smooths integer mass across impossible fractional values. For
    counts and other discrete domains, retain the observed point masses instead.
    This is a distribution diagnostic only; it never supplies forecast or
    calibrated probability authority.
    """
    try:
        xs = [float(value) for value in values]
    except (TypeError, ValueError, OverflowError):
        return {"state": "BLOCKED_INVALID_DENSITY_INPUT", "n": 0,
                "blocker": "NON_NUMERIC_OBSERVATION", "probabilityAuthority": False}
    if any(not math.isfinite(value) for value in xs):
        return {"state": "BLOCKED_INVALID_DENSITY_INPUT", "n": len(xs),
                "blocker": "NONFINITE_OBSERVATION", "probabilityAuthority": False}
    if any(not value.is_integer() for value in xs):
        return {"state": "BLOCKED_INVALID_DENSITY_INPUT", "n": len(xs),
                "blocker": "NONINTEGER_DISCRETE_OBSERVATION", "probabilityAuthority": False}
    if len(xs) < min_n:
        return {"state": "INACTIVE_INSUFFICIENT_DATA", "n": len(xs),
                "blocker": f"INSUFFICIENT_SAMPLE:{len(xs)}<{min_n}",
                "probabilityAuthority": False}
    counts: dict[str, int] = {}
    for value in xs:
        key = str(int(value)) if value.is_integer() else format(value, ".12g")
        counts[key] = counts.get(key, 0) + 1
    masses = {key: count / len(xs) for key, count in sorted(counts.items(), key=lambda item: float(item[0]))}
    return {
        "state": "EMPIRICAL_DISCRETE_DIAGNOSTIC",
        "algorithmId": "ALG-ML-PROB-010",
        "algorithmVersion": require_algorithm("ALG-ML-PROB-010").introduced_version,
        "methodVersion": "EMPIRICAL-DISCRETE-PMF-v1",
        "n": len(xs),
        "uniqueValues": len(counts),
        "mass": masses,
        "inputContentHash": content_hash(xs),
        "probabilityAuthority": False,
    }


def _shared_world_diagnostics(portfolio: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    outcome_rows: list[bytes] = []
    for item in portfolio:
        outcomes = item.get("_selectionOutcomes")
        if isinstance(outcomes, (bytes, bytearray)):
            outcome_rows.append(bytes(outcomes))
    if len(outcome_rows) != len(portfolio) or not outcome_rows:
        return {"state": "BLOCKED_SHARED_OUTCOMES_MISSING", "worldCount": 0,
                "correlations": [], "convergence": "NOT_EVALUATED"}
    n = min(len(x) for x in outcome_rows)
    if n < 2:
        return {"state": "BLOCKED_INSUFFICIENT_WORLDS", "worldCount": n,
                "correlations": [], "convergence": "NOT_EVALUATED"}
    # The runner maps loss/push/win to 0/1/2, so each row is one aligned world.
    correlations = []
    for i in range(len(outcome_rows)):
        for j in range(i + 1, len(outcome_rows)):
            a = [x / 2.0 for x in outcome_rows[i][:n]]
            b = [x / 2.0 for x in outcome_rows[j][:n]]
            ma, mb = sum(a) / n, sum(b) / n
            va = sum((x - ma) ** 2 for x in a)
            vb = sum((x - mb) ** 2 for x in b)
            corr = None if va <= 1e-12 or vb <= 1e-12 else sum((a[k] - ma) * (b[k] - mb) for k in range(n)) / math.sqrt(va * vb)
            correlations.append({"leftIndex": i, "rightIndex": j, "correlation": corr})
    # Fixed prefix-vs-full diagnostic over the same aligned worlds.
    half = max(1, n // 2)
    convergence = []
    for values in outcome_rows:
        full = sum(v == 2 for v in values[:n]) / n
        early = sum(v == 2 for v in values[:half]) / half
        convergence.append({"halfSampleWinRate": early, "fullSampleWinRate": full, "absoluteDelta": abs(early - full)})
    state_distribution: dict[str, int] = {}
    win_count_distribution: dict[str, int] = {}
    all_win = 0
    any_loss = 0
    for world_index in range(n):
        outcomes = [row[world_index] for row in outcome_rows]
        state_key = "".join({0: "L", 1: "P", 2: "W"}.get(value, "?") for value in outcomes)
        state_distribution[state_key] = state_distribution.get(state_key, 0) + 1
        wins = sum(value == 2 for value in outcomes)
        win_count_distribution[str(wins)] = win_count_distribution.get(str(wins), 0) + 1
        all_win += wins == len(outcomes)
        any_loss += any(value == 0 for value in outcomes)
    return {"state": "EXECUTED", "worldCount": n, "correlations": correlations,
            "alignedOutcomeHash": content_hash([list(x[:n]) for x in outcome_rows]),
            "jointStateDistribution": state_distribution,
            "winCountDistribution": win_count_distribution,
            "allLegsWinProbability": all_win / n,
            "anyLegLossProbability": any_loss / n,
            "jointOutcomeMethod": "ALIGNED_SHARED_EVENT_WORLD_ROWS",
            "convergence": "PREFIX_VS_FULL_DIAGNOSTIC", "convergenceByLeg": convergence}


def _calibration_challenger_report(rows: Sequence[Mapping[str, Any]], *, min_train_n: int = 30,
                                   min_test_n: int = 5) -> dict[str, Any]:
    """Fit isotonic calibration only inside event-disjoint chronological folds.

    The report is an OOS challenger diagnostic. It never activates a champion
    calibration cell or changes LR000000.
    """
    normalized = []
    for raw in rows:
        if not isinstance(raw, Mapping) or raw.get("binaryOutcome") not in {0, 1}:
            continue
        decision = _aware_utc_timestamp(raw.get("decisionCutoff"))
        available = _aware_utc_timestamp(raw.get("labelAvailableAt"))
        event_id = str(raw.get("eventId") or "").strip()
        try:
            p = float(raw.get("forecastP", raw.get("selectedP")))
        except (TypeError, ValueError, OverflowError):
            continue
        if (decision is None or available is None or decision >= available or not event_id
                or not math.isfinite(p) or not 0.0 <= p <= 1.0):
            continue
        normalized.append({"decision": decision, "available": available, "eventId": event_id,
                           "p": p, "y": int(raw["binaryOutcome"])})
    cutoffs = sorted({row["decision"] for row in normalized})
    folds = []
    all_base: list[float] = []
    all_base_y: list[int] = []
    all_challenger: list[float] = []
    all_challenger_y: list[int] = []
    from dcm.algorithms.ml_families import isotonic_regression

    def score(preds: list[float], labels: list[int]) -> dict[str, Any]:
        if not preds:
            return {"n": 0, "brier": None, "brierStandardError": None,
                    "logLoss": None, "logLossStandardError": None, "ece": None, "reliability": []}
        sq_errors = [(p-y) ** 2 for p, y in zip(preds, labels)]
        row_losses = [-(y * math.log(max(1e-12, min(1-1e-12, p)))
                        + (1-y) * math.log(max(1e-12, min(1-1e-12, 1-p))))
                      for p, y in zip(preds, labels)]
        brier = sum(sq_errors) / len(preds)
        log_loss = sum(row_losses) / len(preds)
        def standard_error(values: list[float], mean: float) -> float:
            if len(values) < 2:
                return 0.0
            variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
            return math.sqrt(variance / len(values))
        bins = []
        ece = 0.0
        for bin_index in range(10):
            members = [(p, y) for p, y in zip(preds, labels)
                       if min(9, int(p * 10)) == bin_index]
            if not members:
                continue
            mean_p = sum(p for p, _ in members) / len(members)
            rate = sum(y for _, y in members) / len(members)
            count = len(members)
            z = 1.96
            denominator = 1.0 + z*z/count
            center = (rate + z*z/(2*count)) / denominator
            half_width = z * math.sqrt(rate*(1-rate)/count + z*z/(4*count*count)) / denominator
            ece += len(members) / len(preds) * abs(mean_p - rate)
            bins.append({"bin": bin_index, "n": len(members), "meanForecast": mean_p,
                         "observedRate": rate,
                         "observedRateWilson95": [max(0.0, center-half_width), min(1.0, center+half_width)]})
        return {"n": len(preds), "brier": brier,
                "brierStandardError": standard_error(sq_errors, brier),
                "logLoss": log_loss,
                "logLossStandardError": standard_error(row_losses, log_loss), "ece": ece,
                "reliability": bins}

    for cutoff in cutoffs[1:]:
        test = [row for row in normalized if row["decision"] == cutoff]
        test_events = {row["eventId"] for row in test}
        train = [row for row in normalized if row["decision"] < cutoff and row["available"] < cutoff
                 and row["eventId"] not in test_events]
        if len(train) < min_train_n or len(test) < min_test_n:
            continue
        ordered = sorted(train, key=lambda row: (row["p"], row["decision"], row["eventId"]))
        fitted = isotonic_regression([r["p"] for r in ordered], [r["y"] for r in ordered])
        train_x = [r["p"] for r in ordered]

        def predict(p: float) -> float:
            nearest = min(range(len(train_x)), key=lambda i: (abs(train_x[i] - p), i))
            return max(0.001, min(0.999, float(fitted[nearest])))

        base_p = [row["p"] for row in test]
        labels = [row["y"] for row in test]
        challenger_p = [predict(p) for p in base_p]
        base_metrics, challenger_metrics = score(base_p, labels), score(challenger_p, labels)
        folds.append({"testCutoff": cutoff.isoformat(), "trainN": len(train), "testN": len(test),
                      "trainEventCount": len({r["eventId"] for r in train}),
                      "testEventCount": len(test_events), "sameEventOverlap": False,
                      "trainingLabelsAvailableBeforeTest": True,
                      "baseline": base_metrics, "isotonicChallenger": challenger_metrics})
        all_base.extend(base_p); all_base_y.extend(labels)
        all_challenger.extend(challenger_p); all_challenger_y.extend(labels)
    return {
        "state": "CHRONOLOGICAL_OOS_CHALLENGER_EVALUATED" if folds else "BLOCKED_INSUFFICIENT_EVENT_DISJOINT_FOLDS",
        "method": "ISOTONIC_REGRESSION_EVENT_DISJOINT_EXPANDING_WINDOW",
        "foldCount": len(folds), "folds": folds,
        "baselinePooled": score(all_base, all_base_y),
        "isotonicChallengerPooled": score(all_challenger, all_challenger_y),
        "promotionState": "CHALLENGER_ONLY_NO_PROMOTION",
        "learningRevision": "LR000000", "predictiveClaim": "NONE",
    }


def apply_directional_research_conflict_gate(
    forecasts: Sequence[Mapping[str, Any]], *, forecast_cutoff: str,
    allow_manual_order_only: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Block only verified same-market evidence that contradicts a selected side.

    This is a fail-closed review gate, not an inversion rule. Upstream evidence
    must explicitly attest identity, market comparability, cutoff, and hard-gate
    eligibility; unverified trend claims remain diagnostics only.
    """
    cutoff = _aware_utc_timestamp(forecast_cutoff)
    out: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    def market_key(value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

    def side_key(value: Any) -> str:
        raw = str(value or "").strip().upper()
        if raw in {"OVER", "HIGHER", "MORE", "ABOVE"}:
            return "MORE"
        if raw in {"UNDER", "LOWER", "LESS", "BELOW"}:
            return "LESS"
        return ""

    for source in forecasts:
        row = dict(source)
        core = row.get("row") if isinstance(row.get("row"), Mapping) else {}
        selected = side_key(row.get("selectedSide"))
        target_market = market_key(core.get("marketDefinitionId") or core.get("market"))
        try:
            selected_line = float(core.get("line"))
        except (TypeError, ValueError, OverflowError):
            selected_line = None
        conflicts = []
        for evidence in row.get("directionalResearchEvidence") or ():
            if not isinstance(evidence, Mapping):
                continue
            evidence_market = market_key(evidence.get("marketDefinitionId") or evidence.get("market"))
            available = _aware_utc_timestamp(evidence.get("labelAvailableAt") or evidence.get("availableAt"))
            temporal_ok = bool(available and cutoff and available <= cutoff)
            if (not temporal_ok and allow_manual_order_only
                    and str(evidence.get("cutoffRelation") or "").upper() == "BEFORE_DECISION"):
                temporal_ok = True
            direction = side_key(evidence.get("direction"))
            try:
                evidence_line = float(evidence.get("line"))
                sample_n = int(evidence.get("sampleN"))
            except (TypeError, ValueError, OverflowError):
                continue
            if (not selected or not target_market or target_market != evidence_market
                    or not temporal_ok or not direction
                    or sample_n < 1):
                continue
            comparable_line = selected_line is not None and (
                abs(selected_line - evidence_line) <= 1e-9
                or (selected == "MORE" and direction == "LESS" and evidence_line <= selected_line)
                or (selected == "LESS" and direction == "MORE" and evidence_line >= selected_line)
            )
            if not comparable_line or selected == direction:
                continue
            conflicts.append({
                "market": str(core.get("marketDefinitionId") or core.get("market")),
                "selectedSide": selected,
                "researchSide": direction,
                "selectedLine": selected_line,
                "researchLine": evidence_line,
                "sampleN": sample_n,
                "sourceHash": str(evidence.get("sourceHash") or ""),
                "availableAt": available.isoformat() if available else None,
                "temporalBasis": "ABSOLUTE_UTC_CUTOFF" if available and cutoff else "MANUAL_SOURCE_ORDER_ONLY",
                "hardGateEligible": bool(evidence.get("hardGateEligible")
                                           and evidence.get("identityVerified")
                                           and evidence.get("marketComparable")),
            })
        if conflicts:
            hard = any(item["hardGateEligible"] for item in conflicts)
            row["directionalResearchConflicts"] = conflicts
            row["directionalResearchConflictState"] = "BLOCKED_REVIEW_REQUIRED" if hard else "SHADOW_CONFLICT_ONLY"
            if hard:
                row["directionalResearchBlocker"] = "VERIFIED_SAME_MARKET_EVIDENCE_CONTRADICTS_SELECTED_SIDE"
                row["productionSelectable"] = False
                row["modeledPlayable"] = False
                row["grade"] = "LEAN" if row.get("grade") == "PLAYABLE" else row.get("grade")
                row["blocker"] = row.get("blocker") or row["directionalResearchBlocker"]
            decisions.append({"projectionId": str(core.get("projectionId") or ""),
                              "state": row["directionalResearchConflictState"],
                              "conflicts": conflicts, "automaticallyInverted": False})
        out.append(row)
    report = {"state": "EVALUATED", "evaluatedForecasts": len(out),
              "conflictCount": sum(len(item["conflicts"]) for item in decisions),
              "hardBlockedCount": sum(item["state"] == "BLOCKED_REVIEW_REQUIRED" for item in decisions),
              "decisions": decisions, "automaticInverseAllowed": False,
              "temporalBasis": ("MANUAL_SOURCE_ORDER_ONLY" if allow_manual_order_only else
                                "ABSOLUTE_UTC_CUTOFF" if cutoff else "BLOCKED_NO_VALID_FORECAST_CUTOFF")}
    report["contentHash"] = content_hash({k: v for k, v in report.items() if k != "contentHash"})
    return out, report


def execute_advanced_modeling(
    *, forecasts: Sequence[Mapping[str, Any]], portfolio: Sequence[Mapping[str, Any]],
    calibration_state: Mapping[str, Any] | None, forecast_cutoff: str,
    payout_table_hash: str | None = None, stake: float | None = None,
    seed_input_hash: str | None = None, model_config_hash: str | None = None,
    event_world_metadata: Mapping[str, Any] | None = None,
    joint_backend_metadata: Sequence[Mapping[str, Any]] = (),
    run_id: str = "UNAVAILABLE",
    execution_mode: str = "CANONICAL_RUNNER_EXECUTION",
    sport_scopes: Sequence[str] = (),
    directional_research_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate each modeling capability for a canonical runner invocation."""
    rows = list(forecasts)
    started = time.perf_counter()
    receipts: list[dict[str, Any]] = []
    event_ids = [str((row.get("row") or {}).get("eventId") or "") for row in rows]
    market_ids = [str((row.get("row") or {}).get("projectionId") or "") for row in rows]
    input_hashes = [str(value) for row in rows for value in (row.get("evidenceHashes") or [])]
    input_hashes.extend(str(row.get("parameterSnapshotHash")) for row in rows if row.get("parameterSnapshotHash"))
    if seed_input_hash:
        input_hashes.append(seed_input_hash)
    if model_config_hash:
        input_hashes.append(model_config_hash)
    if (calibration_state or {}).get("contentHash"):
        input_hashes.append(str(calibration_state["contentHash"]))
    kde_done = 0
    kde_fallback_done = 0
    kde_blocked = 0
    kde_discrete_rows = 0
    kde_started = time.perf_counter()
    kde_snapshots: list[dict[str, Any]] = []
    historical_kde = list((calibration_state or {}).get("kdeComparableSamples") or [])
    diagnostic_forecasts = [
        row for row in rows
        if row.get("selectedSide") and row.get("state") == "MODELED"
    ][:25]
    for row in diagnostic_forecasts:
        is_continuous = str(row.get("outcomeDomain") or "DISCRETE").upper() in {
            "CONTINUOUS", "CONTINUOUS_APPROXIMATION_VALIDATED"
        }
        kde_discrete_rows += not is_continuous
        comparable_key = "|".join((
            str((row.get("row") or {}).get("sportFamily") or ""),
            str((row.get("row") or {}).get("league") or ""),
            str((row.get("row") or {}).get("market") or ""),
            str(row.get("selectedSide") or ""),
        ))
        comparable = [
            sample for sample in historical_kde
            if isinstance(sample, Mapping)
            and str(sample.get("comparableKey") or "") == comparable_key
            and _timestamp_at_or_before(sample.get("observedAt"), forecast_cutoff)
            and _timestamp_at_or_before(sample.get("labelAvailableAt"), forecast_cutoff)
            and _timestamp_at_or_before(sample.get("observedAt"), str(sample.get("labelAvailableAt") or ""))
        ]
        try:
            comparable_values = [float(sample["value"]) for sample in comparable]
        except (KeyError, TypeError, ValueError):
            comparable_values = []
        result = (gaussian_kde_diagnostic(comparable_values) if is_continuous
                  else empirical_discrete_distribution_diagnostic(comparable_values))
        if result.get("state") in {"SHADOW_DIAGNOSTIC", "EMPIRICAL_DISCRETE_DIAGNOSTIC"}:
            kde_snapshots.append({
                "marketId": str((row.get("row") or {}).get("projectionId") or ""),
                "comparableKey": comparable_key,
                "snapshotHash": result.get("snapshotHash"),
                "inputContentHash": result.get("inputContentHash"),
                "methodState": result.get("state"),
                "diagnostic": result,
            })
        kde_done += result["state"] == "SHADOW_DIAGNOSTIC"
        kde_fallback_done += result["state"] == "EMPIRICAL_DISCRETE_DIAGNOSTIC"
        kde_blocked += result["state"] not in {"SHADOW_DIAGNOSTIC", "EMPIRICAL_DISCRETE_DIAGNOSTIC"}
    kde_state = ("SHADOW_DIAGNOSTIC" if kde_done and not kde_fallback_done else
                 "FALLBACK_EXECUTED" if kde_fallback_done and not kde_done else
                 "MIXED_DIAGNOSTIC_AND_FALLBACK" if kde_done and kde_fallback_done else
                 "EXECUTED_READINESS_ONLY")
    kde_blockers = []
    if kde_done:
        kde_blockers.append("CONTINUOUS_DENSITY_IS_DIAGNOSTIC_ONLY_NO_PROBABILITY_AUTHORITY")
    if kde_fallback_done:
        kde_blockers.append("DISCRETE_EMPIRICAL_FALLBACK_IS_DIAGNOSTIC_ONLY_NO_PROBABILITY_AUTHORITY")
    if kde_blocked and diagnostic_forecasts:
        kde_blockers.append("NO_SUFFICIENT_VALIDATED_COMPARABLE_HISTORY")
    if not diagnostic_forecasts:
        kde_blockers.append("NO_MODELED_MARKET_INPUTS_RESEARCH_ONLY_OR_EMPTY_RUN")
    receipts.append(_receipt("KDE", kde_state,
        producer="cutoff-safe comparable historical outcomes", consumer="advanced-modeling density diagnostics",
        blockers=kde_blockers,
        details={"evaluatedRows": len(diagnostic_forecasts), "populationRows": len(rows),
                 "historicalSampleRows": len(historical_kde),
                 "diagnosticRows": kde_done, "inactiveRows": kde_blocked,
                 "discreteFallbackRows": kde_fallback_done,
                 "discreteRowsEvaluated": kde_discrete_rows,
                 "densitySnapshots": kde_snapshots,
                 "densitySnapshotConsumer": "advanced-modeling receipt and audit diagnostics",
                 "forecastProbabilityProduced": False}, run_id=run_id,
        forecast_cutoff=forecast_cutoff, input_hashes=input_hashes, event_ids=event_ids,
        market_ids=market_ids, applicability="CONTINUOUS_KDE_OR_DISCRETE_EMPIRICAL_FALLBACK; INPUT_READINESS_ALWAYS_EVALUATED",
        duration_ms=round((time.perf_counter() - kde_started) * 1000, 3)))

    svd_started = time.perf_counter()
    history_matrix = (calibration_state or {}).get("historicalRoleOpponentFeatureMatrix")
    matrix_input_summary: dict[str, Any] = {"source": "CANONICAL_FEATURE_MATRIX"}
    if not isinstance(history_matrix, Mapping):
        history_matrix = build_cutoff_safe_svd_matrix(
            (calibration_state or {}).get("walkforwardRows") or [],
            forecast_cutoff=forecast_cutoff,
        )
        matrix_input_summary = {
            "source": history_matrix.get("source", "FROZEN_CHRONOLOGICAL_TRAINING_ROWS.numericFeatures"),
            "sourceRowCount": history_matrix.get("sourceRowCount", 0),
            "excludedAfterCutoffRows": history_matrix.get("excludedAfterCutoffRows", 0),
            "excludedInvalidRows": history_matrix.get("excludedInvalidRows", 0),
            "featureNames": history_matrix.get("featureNames", []),
            "sourceLineageHash": history_matrix.get("sourceLineageHash"),
            "inputMatrixHash": history_matrix.get("inputMatrixHash"),
            "blocker": history_matrix.get("blocker"),
        }
    if isinstance(history_matrix, Mapping):
        svd = normalized_svd_diagnostic(
            history_matrix.get("matrix") or [],
            observed_at=history_matrix.get("observedAt"),
            forecast_cutoff=forecast_cutoff,
        )
    else:
        svd = normalized_svd_diagnostic([], forecast_cutoff=forecast_cutoff)
    receipts.append(_receipt("SVD", svd["state"], producer="canonical historical feature store",
        consumer="advanced-modeling feature diagnostics",
        blockers=[] if svd.get("state") == "SHADOW_DIAGNOSTIC" else [str(svd.get("state") or "VALIDATED_ROLE_OPPONENT_HISTORY_UNAVAILABLE")],
        details={"diagnostic": svd, "matrixInput": matrix_input_summary,
                 "forecastProbabilityProduced": False}, run_id=run_id,
        forecast_cutoff=forecast_cutoff, input_hashes=input_hashes, event_ids=event_ids,
        market_ids=market_ids, applicability="APPLICABLE_WHEN_VALID_ROLE_OPPONENT_MATRIX_EXISTS",
        duration_ms=round((time.perf_counter() - svd_started) * 1000, 3)))

    worlds_started = time.perf_counter()
    world_rows = [r for r in rows if isinstance(r.get("_worldValues"), (list, tuple))
                  and isinstance(r.get("_selectionOutcomes"), (bytes, bytearray))]
    world_receipt = _shared_world_diagnostics(world_rows[:25])
    conservation = dict((event_world_metadata or {}).get("conservationFlags") or {})
    if conservation.get("identitiesHeld") is False:
        world_receipt["state"] = "BLOCKED_CONSERVATION_FAILURE"
    backends = sorted({str(m.get("backend")) for m in joint_backend_metadata if m.get("backend")})
    rng_versions = sorted({str(m.get("rngVersion")) for m in joint_backend_metadata if m.get("rngVersion")})
    receipts.append(_receipt("MONTE_CARLO", world_receipt["state"], producer="dcm.runner shared EventWorld backend",
        consumer="probability and portfolio joint outcomes",
        blockers=[] if world_receipt["state"] == "EXECUTED" else list(dict.fromkeys([
            world_receipt["state"],
            *(["CANONICAL_EVENTWORLD_OUTPUTS_MISSING"] if not world_rows else []),
        ])),
        details={"backend": backends or ["NOT_RECORDED"], "rngVersion": rng_versions or ["NOT_RECORDED"],
                 "seedSource": "input HAR content hash", "seedInputHash": seed_input_hash,
                 "randomSeed": seed_input_hash,
                 "modelConfigHash": model_config_hash, "conservation": conservation,
                 "rngVersion": rng_versions or ["NOT_RECORDED"],
                 "worlds": world_receipt["worldCount"], "diagnostics": world_receipt},
        run_id=run_id, forecast_cutoff=forecast_cutoff, input_hashes=input_hashes,
        event_ids=event_ids, market_ids=market_ids,
        applicability="APPLICABLE_WHEN_SHARED_EVENTWORLDS_EXIST",
        duration_ms=round((time.perf_counter() - worlds_started) * 1000, 3)))

    calibration_started = time.perf_counter()
    calibration_rows = [r for r in rows if r.get("calibrationState")]
    historical = []
    historical_walkforward = []
    for record in (calibration_state or {}).get("settlements") or []:
        if not isinstance(record, Mapping) or record.get("binaryOutcome") not in {0, 1}:
            continue
        available_at = _aware_utc_timestamp(record.get("labelAvailableAt"))
        decision_at = _aware_utc_timestamp(record.get("decisionCutoff"))
        cutoff_at = _aware_utc_timestamp(forecast_cutoff)
        if not available_at or not decision_at or not cutoff_at:
            continue
        if decision_at >= available_at or available_at > cutoff_at:
            continue
        if not _timestamp_at_or_before(record.get("decisionCutoff"), forecast_cutoff):
            continue
        historical.append(dict(record))
    for record in (calibration_state or {}).get("walkforwardRows") or []:
        if not isinstance(record, Mapping):
            continue
        available_at = _aware_utc_timestamp(record.get("labelAvailableAt"))
        decision_at = _aware_utc_timestamp(record.get("decisionCutoff"))
        cutoff_at = _aware_utc_timestamp(forecast_cutoff)
        if (available_at and decision_at and cutoff_at and decision_at < available_at <= cutoff_at
                and record.get("binaryOutcome") in {0, 1}):
            historical_walkforward.append(dict(record))
    cal_metrics = evaluate_calibration_readiness(historical)
    from dcm.learning.walkforward import run_walkforward
    walkforward_metrics = run_walkforward(historical_walkforward)
    calibration_challenger = _calibration_challenger_report(historical_walkforward)
    active = sum(str(r.get("calibrationState")) == "ACTIVE_CHRONOLOGICAL_CELL" for r in calibration_rows)
    calibration_blockers = list(cal_metrics.get("reasons") or []) if not cal_metrics.get("ready") else ["LR000000_PROMOTION_GATE_REMAINS"]
    if not forecast_cutoff:
        calibration_blockers.append("VALID_FORECAST_CUTOFF_MISSING")
    receipts.append(_receipt("CALIBRATION", "EXECUTED_READINESS_ONLY", producer="dcm.learning.calibration",
        consumer="canonical probability records and portfolio gate",
        blockers=calibration_blockers,
        details={"candidateRowsEvaluated": len(calibration_rows), "activeRows": active,
                 "chronologicalReadiness": cal_metrics, "learningRevision": "LR000000",
                 "predictiveClaim": "NONE", "historicalSettlementRows": len(historical),
                 "calibrationSnapshotHash": (calibration_state or {}).get("contentHash"),
                 "walkForward": walkforward_metrics,
                 "calibrationChallenger": calibration_challenger,
                 "outOfSampleMetricsProduced": bool(
                     calibration_challenger.get("foldCount", 0)
                 )}, run_id=run_id,
        forecast_cutoff=forecast_cutoff, input_hashes=input_hashes, event_ids=event_ids,
        market_ids=market_ids, applicability="APPLICABLE_WHEN_CUTOFF_SAFE_LABELS_EXIST",
        duration_ms=round((time.perf_counter() - calibration_started) * 1000, 3)))

    portfolio_started = time.perf_counter()
    selected_portfolio = list(portfolio)
    portfolio_source = "SELECTED_PORTFOLIO"
    if len(selected_portfolio) < 2:
        # A final card can be empty while the run still has modeled candidate
        # outcomes. Analyze those aligned worlds for ranking/diagnostic use;
        # never promote them to selected legs or payout EV.
        selected_portfolio = [row for row in rows
                              if isinstance(row.get("_selectionOutcomes"), (bytes, bytearray))]
        portfolio_source = "MODELED_CANDIDATE_POOL"
    if len(selected_portfolio) >= 2:
        corr = _shared_world_diagnostics(selected_portfolio[:25])
        corr["analysisPopulation"] = portfolio_source
        corr["state"] = "EXECUTED" if corr["state"] == "EXECUTED" else corr["state"]
    else:
        corr = {
            "state": "EXECUTED_EMPTY_PORTFOLIO_DIAGNOSTIC",
            "worldCount": 0,
            "correlations": [],
            "jointStateDistribution": {},
            "winCountDistribution": {},
            "allLegsWinProbability": None,
            "anyLegLossProbability": None,
            "jointOutcomeMethod": "NO_MULTI_SELECTION_INPUTS",
            "analysisPopulation": "EMPTY_OR_SINGLETON_CANDIDATE_POOL",
        }
    receipts.append(_receipt("PORTFOLIO_CORRELATION", corr["state"], producer="shared aligned selection outcomes",
        consumer="dcm.selection.portfolio.build_card / EV joint outcomes",
        blockers=[] if corr["state"] in {"EXECUTED", "EXECUTED_EMPTY_PORTFOLIO_DIAGNOSTIC"} else ["SHARED_PORTFOLIO_OUTCOMES_UNAVAILABLE"],
        details={"correlations": corr.get("correlations", []), "worldCount": corr.get("worldCount", 0),
                 "jointStateDistribution": corr.get("jointStateDistribution", {}),
                 "winCountDistribution": corr.get("winCountDistribution", {}),
                 "allLegsWinProbability": corr.get("allLegsWinProbability"),
                 "anyLegLossProbability": corr.get("anyLegLossProbability"),
                 "alignedOutcomeHash": corr.get("alignedOutcomeHash"),
                 "jointOutcomeMethod": corr.get("jointOutcomeMethod", "NOT_AVAILABLE"),
                 "portfolioSize": len(portfolio), "analyzedCandidateCount": len(selected_portfolio),
                 "analysisPopulation": corr.get("analysisPopulation"),
                 "usesIndependentMarginals": False},
        run_id=run_id, forecast_cutoff=forecast_cutoff, input_hashes=input_hashes,
        event_ids=event_ids, market_ids=market_ids,
        applicability="SELECTED_PORTFOLIO_OR_MODELED_CANDIDATE_POOL; EMPTY_SET_DIAGNOSTIC_IF_NO_MULTI_SELECTION_INPUT",
        duration_ms=round((time.perf_counter() - portfolio_started) * 1000, 3)))

    ev_started = time.perf_counter()
    if not payout_table_hash or stake is None or len(portfolio) < 2:
        ev_state = "EV_UNVERIFIED"
        missing_ev_inputs = []
        if not payout_table_hash:
            missing_ev_inputs.append("CAPTURED_PAYOUT_RULES_MISSING")
        if stake is None:
            missing_ev_inputs.append("ENTRY_STAKE_MISSING")
        if len(portfolio) < 2:
            missing_ev_inputs.append("VERIFIED_MULTI_SELECTION_ENTRY_MISSING")
        ev_details = {"expectedValue": None, "required": ["captured payout table hash", "stake", "entry rules"],
                      "missingInputs": missing_ev_inputs}
        ev_blockers = ["PAYOUT_RULES_OR_ENTRY_CONTRACT_MISSING", *missing_ev_inputs]
    elif corr["state"] != "EXECUTED":
        ev_state = "EV_UNVERIFIED"
        ev_details = {"expectedValue": None}
        ev_blockers = ["JOINT_OUTCOME_DISTRIBUTION_REQUIRED"]
    else:
        from dcm.platform.prizepicks.economics import expected_return_from_worlds
        joint = []
        outcome_rows = [bytes(item["_selectionOutcomes"]) for item in portfolio]
        count = min(map(len, outcome_rows))
        for world_index in range(count):
            joint.append(["WIN" if item[world_index] == 2 else "PUSH" if item[world_index] == 1 else "LOSS"
                          for item in outcome_rows])
        try:
            ev_details = expected_return_from_worlds(table_hash=payout_table_hash, worlds=joint, stake=float(stake))
            # A sound payout calculation from uncalibrated simulated outcomes is
            # useful as a diagnostic. The canonical runner has no verified
            # EntryContract-to-world settlement adapter for voids, reversions,
            # admin removals, and all Flex/Power payout rows, so it is never a
            # complete EV certification on this path.
            if not active or not cal_metrics.get("ready"):
                ev_state = "SHADOW_DIAGNOSTIC_UNCALIBRATED"
                ev_blockers = ["CALIBRATED_JOINT_PROBABILITIES_MISSING"]
            else:
                ev_state = "SHADOW_DIAGNOSTIC_ENTRY_RULES_UNVERIFIED"
                ev_blockers = ["CAPTURED_ENTRY_CONTRACT_AND_COMPLETE_SETTLEMENT_ADAPTER_MISSING"]
            ev_details["certification"] = "BLOCKED_UNVERIFIED_ENTRY_SETTLEMENT_RULES"
        except Exception as exc:
            ev_state, ev_blockers = "BLOCKED_PAYOUT_RULES", [f"{type(exc).__name__}:{exc}"]
            ev_details = {"expectedValue": None}
    receipts.append(_receipt("PAYOUT_EV", ev_state, producer="PrizePicks payout rules + joint outcomes",
        consumer="portfolio ranking and freeze eligibility", blockers=ev_blockers, details=ev_details,
        run_id=run_id, forecast_cutoff=forecast_cutoff, input_hashes=input_hashes,
        event_ids=event_ids, market_ids=market_ids,
        applicability="ENTRY_CONTRACT_CHECKED_EVERY_RUN; PRODUCTION_EV_REQUIRES_VERIFIED_MULTI_SELECTION_ENTRY",
        duration_ms=round((time.perf_counter() - ev_started) * 1000, 3)))

    graph_started = time.perf_counter()
    compiled_dag = compile_advanced_execution_dag()
    registry_rows = load_algorithm_registry()
    lifecycle_counts: dict[str, int] = {}
    for record in registry_rows:
        lifecycle_counts[record.lifecycle] = lifecycle_counts.get(record.lifecycle, 0) + 1
    graph_details = {
        "registrySha256": algorithm_registry_sha256(),
        "registryAlgorithmCount": len(registry_rows),
        "registryLifecycleCounts": lifecycle_counts,
        "dedicatedCapabilityCount": len(CAPABILITY_DAG),
        "registeredDoesNotMeanExecuted": True,
        "unrelatedRegistryAlgorithmsExecutionState": "TRACKED_BY_CANONICAL_ALGORITHM_PLAN_NOT_CLAIMED_BY_ADVANCED_LAYER",
    }
    receipts.append(_receipt("ALGORITHM_GRAPH", "EXECUTED_GRAPH_WITH_CAPABILITY_BLOCKERS",
        producer="dcm.algorithms.registry + compile_advanced_execution_dag",
        consumer="seven-capability execution controller", details=graph_details,
        run_id=run_id, forecast_cutoff=forecast_cutoff, input_hashes=input_hashes,
        event_ids=event_ids, market_ids=market_ids, applicability="APPLICABLE_EVERY_CANONICAL_RUN",
        duration_ms=round((time.perf_counter() - graph_started) * 1000, 3)))
    receipt_by_capability = {r["capability"]: r for r in receipts}
    stages = [{"stage": stage, "algorithmId": CAPABILITY_ALGORITHMS[stage], "input": before, "output": after,
               "state": receipt_by_capability[stage]["state"],
               "blockers": list(receipt_by_capability[stage]["blockers"])}
              for stage, before, after in CAPABILITY_DAG]
    if execution_mode not in {"CANONICAL_RUNNER_EXECUTION", "MANUAL_SHADOW_ANALYSIS", "TEST_FIXTURE"}:
        raise ValueError("ADVANCED_EXECUTION_MODE_INVALID")
    body = {
        "schema": ADVANCED_EXECUTION_SCHEMA,
        "computationLaw": computation_law_identity(),
        "manifestType": "ModelExecutionManifest",
        "mode": execution_mode,
        "runId": run_id,
        "sportScopes": sorted({str(scope).strip().upper() for scope in sport_scopes if str(scope).strip()}),
        "modelId": "DCM_CANONICAL",
        "modelVersion": "UNAVAILABLE",
        "forecastCutoff": forecast_cutoff,
        "seedInputHash": seed_input_hash,
        "modelConfigHash": model_config_hash,
        "canonicalFlow": [
            {"stage": "BOARD", "state": "CANONICAL_RUN_CONSUMED"},
            {"stage": "RESEARCH", "state": "CANONICAL_RUN_CONSUMED"},
            {"stage": "EVIDENCE", "state": "CANONICAL_RUN_CONSUMED"},
            {"stage": "FEATURES", "state": "CANONICAL_RUN_CONSUMED"},
            {"stage": "PARAMETERS", "state": "CANONICAL_RUN_CONSUMED"},
            {"stage": "EVENTWORLD", "state": "CANONICAL_RUN_CONSUMED"},
            {"stage": "PROBABILITY", "state": "CANONICAL_RUN_CONSUMED"},
            {"stage": "CALIBRATION", "state": "EVALUATED_WITH_READINESS_RECEIPT"},
            {"stage": "PORTFOLIO", "state": "CORRELATION_GATE_EVALUATED"},
            {"stage": "EV", "state": "ENTRY_EV_GATE_EVALUATED"},
            {"stage": "FREEZE", "state": "PENDING_RECEIPT_HASH_BIND"},
            {"stage": "SETTLEMENT", "state": "NOT_RUN_APPEND_ONLY_LIFECYCLE"},
        ],
        "compiledDag": compiled_dag,
        "dag": stages,
        "receipts": receipts,
        "capabilityRunThrough": {
            "schema": "pillars_dcm.capability_run_through.v1",
            "evaluationState": "COMPLETED_FOR_ALL_SEVEN_GATES",
            "runContinuesOnInputIssues": True,
            "gates": [{
                "capability": r["capability"],
                "gateEvaluationState": "COMPLETED",
                "computationState": r["state"],
                "inputIssueCount": len(r.get("blockers") or []),
                "inputIssues": list(r.get("blockers") or []),
                "requiredInputs": list(CAPABILITY_INPUT_REQUIREMENTS.get(r["capability"], ("CANONICAL_RUN_CONTEXT",))),
                "inputProducersNeeded": list(CAPABILITY_INPUT_PRODUCERS.get(r["capability"], ())),
                "receiptOutputHash": r["outputHash"],
            } for r in receipts],
            "completedGateCount": len(receipts),
            "requiredGateCount": 7,
        },
        "directionalResearchConflictGate": dict(directional_research_report or {
            "state": "NOT_PROVIDED", "automaticInverseAllowed": False,
        }),
        "capabilityCounts": {r["capability"]: 1 for r in receipts},
        "allCapabilitiesEvaluated": len(receipts) == len(CAPABILITY_DAG) + 1,
        "fullModelingExecution": False,
        "executionDurationMs": round((time.perf_counter() - started) * 1000, 3),
        "certification": {"learningRevision": "LR000000", "predictiveClaim": "NONE",
                          "productionRootCertified": False},
        "limitations": ["KDE and SVD are diagnostic-only and cannot emit forecast probability.",
                        "Settlement is a later append-only lifecycle stage.",
                        "Payout EV is not certified without calibrated joint probabilities and the captured, fully modeled entry settlement rules."],
    }
    body["contentHash"] = content_hash(_deterministic_hash_payload(body))
    return body


def validate_advanced_execution_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("schema") != ADVANCED_EXECUTION_SCHEMA:
        raise ValueError("ADVANCED_EXECUTION_SCHEMA_INVALID")
    law = computation_law_identity()
    if receipt.get("computationLaw") != law:
        raise ValueError("ADVANCED_EXECUTION_COMPUTATION_LAW_IDENTITY_MISMATCH")
    rows = receipt.get("receipts")
    if not isinstance(rows, list) or {r.get("capability") for r in rows} != {r[0] for r in CAPABILITY_DAG} | {"ALGORITHM_GRAPH"}:
        raise ValueError("ADVANCED_EXECUTION_CAPABILITY_RECEIPTS_INCOMPLETE")
    for row in rows:
        if row.get("algorithmId") != CAPABILITY_ALGORITHMS.get(str(row.get("capability"))):
            raise ValueError("ADVANCED_EXECUTION_ALGORITHM_ID_MISMATCH")
        require_algorithm(str(row["algorithmId"]))
        if row.get("state") in {"EXECUTED", "EXECUTED_READINESS_ONLY", "SHADOW_DIAGNOSTIC", "SHADOW_DIAGNOSTIC_UNCALIBRATED"}:
            if not row.get("producer") or not row.get("consumer"):
                raise ValueError("ADVANCED_EXECUTION_PRODUCER_CONSUMER_MISSING")
        for field in ("runId", "algorithmVersion", "requirementIds", "inputContentHashes",
                      "applicabilityVerdict", "executionMethod", "executionDurationMs",
                      "outputHash", "producer", "consumer", "computationLawVersion",
                      "computationLawSha256"):
            if field not in row:
                raise ValueError(f"ADVANCED_EXECUTION_REQUIRED_RECEIPT_FIELD_MISSING:{field}")
        if (row.get("computationLawVersion") != law["version"]
                or row.get("computationLawSha256") != law["sha256"]):
            raise ValueError("ADVANCED_EXECUTION_RECEIPT_COMPUTATION_LAW_MISMATCH")
        if row.get("outputHash") != content_hash({
            k: v for k, v in row.items() if k not in {"outputHash", "executionDurationMs"}
        }):
            raise ValueError("ADVANCED_EXECUTION_ALGORITHM_OUTPUT_HASH_MISMATCH")
    if receipt.get("contentHash") != content_hash(_deterministic_hash_payload(receipt)):
        raise ValueError("ADVANCED_EXECUTION_HASH_MISMATCH")
