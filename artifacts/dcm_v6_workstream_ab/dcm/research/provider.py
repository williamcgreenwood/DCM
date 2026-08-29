"""ResearchProvider boundary. Python has no unrestricted net; the operator fills evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from dcm.research.claims import claim_record, dedupe


class ResearchProvider(Protocol):
    def resolve(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class FixtureProvider:
    """Sanitized contract evidence. Passing this does not prove live-stat research."""

    def __init__(self, cutoff: str):
        self.cutoff = cutoff

    def resolve(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        scope = request["scope"]
        value: dict[str, Any]
        if scope == "SPORT":
            value = {"distribution_family": "count_or_yards", "overtime": "INCLUDE_FULL_GAME"}
        elif scope == "EVENT":
            value = {"starters_known": True, "environment": "neutral_fixture"}
        elif scope == "TEAM":
            value = {"pace": 1.0, "injury_cluster": False}
        elif scope == "PLAYER":
            value = {
                "status": "ACTIVE",
                "opportunity_index": 1.0,
                "efficiency_index": 1.0,
                "role": "starter_or_feature",
            }
        else:
            value = {"line_history": "fixture", "definition_verified": True}
        return [
            claim_record(
                source_id="FIXTURE_SYNTHETIC_V1",
                url="fixture://pillars/synthetic",
                published_at=self.cutoff,
                observed_at=self.cutoff,
                forecast_cutoff=self.cutoff,
                semantic_scope=scope,
                scope_id=str(request["scope_id"]),
                claim_type=str(request["need"]),
                claim_value=value,
                reliability=0.55 if scope in {"PLAYER", "MARKET"} else 0.7,
                freshness=1.0,
            )
        ]


class FileProvider:
    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir

    def resolve(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        path = self.evidence_dir / f"{request['request_id']}.json"
        if not path.is_file():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else [data]


def collect(requests: list[dict], provider: ResearchProvider) -> dict[str, Any]:
    claims: list[dict] = []
    missing: list[str] = []
    reused = 0
    seen_scope: set[tuple[str, str]] = set()
    for req in requests:
        key = (req["scope"], str(req["scope_id"]))
        if key in seen_scope and req["scope"] != "MARKET":
            reused += 1
            continue
        seen_scope.add(key)
        got = provider.resolve(req)
        if not got:
            missing.append(req["request_id"])
        else:
            claims.extend(got)
    claims = dedupe(claims)
    return {
        "claims": claims,
        "missing": missing,
        "requested": len(requests),
        "reused": reused,
        "complete": len(missing) == 0,
    }
