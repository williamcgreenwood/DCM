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

CLAIM_TYPE_TO_FEATURE = {
    "STATUS": "status",
    "ROLE": "role",
    "STARTER": "starter",
    "DEPTH": "depth",
    "INJURY": "injury",
    "QB_ID": "qb_id",
    "TEAM": "team",
    "OPPONENT": "opponent",
    "PACE": "pace",
    "PASS_RATE": "pass_rate",
    "PASS_DEFENSE": "pass_defense",
    "RUSH_DEFENSE": "rush_defense",
    "WEATHER": "weather",
    "VENUE": "venue",
    "GAMESTATUS": "gameStatus",
    "GAME_STATUS": "gameStatus",
}


def _authority(claim: Mapping[str, Any]) -> int:
    raw = claim.get("authority") or claim.get("source_authority") or ""
    ctype = str(claim.get("claim_type") or "FACT").upper().split("_", 1)[0]; weight = {"STATUS": 1.0, "INJURY": 1.0, "ROLE": 0.98, "STARTER": 0.98, "WEATHER": 0.90, "HISTORY": 0.85}.get(ctype, 1.0)
    if isinstance(raw, (int, float)): return int(round((float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)) * weight))
    token = str(raw).upper()
    aliases = {"OFFICIAL_LEAGUE": 100, "OFFICIAL_PLATFORM": 100, "OFFICIAL_TEAM": 98, "STRUCTURED_STAT": 80, "BOX_SCORE_VENDOR": 80, "REPUTABLE_REPORTING": 50, "SEARCH_FALLBACK": 20, "FIXTURE": 0}
    if token in AUTHORITY_RANK: return int(round(AUTHORITY_RANK[token] * weight))
    if token in aliases: return int(round(aliases[token] * weight))
    rel = float(claim.get("reliability") or 0.0)
    return int(round(max(0.0, min(1.0, rel)) * 80 * weight))


