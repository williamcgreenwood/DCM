"""Runtime refinement of research deltas.

Keeps classify_delta deterministic and adds:
- HistoricalGapResolver when expected completed event IDs are declared
- adaptive freshness from stored timestamps + forecast cutoff + event start
"""
from __future__ import annotations

from typing import Any

from dcm.research.freshness import apply_adaptive_freshness
from dcm.research.historical_gap import apply_history_gap
from dcm.research.research_store import ResearchStore, classify_delta
from dcm.research.scopes import canonical_scope


def refine_delta(
    request: dict[str, Any],
    prior: dict[str, Any] | None,
    delta: dict[str, Any],
) -> dict[str, Any]:
    delta = apply_history_gap(request, prior, delta)
    return apply_adaptive_freshness(request, prior, delta)


def classify_requests(
    requests: list[dict[str, Any]],
    store: ResearchStore | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for req in requests:
        if not isinstance(req, dict):
            continue
        prior = None
        if store is not None:
            prior = store.prior_fields(str(req.get("scope") or ""), str(req.get("scope_id") or ""))
        extra = req.get("context") if isinstance(req.get("context"), dict) else {}
        required = int(req.get("requiredHistoryCount") or extra.get("requiredHistoryCount") or 3)
        delta = classify_delta(
            request=req,
            prior=prior,
            current_affiliation=str(
                req.get("affiliationId") or extra.get("affiliationId") or extra.get("teamId") or ""
            ),
            current_opponent=str(req.get("opponentId") or extra.get("opponentId") or extra.get("opponent") or ""),
            current_role_epoch=str(req.get("roleEpochId") or extra.get("roleEpochId") or ""),
            current_definition=str(req.get("definitionId") or extra.get("definitionId") or ""),
            known_history_count=None if prior is None else prior.get("historyCount"),
            required_history_count=required,
        )
        delta = refine_delta(req, prior, delta)
        rec = dict(req)
        rec["deltaClass"] = delta["deltaClass"]
        rec["deltaReason"] = delta.get("reason") or delta.get("deltaReason")
        rec["acquire"] = bool(delta["acquire"])
        if "lastVerified" in delta:
            rec["lastVerified"] = delta["lastVerified"]
        if "knownHistoryCount" in delta:
            rec["knownHistoryCount"] = delta["knownHistoryCount"]
        if "appendEventIds" in delta:
            rec["appendEventIds"] = delta["appendEventIds"]
            rec["reuseEventIds"] = delta.get("reuseEventIds")
        if "freshnessEvaluation" in delta:
            rec["freshnessEvaluation"] = delta["freshnessEvaluation"]
        if "freshnessInputs" in delta:
            rec["freshnessInputs"] = delta["freshnessInputs"]
        rec["priorContentHash"] = (prior or {}).get("contentHash")
        rec["scope"] = canonical_scope(str(rec.get("scope") or ""))
        out.append(rec)
    return out
