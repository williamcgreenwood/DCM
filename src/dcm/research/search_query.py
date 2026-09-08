"""Field-aware query planning for host web-research batches."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash


QUERY_SCHEMA = "pillars_dcm.research_query_plan.v1"
_TERM = re.compile(r"[A-Za-z0-9_]+")


def _cutoff_date(cutoff: str | None) -> str | None:
    if not cutoff:
        return None
    try:
        text = str(cutoff).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.date().isoformat()
    except ValueError:
        return None


def _terms(value: Any) -> list[str]:
    terms: set[str] = set()
    for token in _TERM.findall(str(value or "")):
        lowered = token.lower()
        if len(lowered) > 1:
            terms.add(lowered)
        terms.update(part for part in lowered.split("_") if len(part) > 1)
    return sorted(terms)


_SCOPE_INTENTS = {
    "SPORT": ("rules", "competition format", "scoring"),
    "COMPETITION": ("competition context", "schedule", "standings"),
    "EVENT": ("schedule", "venue", "start time", "status", "lineup"),
    "ENVIRONMENT": ("weather", "surface", "venue conditions"),
    "AFFILIATION": ("team context", "roster", "depth chart", "recent game logs"),
    "COUNTERPARTY": ("opponent defense", "matchup", "recent game logs"),
    "SUBJECT": ("role", "status", "comparable game logs", "opportunity", "efficiency"),
    "MARKET_DEFINITION": ("official market definition", "settlement rules", "stat definition"),
    "OFFER": ("line", "over under", "odds", "availability"),
}

_NEED_FIELD_ALIASES = {
    "start": "scheduled_start",
    "time": "scheduled_start",
    "venue": "venue",
    "starter": "starters_known",
    "starters": "starters_known",
    "lineup": "lineup_status",
    "status": "status",
    "environment": "environment",
    "weather": "weather",
    "surface": "surface",
    "role": "role",
    "logs": "game_logs",
    "history": "game_logs",
    "opportunity": "opportunity",
    "efficiency": "efficiency",
    "roster": "roster",
    "depth": "depth",
    "defense": "defense",
    "matchup": "matchup",
    "definition": "definition_verified",
    "rules": "settlement_rules",
    "line": "line",
    "odds": "odds",
    "availability": "availability",
}


def _required_fields(action: Mapping[str, Any], request: Mapping[str, Any]) -> list[str]:
    explicit = request.get("requiredFields") or request.get("knownMissing") or action.get("requiredFields") or action.get("knownMissing") or []
    if isinstance(explicit, Mapping):
        explicit = list(explicit)
    fields = {str(value) for value in explicit if str(value)}
    need = request.get("need") or action.get("need") or ""
    for token in _terms(need):
        field = _NEED_FIELD_ALIASES.get(token)
        if field:
            fields.add(field)
    return sorted(fields)


def compile_query(action: Mapping[str, Any], *, request: Mapping[str, Any] | None = None, cutoff: str | None = None) -> dict[str, Any]:
    request = request or {}
    scope = str(action.get("scope") or request.get("scope") or "SUBJECT").upper()
    sid = str(action.get("scopeId") or request.get("scope_id") or request.get("scopeId") or "")
    context = action.get("context") if isinstance(action.get("context"), Mapping) else request.get("context")
    context_terms = _terms(" ".join(str(v) for v in context.values())) if isinstance(context, Mapping) else _terms(context)
    required_fields = _required_fields(action, request)
    intent = list(_SCOPE_INTENTS.get(scope, ("official statistics", "status", "history")))
    base_terms = list(dict.fromkeys([scope.lower(), *context_terms[:12], *intent, *required_fields[:16]]))
    if sid:
        base_terms.insert(0, sid)
    source_candidates = [str(x) for x in (action.get("sourceCandidates") or []) if str(x)]
    source_hint = source_candidates[0] if source_candidates else ""
    date_clause = f" before:{_cutoff_date(cutoff)}" if _cutoff_date(cutoff) else ""
    query = " ".join(base_terms) + date_clause
    variants = [query]
    if required_fields:
        variants.append(" ".join([sid, *required_fields[:10], "official"] + ([f"before:{_cutoff_date(cutoff)}"] if _cutoff_date(cutoff) else [])))
    if source_hint:
        variants.append(" ".join([sid, *intent[:4], source_hint] + ([f"before:{_cutoff_date(cutoff)}"] if _cutoff_date(cutoff) else [])))
    body: dict[str, Any] = {
        "schema": QUERY_SCHEMA,
        "scope": scope,
        "actionId": str(action.get("actionId") or "") or None,
        "requestId": str(request.get("request_id") or request.get("requestId") or "") or None,
        "requiredFields": required_fields,
        "sourceCandidates": source_candidates,
        "cutoff": str(cutoff or "") or None,
        "queryVariants": list(dict.fromkeys(v.strip() for v in variants if v.strip())),
        "negativeTerms": ["rumor", "unverified", "prediction"],
        "verificationPlan": {
            "requirePublishedOrUpdatedTime": True,
            "requirePublicUrl": True,
            "rejectAfterCutoff": bool(cutoff),
            "requireAllFields": required_fields,
            "requireTwoSourcesForContradiction": True,
        },
        "budget": {"maxSearchCalls": 3, "maxSourcesPerCall": 8, "maxEvidenceItems": max(8, len(required_fields) * 2)},
    }
    body["planHash"] = content_hash(body)
    return body


__all__ = ["QUERY_SCHEMA", "compile_query"]
