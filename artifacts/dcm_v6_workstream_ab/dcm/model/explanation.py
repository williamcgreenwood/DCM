"""Machine-readable PropExplanation. Drivers come from encoded snapshot/feature diffs.

Never invents prose. Human text is an optional rendering of the object only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.ml.feature_store import FEATURE_SCHEMA_VERSION
from dcm.model.basketball_efficiency import EFF_VERSION
from dcm.model.basketball_efficiency import LEAGUE_PRIORS as EFF_PRIORS
from dcm.model.basketball_opportunity import OPP_VERSION
from dcm.model.basketball_opportunity import LEAGUE_PRIORS as OPP_PRIORS
from dcm.model.market_derive import MARKET_REGISTRY_VERSION
from dcm.version import SOFTWARE

EXPLANATION_SCHEMA = "dcm.prop_explanation.v1-20260830"

REQUIRED_EXPLANATION_KEYS = (
    "player",
    "team",
    "opponent",
    "market",
    "line",
    "direction",
    "projectedOpportunity",
    "projectedEfficiency",
    "projectionMean",
    "projectionMedian",
    "pMore",
    "pLess",
    "pPush",
    "selectedP",
    "evidenceSafeP",
    "lowerBound",
    "reliability",
    "dataQuality",
    "volatility",
    "fragility",
    "oodRisk",
    "falseSignRisk",
    "monteCarloSE",
    "epistemicUncertainty",
    "lineTolerance",
    "true_unclamped_line_tolerance",
    "offered_line",
    "break_even_line",
    "playable_break_line",
    "edge_elasticity",
    "robustness_area",
    "topPositiveDrivers",
    "topNegativeDrivers",
    "primaryFailurePaths",
    "featureHashes",
    "evidenceHashes",
    "parameterSnapshotHash",
    "modelIds",
    "simulationHash",
)

# Encoded sign: whether a higher value lifts MORE counting-stat markets.
_HIGHER_LIFTS_MORE = {
    "minutes_mean": True,
    "fga_per_min": True,
    "fta_per_min": True,
    "reb_per_min": True,
    "ast_per_min": True,
    "stl_per_min": True,
    "blk_per_min": True,
    "three_pa_share": True,
    "two_fg_pct": True,
    "three_fg_pct": True,
    "ft_pct": True,
    "tov_per_min": False,
}

_OPP_KEYS = (
    "minutes_mean", "fga_per_min", "fta_per_min", "reb_per_min",
    "ast_per_min", "stl_per_min", "blk_per_min", "three_pa_share", "tov_per_min",
)
_EFF_KEYS = ("two_fg_pct", "three_fg_pct", "ft_pct")


def _f(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return x


def _league_key(row: dict[str, Any]) -> str:
    return str(row.get("league") or "").strip().upper()


def _priors_for(row: dict[str, Any]) -> dict[str, float]:
    league = _league_key(row)
    out = dict(OPP_PRIORS.get(league) or OPP_PRIORS["WNBA"])
    out.update(EFF_PRIORS.get(league) or EFF_PRIORS["WNBA"])
    return out


def _market_sign_override(market: str, feature: str) -> bool | None:
    """Market-specific encoded sign. None means keep the default."""
    m = str(market or "").strip().lower()
    if feature == "tov_per_min" and m in {"tov", "to", "turnovers", "turnover"}:
        return True
    if feature == "reb_per_min" and m in {"reb", "rebounds", "rebound", "oreb"}:
        return True
    if feature == "ast_per_min" and m in {"ast", "assists", "assist"}:
        return True
    return None


def _driver_record(
    *,
    feature: str,
    family: str,
    observed: float,
    baseline: float,
    direction: str,
    market: str,
    source: str,
) -> dict[str, Any] | None:
    delta = observed - baseline
    if abs(delta) < 1e-9:
        return None
    default_higher = _HIGHER_LIFTS_MORE.get(feature, True)
    higher_lifts_more = _market_sign_override(market, feature)
    if higher_lifts_more is None:
        higher_lifts_more = default_higher
    more_positive = (delta > 0) if higher_lifts_more else (delta < 0)
    contributes_positive = more_positive if direction == "MORE" else (not more_positive)
    return {
        "feature": feature,
        "family": family,
        "observed": observed,
        "baseline": baseline,
        "delta": delta,
        "directionContribution": "positive" if contributes_positive else "negative",
        "source": source,
    }


def _drivers_from_snapshot(
    row: dict[str, Any],
    snapshot: dict[str, Any],
    direction: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    params = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}
    opp = snapshot.get("opportunity") if isinstance(snapshot.get("opportunity"), dict) else {}
    priors = _priors_for(row)
    market = str(row.get("market") or "")
    records: list[dict[str, Any]] = []
    for key in _OPP_KEYS:
        observed = _f(params.get(key))
        if observed is None:
            observed = _f(opp.get(key))
        baseline = _f(priors.get(key))
        if observed is None or baseline is None:
            continue
        rec = _driver_record(
            feature=key,
            family="OPPORTUNITY",
            observed=observed,
            baseline=baseline,
            direction=direction,
            market=market,
            source="parameter_snapshot_vs_league_prior",
        )
        if rec is not None:
            records.append(rec)
    for key in _EFF_KEYS:
        observed = _f(params.get(key))
        baseline = _f(priors.get(key))
        if observed is None or baseline is None:
            continue
        rec = _driver_record(
            feature=key,
            family="EFFICIENCY",
            observed=observed,
            baseline=baseline,
            direction=direction,
            market=market,
            source="parameter_snapshot_vs_league_prior",
        )
        if rec is not None:
            records.append(rec)
    # Role vs season minutes when both encoded on the snapshot.
    role_epoch = snapshot.get("role_epoch") if isinstance(snapshot.get("role_epoch"), dict) else {}
    selected = role_epoch.get("selected_epoch") if isinstance(role_epoch.get("selected_epoch"), dict) else {}
    role_minutes = _f(selected.get("minutes_mean") or selected.get("mean_minutes"))
    season_minutes = _f((snapshot.get("opportunity") or {}).get("minutes_mean"))
    if role_minutes is not None and season_minutes is not None and abs(role_minutes - season_minutes) > 1e-9:
        rec = _driver_record(
            feature="role_vs_season_minutes",
            family="ROLE",
            observed=role_minutes,
            baseline=season_minutes,
            direction=direction,
            market=market,
            source="role_epoch_vs_opportunity_minutes",
        )
        if rec is not None:
            records.append(rec)
    records.sort(key=lambda d: abs(float(d["delta"])), reverse=True)
    positive = [d for d in records if d["directionContribution"] == "positive"][:5]
    negative = [d for d in records if d["directionContribution"] == "negative"][:5]
    return positive, negative


def _failure_paths(
    row: dict[str, Any],
    snapshot: dict[str, Any],
    side_eval: dict[str, Any],
) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    opp = snapshot.get("opportunity") if isinstance(snapshot.get("opportunity"), dict) else {}
    eff = snapshot.get("efficiency") if isinstance(snapshot.get("efficiency"), dict) else {}
    surf = side_eval.get("lineSurface") if isinstance(side_eval.get("lineSurface"), dict) else {}
    support_o = int(opp.get("support_n") or 0)
    support_e = int(eff.get("support_n") or 0)
    if snapshot.get("synthetic"):
        paths.append({"code": "SYNTHETIC_EVIDENCE", "source": "parameter_snapshot.synthetic", "value": True})
    blocker = snapshot.get("blocker")
    if blocker:
        paths.append({"code": str(blocker), "source": "parameter_snapshot.blocker", "value": str(blocker)})
    if support_o < 3:
        paths.append({"code": "THIN_OPPORTUNITY_SUPPORT", "source": "snapshot.opportunity.support_n", "value": support_o})
    if support_e < 3:
        paths.append({"code": "THIN_EFFICIENCY_SUPPORT", "source": "snapshot.efficiency.support_n", "value": support_e})
    ood = _f(snapshot.get("ood_risk")) or 0.0
    if ood >= 0.35:
        paths.append({"code": "ELEVATED_OOD_RISK", "source": "parameter_snapshot.ood_risk", "value": ood})
    fragility = _f(side_eval.get("fragility")) or 0.0
    if fragility >= 0.45:
        paths.append({"code": "ELEVATED_FRAGILITY", "source": "side_eval.fragility", "value": fragility})
    elasticity = _f(surf.get("edge_elasticity")) or 0.0
    if elasticity >= 0.30:
        paths.append({"code": "HIGH_EDGE_ELASTICITY", "source": "line_surface.edge_elasticity", "value": elasticity})
    false_sign = _f(side_eval.get("falseSignRisk")) or 0.0
    if false_sign >= 0.30:
        paths.append({"code": "ELEVATED_FALSE_SIGN_RISK", "source": "side_eval.falseSignRisk", "value": false_sign})
    reliability = _f(side_eval.get("reliability") if "reliability" in side_eval else snapshot.get("reliability")) or 0.0
    if reliability <= 0.35:
        paths.append({"code": "LOW_RELIABILITY", "source": "side_eval.reliability", "value": reliability})
    status = str(snapshot.get("status") or "").strip().upper()
    if status and status not in {"ACTIVE", "AVAILABLE", "PROBABLE", "EXPECTED_ACTIVE"}:
        paths.append({"code": "NON_ACTIVE_STATUS", "source": "parameter_snapshot.status", "value": status})
    return paths


def _model_ids() -> list[str]:
    return [
        f"software:{SOFTWARE}",
        f"opportunity:{OPP_VERSION}",
        f"efficiency:{EFF_VERSION}",
        f"marketRegistry:{MARKET_REGISTRY_VERSION}",
        f"featureSchema:{FEATURE_SCHEMA_VERSION}",
        f"explanation:{EXPLANATION_SCHEMA}",
    ]


def _projected_opportunity(snapshot: dict[str, Any]) -> dict[str, Any]:
    params = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}
    opp = snapshot.get("opportunity") if isinstance(snapshot.get("opportunity"), dict) else {}
    out: dict[str, Any] = {}
    for key in ("minutes_mean", "minutes_sd", "fga_per_min", "fta_per_min", "reb_per_min", "ast_per_min",
                "pass_att_mean", "rush_att_mean", "routes_mean", "pa_mean", "support_n"):
        if key in opp and opp[key] is not None:
            out[key] = opp[key]
        elif key in params and params[key] is not None:
            out[key] = params[key]
    return out


def _projected_efficiency(snapshot: dict[str, Any]) -> dict[str, Any]:
    params = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}
    eff = snapshot.get("efficiency") if isinstance(snapshot.get("efficiency"), dict) else {}
    out: dict[str, Any] = {}
    for key in ("two_fg_pct", "three_fg_pct", "ft_pct", "support_n"):
        if key in params and params[key] is not None:
            out[key] = params[key]
        elif key in eff and eff[key] is not None:
            out[key] = eff[key]
    return out


def build_prop_explanation(
    row: dict[str, Any],
    snapshot: dict[str, Any],
    ledger_summary: dict[str, Any],
    side_eval: dict[str, Any],
    feature_hashes: list[str] | None,
    evidence_hashes: list[str] | None,
) -> dict[str, Any]:
    """Build a machine-readable explanation. Drivers are encoded diffs, never prose."""
    row = row if isinstance(row, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    ledger_summary = ledger_summary if isinstance(ledger_summary, dict) else {}
    side_eval = side_eval if isinstance(side_eval, dict) else {}
    direction = str(side_eval.get("side") or row.get("side") or "MORE").upper()
    if direction not in {"MORE", "LESS"}:
        direction = "MORE"
    surf = side_eval.get("lineSurface") if isinstance(side_eval.get("lineSurface"), dict) else {}
    positive, negative = _drivers_from_snapshot(row, snapshot, direction)
    hashes_f = [str(h) for h in (feature_hashes or []) if h]
    hashes_e = [str(h) for h in (evidence_hashes or snapshot.get("evidence_hashes") or []) if h]
    param_hash = str(snapshot.get("parameter_snapshot_hash") or snapshot.get("parameterSnapshotHash") or "")
    mean = _f(ledger_summary.get("mean") if "mean" in ledger_summary else ledger_summary.get("projectionMean"))
    median = _f(ledger_summary.get("median") if "median" in ledger_summary else ledger_summary.get("projectionMedian"))
    p_more = _f(ledger_summary.get("pMore") if "pMore" in ledger_summary else ledger_summary.get("pHigher"))
    p_less = _f(ledger_summary.get("pLess") if "pLess" in ledger_summary else ledger_summary.get("pLower"))
    p_push = _f(ledger_summary.get("pPush"))
    sim_hash = content_hash({
        "playerId": row.get("playerId"),
        "eventId": row.get("eventId"),
        "market": row.get("market"),
        "line": row.get("line"),
        "direction": direction,
        "parameterSnapshotHash": param_hash,
        "mean": mean,
        "median": median,
        "pMore": p_more,
        "pLess": p_less,
        "pPush": p_push,
        "n": ledger_summary.get("n") or ledger_summary.get("worldCount"),
    })
    selected_p = _f(side_eval.get("rawP") if "rawP" in side_eval else side_eval.get("selectedP"))
    explanation = {
        "schema": EXPLANATION_SCHEMA,
        "player": row.get("playerName") or row.get("player"),
        "team": row.get("team"),
        "opponent": row.get("opponent"),
        "market": row.get("market"),
        "line": row.get("line"),
        "direction": direction,
        "projectionId": row.get("projectionId"),
        "projectedOpportunity": _projected_opportunity(snapshot),
        "projectedEfficiency": _projected_efficiency(snapshot),
        "projectionMean": mean,
        "projectionMedian": median,
        "pMore": p_more,
        "pLess": p_less,
        "pPush": p_push,
        "selectedP": selected_p,
        "evidenceSafeP": _f(side_eval.get("evidenceSafeP")),
        "lowerBound": _f(side_eval.get("lowerBound")),
        "reliability": _f(side_eval.get("reliability") if "reliability" in side_eval else snapshot.get("reliability")),
        "dataQuality": _f(snapshot.get("data_quality") if "data_quality" in snapshot else snapshot.get("dataQuality")),
        "volatility": _f(side_eval.get("volatility")),
        "fragility": _f(side_eval.get("fragility")),
        "oodRisk": _f(snapshot.get("ood_risk") if "ood_risk" in snapshot else snapshot.get("oodRisk")),
        "falseSignRisk": _f(side_eval.get("falseSignRisk")),
        "monteCarloSE": _f(side_eval.get("monteCarloSE")),
        "epistemicUncertainty": _f(side_eval.get("epistemicUncertainty")),
        "lineTolerance": _f(surf.get("true_unclamped_line_tolerance")),
        "true_unclamped_line_tolerance": _f(surf.get("true_unclamped_line_tolerance")),
        "offered_line": _f(surf.get("offered_line")),
        "break_even_line": _f(surf.get("break_even_line")),
        "playable_break_line": _f(surf.get("playable_break_line")),
        "edge_elasticity": _f(surf.get("edge_elasticity")),
        "robustness_area": _f(surf.get("robustness_area")),
        "topPositiveDrivers": positive,
        "topNegativeDrivers": negative,
        "primaryFailurePaths": _failure_paths(row, snapshot, side_eval),
        "featureHashes": hashes_f,
        "evidenceHashes": hashes_e,
        "parameterSnapshotHash": param_hash,
        "modelIds": _model_ids(),
        "simulationHash": sim_hash,
    }
    return explanation


def render_prop_explanation_text(obj: dict[str, Any]) -> str:
    """Optional human text generated FROM the explanation object only. Never invents drivers."""
    obj = obj if isinstance(obj, dict) else {}
    parts = [
        f"{obj.get('player')} {obj.get('market')} {obj.get('line')} {obj.get('direction')}",
        f"mean={obj.get('projectionMean')} median={obj.get('projectionMedian')}",
        f"pMore={obj.get('pMore')} pLess={obj.get('pLess')} pPush={obj.get('pPush')}",
        f"tolerance={obj.get('lineTolerance')}",
    ]
    pos = obj.get("topPositiveDrivers") or []
    neg = obj.get("topNegativeDrivers") or []
    if pos:
        parts.append("+" + ",".join(str(d.get("feature")) for d in pos if isinstance(d, dict)))
    if neg:
        parts.append("-" + ",".join(str(d.get("feature")) for d in neg if isinstance(d, dict)))
    fails = obj.get("primaryFailurePaths") or []
    if fails:
        parts.append("fail=" + ",".join(str(d.get("code")) for d in fails if isinstance(d, dict)))
    return " | ".join(parts)


def load_feature_hash_index(dest: Path) -> dict[tuple[str, str], list[str]]:
    """entity+eventId → content hashes of FeatureStore records (and their sourceHashes)."""
    path = Path(dest) / "feature_store.jsonl"
    out: dict[tuple[str, str], list[str]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        key = (str(rec.get("entity") or ""), str(rec.get("eventId") or ""))
        bucket = out.setdefault(key, [])
        rec_hash = content_hash(rec)
        if rec_hash not in bucket:
            bucket.append(rec_hash)
        for h in rec.get("sourceHashes") or []:
            s = str(h)
            if s and s not in bucket:
                bucket.append(s)
    return out


def persist_prop_explanations(dest: Path, explanations: list[dict[str, Any]]) -> str:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "prop_explanations.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for obj in explanations:
            handle.write(json.dumps(obj, sort_keys=True, ensure_ascii=True) + "\n")
    return content_hash(explanations)
