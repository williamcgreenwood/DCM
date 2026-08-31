"""Convert simple host observations into EvidenceClaims.

The host supplies source/url/timestamps/entity/data. DCM owns identity
resolution, cutoff, source policy, reliability/freshness, hashing, dedupe,
conflicts, EvidenceGraph insertion and cache identity.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dcm.chat.state import read_json, write_json
from dcm.research.authority import derive_quality
from dcm.research.claims import claim_record, conflict_ledger, dedupe
from dcm.research.coverage import coverage_report
from dcm.research.evidence_graph import build_evidence_graph
from dcm.research.provider import BundleProvider, _validate_source_url
from dcm.research.research_store import ResearchStore
from dcm.research.scopes import canonical_scope, lookup_scopes


def _load_observations(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() in {".jsonl", ".ndjson"} or "\n{" in text[:200] or text.startswith("{") and "\n" in text:
        out: list[dict[str, Any]] = []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if isinstance(rec, dict):
                out.append(rec)
        return out
    parsed = json.loads(text)
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    return []


def _match_request(obs: dict[str, Any], requests: list[dict[str, Any]]) -> dict[str, Any] | None:
    entity = obs.get("entityRef") if isinstance(obs.get("entityRef"), dict) else {}
    kind = canonical_scope(str(entity.get("kind") or obs.get("scope") or obs.get("semantic_scope") or ""))
    entity_id = str(entity.get("id") or obs.get("scope_id") or obs.get("scopeId") or "")
    aliases = set(lookup_scopes(kind)) | {kind}
    for req in requests:
        if str(req.get("scope_id") or "") != entity_id:
            continue
        if str(req.get("scope") or "") in aliases or canonical_scope(str(req.get("scope") or "")) == kind:
            return req
    return None


def observation_to_claim(
    obs: dict[str, Any],
    *,
    cutoff: str,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        str(entity.get("kind") or obs.get("scope") or (request or {}).get("scope") or "")
    )
    entity_id = str(
        entity.get("id")
        or obs.get("scope_id")
        or (request or {}).get("scope_id")
        or ""
    )
    if not kind or not entity_id:
        raise ValueError("HOST_OBSERVATION_ENTITY_REF_REQUIRED")
    data = obs.get("data")
    if data is None:
        data = {}
    if not isinstance(data, dict):
        data = {"value": data}
    evidence_type = str(
        obs.get("evidenceType")
        or obs.get("claim_type")
        or (request or {}).get("need")
        or "HOST_OBSERVATION"
    )
    source_label = str(obs.get("sourceLabel") or obs.get("source_id") or "HOST_WEB")
    quality = derive_quality(
        source_id=source_label,
        url=url,
        published_at=published,
        observed_at=retrieved,
        forecast_cutoff=cutoff,
    )
    # Host-supplied hashes/reliability are ignored. DCM recomputes them.
    return claim_record(
        source_id=source_label,
        url=url,
        published_at=published,
        observed_at=retrieved,
        forecast_cutoff=cutoff,
        semantic_scope=kind,
        scope_id=entity_id,
        claim_type=evidence_type,
        claim_value=data,
        reliability=quality["reliability"],
        freshness=quality["freshness"],
    )


def import_observations(
    dest: Path,
    observations_path: Path,
    *,
    store_root: Path | None = None,
) -> dict[str, Any]:
    dest = Path(dest)
    requests = read_json(dest / "research_requests.json") or []
    if not isinstance(requests, list):
        requests = []
    cutoff = ""
    freeze = read_json(dest / "freeze.json") or {}
    board = read_json(dest / "board.json") or {}
    host_state = read_json(dest / "host_state.json") or {}
    cutoff = str(
        host_state.get("forecastCutoff")
        or freeze.get("forecastCutoff")
        or board.get("forecastCutoff")
        or ""
    )
    if not cutoff:
        raise ValueError("FORECAST_CUTOFF_REQUIRED")
    observations = _load_observations(Path(observations_path))
    claims: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for i, obs in enumerate(observations):
        try:
            req = _match_request(obs, requests)
            claims.append(observation_to_claim(obs, cutoff=cutoff, request=req))
        except (ValueError, TypeError, KeyError) as exc:
            errors.append({"index": i, "error": str(exc)})
    claims = dedupe(claims)
    bundle_path = dest / "evidence_bundle.jsonl"
    existing = BundleProvider(bundle_path)
    if claims:
        existing.append(claims)
    all_claims = existing.all_claims()
    coverage = coverage_report(requests, all_claims)
    write_json(dest / "evidence_coverage.json", coverage)
    write_json(dest / "evidence" / "coverage.json", coverage)
    write_json(dest / "evidence" / "conflicts.json", conflict_ledger(all_claims))
    (dest / "evidence").mkdir(exist_ok=True)
    write_json(dest / "evidence" / "claims.json", all_claims)
    offer_doc = read_json(dest / "subject_offer_sets.json") or read_json(dest / "player_offer_sets.json") or {}
    offer_sets = offer_doc.get("sets") or offer_doc.get("offerSets") or []
    if isinstance(offer_sets, list):
        graph = build_evidence_graph(all_claims, offer_sets, packets=[])
        write_json(dest / "evidence_graph.json", graph)
    store = ResearchStore(store_root or dest / "research_store")
    stored = []
    for claim in claims:
        stored.append(
            store.put_claim(
                claim,
                sport=str(claim.get("semantic_scope") or ""),
                entity_kind=str(claim.get("semantic_scope") or ""),
                as_of=cutoff,
            )
        )
    return {
        "imported": len(claims),
        "rejected": len(errors),
        "errors": errors,
        "bundlePath": str(bundle_path),
        "claimCount": len(all_claims),
        "coverageComplete": bool(coverage.get("complete")),
        "incompleteRequests": coverage.get("incompleteRequests"),
        "conflicts": conflict_ledger(all_claims),
        "store": store.telemetry(),
        "stored": stored,
        "hostInventedHashes": False,
    }
