"""EvidenceClaim records and immutable conflict accounting."""

from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.temporal import assert_not_after_cutoff


def claim_record(
    *,
    source_id: str,
    url: str,
    published_at: str,
    observed_at: str,
    forecast_cutoff: str,
    semantic_scope: str,
    scope_id: str,
    claim_type: str,
    claim_value: Any,
    supports: list[str] | None = None,
    conflicts: list[str] | None = None,
    reliability: float,
    freshness: float,
) -> dict[str, Any]:
    assert_not_after_cutoff(observed_at, forecast_cutoff, field="observed_at")
    if str(published_at).strip():
        assert_not_after_cutoff(published_at, forecast_cutoff, field="published_at")
    body = {
        "source_id": source_id,
        "url": url,
        "published_at": published_at,
        "observed_at": observed_at,
        "forecast_cutoff": forecast_cutoff,
        "semantic_scope": semantic_scope,
        "scope_id": scope_id,
        "claim_type": claim_type,
        "claim_value": claim_value,
        "supports": supports or [],
        "conflicts": conflicts or [],
        "reliability": reliability,
        "freshness": freshness,
    }
    body["source_hash"] = content_hash(
        {"source_id": source_id, "url": url, "published_at": published_at}
    )
    body["claim_hash"] = content_hash(body)
    return body


def dedupe(claims: list[dict]) -> list[dict]:
    """Remove byte-logically identical claims without mutating hashed content."""
    seen: dict[str, dict] = {}
    for claim in claims:
        claim_hash = str(claim.get("claim_hash") or content_hash(claim))
        if claim_hash not in seen:
            seen[claim_hash] = claim
    return [seen[key] for key in sorted(seen)]


def conflict_ledger(claims: list[dict]) -> list[dict[str, Any]]:
    """Record divergent values separately from immutable EvidenceClaims.

    Only claims for the same semantic subject/type at the same observation
    timestamp are treated as unresolved contemporaneous contradictions.
    Historical changes at different observation times are preserved as lineage,
    not mislabeled as conflicts.
    """
    groups: dict[tuple[str, str, str, str], list[dict]] = {}
    for claim in claims:
        key = (
            str(claim.get("semantic_scope") or ""),
            str(claim.get("scope_id") or ""),
            str(claim.get("claim_type") or ""),
            str(claim.get("observed_at") or ""),
        )
        groups.setdefault(key, []).append(claim)

    out: list[dict[str, Any]] = []
    for (scope, scope_id, claim_type, observed_at), rows in sorted(groups.items()):
        by_value: dict[str, list[str]] = {}
        for row in rows:
            value_hash = content_hash(row.get("claim_value"))
            by_value.setdefault(value_hash, []).append(str(row.get("claim_hash") or ""))
        if len(by_value) <= 1:
            continue
        out.append(
            {
                "scope": scope,
                "scopeId": scope_id,
                "claimType": claim_type,
                "observedAt": observed_at,
                "valueHashes": sorted(by_value),
                "claimHashes": sorted(
                    h for hashes in by_value.values() for h in hashes if h
                ),
                "sourceCount": len(rows),
                "state": "UNRESOLVED_CONTEMPORANEOUS_CONFLICT",
            }
        )
    return out
