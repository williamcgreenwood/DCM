"""Evidence-gated acceptance ladder for Domains 2, 3, 4 and 6.

This module does not manufacture predictive acceptance.  It evaluates frozen,
chronological evidence and reports PASS/INSUFFICIENT_EVIDENCE/FAIL with explicit
criteria.  Predictive superiority is claimable only when every required domain
passes on unseen chronological data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Iterable

ACCEPTANCE_VERSION = "DCM_PREDICTIVE_ACCEPTANCE_V1_2026-10-09"


@dataclass(frozen=True)
class GateResult:
    domain: str
    status: str
    metrics: dict[str, Any]
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "status": self.status,
            "metrics": dict(self.metrics),
            "reasons": list(self.reasons),
        }


def _f(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _binary_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        result = str(row.get("result") or row.get("settlement") or "").upper()
        if result not in {"WIN", "LOSS"}:
            continue
        p = _f(row.get("calibratedP") or row.get("selectedP") or row.get("evidenceSafeP"))
        if p is None:
            continue
        copy = dict(row)
        copy["_p"] = min(1.0, max(0.0, p))
        copy["_y"] = 1.0 if result == "WIN" else 0.0
        out.append(copy)
    return out


def _proper_scores(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    if not rows:
        return {"n": 0, "brier": None, "logLoss": None, "ece": None}
    n = len(rows)
    brier = sum((r["_p"] - r["_y"]) ** 2 for r in rows) / n
    ll = -sum(
        r["_y"] * math.log(max(1e-12, min(1 - 1e-12, r["_p"])))
        + (1 - r["_y"]) * math.log(max(1e-12, min(1 - 1e-12, 1 - r["_p"])))
        for r in rows
    ) / n
    bins: list[list[dict[str, Any]]] = [[] for _ in range(10)]
    for row in rows:
        bins[min(9, int(row["_p"] * 10))].append(row)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        mp = sum(r["_p"] for r in bucket) / len(bucket)
        my = sum(r["_y"] for r in bucket) / len(bucket)
        ece += len(bucket) / n * abs(mp - my)
    return {"n": n, "brier": brier, "logLoss": ll, "ece": ece}


def _unique(rows: list[dict[str, Any]], key: str) -> int:
    return len({str(r.get(key) or "") for r in rows if str(r.get(key) or "")})


def domain2_cfb_predictive_acceptance(
    rows: list[dict[str, Any]],
    *,
    baseline_mae: float | None = None,
    model_mae: float | None = None,
    min_games: int = 500,
    required_relative_mae_improvement: float = 0.15,
) -> GateResult:
    cfb = [r for r in rows if str(r.get("league") or "").upper() == "CFB"]
    games = _unique(cfb, "eventId")
    reasons: list[str] = []
    if games < min_games:
        reasons.append(f"INSUFFICIENT_OOS_CFB_GAMES:{games}<{min_games}")
    if baseline_mae is None or model_mae is None:
        reasons.append("PASS_ATTEMPT_MAE_COMPARISON_MISSING")
        improvement = None
    elif baseline_mae <= 0:
        reasons.append("BASELINE_MAE_INVALID")
        improvement = None
    else:
        improvement = (baseline_mae - model_mae) / baseline_mae
        if improvement < required_relative_mae_improvement:
            reasons.append(
                f"MAE_IMPROVEMENT_BELOW_GATE:{improvement:.4f}<{required_relative_mae_improvement:.4f}"
            )
    status = "PASS" if not reasons else (
        "INSUFFICIENT_EVIDENCE" if any(r.startswith("INSUFFICIENT_") or r.endswith("_MISSING") for r in reasons) else "FAIL"
    )
    return GateResult(
        "DOMAIN_2_CFB_OPPORTUNITY_EVENTWORLD",
        status,
        {
            "oosCfbGames": games,
            "baselineMae": baseline_mae,
            "modelMae": model_mae,
            "relativeMaeImprovement": improvement,
            "minGames": min_games,
        },
        tuple(reasons),
    )


def domain3_distribution_calibration_acceptance(
    rows: list[dict[str, Any]],
    *,
    min_settled: int = 500,
    max_ece: float = 0.08,
    max_brier_regression: float = 0.0,
    baseline_brier: float | None = None,
) -> GateResult:
    scored = _binary_rows(rows)
    metrics = _proper_scores(scored)
    reasons: list[str] = []
    if int(metrics["n"] or 0) < min_settled:
        reasons.append(f"INSUFFICIENT_SETTLED_PREDICTIONS:{metrics['n']}<{min_settled}")
    ece = metrics["ece"]
    if ece is None:
        reasons.append("CALIBRATION_ECE_UNDEFINED")
    elif float(ece) > max_ece:
        reasons.append(f"CALIBRATION_ECE_ABOVE_GATE:{float(ece):.4f}>{max_ece:.4f}")
    brier = metrics["brier"]
    if baseline_brier is None:
        reasons.append("BASELINE_BRIER_MISSING")
    elif brier is None:
        reasons.append("BRIER_UNDEFINED")
    elif float(brier) > baseline_brier + max_brier_regression:
        reasons.append("BRIER_DOES_NOT_BEAT_OR_MATCH_BASELINE")
    status = "PASS" if not reasons else (
        "INSUFFICIENT_EVIDENCE" if any(r.startswith("INSUFFICIENT_") or r.endswith("_MISSING") for r in reasons) else "FAIL"
    )
    return GateResult("DOMAIN_3_DISTRIBUTION_CALIBRATION", status, metrics, tuple(reasons))


def domain4_covariance_portfolio_acceptance(
    portfolio_rows: list[dict[str, Any]],
    *,
    min_frozen_portfolios: int = 200,
    max_lineage_fault_rate: float = 0.0,
) -> GateResult:
    frozen = [r for r in portfolio_rows if str(r.get("freezeId") or "")]
    n = len(frozen)
    reasons: list[str] = []
    if n < min_frozen_portfolios:
        reasons.append(f"INSUFFICIENT_FROZEN_PORTFOLIOS:{n}<{min_frozen_portfolios}")
    missing_joint = sum(
        1 for r in frozen
        if not (
            r.get("jointWorldCount")
            or r.get("pairwiseSelectionCorrelations")
            or r.get("dependencyGraphHash")
        )
    )
    if frozen and missing_joint:
        reasons.append(f"COVARIANCE_OR_DEPENDENCY_EVIDENCE_MISSING:{missing_joint}")
    faults = sum(1 for r in frozen if bool(r.get("lineageFault")))
    fault_rate = faults / n if n else None
    if fault_rate is not None and fault_rate > max_lineage_fault_rate:
        reasons.append(f"PORTFOLIO_LINEAGE_FAULT_RATE:{fault_rate:.6f}")
    status = "PASS" if not reasons else (
        "INSUFFICIENT_EVIDENCE" if any(r.startswith("INSUFFICIENT_") for r in reasons) else "FAIL"
    )
    return GateResult(
        "DOMAIN_4_COVARIANCE_PORTFOLIO",
        status,
        {
            "frozenPortfolios": n,
            "missingDependenceEvidence": missing_joint,
            "lineageFaultRate": fault_rate,
        },
        tuple(reasons),
    )


def domain6_model_promotion_acceptance(
    challenger_rows: list[dict[str, Any]],
    champion_rows: list[dict[str, Any]],
    *,
    min_predictions: int = 200,
    min_event_groups: int = 30,
    min_chronological_days: int = 30,
) -> GateResult:
    chal = _binary_rows(challenger_rows)
    champ = _binary_rows(champion_rows)
    cm = _proper_scores(chal)
    hm = _proper_scores(champ)
    reasons: list[str] = []
    n = int(cm["n"] or 0)
    event_groups = _unique(chal, "eventGroupId") or _unique(chal, "eventId")
    if n < min_predictions:
        reasons.append(f"INSUFFICIENT_OOS_PREDICTIONS:{n}<{min_predictions}")
    if event_groups < min_event_groups:
        reasons.append(f"INSUFFICIENT_EVENT_GROUPS:{event_groups}<{min_event_groups}")

    cutoffs = sorted(
        str(r.get("decisionCutoff") or "") for r in chal if str(r.get("decisionCutoff") or "")
    )
    span_days = 0
    if len(cutoffs) >= 2:
        try:
            a = datetime.fromisoformat(cutoffs[0].replace("Z", "+00:00"))
            b = datetime.fromisoformat(cutoffs[-1].replace("Z", "+00:00"))
            span_days = max(0, (b - a).days)
        except ValueError:
            reasons.append("INVALID_DECISION_CUTOFF")
    else:
        reasons.append("INSUFFICIENT_CHRONOLOGICAL_CUTOFFS")
    if span_days < min_chronological_days:
        reasons.append(f"INSUFFICIENT_CHRONOLOGICAL_SPAN:{span_days}<{min_chronological_days}")

    if cm["brier"] is None or hm["brier"] is None:
        reasons.append("BRIER_COMPARISON_MISSING")
    elif float(cm["brier"]) >= float(hm["brier"]):
        reasons.append("CHALLENGER_BRIER_NOT_BETTER")
    if cm["logLoss"] is None or hm["logLoss"] is None:
        reasons.append("LOGLOSS_COMPARISON_MISSING")
    elif float(cm["logLoss"]) >= float(hm["logLoss"]):
        reasons.append("CHALLENGER_LOGLOSS_NOT_BETTER")

    status = "PASS" if not reasons else (
        "INSUFFICIENT_EVIDENCE" if any(r.startswith("INSUFFICIENT_") or r.endswith("_MISSING") for r in reasons) else "FAIL"
    )
    return GateResult(
        "DOMAIN_6_MODEL_PROMOTION",
        status,
        {
            "challenger": cm,
            "champion": hm,
            "eventGroups": event_groups,
            "chronologicalSpanDays": span_days,
        },
        tuple(reasons),
    )


def predictive_superiority_claim(
    domain2: GateResult,
    domain3: GateResult,
    domain4: GateResult,
    domain6: GateResult,
) -> dict[str, Any]:
    gates = [domain2, domain3, domain4, domain6]
    passed = all(g.passed for g in gates)
    return {
        "version": ACCEPTANCE_VERSION,
        "predictiveSuperiority": "EARNED" if passed else "NONE",
        "status": "PASS" if passed else "NOT_EARNED",
        "gates": [g.to_dict() for g in gates],
        "reason": None if passed else "ALL_DOMAIN_ACCEPTANCE_GATES_MUST_PASS_ON_CHRONOLOGICAL_OOS_EVIDENCE",
    }


__all__ = [
    "ACCEPTANCE_VERSION",
    "GateResult",
    "domain2_cfb_predictive_acceptance",
    "domain3_distribution_calibration_acceptance",
    "domain4_covariance_portfolio_acceptance",
    "domain6_model_promotion_acceptance",
    "predictive_superiority_claim",
]
