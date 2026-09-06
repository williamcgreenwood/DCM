"""Versioned SourceCatalog / SourceAdapter capability registry.

The catalog is data. Adapters remain the parsers. Production must not assume
ChatGPT can log into a site; authenticated sources are optional capabilities.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.scopes import canonical_scope

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "source_catalog.json"
CATALOG_SCHEMA = "pillars_dcm.source_catalog.v1"


def _load_raw(path: Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else CATALOG_PATH
    if not target.is_file():
        raise FileNotFoundError(f"SOURCE_CATALOG_MISSING:{target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("SOURCE_CATALOG_INVALID")
    return data


@lru_cache(maxsize=4)
def load_source_catalog(path: str | None = None) -> dict[str, Any]:
    raw = _load_raw(Path(path) if path else None)
    sources = [s for s in (raw.get("sources") or []) if isinstance(s, dict)]
    body = {
        "schema": str(raw.get("schema") or CATALOG_SCHEMA),
        "catalogVersion": str(raw.get("catalogVersion") or ""),
        "priorityOrder": list(raw.get("priorityOrder") or []),
        "notes": list(raw.get("notes") or []),
        "sourceCount": len(sources),
        "sources": sources,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def sources_for(
    *,
    sport: str | None = None,
    competition: str | None = None,
    entity_kind: str | None = None,
    field: str | None = None,
    catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cat = catalog or load_source_catalog()
    kind = canonical_scope(entity_kind) if entity_kind else None
    sport_l = str(sport or "").strip().lower()
    comp_u = str(competition or "").strip().upper()
    field_l = str(field or "").strip().lower()
    out: list[dict[str, Any]] = []
    for src in cat.get("sources") or []:
        sports = [str(x).lower() for x in (src.get("sports") or [])]
        comps = [str(x).upper() for x in (src.get("competitions") or [])]
        kinds = [canonical_scope(x) for x in (src.get("entityKinds") or [])]
        fields = [str(x).lower() for x in (src.get("fields") or [])]
        if sport_l and sports and "*" not in sports and sport_l not in sports:
            continue
        if comp_u and comps and "*" not in comps and comp_u not in comps:
            continue
        if kind and kinds and "*" not in kinds and kind not in kinds:
            continue
        if field_l and fields and "*" not in fields and field_l not in fields:
            continue
        out.append(src)
    order = {name: i for i, name in enumerate(cat.get("priorityOrder") or [])}
    out.sort(
        key=lambda s: (
            int(order.get(str(s.get("tier") or ""), 99)),
            float(s.get("cost") or 9.0),
            str(s.get("sourceId") or ""),
        )
    )
    return out


def estimated_cost(source_id: str, catalog: dict[str, Any] | None = None) -> float:
    cat = catalog or load_source_catalog()
    for src in cat.get("sources") or []:
        if str(src.get("sourceId") or "") == str(source_id):
            try:
                return float(src.get("cost") or 1.0)
            except (TypeError, ValueError):
                return 1.0
    return 3.0


def catalog_summary(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    cat = catalog or load_source_catalog()
    return {
        "schema": cat.get("schema"),
        "catalogVersion": cat.get("catalogVersion"),
        "sourceCount": cat.get("sourceCount"),
        "contentHash": cat.get("contentHash"),
        "sourceIds": [str(s.get("sourceId") or "") for s in (cat.get("sources") or [])],
        "authenticatedRequired": False,
        "secretsInRepo": False,
        "liveFetchDefault": False,
    }


def source_health_seeds(
    *,
    sport: str,
    competition: str,
    catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Derive health-router seeds from the versioned capability catalog.

    The catalog is the single source for source IDs, adapters, costs, and
    fallbacks. Claim authority is deliberately conservative and explicit here:
    source availability does not turn a discovery page into an authoritative
    injury, depth-chart, or statistical claim.
    """
    authority = {
        "cfb_official_athletics": {"EVENT": 100, "AFFILIATION": 90, "SUBJECT": 80, "COUNTERPARTY": 80},
        "college_football_reference": {"SUBJECT": 85, "AFFILIATION": 80, "EVENT": 60},
        "open_meteo_weather": {"ENVIRONMENT": 90, "EVENT": 50},
        "espn_status": {"SUBJECT": 70, "EVENT": 75, "ENVIRONMENT": 40},
        "generic_web_search": {"SUBJECT": 20, "EVENT": 20, "AFFILIATION": 20, "COUNTERPARTY": 20, "ENVIRONMENT": 20},
    }
    seeds: list[dict[str, Any]] = []
    for source in sources_for(sport=sport, competition=competition, catalog=catalog):
        sid = str(source.get("sourceId") or "")
        if not sid or sid == "prizepicks_offer":
            continue
        seeds.append({
            "sourceId": sid,
            "catalogSourceId": sid,
            "adapter": source.get("adapterId") or sid,
            "domain": source.get("domain") or "",
            "authorityByClaimType": authority.get(sid, {}),
            "sports": [competition],
            "fields": list(source.get("fields") or []),
            "cost": source.get("cost") or 1.0,
            "expectedFreshness": 0.9 if str(source.get("expectedFreshness") or "").startswith("same_event") else 0.7,
            "rateLimit": source.get("rateLimit"),
            "knownFailureModes": list(source.get("knownFailureModes") or []),
            "fallbackSourceIds": list(source.get("fallbackSourceIds") or []),
        })
    return seeds
