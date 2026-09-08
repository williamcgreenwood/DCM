"""Incremental semantic coverage with a deterministic full-scan audit mode."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash
from dcm.research.coverage import coverage_report, evaluate_request
from dcm.research.scopes import canonical_scope, scopes_match


class IncrementalCoverageMismatch(RuntimeError):
    code = "COVERAGE_INCREMENTAL_MISMATCH"


def _request_id(request: Mapping[str, Any]) -> str:
    return str(request.get("request_id") or request.get("requestId") or "")


def _row_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    return content_hash(sorted((dict(row) for row in rows), key=lambda row: str(row.get("requestId") or "")))


def coverage_index_hash(requests: Iterable[Mapping[str, Any]]) -> str:
    rows = [
        {
            "requestId": _request_id(req),
            "scope": canonical_scope(str(req.get("scope") or "")),
            "scopeId": str(req.get("scope_id") or req.get("scopeId") or ""),
        }
        for req in requests
    ]
    return content_hash(sorted(rows, key=lambda row: (row["scope"], row["scopeId"], row["requestId"])))


def _dirty_ids(requests: list[dict[str, Any]], changed_claims: Iterable[Mapping[str, Any]] | None) -> set[str]:
    changed = list(changed_claims or [])
    if not changed:
        return {_request_id(req) for req in requests}
    dirty: set[str] = set()
    for claim in changed:
        claim_scope = str(claim.get("semantic_scope") or claim.get("scope") or "")
        claim_id = str(claim.get("scope_id") or claim.get("scopeId") or "")
        for req in requests:
            req_scope = str(req.get("scope") or "")
            req_id = str(req.get("scope_id") or req.get("scopeId") or "")
            if claim_id == req_id and scopes_match(req_scope, claim_scope):
                dirty.add(_request_id(req))
    return dirty


def incremental_coverage_report(
    requests: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    *,
    prior: Mapping[str, Any] | None = None,
    changed_claims: Iterable[Mapping[str, Any]] | None = None,
    verify_full: bool = False,
) -> dict[str, Any]:
    """Evaluate only requests touched by changed claims, then reuse old rows.

    The optional full verification is intended for audit cadence and small
    runs.  It turns incremental recomputation into a tested optimization rather
    than a second semantic definition.
    """
    requests = [dict(req) for req in requests if isinstance(req, Mapping)]
    claims = [dict(claim) for claim in claims if isinstance(claim, Mapping)]
    idx_hash = coverage_index_hash(requests)
    dirty = _dirty_ids(requests, changed_claims)
    prior_rows = {
        str(row.get("requestId") or ""): dict(row)
        for row in ((prior or {}).get("requests") or [])
        if isinstance(row, Mapping)
    }
    can_reuse = bool(prior_rows) and str((prior or {}).get("coverageIndexHash") or idx_hash) == idx_hash
    rows: list[dict[str, Any]] = []
    evaluated = 0
    for req in requests:
        rid = _request_id(req)
        if can_reuse and rid not in dirty and rid in prior_rows:
            rows.append(prior_rows[rid])
        else:
            rows.append(evaluate_request(req, claims))
            evaluated += 1
    rows.sort(key=lambda row: str(row.get("requestId") or ""))
    incomplete = [row for row in rows if not row.get("complete")]
    body: dict[str, Any] = {
        "complete": not incomplete,
        "requested": len(rows),
        "completeRequests": len(rows) - len(incomplete),
        "incompleteRequests": len(incomplete),
        "missingRequirementCount": sum(len(row.get("missing") or []) for row in incomplete),
        "requests": rows,
        "mode": "incremental",
        "dirtyRequestIds": sorted(dirty),
        "requestsEvaluated": evaluated,
        "coverageIndexHash": idx_hash,
    }
    body["incrementalCoverageSha"] = content_hash({k: v for k, v in body.items() if k != "incrementalCoverageSha"})
    if verify_full:
        full = coverage_report(requests, claims)
        if _row_digest(full.get("requests") or []) != _row_digest(rows):
            raise IncrementalCoverageMismatch("COVERAGE_INCREMENTAL_MISMATCH")
        body["equalityVerified"] = True
        body["fullCoverageSha"] = content_hash(full)
    else:
        body["equalityVerified"] = False
        body["fullCoverageSha"] = None
    return body


__all__ = ["IncrementalCoverageMismatch", "coverage_index_hash", "incremental_coverage_report"]
