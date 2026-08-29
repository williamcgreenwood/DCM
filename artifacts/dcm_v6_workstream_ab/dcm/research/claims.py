"""EvidenceClaim store. Structured records, not prose blobs."""

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
    assert_not_after_cutoff(observed_at, forecast_cutoff)
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
    body["source_hash"] = content_hash({"source_id": source_id, "url": url, "published_at": published_at})
    body["claim_hash"] = content_hash(body)
    return body


def dedupe(claims: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for c in claims:
        key = content_hash(
            {
                "scope": c.get("semantic_scope"),
                "scope_id": c.get("scope_id"),
                "claim_type": c.get("claim_type"),
                "claim_value": c.get("claim_value"),
            }
        )
        prev = seen.get(key)
        if prev is None:
            seen[key] = c
        elif prev.get("claim_hash") != c.get("claim_hash"):
            prev.setdefault("conflicts", []).append(c["claim_hash"])
            c.setdefault("conflicts", []).append(prev["claim_hash"])
            seen[key + c["claim_hash"]] = c
    return list(seen.values())
