"""CFB champion / challenger model selection. Portable stdlib champions only.

Advanced families (XGBoost, GP, GNN, TabPFN, neural SDEs) remain
PERMANENT_CHALLENGER and are never required for ChatGPT execution.
Selection is chronological-metric based when a benchmark table is supplied;
otherwise the registered portable champion is used.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.cfb.markets import ACTIVE_CFB_MARKETS, MARKET_CONTRACTS
from dcm.contracts.hashes import content_hash

# Production champions are ChatGPT-native. Challengers are recorded, not forced.
_RATE_CHAMPION = {
    "algorithmId": "ALG-ML-PROB-001",
    "family": "EmpiricalBayes",
    "fallback": "ALG-ML-TABULAR-001",
}
_COUNT_CHAMPION = {
    "algorithmId": "ALG-ML-PROB-001",
    "family": "HierarchicalBayesPoisson",
    "fallback": "ALG-ML-TABULAR-001",
}
_YARDS_CHAMPION = {
    "algorithmId": "ALG-ML-TABULAR-001",
    "family": "RegularizedGLM",
    "fallback": "ALG-ML-PROB-001",
}
_BINOMIAL_CHAMPION = {
    "algorithmId": "ALG-ML-PROB-001",
    "family": "BetaBinomial",
    "fallback": "ALG-ML-TABULAR-001",
}

_BY_DISTRIBUTION = {
    "NegativeBinomial": _COUNT_CHAMPION,
    "Poisson": _COUNT_CHAMPION,
    "Binomial": _BINOMIAL_CHAMPION,
    "Normal": _YARDS_CHAMPION,
    "Student-t": _YARDS_CHAMPION,
}

CHALLENGERS = (
    {"algorithmId": "ALG-ML-TABULAR-005", "family": "HistGradientBoosting", "lifecycle": "PERMANENT_CHALLENGER"},
    {"algorithmId": "ALG-ML-TABULAR-003", "family": "RandomForest", "lifecycle": "PERMANENT_CHALLENGER"},
    {"algorithmId": "ALG-ML-PROB-002", "family": "GaussianProcess", "lifecycle": "PERMANENT_CHALLENGER"},
)


def _metrics_ok(row: Mapping[str, Any]) -> bool:
    """Prefer lower log-loss / Brier / ECE; require portable CPU."""
    if row.get("gpuOnly"):
        return False
    return True


def select_champion(
    market: str,
    *,
    role: str | None = None,
    sample_n: int = 0,
    benchmark: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canon = str(market or "").lower()
    spec = MARKET_CONTRACTS.get(canon) or {}
    dist = str(spec.get("distribution") or "Normal")
    base = dict(_BY_DISTRIBUTION.get(dist, _YARDS_CHAMPION))
    if sample_n < 4:
        base = dict(_RATE_CHAMPION)
        base["supportRegime"] = "SMALL_SAMPLE"
        base["note"] = "Early-season / thin support uses Empirical Bayes + role-comparable priors."
    else:
        base["supportRegime"] = "STANDARD"
        base["note"] = "Portable champion; challengers remain unelected until chronological metrics win."
    if benchmark:
        candidates = [c for c in (benchmark.get("candidates") or []) if _metrics_ok(c)]
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda c: (
                    float(c.get("logLoss") or 9e9),
                    float(c.get("brier") or 9e9),
                    float(c.get("ece") or 9e9),
                    float(c.get("cpuMs") or 9e9),
                ),
            )
            winner = ranked[0]
            if winner.get("algorithmId") and not winner.get("gpuOnly"):
                base["algorithmId"] = str(winner["algorithmId"])
                base["family"] = str(winner.get("family") or base["family"])
                base["note"] = "Chronological benchmark selected portable champion."
    base.update({
        "sport": "CFB",
        "market": canon,
        "role": str(role or ""),
        "sampleN": int(sample_n),
        "distribution": dist,
        "challengers": [dict(c) for c in CHALLENGERS],
        "gpuRequired": False,
        "actualProducer": "dcm.model.gridiron_models.empirical_bayes_shrink",
        "lifecycle": "SHADOW_DIAGNOSTIC" if not benchmark else "SELECTED",
        "note": (
            base.get("note")
            or "Selector is diagnostic unless a chronological benchmark actually dispatches a different producer."
        ),
    })
    if not benchmark:
        base["lifecycle"] = "SHADOW_DIAGNOSTIC"
        base["note"] = (
            "Portable Empirical Bayes (ALG-ML-PROB-001) is the actual ParameterSnapshot producer. "
            "This table does not dispatch a different model at LR000000."
        )
    return base


def select_cfb_champions(
    modeled: list[Mapping[str, Any]],
    *,
    benchmarks: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    by_market: dict[str, dict[str, Any]] = {}
    for prop in modeled:
        row = prop.get("row") if isinstance(prop.get("row"), dict) else prop
        if str(row.get("league") or "").upper() != "CFB":
            continue
        market = str(row.get("market") or "").lower()
        if market not in ACTIVE_CFB_MARKETS or market in by_market:
            continue
        snap = prop.get("parameterSnapshot") if isinstance(prop.get("parameterSnapshot"), dict) else {}
        opp = snap.get("opportunity") if isinstance(snap.get("opportunity"), dict) else {}
        sample_n = int(opp.get("support_n") or 0)
        by_market[market] = select_champion(
            market,
            role=str(row.get("role") or ""),
            sample_n=sample_n,
            benchmark=(benchmarks or {}).get(market),
        )
    body = {
        "schema": "pillars_dcm.cfb_champion_challenger.v1",
        "markets": by_market,
        "marketCount": len(by_market),
        "learningRevision": "LR000000",
        "predictiveClaim": "NONE",
        "selectorLifecycle": "SHADOW_DIAGNOSTIC",
        "actualChampionProducer": "dcm.model.gridiron_models",
        "actualChampionAlgorithmId": "ALG-ML-PROB-001",
        "note": "Champions are portable. The selector table is SHADOW until a chronological benchmark dispatches a different producer. Empirical Bayes already runs inside ParameterSnapshots.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "markets"}})
    return body
