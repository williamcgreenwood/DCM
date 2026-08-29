"""ResearchProvider boundary and production-evidence gating.

FixtureProvider remains available for deterministic engineering tests, but fixture
claims are never production-eligible. FileProvider is the production boundary:
ChatGPT/the operator writes structured, timestamped evidence records after web
research and the runtime validates them before modeling.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from dcm.research.claims import claim_record, dedupe
from dcm.contracts.hashes import content_hash
from dcm.research.temporal import assert_not_after_cutoff


class ResearchProvider(Protocol):
    def resolve(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


def _is_fixture_claim(claim: dict[str, Any]) -> bool:
    source = str(claim.get("source_id") or "").upper()
    url = str(claim.get("url") or "").lower()
    return source.startswith("FIXTURE_") or url.startswith("fixture://") or bool(claim.get("synthetic"))


def _validate_claim(claim: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    required = {
        "source_id", "url", "published_at", "observed_at", "forecast_cutoff",
        "semantic_scope", "scope_id", "claim_type", "claim_value",
        "reliability", "freshness", "source_hash", "claim_hash",
    }
    missing = sorted(required - set(claim))
    if missing:
        raise ValueError(f"EVIDENCE_CLAIM_MISSING_FIELDS:{','.join(missing)}")
    if str(claim["semantic_scope"]) != str(request["scope"]):
        raise ValueError("EVIDENCE_SCOPE_MISMATCH")
    if str(claim["scope_id"]) != str(request["scope_id"]):
        raise ValueError("EVIDENCE_SCOPE_ID_MISMATCH")
    cutoff = str(request["forecast_cutoff"])
    assert_not_after_cutoff(str(claim["observed_at"]), cutoff)
    if str(claim.get("forecast_cutoff")) != cutoff:
        raise ValueError("EVIDENCE_CUTOFF_MISMATCH")
    reliability = float(claim.get("reliability", 0.0))
    freshness = float(claim.get("freshness", 0.0))
    if not (0.0 <= reliability <= 1.0 and 0.0 <= freshness <= 1.0):
        raise ValueError("EVIDENCE_QUALITY_OUT_OF_RANGE")
    expected_source = content_hash({
        "source_id": claim["source_id"], "url": claim["url"], "published_at": claim["published_at"]
    })
    if str(claim.get("source_hash")) != expected_source:
        raise ValueError("EVIDENCE_SOURCE_HASH_MISMATCH")
    expected_claim = content_hash({k: v for k, v in claim.items() if k != "claim_hash"})
    if str(claim.get("claim_hash")) != expected_claim:
        raise ValueError("EVIDENCE_CLAIM_HASH_MISMATCH")
    return claim


class FixtureProvider:
    """Synthetic contract evidence for tests only; never production-selectable."""
    production_capable = False

    def __init__(self, cutoff: str):
        self.cutoff = cutoff

    def resolve(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        scope = request["scope"]
        if scope == "SPORT":
            value = {"distribution_family": "development_fixture", "overtime": "INCLUDE_FULL_GAME"}
        elif scope == "EVENT":
            value = {"starters_known": True, "environment": "neutral_fixture"}
        elif scope == "TEAM":
            value = {"pace_multiplier": 1.0, "matchup_efficiency_multiplier": 1.0, "injury_cluster": False}
        elif scope == "PLAYER":
            value = {"status": "ACTIVE", "role": "starter_or_feature", "opportunity": {"support_n": 0},
                     "efficiency": {"support_n": 0}, "game_logs": [], "production_eligible": False}
        else:
            value = {"line_history": "fixture", "definition_verified": False, "production_eligible": False}
        claim = claim_record(
            source_id="FIXTURE_SYNTHETIC_V2", url="fixture://pillars/synthetic",
            published_at=self.cutoff, observed_at=self.cutoff, forecast_cutoff=self.cutoff,
            semantic_scope=scope, scope_id=str(request["scope_id"]), claim_type=str(request["need"]),
            claim_value=value, reliability=0.35, freshness=1.0,
        )
        claim["synthetic"] = True
        claim["production_eligible"] = False
        return [claim]


class FileProvider:
    """Production evidence provider reading one request-scoped JSON file per request."""
    production_capable = True

    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir

    def resolve(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        path = self.evidence_dir / f"{request['request_id']}.json"
        if not path.is_file():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        records = data if isinstance(data, list) else [data]
        return [_validate_claim(dict(rec), request) for rec in records if isinstance(rec, dict)]


def claims_by_scope(claims: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for claim in claims:
        key = (str(claim.get("semantic_scope") or ""), str(claim.get("scope_id") or ""))
        out.setdefault(key, []).append(claim)
    return out


def collect(requests: list[dict], provider: ResearchProvider) -> dict[str, Any]:
    claims: list[dict] = []
    missing: list[str] = []
    malformed: list[str] = []
    reused = 0
    seen_scope: set[tuple[str, str]] = set()
    for req in requests:
        key = (str(req["scope"]), str(req["scope_id"]))
        if key in seen_scope and req["scope"] != "MARKET":
            reused += 1
            continue
        seen_scope.add(key)
        try:
            got = provider.resolve(req)
        except (ValueError, TypeError, json.JSONDecodeError):
            malformed.append(req["request_id"])
            continue
        if not got:
            missing.append(req["request_id"])
        else:
            claims.extend(got)
    claims = dedupe(claims)
    fixture_claims = [c for c in claims if _is_fixture_claim(c)]
    production_claims = [c for c in claims if not _is_fixture_claim(c)]
    structural_complete = not missing and not malformed
    provider_capable = bool(getattr(provider, "production_capable", False))
    production_ready = structural_complete and provider_capable and not fixture_claims and bool(production_claims)
    return {
        "claims": claims, "missing": missing, "malformed": malformed, "requested": len(requests),
        "reused": reused, "complete": structural_complete, "production_ready": production_ready,
        "evidence_mode": "PRODUCTION" if production_ready else "SYNTHETIC_OR_INCOMPLETE",
        "fixture_claims": len(fixture_claims), "production_claims": len(production_claims),
    }
