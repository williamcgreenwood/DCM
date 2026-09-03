"""MaterialFactResolution: claims do not feed models blindly.

Lineage: SourceDocument → EvidenceClaim → MaterialFactResolution → Feature
→ ParameterSnapshot → EventWorld → PropEvaluation.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash


AUTHORITY_RANK = {
    "OFFICIAL": 100,
    "STRUCTURED_STAT": 80,
    "REPUTABLE_REPORTING": 50,
    "SEARCH_FALLBACK": 20,
    "FIXTURE": 0,
}


def _authority(claim: Mapping[str, Any]) -> int:
    raw = str(claim.get("authority") or claim.get("source_authority") or "").upper()
    if raw in AUTHORITY_RANK:
        return AUTHORITY_RANK[raw]
    rel = float(claim.get("reliability") or 0.0)
    return int(round(rel * 80))


def _freshness(claim: Mapping[str, Any]) -> float:
    try:
        return float(claim.get("freshness") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fact_key(claim: Mapping[str, Any]) -> str:
    scope = str(claim.get("semantic_scope") or claim.get("scope") or "")
    scope_id = str(claim.get("scope_id") or "")
    ctype = str(claim.get("claim_type") or "FACT")
    return f"{scope}|{scope_id}|{ctype}"


def resolve_material_facts(
    claims: Iterable[Mapping[str, Any]],
    *,
    cutoff: str | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in claims:
        rec = dict(raw)
        if cutoff and str(rec.get("observed_at") or "") > str(cutoff):
            rec["excluded"] = "POST_CUTOFF"
            continue
        grouped[_fact_key(rec)].append(rec)

    facts: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for key, group in grouped.items():
        ranked = sorted(group, key=lambda c: (_authority(c), _freshness(c), str(c.get("published_at") or "")), reverse=True)
        winner = ranked[0]
        values = [json_safe_value(c.get("claim_value")) for c in ranked]
        unique_values = []
        for v in values:
            if v not in unique_values:
                unique_values.append(v)
        conflict = len(unique_values) > 1
        if conflict:
            conflicts.append({
                "factKey": key,
                "values": unique_values,
                "winnerSource": winner.get("source_id"),
                "action": "REVERIFY_OR_HOLD" if _authority(winner) < 80 else "AUTHORITY_WINS",
            })
        fact = {
            "factKey": key,
            "scope": winner.get("semantic_scope") or winner.get("scope"),
            "scopeId": winner.get("scope_id"),
            "claimType": winner.get("claim_type"),
            "value": winner.get("claim_value"),
            "sourceId": winner.get("source_id"),
            "claimHash": winner.get("claim_hash"),
            "authority": _authority(winner),
            "freshness": _freshness(winner),
            "conflict": conflict,
            "claimCount": len(ranked),
            "holdPlayable": bool(conflict and _authority(winner) < 80),
        }
        facts.append(fact)

    body = {
        "schema": "pillars_dcm.material_fact_resolution.v1",
        "factCount": len(facts),
        "conflictCount": len(conflicts),
        "facts": sorted(facts, key=lambda r: str(r["factKey"])),
        "conflicts": conflicts,
        "lineage": [
            "SourceDocument", "EvidenceClaim", "MaterialFactResolution",
            "Feature", "ParameterSnapshot", "EventWorld", "PropEvaluation",
        ],
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "facts", "conflicts"}})
    return body


def hold_playable_scope_ids(facts: Mapping[str, Any] | None) -> set[str]:
    """Subject/event/affiliation ids whose unresolved conflicts hold PLAYABLE."""
    out: set[str] = set()
    if not isinstance(facts, Mapping):
        return out
    for fact in facts.get("facts") or []:
        if not isinstance(fact, Mapping):
            continue
        if fact.get("holdPlayable") and fact.get("scopeId"):
            out.add(str(fact["scopeId"]))
    return out


def apply_hold_playable(rec: dict[str, Any], hold_ids: set[str]) -> dict[str, Any]:
    """Demote PLAYABLE when a material conflict is unresolved. Never raises P."""
    if not hold_ids:
        return rec
    row = rec.get("row") if isinstance(rec.get("row"), dict) else rec
    pid = str(row.get("playerId") or "")
    eid = str(row.get("eventId") or "")
    tid = str(row.get("teamId") or row.get("team") or "")
    if not hold_ids.intersection({pid, eid, tid}):
        return rec
    out = dict(rec)
    out["materialFactHold"] = True
    if out.get("grade") == "PLAYABLE":
        out["grade"] = "LEAN"
        out["blocker"] = out.get("blocker") or "MATERIAL_FACT_CONFLICT"
        out["modeledPlayable"] = False
        out["productionSelectable"] = False
    return out


def json_safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(k): json_safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe_value(v) for v in value]
    return str(value)
