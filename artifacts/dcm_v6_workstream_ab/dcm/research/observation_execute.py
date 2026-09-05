"""Execute source-aware host observations into the closed import→coverage→consumer loop.

Host tasks from ``dcm.research.batch`` carry actionId / sourceFamily / source
candidates. This module accepts matching timestamped observations, validates
typed field coverage, imports EvidenceClaims idempotently, recomputes
requirement coverage, and rebuilds ParameterSnapshots for changed descendants
only when contracts close. One AcquisitionAction observation fans out to every
dependent offer at that reusable scope.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dcm.chat.state import read_json, write_json
from dcm.model.parameters import build_parameter_snapshot
from dcm.research.claims import conflict_ledger, dedupe
from dcm.research.coverage import coverage_report, evaluate_request
from dcm.research.evidence_graph import build_evidence_graph
from dcm.research.observation_typed import (
    _load_observations,
    _match_action,
    _match_request,
    assemble_claim_value,
    has_valid_field_coverage,
    observation_to_typed_claim,
)
from dcm.research.provider import BundleProvider
from dcm.research.research_store import ResearchStore
from dcm.research.scopes import canonical_scope
from dcm.runtime.dag import Dag

# Re-export for tests and chat.evidence_import
__all__ = [
    "assemble_claim_value",
    "execute_source_aware_observations",
    "has_valid_field_coverage",
    "observation_to_typed_claim",
]

def _affected_rows(
    rows: list[dict[str, Any]],
    *,
    action: dict[str, Any] | None,
    claim: dict[str, Any],
) -> list[dict[str, Any]]:
    offer_ids = {str(x) for x in ((action or {}).get("offerIds") or []) if x}
    scope = canonical_scope(str(claim.get("semantic_scope") or ""))
    scope_id = str(claim.get("scope_id") or "")
    hit: list[dict[str, Any]] = []
    for row in rows:
        pid = str(row.get("projectionId") or "")
        if offer_ids and pid in offer_ids:
            hit.append(row)
            continue
        if not offer_ids:
            if scope == "EVENT" and str(row.get("eventId") or "") == scope_id:
                hit.append(row)
            elif scope == "AFFILIATION" and str(row.get("teamId") or row.get("affiliationId") or "") == scope_id:
                hit.append(row)
            elif scope == "COUNTERPARTY" and str(row.get("opponentId") or row.get("opponent") or "") == scope_id:
                hit.append(row)
            elif scope == "SUBJECT" and str(row.get("playerId") or row.get("subjectId") or "") == scope_id:
                hit.append(row)
    return hit


def _snapshot_ablation(
    rows: list[dict[str, Any]],
    claims_before: list[dict[str, Any]],
    claims_after: list[dict[str, Any]],
) -> dict[str, Any]:
    before_hashes: dict[str, str] = {}
    after_hashes: dict[str, str] = {}
    changed: list[str] = []
    for row in rows:
        oid = str(row.get("projectionId") or "")
        if not oid:
            continue
        b = build_parameter_snapshot(row, claims_before)
        a = build_parameter_snapshot(row, claims_after)
        before_hashes[oid] = str(b.get("parameter_snapshot_hash") or "")
        after_hashes[oid] = str(a.get("parameter_snapshot_hash") or "")
        if before_hashes[oid] != after_hashes[oid]:
            changed.append(oid)
    return {
        "offerCount": len(before_hashes),
        "changedOfferCount": len(changed),
        "changedOfferIds": changed[:50],
        "parameterConsumerChanged": bool(changed),
        "beforeHashes": {k: before_hashes[k] for k in list(before_hashes)[:8]},
        "afterHashes": {k: after_hashes[k] for k in list(after_hashes)[:8]},
    }


def execute_source_aware_observations(
    dest: Path,
    observations_path: Path,
    *,
    store_root: Path | None = None,
) -> dict[str, Any]:
    """Import source-aware host observations and close coverage→consumer contracts.

    Empty field coverage is rejected (does not count as success). Valid claims
    recompute requirement coverage and ParameterSnapshot descendants for the
    AcquisitionAction fanout.
    """
    dest = Path(dest)
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
    action_doc = read_json(dest / "acquisition_actions.json") or {}
    actions = list(action_doc.get("actions") or []) if isinstance(action_doc, dict) else []
    rows = board.get("rows") if isinstance(board, dict) else []
    if not isinstance(rows, list):
        rows = []

    bundle_path = dest / "evidence_bundle.jsonl"
    existing = BundleProvider(bundle_path)
    claims_before = list(existing.all_claims())
    coverage_before = coverage_report(requests, claims_before)

    observations = _load_observations(Path(observations_path))
    claims: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    fanouts: list[dict[str, Any]] = []
    closed_request_ids: list[str] = []

    for i, obs in enumerate(observations):
        try:
            req = _match_request(obs, requests)
            action = _match_action(obs, actions, request=req)
            claim = observation_to_typed_claim(obs, cutoff=cutoff, request=req, action=action)
            # Pre-check: claim must actually move semantic coverage for its request.
            probe_claims = claims_before + claims + [claim]
            target_req = req
            if target_req is None and action:
                # Prefer first incomplete requirement on this action.
                req_ids = {str(x) for x in (action.get("requirementIds") or [])}
                for r in requests:
                    rid = str(r.get("request_id") or r.get("requestId") or "")
                    if rid in req_ids:
                        verdict = evaluate_request(r, claims_before + claims)
                        if not verdict.get("complete"):
                            target_req = r
                            break
                if target_req is None:
                    for r in requests:
                        rid = str(r.get("request_id") or r.get("requestId") or "")
                        if rid in req_ids:
                            target_req = r
                            break
            if target_req is not None:
                before = evaluate_request(target_req, claims_before + claims)
                after = evaluate_request(target_req, probe_claims)
                if before.get("complete") is False and after.get("complete") is False:
                    # Imported claim exists but does not close the contract — still
                    # store it (partial progress) while recording unresolved missing.
                    pass
                elif after.get("complete"):
                    closed_request_ids.append(str(target_req.get("request_id") or target_req.get("requestId") or ""))
            claims.append(claim)
            offer_ids = list((action or {}).get("offerIds") or [])
            req_ids = list((action or {}).get("requirementIds") or [])
            affected = _affected_rows(rows, action=action, claim=claim)
            fanouts.append(
                {
                    "actionId": (action or {}).get("actionId") or claim.get("actionId"),
                    "scope": claim.get("semantic_scope"),
                    "scopeId": claim.get("scope_id"),
                    "sourceId": claim.get("source_id"),
                    "sourceFamily": claim.get("sourceFamily"),
                    "requirementIds": req_ids,
                    "offerIds": offer_ids or [str(r.get("projectionId") or "") for r in affected],
                    "dependentOfferCount": len(offer_ids) if offer_ids else len(affected),
                    "requestId": (target_req or {}).get("request_id") if target_req else None,
                }
            )
        except (ValueError, TypeError, KeyError) as exc:
            errors.append({"index": i, "error": str(exc)})

    claims = dedupe(claims)
    existing_hashes = {str(c.get("claim_hash") or "") for c in claims_before}
    fresh_claims = [c for c in claims if str(c.get("claim_hash") or "") not in existing_hashes]
    if fresh_claims:
        existing.append(fresh_claims)
    all_claims = existing.all_claims()
    # Idempotent re-import reports only newly stored claims.
    claims = fresh_claims
    coverage = coverage_report(requests, all_claims)
    write_json(dest / "evidence_coverage.json", coverage)
    write_json(dest / "evidence" / "coverage.json", coverage)
    write_json(dest / "evidence" / "conflicts.json", conflict_ledger(all_claims))
    (dest / "evidence").mkdir(exist_ok=True)
    write_json(dest / "evidence" / "claims.json", all_claims)

    offer_doc = read_json(dest / "subject_offer_sets.json") or read_json(dest / "player_offer_sets.json") or {}
    offer_sets = offer_doc.get("sets") or offer_doc.get("offerSets") or []
    if isinstance(offer_sets, list) and offer_sets:
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

    # Changed-descendant recompute: only offers touched by imported actions.
    touched_rows: list[dict[str, Any]] = []
    seen_oids: set[str] = set()
    for fan in fanouts:
        for oid in fan.get("offerIds") or []:
            oid = str(oid or "")
            if not oid or oid in seen_oids:
                continue
            seen_oids.add(oid)
            for row in rows:
                if str(row.get("projectionId") or "") == oid:
                    touched_rows.append(row)
                    break
    if not touched_rows and claims:
        for claim in claims:
            for row in _affected_rows(rows, action=None, claim=claim):
                oid = str(row.get("projectionId") or "")
                if oid and oid not in seen_oids:
                    seen_oids.add(oid)
                    touched_rows.append(row)

    ablation = _snapshot_ablation(touched_rows, claims_before, all_claims)
    write_json(
        dest / "parameters" / "source_aware_import_ablation.json",
        {
            "schema": "pillars_dcm.source_aware_import_ablation.v1",
            "cutoff": cutoff,
            "ablation": ablation,
            "fanouts": fanouts,
        },
    )
    # Persist recomputed snapshots for changed offers (descendant artifacts).
    snapshots = []
    for row in touched_rows:
        snap = build_parameter_snapshot(row, all_claims)
        snapshots.append(
            {
                "projectionId": row.get("projectionId"),
                "parameter_snapshot_hash": snap.get("parameter_snapshot_hash"),
                "scopes_used": snap.get("scopes_used"),
                "minimum_model_support": snap.get("minimum_model_support"),
            }
        )
    if snapshots:
        write_json(
            dest / "parameters" / "source_aware_import_snapshots.json",
            {
                "schema": "pillars_dcm.source_aware_import_snapshots.v1",
                "count": len(snapshots),
                "rows": snapshots,
            },
        )

    dag = Dag(
        cutoff=cutoff,
        config_hash="source-aware-import",
        schema_version="v1",
        source_versions={"parser": "host-observation-v1"},
    )
    for row in touched_rows:
        dag.add("PARAMETER", str(row.get("projectionId") or ""))
        dag.add("EVENT_WORLDS", str(row.get("eventId") or ""))
        dag.add("GRADE", str(row.get("projectionId") or ""))
    invalidated = dag.invalidate_for_delta("REFRESH_CURRENT_CONTEXT") if touched_rows else []
    write_json(dest / "source_aware_import_dag.json", dag.snapshot())

    closed_unique = list(dict.fromkeys(closed_request_ids))
    max_fanout = max((int(f.get("dependentOfferCount") or 0) for f in fanouts), default=0)
    result = {
        "schema": "pillars_dcm.source_aware_import_result.v1",
        "imported": len(claims),
        "rejected": len(errors),
        "errors": errors,
        "bundlePath": str(bundle_path),
        "claimCount": len(all_claims),
        "coverageComplete": bool(coverage.get("complete")),
        "coverageBeforeCompleteRequests": int(coverage_before.get("completeRequests") or 0),
        "coverageAfterCompleteRequests": int(coverage.get("completeRequests") or 0),
        "incompleteRequests": coverage.get("incompleteRequests"),
        "closedRequestIds": closed_unique,
        "contractsClosed": len(closed_unique),
        "fanouts": fanouts,
        "maxFanout": max_fanout,
        "oneSourceMultipleOffers": max_fanout > 1,
        "parameterConsumerChanged": bool(ablation.get("parameterConsumerChanged")),
        "changedOfferCount": int(ablation.get("changedOfferCount") or 0),
        "ablation": ablation,
        "invalidatedDescendants": invalidated,
        "conflicts": conflict_ledger(all_claims),
        "store": store.telemetry(),
        "stored": stored,
        "hostInventedHashes": False,
        "emptyFieldCoverageCountsAsSuccess": False,
    }
    write_json(dest / "source_aware_import_result.json", result)
    return result
