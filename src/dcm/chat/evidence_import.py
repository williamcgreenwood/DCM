"""Convert simple host observations into EvidenceClaims.

The host supplies source/url/timestamps/entity/data. DCM owns identity
resolution, cutoff, source policy, reliability/freshness, hashing, dedupe,
conflicts, EvidenceGraph insertion and cache identity.

When ``acquisition_actions.json`` is present, import runs the source-aware
closed loop (typed field validation, fanout, coverage + ParameterSnapshot
descendant recompute). Empty field coverage never counts as success.
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
def _observation_execute():
    from dcm.research import observation_execute as mod
    return mod
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
    """Legacy entry: validate + convert one observation (rejects empty fields)."""
    return _observation_execute().observation_to_typed_claim(obs, cutoff=cutoff, request=request, action=None)


def import_observations(
    dest: Path,
    observations_path: Path,
    *,
    store_root: Path | None = None,
) -> dict[str, Any]:
    dest = Path(dest)
    # Prefer the source-aware closed loop whenever the run has acquisition actions
    # or host observations carry action/source projection fields.
    action_doc = read_json(dest / "acquisition_actions.json") or {}
    observations = _load_observations(Path(observations_path))
    source_aware = bool(action_doc.get("actions")) or any(
        isinstance(obs, dict)
        and (
            obs.get("actionId")
            or obs.get("sourceFamily")
            or obs.get("sourceCandidates")
            or obs.get("claims")
            or obs.get("parserVersion")
        )
        for obs in observations
    )
    if source_aware:
        return _observation_execute().execute_source_aware_observations(
            dest,
            Path(observations_path),
            store_root=store_root,
        )

    requests = read_json(dest / "research_requests.json") or []
    if not isinstance(requests, list):
        requests = []
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
        "emptyFieldCoverageCountsAsSuccess": False,
    }


__all__ = [
    "assemble_claim_value",
    "has_valid_field_coverage",
    "import_observations",
    "observation_to_claim",
]


def __getattr__(name: str):
    if name in {"assemble_claim_value", "has_valid_field_coverage", "observation_to_typed_claim"}:
        return getattr(_observation_execute(), name)
    raise AttributeError(name)