def _freshness(claim: Mapping[str, Any]) -> float:
    try:
        return float(claim.get("freshness") if claim.get("freshness") is not None else claim.get("freshnessScore") or 0.0)
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
        observed_at = rec.get("observed_at") or rec.get("observedAt")
        published_at = rec.get("published_at") or rec.get("publishedAt")
        if cutoff and (is_after_cutoff(observed_at, cutoff) or is_after_cutoff(published_at, cutoff)):
            rec["excluded"] = "POST_CUTOFF"
            excluded_post_cutoff += 1
            continue
        grouped[_fact_key(rec)].append(rec)

    facts: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for key, group in grouped.items():
        by_lineage_value: dict[tuple[str, str], dict[str, Any]] = {}
        for raw_claim in group:
            claim = dict(raw_claim)
            claim_hash = str(claim.get("claim_hash") or claim.get("claimHash") or content_hash(claim))
            claim["_resolvedClaimHash"] = claim_hash
            lineage = claim.get("lineage_cluster_id") or claim.get("lineageClusterId") or claim.get("document_hash") or claim.get("source_hash")
            if not lineage:
                lineage = content_hash({"sourceId": claim.get("source_id"), "url": claim.get("url")})
            claim["_lineageId"] = str(lineage)
            value_hash = content_hash(json_safe_value(claim.get("claim_value")))
            dedupe_key = (claim["_lineageId"], value_hash)
            prior = by_lineage_value.get(dedupe_key)
            if prior is None or (_authority(claim), _freshness(claim), str(claim.get("published_at") or "")) > (_authority(prior), _freshness(prior), str(prior.get("published_at") or "")):
                by_lineage_value[dedupe_key] = claim

        deduped = list(by_lineage_value.values())
        observed = [parse_ts(c.get("observed_at") or c.get("observedAt")) for c in deduped]
        latest_observed = max((value for value in observed if value is not None), default=None)
        active = [c for c in deduped if latest_observed is None or parse_ts(c.get("observed_at") or c.get("observedAt")) == latest_observed]
        # Stable tie-breaking: strongest evidence first, then the smallest
        # immutable claim hash. Input order must not decide a MaterialFact winner.
        ranked = sorted(active, key=lambda c: str(c.get("_resolvedClaimHash") or ""))
        ranked = sorted(
            ranked,
            key=lambda c: (
                _authority(c),
                _freshness(c),
                parse_ts(c.get("published_at") or c.get("publishedAt")) or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        if not ranked:
            continue
        winner = ranked[0]
        by_value: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for claim in ranked:
            by_value[content_hash(json_safe_value(claim.get("claim_value")))].append(claim)
        unique_values = [json_safe_value(by_value[value_hash][0].get("claim_value")) for value_hash in sorted(by_value)]
        winner_value_hash = content_hash(json_safe_value(winner.get("claim_value")))
        supporting = [c for c in ranked if content_hash(json_safe_value(c.get("claim_value"))) == winner_value_hash]
        conflicting_claims = [c for c in ranked if content_hash(json_safe_value(c.get("claim_value"))) != winner_value_hash]
        conflict = bool(conflicting_claims)
        claim_type = str(winner.get("claim_type") or "FACT")
        authority_label = str(winner.get("authority") or winner.get("source_authority") or "DERIVED").upper()
        freshness_supplied = any("freshness" in c or "freshnessScore" in c for c in ranked)
        explicit_states = {str(c.get("state") or "").upper() for c in ranked}
        if claim_type.upper() in {"NOT_APPLICABLE", "N/A"} or str(winner.get("claim_value") or "").upper() in {"NOT_APPLICABLE", "N/A"}:
            state = "NOT_APPLICABLE"
        elif conflict:
            state = "CONFLICTED"
        elif winner.get("claim_value") is None:
            state = "UNRESOLVED"
        elif "UNRESOLVED" in explicit_states:
            state = "UNRESOLVED"
        elif "STALE" in explicit_states or (freshness_supplied and max(_freshness(c) for c in ranked) <= 0.0):
            state = "STALE"
        elif _authority(winner) >= 80:
            state = "CONFIRMED"
        else:
            state = "PROBABLE"
        lineage_ids = sorted({str(c.get("_lineageId") or "") for c in deduped if c.get("_lineageId")})
        active_lineage_ids = sorted({str(c.get("_lineageId") or "") for c in ranked if c.get("_lineageId")})
        historical_hashes = sorted(str(c.get("_resolvedClaimHash") or "") for c in deduped if c.get("_resolvedClaimHash"))
        supporting_hashes = sorted(str(c.get("_resolvedClaimHash") or "") for c in supporting if c.get("_resolvedClaimHash"))
        conflicting_hashes = sorted(str(c.get("_resolvedClaimHash") or "") for c in conflicting_claims if c.get("_resolvedClaimHash"))
        if conflict:
            conflicts.append({
                "factKey": key,
                "values": unique_values,
                "winnerSource": winner.get("source_id"),
                "winnerAuthority": _authority(winner),
                "state": "CONFLICTED",
                "independentLineageCount": len(lineage_ids),
                "claimHashes": sorted(supporting_hashes + conflicting_hashes),
                "action": "HOLD_UNTIL_REVERIFIED",
            })
        fact = {
            "factKey": key,
            "scope": winner.get("semantic_scope") or winner.get("scope"),
            "scopeId": winner.get("scope_id"),
            "claimType": winner.get("claim_type"),
            "value": winner.get("claim_value"),
            "sourceId": winner.get("source_id"),
            "claimHash": str(winner.get("_resolvedClaimHash") or ""),
            "sourceHash": winner.get("source_hash") or winner.get("document_hash"),
            "authority": _authority(winner),
            "authorityClass": authority_label,
            "authorityPolicy": {"claimType": claim_type, "sourceClass": authority_label},
            "freshness": _freshness(winner),
            "validTime": winner.get("valid_at") or winner.get("published_at"),
            "observedTime": winner.get("observed_at"),
            "forecastCutoff": cutoff,
            "state": state,
            "conflict": conflict,
            "claimCount": len(ranked),
            "historicalClaimCount": len(deduped),
            "historicalClaimHashes": historical_hashes,
            "supportingClaimHashes": supporting_hashes,
            "conflictingClaimHashes": conflicting_hashes,
            "lineageClusterIds": lineage_ids,
            "activeLineageClusterIds": active_lineage_ids,
            "independentLineageCount": len(lineage_ids),
            "activeIndependentLineageCount": len(active_lineage_ids),
            "holdPlayable": state in {"CONFLICTED", "UNRESOLVED", "STALE"},
            "resolutionReason": {"CONFIRMED": "single_or_consistent_high_authority_lineage", "PROBABLE": "single_or_consistent_lower_authority_lineage", "CONFLICTED": "latest_claims_disagree_after_lineage_deduplication", "STALE": "source_marked_stale_or_freshness_exhausted", "UNRESOLVED": "no_usable_claim_value_or_resolution", "NOT_APPLICABLE": "claim_explicitly_not_applicable"}.get(state, "UNRESOLVED"),
        }
        fact["contentHash"] = content_hash({
            "factKey": fact["factKey"],
            "value": json_safe_value(fact["value"]),
            "claimType": fact["claimType"],
            "authority": fact["authority"],
            "state": fact["state"],
            "supportingClaimHashes": fact["supportingClaimHashes"],
            "conflictingClaimHashes": fact["conflictingClaimHashes"],
            "historicalClaimHashes": fact["historicalClaimHashes"],
            "lineageClusterIds": fact["lineageClusterIds"],
            "activeLineageClusterIds": fact["activeLineageClusterIds"],
        })
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
        "states": ["CONFIRMED", "PROBABLE", "CONFLICTED", "STALE", "UNRESOLVED", "NOT_APPLICABLE"],
    }
    body["contentHash"] = content_hash({
        "schema": body["schema"],
        "facts": sorted_facts,
        "conflicts": sorted_conflicts,
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
        emitted = False
        mapped = CLAIM_TYPE_TO_FEATURE.get(str(fact.get("claimType") or "").upper())
        per_fact_hash = str(fact.get("contentHash") or fact_hash)
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
                "materialFactHash": per_fact_hash,
                "factKey": fact.get("factKey"),
                "claimHashes": [fact.get("claimHash")] if fact.get("claimHash") else [],
                "sourceHashes": [fact.get("sourceHash")] if fact.get("sourceHash") else [],
                "validTime": fact.get("validTime"),
                "observedTime": fact.get("observedTime"),
                "forecastCutoff": fact.get("forecastCutoff") or cutoff,
                "authority": fact.get("authority"),
                "freshness": fact.get("freshness"),
                "contradictionState": str(fact.get("state") or ("CONFLICTED" if fact.get("conflict") else "CLEAR")),
                "resolutionState": str(fact.get("state") or "UNRESOLVED"),
                "supportingClaimHashes": list(fact.get("supportingClaimHashes") or []),
                "conflictingClaimHashes": list(fact.get("conflictingClaimHashes") or []),
                "lineageClusterIds": list(fact.get("lineageClusterIds") or []),
                "activeLineageClusterIds": list(fact.get("activeLineageClusterIds") or []),
            }
            rec["contentHash"] = content_hash({k: v for k, v in rec.items() if k != "contentHash"})
            out.append(rec)
            emitted = True
        if mapped and not emitted:
            scalar = payload.get(mapped) if mapped in payload else (value if not isinstance(value, Mapping) else payload.get("value"))
            if scalar is not None:
                rec = {
                    "schema": "pillars_dcm.feature_record.v1",
                    "family": _feature_family(mapped),
                    "name": mapped,
                    "value": json_safe_value(scalar),
                    "scope": fact.get("scope"),
                    "scopeId": fact.get("scopeId"),
                    "materialFactHash": per_fact_hash,
                    "factKey": fact.get("factKey"),
                    "claimHashes": [fact.get("claimHash")] if fact.get("claimHash") else [],
                    "sourceHashes": [fact.get("sourceHash")] if fact.get("sourceHash") else [],
                    "validTime": fact.get("validTime"),
                    "observedTime": fact.get("observedTime"),
                    "forecastCutoff": fact.get("forecastCutoff") or cutoff,
                    "authority": fact.get("authority"),
                    "freshness": fact.get("freshness"),
                    "contradictionState": str(fact.get("state") or ("CONFLICTED" if fact.get("conflict") else "CLEAR")),
                    "resolutionState": str(fact.get("state") or "UNRESOLVED"),
                    "supportingClaimHashes": list(fact.get("supportingClaimHashes") or []),
                    "conflictingClaimHashes": list(fact.get("conflictingClaimHashes") or []),
                    "lineageClusterIds": list(fact.get("lineageClusterIds") or []),
                    "activeLineageClusterIds": list(fact.get("activeLineageClusterIds") or []),
                }
                rec["contentHash"] = content_hash({k: v for k, v in rec.items() if k != "contentHash"})
                out.append(rec)
                emitted = True
        if not emitted and value is not None:
            rec = {
                "schema": "pillars_dcm.feature_record.v1",
                "family": "CONTEXT",
                "name": str(fact.get("claimType") or "fact"),
                "value": json_safe_value(value),
                "scope": fact.get("scope"),
                "scopeId": fact.get("scopeId"),
                "materialFactHash": per_fact_hash,
                "factKey": fact.get("factKey"),
                "claimHashes": [fact.get("claimHash")] if fact.get("claimHash") else [],
                "sourceHashes": [fact.get("sourceHash")] if fact.get("sourceHash") else [],
                "validTime": fact.get("validTime"),
                "observedTime": fact.get("observedTime"),
                "forecastCutoff": fact.get("forecastCutoff") or cutoff,
                "authority": fact.get("authority"),
                "freshness": fact.get("freshness"),
                "contradictionState": str(fact.get("state") or ("CONFLICTED" if fact.get("conflict") else "CLEAR")),
                "resolutionState": str(fact.get("state") or "UNRESOLVED"),
                "supportingClaimHashes": list(fact.get("supportingClaimHashes") or []),
                "conflictingClaimHashes": list(fact.get("conflictingClaimHashes") or []),
                "lineageClusterIds": list(fact.get("lineageClusterIds") or []),
                "activeLineageClusterIds": list(fact.get("activeLineageClusterIds") or []),
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


def apply_fact_features_to_packets(
    *,
    player: dict[str, Any],
    team: dict[str, Any],
    event: dict[str, Any],
    environment: dict[str, Any],
    counterparty: dict[str, Any],
    row: Mapping[str, Any],
    features: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Overlay resolved FeatureRecords onto modeling packets BEFORE RoleEpoch/fit."""
    player = dict(player)
    team = dict(team)
    event = dict(event)
    environment = dict(environment)
    counterparty = dict(counterparty)
    pid = str(row.get("playerId") or row.get("subjectId") or "")
    eid = str(row.get("eventId") or "")
    tid = str(row.get("teamId") or row.get("affiliationId") or row.get("team") or "")
    oid = str(row.get("opponentId") or row.get("opponent") or "")
    hashes: list[str] = []
    applied: list[str] = []
    for feat in features or []:
        if not isinstance(feat, Mapping):
            continue
        name = str(feat.get("name") or "")
        if not name:
            continue
        scope = str(feat.get("scope") or "").upper()
        sid = str(feat.get("scopeId") or "")
        value = feat.get("value")
        target: dict[str, Any] | None = None
        if scope in {"SUBJECT", "PLAYER"} and (not sid or sid == pid):
            target = player
        elif scope in {"AFFILIATION", "TEAM"} and (not sid or sid == tid):
            target = team
        elif scope in {"COUNTERPARTY", "OPPONENT"} and (not sid or sid == oid):
            target = counterparty
        elif scope == "EVENT" and (not sid or sid == eid):
            target = event
        elif scope == "ENVIRONMENT" and (not sid or sid in {eid, f"env:{eid}"} or str(sid).startswith("env:")):
            target = environment
        elif sid == pid:
            target = player
        elif sid == tid:
            target = team
        elif sid == oid:
            target = counterparty
        elif sid == eid:
            target = event
        if target is None:
            continue
        target[name] = value
        if name == "status" and target is player:
            player["status"] = value
        if name == "role" and target is player:
            player["role"] = value
            player["projected_role"] = value
        if name == "qb_id" and target is player:
            player["qb_id"] = value
        if name in {"pace", "pass_rate"} and target is team:
            team[name] = value
            if name == "pace":
                team["pace_multiplier"] = value
        if name in {"pass_defense", "rush_defense"}:
            counterparty[name] = value
            opp = event.get("opponent") if isinstance(event.get("opponent"), dict) else {}
            opp = dict(opp)
            opp[name] = value
            event["opponent"] = opp
        if name in {"weather", "venue", "gameStatus", "surface"}:
            event[name] = value
            environment[name] = value
        hashes.append(str(feat.get("materialFactHash") or feat.get("contentHash") or ""))
        applied.append(name)
    if environment:
        event = {**event, **{k: v for k, v in environment.items() if v is not None}}
    if counterparty:
        team = {**team, **{k: v for k, v in counterparty.items() if k not in team or team.get(k) in (None, "", 1.0)}}
        if not isinstance(event.get("opponent"), dict):
            event["opponent"] = dict(counterparty)
        else:
            event["opponent"] = {**event["opponent"], **counterparty}
    return {
        "player": player,
        "team": team,
        "event": event,
        "environment": environment,
        "counterparty": counterparty,
        "materialFactHashes": [h for h in hashes if h],
        "applied": applied,
    }


def facts_for_refresh(facts: Mapping[str, Any] | None) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Index MaterialFacts by (scope, scopeId, claimType-or-field). Never latest-claim-wins across types."""
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not isinstance(facts, Mapping):
        return out
    for fact in facts.get("facts") or []:
        if not isinstance(fact, Mapping):
            continue
        scope = str(fact.get("scope") or "")
        sid = str(fact.get("scopeId") or "")
        ctype = str(fact.get("claimType") or "FACT")
        out[(scope, sid, ctype)] = dict(fact)
        value = fact.get("value")
        if isinstance(value, Mapping):
            for key in FACT_FEATURE_KEYS:
                if key in value and value[key] is not None:
                    out[(scope, sid, key)] = {**dict(fact), "field": key, "fieldValue": value[key]}
    return out

