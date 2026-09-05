"""Typed claim builders for source-aware host observations.

Canonical consumers import from ``dcm.research.observation_execute``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dcm.research.authority import derive_quality
from dcm.research.claims import claim_record
from dcm.research.provider import _validate_source_url
from dcm.research.scopes import canonical_scope, lookup_scopes

def _load_observations(path: Path) -> list[dict[str, Any]]:
    import json

    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            rows = parsed.get("observations") or parsed.get("rows")
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
            return [parsed]
    except json.JSONDecodeError:
        pass
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _nonempty_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"value": value} if value not in (None, "", [], {}) else {}
    return {
        str(k): v
        for k, v in value.items()
        if v not in (None, "", [], {}) and not str(k).startswith("_")
    }


def assemble_claim_value(obs: dict[str, Any]) -> dict[str, Any]:
    """Merge ``data`` and typed ``claims[]`` into a semantic claim_value."""
    data = obs.get("data")
    merged: dict[str, Any] = {}
    if isinstance(data, dict):
        merged.update(data)
    elif data not in (None, ""):
        merged["value"] = data
    typed = obs.get("claims") or obs.get("fields") or []
    field_units: dict[str, str] = {}
    field_provenance: dict[str, str] = {}
    if isinstance(typed, list):
        for row in typed:
            if not isinstance(row, dict):
                continue
            field = str(row.get("field") or row.get("name") or "").strip()
            if not field:
                continue
            if "value" in row:
                merged[field] = row.get("value")
            unit = row.get("unit") or row.get("units")
            if unit not in (None, ""):
                field_units[field] = str(unit)
            prov = row.get("provenance") or row.get("sourceField")
            if prov not in (None, ""):
                field_provenance[field] = str(prov)
    if field_units:
        merged["_fieldUnits"] = field_units
    if field_provenance:
        merged["_fieldProvenance"] = field_provenance
    return merged


def has_valid_field_coverage(claim_value: dict[str, Any]) -> bool:
    return bool(_nonempty_fields(claim_value))


def _match_request(obs: dict[str, Any], requests: list[dict[str, Any]]) -> dict[str, Any] | None:
    entity = obs.get("entityRef") if isinstance(obs.get("entityRef"), dict) else {}
    kind = canonical_scope(str(entity.get("kind") or obs.get("scope") or obs.get("semantic_scope") or ""))
    entity_id = str(entity.get("id") or obs.get("scope_id") or obs.get("scopeId") or "")
    req_id = str(obs.get("requestId") or obs.get("request_id") or "")
    aliases = set(lookup_scopes(kind)) | {kind}
    if req_id:
        for req in requests:
            if str(req.get("request_id") or req.get("requestId") or "") == req_id:
                return req
    for req in requests:
        if str(req.get("scope_id") or "") != entity_id:
            continue
        if str(req.get("scope") or "") in aliases or canonical_scope(str(req.get("scope") or "")) == kind:
            return req
    return None


def _match_action(
    obs: dict[str, Any],
    actions: list[dict[str, Any]],
    *,
    request: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    action_id = str(obs.get("actionId") or obs.get("action_id") or "")
    if action_id:
        for act in actions:
            if str(act.get("actionId") or "") == action_id:
                return act
    scope = canonical_scope(
        str(
            (obs.get("entityRef") or {}).get("kind")
            if isinstance(obs.get("entityRef"), dict)
            else obs.get("scope")
            or (request or {}).get("scope")
            or ""
        )
    )
    scope_id = str(
        (obs.get("entityRef") or {}).get("id")
        if isinstance(obs.get("entityRef"), dict)
        else obs.get("scopeId")
        or obs.get("scope_id")
        or (request or {}).get("scope_id")
        or ""
    )
    if scope and scope_id:
        want = f"AA_{scope}_{scope_id}"
        for act in actions:
            if str(act.get("actionId") or "") == want:
                return act
            if canonical_scope(str(act.get("scope") or "")) == scope and str(act.get("scopeId") or "") == scope_id:
                return act
    return None


def observation_to_typed_claim(
    obs: dict[str, Any],
    *,
    cutoff: str,
    request: dict[str, Any] | None = None,
    action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a source-aware host observation and build an EvidenceClaim."""
    url = str(obs.get("sourceUrl") or obs.get("url") or "")
    if not url:
        raise ValueError("HOST_OBSERVATION_SOURCE_URL_REQUIRED")
    _validate_source_url(url)
    retrieved = str(obs.get("retrievedAt") or obs.get("observed_at") or obs.get("observedAt") or "")
    if not retrieved:
        raise ValueError("HOST_OBSERVATION_RETRIEVED_AT_REQUIRED")
    published = str(obs.get("publishedAt") or obs.get("published_at") or retrieved)
    entity = obs.get("entityRef") if isinstance(obs.get("entityRef"), dict) else {}
    kind = canonical_scope(
        str(
            entity.get("kind")
            or obs.get("scope")
            or (action or {}).get("scope")
            or (request or {}).get("scope")
            or ""
        )
    )
    entity_id = str(
        entity.get("id")
        or obs.get("scope_id")
        or obs.get("scopeId")
        or (action or {}).get("scopeId")
        or (request or {}).get("scope_id")
        or ""
    )
    if not kind or not entity_id:
        raise ValueError("HOST_OBSERVATION_ENTITY_REF_REQUIRED")
    claim_value = assemble_claim_value(obs)
    if not has_valid_field_coverage(claim_value):
        raise ValueError("EMPTY_FIELD_COVERAGE")
    evidence_type = str(
        obs.get("evidenceType")
        or obs.get("claim_type")
        or (request or {}).get("need")
        or (action or {}).get("sourceFamily")
        or "HOST_OBSERVATION"
    )
    source_label = str(
        obs.get("sourceLabel")
        or obs.get("sourceId")
        or obs.get("source_id")
        or (action or {}).get("sourceId")
        or "HOST_WEB"
    )
    quality = derive_quality(
        source_id=source_label,
        url=url,
        published_at=published,
        observed_at=retrieved,
        forecast_cutoff=cutoff,
    )
    parser_version = str(
        obs.get("parserVersion") or obs.get("parser_version") or "host-observation-v1"
    )
    return claim_record(
        source_id=source_label,
        url=url,
        published_at=published,
        observed_at=retrieved,
        forecast_cutoff=cutoff,
        semantic_scope=kind,
        scope_id=entity_id,
        claim_type=evidence_type,
        claim_value=claim_value,
        reliability=quality["reliability"],
        freshness=quality["freshness"],
        valid_from=obs.get("validFrom") or obs.get("valid_from") or obs.get("validAt") or obs.get("valid_at"),
        valid_to=obs.get("validTo") or obs.get("valid_to"),
        supersedes=obs.get("supersedes") if isinstance(obs.get("supersedes"), (list, tuple)) else ([obs.get("supersedes")] if obs.get("supersedes") else None),
        retracts=obs.get("retracts") if isinstance(obs.get("retracts"), (list, tuple)) else ([obs.get("retracts")] if obs.get("retracts") else None),
        correction_of=str(obs.get("correctionOf") or obs.get("correction_of") or "") or None,
        state=str(obs.get("state") or "") or None,
        parser_version=parser_version,
        action_id=str(obs.get("actionId") or (action or {}).get("actionId") or "") or None,
        source_family=str(obs.get("sourceFamily") or (action or {}).get("sourceFamily") or "") or None,
    )


