"""Auditable advanced-modeling execution receipts for the canonical runner.

This layer deliberately orchestrates existing DCM producers/consumers. KDE and
SVD are diagnostic-only; neither may manufacture or replace a forecast
probability. Missing historical, calibration, or payout evidence is represented
as a typed blocker in the receipt.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from dcm.contracts.hashes import content_hash
from dcm.learning.calibration import evaluate_calibration_readiness
from dcm.algorithms.registry import require_algorithm

ADVANCED_EXECUTION_SCHEMA = "pillars_dcm.advanced_modeling_execution.v1"
MIN_KDE_SAMPLE = 30
MIN_SVD_ROWS = 8

CAPABILITY_DAG = (
    ("SVD", "FEATURES", "PARAMETERS"),
    ("MONTE_CARLO", "EVENTWORLD", "PROBABILITY"),
    ("KDE", "EVENTWORLD", "PROBABILITY_DIAGNOSTIC"),
    ("CALIBRATION", "PROBABILITY", "PORTFOLIO"),
    ("PORTFOLIO_CORRELATION", "PROBABILITY", "PORTFOLIO"),
    ("PAYOUT_EV", "PORTFOLIO", "FREEZE"),
)
CAPABILITY_DEPENDENCIES = {
    "SVD": ("FEATURES",),
    "MONTE_CARLO": ("PARAMETERS", "EVENTWORLD"),
    "KDE": ("EVIDENCE", "EVENTWORLD"),
    "CALIBRATION": ("PROBABILITY", "HISTORICAL_SETTLEMENTS"),
    "PORTFOLIO_CORRELATION": ("CALIBRATION", "PORTFOLIO", "SHARED_EVENT_OUTCOMES"),
    "PAYOUT_EV": ("PORTFOLIO_CORRELATION", "PAYOUT_RULES", "CALIBRATED_JOINT_PROBABILITIES"),
}
CAPABILITY_ALGORITHMS = {
    "KDE": "ALG-ML-PROB-009",
    "SVD": "ALG-ML-TABULAR-013",
    "MONTE_CARLO": "ALG-MC-001",
    "CALIBRATION": "ALG-CAL-001",
    "PORTFOLIO_CORRELATION": "ALG-PORT-001",
    "PAYOUT_EV": "ALG-EV-001",
}


def compile_advanced_execution_dag() -> dict[str, Any]:
    """Compile and validate the bounded modeling DAG against the live registry."""
    nodes = []
    node_ids = {capability for capability, _producer, _consumer in CAPABILITY_DAG}
    seen: set[str] = set()
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
        }
        nodes.append(node)
        seen.add(capability)
    return {"schema": "pillars_dcm.advanced_modeling_dag.v1", "version": "1.0.0",
            "nodes": nodes, "validated": True}


def _receipt(capability: str, state: str, *, producer: str, consumer: str,
             blockers: Sequence[str] = (), details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    algorithm_id = CAPABILITY_ALGORITHMS[capability]
    record = require_algorithm(algorithm_id)
    return {
        "capability": capability,
        "algorithmId": algorithm_id,
        "algorithmLifecycle": record.lifecycle,
        "fallbackAlgorithmId": record.fallback_algorithm_id,
        "state": state,
        "producer": producer,
        "consumer": consumer,
        "blockers": list(blockers),
        "details": dict(details or {}),
    }


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


def gaussian_kde_diagnostic(values: Sequence[float], *, min_n: int = MIN_KDE_SAMPLE) -> dict[str, Any]:
    """Select bandwidth by deterministic leave-one-out likelihood.

    The returned density is explicitly diagnostic and has no probability-field
    or calibration interface. Sparse samples abstain.
    """
    xs = [float(x) for x in values if math.isfinite(float(x))]
    if len(xs) < min_n:
        return {"state": "INACTIVE_INSUFFICIENT_DATA", "n": len(xs),
                "blocker": f"INSUFFICIENT_SAMPLE:{len(xs)}<{min_n}", "forecastProbability": None}
    mean = sum(xs) / len(xs)
    variance = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    sigma = math.sqrt(max(variance, 1e-12))
    base = 1.06 * sigma * len(xs) ** (-0.2)
    candidates = [base * factor for factor in (0.5, 0.75, 1.0, 1.5, 2.0)]
    root_2pi = math.sqrt(2.0 * math.pi)
    best_h, best_score = candidates[0], -math.inf
    for h in candidates:
        score = 0.0
        for i, point in enumerate(xs):
            density = sum(math.exp(-0.5 * ((point - other) / h) ** 2)
                          for j, other in enumerate(xs) if i != j)
            density /= (len(xs) - 1) * h * root_2pi
            score += math.log(max(density, 1e-300))
        score /= len(xs)
        if score > best_score:
            best_h, best_score = h, score
    density_se = math.sqrt(max(0.0, 1.0 / (len(xs) * best_h * root_2pi)))
    return {
        "state": "SHADOW_DIAGNOSTIC",
        "n": len(xs),
        "bandwidth": best_h,
        "looLogLikelihood": best_score,
        "densityUncertaintyDiagnostic": density_se,
        "forecastProbability": None,
        "probabilityAuthority": "NONE_DIAGNOSTIC_ONLY",
    }


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
    if observed_at is not None:
        if len(observed_at) != len(rows) or not forecast_cutoff:
            return {"state": "BLOCKED_TEMPORAL_METADATA_MISSING", "forecastProbability": None}
        if any(str(ts) > forecast_cutoff for ts in observed_at):
            return {"state": "BLOCKED_POST_CUTOFF_FEATURE", "forecastProbability": None}
    if len(rows) < min_rows or width < 2:
        return {"state": "INACTIVE_INSUFFICIENT_DATA", "rows": len(rows), "columns": width,
                "blocker": "INSUFFICIENT_FEATURE_MATRIX", "forecastProbability": None}
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
    return {
        "state": "SHADOW_DIAGNOSTIC", "rows": len(rows), "columns": width,
        "rank": rank, "singularValues": [float(x) for x in singular],
        "normalization": "COLUMN_ZSCORE", "stability": "NOT_EVALUATED_NO_CHRONOLOGICAL_FOLDS",
        "forecastProbability": None,
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
    return {"state": "EXECUTED", "worldCount": n, "correlations": correlations,
            "alignedOutcomeHash": content_hash([list(x[:n]) for x in outcome_rows]),
            "convergence": "PREFIX_VS_FULL_DIAGNOSTIC", "convergenceByLeg": convergence}


def execute_advanced_modeling(
    *, forecasts: Sequence[Mapping[str, Any]], portfolio: Sequence[Mapping[str, Any]],
    calibration_state: Mapping[str, Any] | None, forecast_cutoff: str,
    payout_table_hash: str | None = None, stake: float | None = None,
    seed_input_hash: str | None = None, model_config_hash: str | None = None,
    event_world_metadata: Mapping[str, Any] | None = None,
    joint_backend_metadata: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Evaluate each modeling capability for a canonical runner invocation."""
    rows = list(forecasts)
    receipts: list[dict[str, Any]] = []
    kde_done = 0
    kde_blocked = 0
    historical_kde = list((calibration_state or {}).get("kdeComparableSamples") or [])
    diagnostic_forecasts = [
        row for row in rows
        if row.get("selectedSide") and row.get("state") == "MODELED"
    ][:25]
    for row in diagnostic_forecasts:
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
        result = gaussian_kde_diagnostic(comparable_values)
        kde_done += result["state"] == "SHADOW_DIAGNOSTIC"
        kde_blocked += result["state"] != "SHADOW_DIAGNOSTIC"
    receipts.append(_receipt("KDE", "SHADOW_DIAGNOSTIC" if kde_done else "INACTIVE_INSUFFICIENT_DATA",
        producer="cutoff-safe comparable historical outcomes", consumer="advanced-modeling density diagnostics",
        blockers=["KDE_IS_DIAGNOSTIC_ONLY_NO_PROBABILITY_AUTHORITY"] + (["NO_SUFFICIENT_VALIDATED_COMPARABLE_HISTORY"] if not kde_done else []),
        details={"evaluatedRows": len(diagnostic_forecasts), "populationRows": len(rows),
                 "historicalSampleRows": len(historical_kde),
                 "diagnosticRows": kde_done, "inactiveRows": kde_blocked,
                 "forecastProbabilityProduced": False}))

    history_matrix = (calibration_state or {}).get("historicalRoleOpponentFeatureMatrix")
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
        details={"diagnostic": svd, "forecastProbabilityProduced": False}))

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
        blockers=[] if world_receipt["state"] == "EXECUTED" else [world_receipt["state"]],
        details={"backend": backends or ["NOT_RECORDED"], "rngVersion": rng_versions or ["NOT_RECORDED"],
                 "seedSource": "input HAR content hash", "seedInputHash": seed_input_hash,
                 "modelConfigHash": model_config_hash, "conservation": conservation,
                 "worlds": world_receipt["worldCount"], "diagnostics": world_receipt}))

    calibration_rows = [r for r in rows if r.get("calibrationState")]
    historical = list((calibration_state or {}).get("settlements") or [])
    cal_metrics = evaluate_calibration_readiness(historical)
    active = sum(str(r.get("calibrationState")) == "ACTIVE_CHRONOLOGICAL_CELL" for r in calibration_rows)
    receipts.append(_receipt("CALIBRATION", "EXECUTED_READINESS_ONLY", producer="dcm.learning.calibration",
        consumer="canonical probability records and portfolio gate",
        blockers=list(cal_metrics.get("reasons") or []) if not cal_metrics.get("ready") else ["LR000000_PROMOTION_GATE_REMAINS"],
        details={"candidateRowsEvaluated": len(calibration_rows), "activeRows": active,
                 "chronologicalReadiness": cal_metrics, "learningRevision": "LR000000",
                 "predictiveClaim": "NONE"}))

    corr = _shared_world_diagnostics(portfolio) if len(portfolio) >= 2 else {
        "state": "SKIPPED_NOT_APPLICABLE", "worldCount": 0, "correlations": [],
    }
    receipts.append(_receipt("PORTFOLIO_CORRELATION", corr["state"], producer="shared aligned selection outcomes",
        consumer="dcm.selection.portfolio.build_card / EV joint outcomes",
        blockers=[] if corr["state"] in {"EXECUTED", "SKIPPED_NOT_APPLICABLE"} else ["SHARED_PORTFOLIO_OUTCOMES_UNAVAILABLE"],
        details={"correlations": corr.get("correlations", []), "worldCount": corr.get("worldCount", 0),
                 "portfolioSize": len(portfolio), "usesIndependentMarginals": False}))

    if not payout_table_hash or stake is None or len(portfolio) < 2:
        ev_state = "BLOCKED_MISSING_ENTRY_CONTRACT"
        ev_details = {"expectedValue": None, "required": ["captured payout table hash", "stake", "entry rules"]}
        ev_blockers = ["PAYOUT_RULES_OR_ENTRY_CONTRACT_MISSING"]
    elif corr["state"] != "EXECUTED":
        ev_state = "BLOCKED_JOINT_PROBABILITIES_MISSING"
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
        consumer="portfolio ranking and freeze eligibility", blockers=ev_blockers, details=ev_details))

    compiled_dag = compile_advanced_execution_dag()
    receipt_by_capability = {r["capability"]: r for r in receipts}
    stages = [{"stage": stage, "algorithmId": CAPABILITY_ALGORITHMS[stage], "input": before, "output": after,
               "state": receipt_by_capability[stage]["state"],
               "blockers": list(receipt_by_capability[stage]["blockers"])}
              for stage, before, after in CAPABILITY_DAG]
    body = {
        "schema": ADVANCED_EXECUTION_SCHEMA,
        "mode": "CANONICAL_RUNNER_EXECUTION",
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
            {"stage": "PORTFOLIO", "state": "CONSUMED_OR_NOT_APPLICABLE"},
            {"stage": "EV", "state": "EXECUTED_OR_TYPED_BLOCKER"},
            {"stage": "FREEZE", "state": "PENDING_RECEIPT_HASH_BIND"},
            {"stage": "SETTLEMENT", "state": "NOT_RUN_APPEND_ONLY_LIFECYCLE"},
        ],
        "compiledDag": compiled_dag,
        "dag": stages,
        "receipts": receipts,
        "capabilityCounts": {r["capability"]: 1 for r in receipts},
        "allCapabilitiesEvaluated": len(receipts) == len(CAPABILITY_DAG),
        "fullModelingExecution": all(r["state"] in {"EXECUTED", "EXECUTED_READINESS_ONLY", "SHADOW_DIAGNOSTIC", "SKIPPED_NOT_APPLICABLE"} for r in receipts),
        "certification": {"learningRevision": "LR000000", "predictiveClaim": "NONE",
                          "productionRootCertified": False},
        "limitations": ["KDE and SVD are diagnostic-only and cannot emit forecast probability.",
                        "Settlement is a later append-only lifecycle stage.",
                        "Payout EV is not certified without calibrated joint probabilities and the captured, fully modeled entry settlement rules."],
    }
    body["contentHash"] = content_hash(body)
    return body


