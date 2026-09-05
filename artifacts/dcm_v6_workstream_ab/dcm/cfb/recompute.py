"""Full probability/risk bundle after a material world rebuild or line update.

Do not grade using stale evidenceSafeP or stale lowerBound. If the preferred
direction flips and both sides are offered, update it. Respect offered sides.
"""
from __future__ import annotations

import statistics
from typing import Any, Callable, Mapping

from dcm.learning.calibration import apply_calibration, cell_key
from dcm.model.distributions import from_worlds
from dcm.model.grade import grade as default_grade
from dcm.model.line_surface import surface as line_surface
from dcm.model.ranking import selection_score
from dcm.model.uncertainty import probability_bundle


def recompute_full_bundle(
    rec: dict[str, Any],
    *,
    grade_fn: Callable[..., str] | None = None,
    calibration_cells: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rec = dict(rec)
    row = dict(rec.get("row") or rec)
    raw_values = rec.get("_worldValues") or []
    if not isinstance(raw_values, list) or not raw_values:
        rec["selectionScore"] = selection_score(rec)
        return rec
    values = [float(v) for v in raw_values]
    snapshot = rec.get("parameterSnapshot") if isinstance(rec.get("parameterSnapshot"), dict) else {}
    dist = from_worlds(values, float(row.get("line") or 0.0))
    rec["pHigher"] = dist["pHigher"]
    rec["pLower"] = dist["pLower"]
    rec["pPush"] = dist["pPush"]
    rec["mean"] = dist["mean"]
    rec["median"] = statistics.median(values) if values else dist["mean"]
    sd = statistics.pstdev(values) if len(values) >= 2 else 0.0
    volatility = min(1.0, sd / (abs(float(dist["mean"])) + 1.0))
    support_n = min(
        int((snapshot.get("opportunity") or {}).get("support_n", 0) or 0),
        int((snapshot.get("efficiency") or {}).get("support_n", 0) or 0),
    )
    offered_sides: list[str] = []
    if row.get("offeredHigher"):
        offered_sides.append("MORE")
    if row.get("offeredLower"):
        offered_sides.append("LESS")
    if not offered_sides:
        side = str(rec.get("selectedSide") or "MORE")
        offered_sides = [side]
    grader = grade_fn or default_grade
    demon = str(row.get("modifier") or "") == "DEMON"
    evaluations: dict[str, dict[str, Any]] = {}
    cells = calibration_cells or {}
    for side in offered_sides:
        raw_p = dist["pHigher"] if side == "MORE" else dist["pLower"]
        ckey = cell_key(str(row.get("sportFamily") or ""), str(row.get("league") or ""), str(row.get("market") or ""), side)
        cal = apply_calibration(raw_p, key=ckey, cells=cells)
        unc = probability_bundle(
            raw_selected_p=float(cal["calibrated"]),
            n_worlds=len(values),
            support_n=support_n,
            data_quality=float(snapshot.get("data_quality") or rec.get("dataQuality") or 0.0),
            ood_risk=float(snapshot.get("ood_risk") or rec.get("oodRisk") or 1.0),
            volatility=volatility,
            synthetic=bool(snapshot.get("synthetic")),
        )
        safe_p = float(unc["evidence_safe_probability"])
        surf = line_surface(values, float(row.get("line") or 0.0), side=side, playable_p=0.63 if demon else 0.58)
        fragility = min(
            1.0,
            0.10 + float(unc["epistemic_uncertainty"]) * 0.70
            + float(snapshot.get("ood_risk") or rec.get("oodRisk") or 0.0) * 0.20
            + min(0.20, float(surf["edge_elasticity"]) * 0.20),
        )
        side_grade = grader(
            selected_p=safe_p,
            lower_bound=float(unc["lower_bound"]),
            demon=demon,
            fragility=fragility,
            robustness_area=float(surf["robustness_area"]),
            elasticity=float(surf["edge_elasticity"]),
            false_sign=float(unc["false_sign_risk"]),
        )
        evaluations[side] = {
            "side": side,
            "rawP": raw_p,
            "calibratedP": float(cal["calibrated"]),
            "calibrationState": cal["state"],
            "evidenceSafeP": safe_p,
            "lowerBound": float(unc["lower_bound"]),
            "monteCarloSE": float(unc["monte_carlo_se"]),
            "epistemicUncertainty": float(unc["epistemic_uncertainty"]),
            "aleatoricUncertainty": float(unc["aleatoric_uncertainty"]),
            "reliability": float(unc["reliability"]),
            "falseSignRisk": float(unc["false_sign_risk"]),
            "volatility": volatility,
            "fragility": fragility,
            "lineSurface": surf,
            "grade": side_grade,
        }
    forced = row.get("side") if row.get("side") in evaluations else None
    prev = rec.get("selectedSide") if rec.get("selectedSide") in evaluations else None
    chosen_side = forced or max(
        evaluations,
        key=lambda x: (evaluations[x]["evidenceSafeP"], evaluations[x]["lowerBound"]),
    )
    ev = evaluations[chosen_side]
    rec["selectedSide"] = chosen_side
    rec["selectedP"] = ev["rawP"]
    rec["rawP"] = ev["rawP"]
    rec["calibratedP"] = ev["calibratedP"]
    rec["evidenceSafeP"] = ev["evidenceSafeP"]
    rec["lowerBound"] = ev["lowerBound"]
    rec["grade"] = ("LEAN" if rec.get("state") == "MODELED_DIAGNOSTIC" and ev["grade"] == "PLAYABLE" else ev["grade"])
    rec["lineSurface"] = ev["lineSurface"]
    rec["trueLineTolerance"] = ev["lineSurface"].get("true_unclamped_line_tolerance")
    rec["sideEvaluations"] = evaluations
    rec["reliability"] = ev["reliability"]
    rec["volatility"] = ev["volatility"]
    rec["fragility"] = ev["fragility"]
    rec["falseSignRisk"] = ev["falseSignRisk"]
    rec["epistemicUncertainty"] = ev["epistemicUncertainty"]
    rec["aleatoricUncertainty"] = ev["aleatoricUncertainty"]
    rec["monteCarloSE"] = ev["monteCarloSE"]
    rec["calibrationState"] = ev["calibrationState"]
    rec["worldCount"] = len(values)
    rec["dataQuality"] = snapshot.get("data_quality", rec.get("dataQuality"))
    rec["oodRisk"] = snapshot.get("ood_risk", rec.get("oodRisk"))
    rec["selectionScore"] = selection_score(rec)
    rec["directionFlipped"] = bool(prev and prev != chosen_side)
    return rec
