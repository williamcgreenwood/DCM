"""MaterialFactResolution: claims do not feed models blindly.

Lineage: SourceDocument → EvidenceClaim → MaterialFactResolution → Feature
→ ParameterSnapshot → EventWorld → PropEvaluation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash


AUTHORITY_RANK = {
    "OFFICIAL": 100,
    "STRUCTURED_STAT": 80,
    "REPUTABLE_REPORTING": 50,
    "SEARCH_FALLBACK": 20,
    "FIXTURE": 0,
}

FACT_FEATURE_KEYS = (
    "starter", "role", "depth", "injury", "status", "team", "opponent",
    "qb_id", "pace", "pass_rate", "weather", "venue", "gameStatus",
    "pass_defense", "rush_defense",
)


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


def parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_after_cutoff(observed: Any, cutoff: Any) -> bool:
    """True when observed is strictly after cutoff. ISO-normalized, not naive strings."""
    obs = parse_ts(observed)
    cut = parse_ts(cutoff)
    if obs is not None and cut is not None:
        return obs > cut
    if cutoff and observed:
        return str(observed) > str(cutoff)
    return False


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
    excluded_post_cutoff = 0
    for raw in claims:
        rec = dict(raw)
        if cutoff and is_after_cutoff(rec.get("observed_at") or rec.get("observedAt"), cutoff):
            rec["excluded"] = "POST_CUTOFF"
            excluded_post_cutoff += 1
            continue
        grouped[_fact_key(rec)].append(rec)

    facts: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for key, group in grouped.items():
        ranked = sorted(
            group,
            key=lambda c: (
                _authority(c),
                _freshness(c),
                parse_ts(c.get("published_at") or c.get("publishedAt")) or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
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
                "winnerAuthority": _authority(winner),
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
            "sourceHash": winner.get("source_hash") or winner.get("document_hash"),
            "authority": _authority(winner),
            "freshness": _freshness(winner),
            "validTime": winner.get("valid_at") or winner.get("published_at"),
            "observedTime": winner.get("observed_at"),
            "forecastCutoff": cutoff,
            "conflict": conflict,
            "claimCount": len(ranked),
            "holdPlayable": bool(conflict and _authority(winner) < 80),
        }
        facts.append(fact)

    sorted_facts = sorted(facts, key=lambda r: str(r["factKey"]))
    sorted_conflicts = sorted(conflicts, key=lambda r: str(r.get("factKey") or ""))
    body = {
        "schema": "pillars_dcm.material_fact_resolution.v1",
        "factCount": len(sorted_facts),
        "conflictCount": len(sorted_conflicts),
        "excludedPostCutoff": excluded_post_cutoff,
        "facts": sorted_facts,
        "conflicts": sorted_conflicts,
        "lineage": [
            "SourceDocument", "EvidenceClaim", "MaterialFactResolution",
            "Feature", "ParameterSnapshot", "EventWorld", "PropEvaluation",
        ],
    }
    body["contentHash"] = content_hash({
        "schema": body["schema"],
        "facts": [
            {
                "factKey": f.get("factKey"),
                "value": json_safe_value(f.get("value")),
                "authority": f.get("authority"),
                "conflict": f.get("conflict"),
                "claimHash": f.get("claimHash"),
                "sourceId": f.get("sourceId"),
            }
            for f in sorted_facts
        ],
        "conflicts": [
            {"factKey": c.get("factKey"), "values": json_safe_value(c.get("values"))}
            for c in sorted_conflicts
        ],
        "excludedPostCutoff": excluded_post_cutoff,
    })
    return body


def facts_to_features(
    facts: Mapping[str, Any] | None,
    *,
    cutoff: str | None = None,
) -> list[dict[str, Any]]:
    """MaterialFactResolution → FeatureRecords with provenance."""
    out: list[dict[str, Any]] = []
    if not isinstance(facts, Mapping):
        return out
    fact_hash = str(facts.get("contentHash") or "")
    for fact in facts.get("facts") or []:
        if not isinstance(fact, Mapping):
            continue
        if cutoff and is_after_cutoff(fact.get("observedTime"), cutoff):
            continue
        value = fact.get("value")
        payload = value if isinstance(value, Mapping) else {"value": value}
        for key in FACT_FEATURE_KEYS:
            if key not in payload or payload[key] is None:
                continue
            rec = {
                "schema": "pillars_dcm.feature_record.v1",
                "family": _feature_family(key),
                "name": key,
                "value": payload[key],
                "scope": fact.get("scope"),
                "scopeId": fact.get("scopeId"),
                "materialFactHash": fact_hash,
                "factKey": fact.get("factKey"),
                "claimHashes": [fact.get("claimHash")] if fact.get("claimHash") else [],
                "sourceHashes": [fact.get("sourceHash")] if fact.get("sourceHash") else [],
                "validTime": fact.get("validTime"),
                "observedTime": fact.get("observedTime"),
                "forecastCutoff": fact.get("forecastCutoff") or cutoff,
                "authority": fact.get("authority"),
                "freshness": fact.get("freshness"),
                "contradictionState": "CONFLICT" if fact.get("conflict") else "CLEAR",
            }
            rec["contentHash"] = content_hash({k: v for k, v in rec.items() if k != "contentHash"})
            out.append(rec)
        if not any(k in payload for k in FACT_FEATURE_KEYS) and value is not None:
            rec = {
                "schema": "pillars_dcm.feature_record.v1",
                "family": "CONTEXT",
                "name": str(fact.get("claimType") or "fact"),
                "value": json_safe_value(value),
                "scope": fact.get("scope"),
                "scopeId": fact.get("scopeId"),
                "materialFactHash": fact_hash,
                "factKey": fact.get("factKey"),
                "claimHashes": [fact.get("claimHash")] if fact.get("claimHash") else [],
                "sourceHashes": [fact.get("sourceHash")] if fact.get("sourceHash") else [],
                "validTime": fact.get("validTime"),
                "observedTime": fact.get("observedTime"),
                "forecastCutoff": fact.get("forecastCutoff") or cutoff,
                "authority": fact.get("authority"),
                "freshness": fact.get("freshness"),
                "contradictionState": "CONFLICT" if fact.get("conflict") else "CLEAR",
            }
            rec["contentHash"] = content_hash({k: v for k, v in rec.items() if k != "contentHash"})
            out.append(rec)
    return out


def apply_facts_to_context(context: dict[str, Any], features: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Overlay resolved facts onto a player/event parameter context. Never post-cutoff."""
    out = dict(context)
    for feat in features:
        name = str(feat.get("name") or "")
        if not name:
            continue
        out[name] = feat.get("value")
        out.setdefault("_materialFactHashes", []).append(feat.get("materialFactHash"))
    return out


def _feature_family(name: str) -> str:
    if name in {"starter", "role", "depth", "injury", "status"}:
        return "AVAILABILITY" if name in {"injury", "status"} else "ROLE"
    if name in {"pace", "pass_rate", "pass_defense", "rush_defense"}:
        return "AFFILIATION" if name in {"pace", "pass_rate"} else "COUNTERPARTY"
    if name in {"weather", "venue", "gameStatus"}:
        return "ENVIRONMENT" if name != "gameStatus" else "EVENT"
    if name in {"team", "opponent", "qb_id"}:
        return "IDENTITY"
    return "CONTEXT"


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