def validate_advanced_execution_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("schema") != ADVANCED_EXECUTION_SCHEMA:
        raise ValueError("ADVANCED_EXECUTION_SCHEMA_INVALID")
    rows = receipt.get("receipts")
    if not isinstance(rows, list) or {r.get("capability") for r in rows} != {r[0] for r in CAPABILITY_DAG}:
        raise ValueError("ADVANCED_EXECUTION_CAPABILITY_RECEIPTS_INCOMPLETE")
    for row in rows:
        if row.get("algorithmId") != CAPABILITY_ALGORITHMS.get(str(row.get("capability"))):
            raise ValueError("ADVANCED_EXECUTION_ALGORITHM_ID_MISMATCH")
        require_algorithm(str(row["algorithmId"]))
        if row.get("state") in {"EXECUTED", "EXECUTED_READINESS_ONLY", "SHADOW_DIAGNOSTIC", "SHADOW_DIAGNOSTIC_UNCALIBRATED"}:
            if not row.get("producer") or not row.get("consumer"):
                raise ValueError("ADVANCED_EXECUTION_PRODUCER_CONSUMER_MISSING")
    if receipt.get("contentHash") != content_hash({k: v for k, v in receipt.items() if k != "contentHash"}):
        raise ValueError("ADVANCED_EXECUTION_HASH_MISMATCH")
