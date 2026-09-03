"""Bridge from run artifacts to the next optimized host research batch."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dcm.algorithms.selection import AlgorithmSelectionEngine
from dcm.chat.state import read_json, write_json
from dcm.research.batch import build_next_research_batch
from dcm.research.provider import BundleProvider
from dcm.research.research_store import ResearchStore, hydrate_reused_claims


def next_research_batch(
    dest: Path,
    *,
    max_entities: int = 25,
    max_dependent_offers: int = 500,
    store_root: Path | None = None,
) -> dict[str, Any]:
    dest = Path(dest)
    requests = read_json(dest / "research_requests.json") or []
    coverage = read_json(dest / "evidence_coverage.json") or read_json(dest / "evidence" / "coverage.json") or {}
    store = ResearchStore(store_root or dest / "research_store")
    batch = build_next_research_batch(
        requests if isinstance(requests, list) else [],
        coverage=coverage if isinstance(coverage, dict) else {},
        store=store,
        max_entities=max_entities,
        max_dependent_offers=max_dependent_offers,
    )
    reused_claims = hydrate_reused_claims(
        store,
        [
            {
                "scope": t.get("scope"),
                "scope_id": t.get("scopeId") or t.get("scope_id"),
                "acquire": False,
                "deltaClass": t.get("deltaClass"),
            }
            for t in (batch.get("reused") or [])
        ],
    )
    if reused_claims:
        bundle = BundleProvider(dest / "evidence_bundle.jsonl")
        existing = {str(c.get("claim_hash") or "") for c in bundle.all_claims()}
        fresh = [c for c in reused_claims if str(c.get("claim_hash") or "") not in existing]
        if fresh:
            bundle.append(fresh)
        write_json(dest / "evidence" / "claims.json", bundle.all_claims())
    reused = int(batch.get("reusedCount") or 0)
    acquired = int(batch.get("unresolvedCount") or 0)
    batch["storeTelemetry"] = store.telemetry(reused=reused, acquired=acquired)
    batch["hydratedClaimCount"] = len(reused_claims)
    selection = AlgorithmSelectionEngine().select(
        "RESEARCH_SCHEDULE",
        {"consumer": "dcm.chat.research_bridge.next_research_batch"},
    )
    batch["algorithmSelection"] = selection.to_dict()
    write_json(dest / "host_research_batch.json", batch)
    return batch
