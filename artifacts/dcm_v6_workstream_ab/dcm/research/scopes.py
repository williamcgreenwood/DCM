"""Canonical research scopes and adapter-only PLAYER/TEAM aliases.

Universal core:
  SPORT → COMPETITION → EVENT → AFFILIATION / SUBJECT / COUNTERPARTY / ENVIRONMENT
  → MARKET_DEFINITION → OFFER

PLAYER and TEAM are compatibility aliases used only inside source/sport adapters
and claim lookup. Canonical planner/provider requests emit the universal names.
"""
from __future__ import annotations

from typing import Any, Iterable

CANONICAL_SCOPES = (
    "SPORT",
    "COMPETITION",
    "EVENT",
    "AFFILIATION",
    "SUBJECT",
    "COUNTERPARTY",
    "ENVIRONMENT",
    "MARKET_DEFINITION",
    "OFFER",
)

# Adapter/compatibility aliases. Never emitted by plan_research.
ADAPTER_SCOPES = ("PLAYER", "TEAM", "MARKET")

SCOPE_ORDER = CANONICAL_SCOPES
SCOPE_RANK = {name: i for i, name in enumerate(SCOPE_ORDER)}

# Lookup aliases: a consumer asking for left also accepts right.
_LOOKUP_ALIASES: dict[str, tuple[str, ...]] = {
    "SUBJECT": ("SUBJECT", "PLAYER"),
    "PLAYER": ("SUBJECT", "PLAYER"),
    "AFFILIATION": ("AFFILIATION", "TEAM"),
    "TEAM": ("AFFILIATION", "TEAM", "COUNTERPARTY"),
    "COUNTERPARTY": ("COUNTERPARTY", "TEAM"),
    "ENVIRONMENT": ("ENVIRONMENT",),
    "EVENT": ("EVENT",),
    "SPORT": ("SPORT",),
    "COMPETITION": ("COMPETITION",),
    "MARKET_DEFINITION": ("MARKET_DEFINITION",),
    "OFFER": ("OFFER",),
    "MARKET": ("MARKET", "MARKET_DEFINITION", "OFFER"),
}

# Planner/provider canonicalization: adapter names map onto universal names.
TO_CANONICAL = {
    "PLAYER": "SUBJECT",
    "TEAM": "AFFILIATION",
    "MARKET": "MARKET_DEFINITION",
}

# Fixture/provider payload families.
SUBJECT_SCOPES = frozenset({"SUBJECT", "PLAYER"})
AFFILIATION_SCOPES = frozenset({"AFFILIATION", "TEAM"})
COUNTERPARTY_SCOPES = frozenset({"COUNTERPARTY"})
ENVIRONMENT_SCOPES = frozenset({"ENVIRONMENT"})


def canonical_scope(scope: str) -> str:
    raw = str(scope or "").strip().upper()
    return TO_CANONICAL.get(raw, raw)


def lookup_scopes(scope: str) -> tuple[str, ...]:
    raw = str(scope or "").strip().upper()
    return _LOOKUP_ALIASES.get(raw, (raw,) if raw else tuple())


def scopes_match(left: str, right: str) -> bool:
    return str(right or "").strip().upper() in lookup_scopes(left)


def claim_matches(claim: dict[str, Any], scope: str, scope_id: str) -> bool:
    if str(claim.get("scope_id") or "") != str(scope_id):
        return False
    return scopes_match(scope, str(claim.get("semantic_scope") or ""))


def claims_for(claims: Iterable[dict[str, Any]], scope: str, scope_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for claim in claims or []:
        if isinstance(claim, dict) and claim_matches(claim, scope, scope_id):
            out.append(claim)
    return out


def is_canonical_scope(scope: str) -> bool:
    return str(scope or "").strip().upper() in CANONICAL_SCOPES
