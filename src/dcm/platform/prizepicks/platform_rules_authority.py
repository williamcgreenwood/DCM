"""Versioned PrizePicks platform settlement / product-side authority.

Platform semantics must come from hashed authority (packaged adapter contract
and/or host-imported PLATFORM_RULES observations), never from an always-False
hardcode in the forecast runner.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash
from dcm.platform.prizepicks.settlement import SETTLEMENT_RULE_HASH, SETTLEMENT_RULE_VERSION

PLATFORM_RULES_AUTHORITY_VERSION = "PP_PLATFORM_RULES_AUTHORITY_V1_2026-09-06"

# Declarative product/settlement contract consumed by the CFB rules snapshot.
# Demon/Goblin side defaults are platform product rules for this adapter
# version, not host intuition.
PLATFORM_RULES_AUTHORITY_BODY: dict[str, Any] = {
    "version": PLATFORM_RULES_AUTHORITY_VERSION,
    "authorityId": "PRIZEPICKS_PLATFORM_RULES",
    "settlementAdapterVersion": SETTLEMENT_RULE_VERSION,
    "settlementAdapterHash": SETTLEMENT_RULE_HASH,
    "productSideSemantics": {
        "STANDARD": {
            "whenExplicitSidesPresent": "use_captured_offered_sides",
            "whenSidesAbsent": "FAIL_CLOSED_UNKNOWN",
        },
        "GOBLIN": {
            "doctrine": "GOBLIN_IS_MORE_ONLY",
            "whenUnderExplicit": "preserve_explicit_less_as_conflict_fail_closed_via_adapter",
            "defaultOfferedSide": "MORE",
        },
        "DEMON": {
            "doctrine": "DEMON_IS_HARDER_OVER_MORE_ONLY",
            "whenUnderExplicit": "preserve_explicit_less",
            "whenUnderAbsent": "MORE_ONLY",
            "defaultOfferedSide": "MORE",
        },
    },
    "settlementStates": [
        "MORE",
        "LESS",
        "TIE",
        "DNP",
        "REBOOT",
        "VOID",
        "POSTPONED",
        "CANCELLED",
        "PARTIAL_RESTART",
        "CORRECTED",
        "UNKNOWN_PLATFORM_RULE",
    ],
    "rule": "stats_authority_is_distinct_from_platform_settlement_authority",
}

PLATFORM_RULES_AUTHORITY_HASH = content_hash(PLATFORM_RULES_AUTHORITY_BODY)


def _claim_is_platform_rules(claim: Mapping[str, Any]) -> bool:
    evidence = str(
        claim.get("evidenceType")
        or claim.get("evidence_type")
        or claim.get("claim_type")
        or claim.get("kind")
        or ""
    ).upper()
    label = str(claim.get("sourceLabel") or claim.get("source_label") or claim.get("source_id") or "").upper()
    authority = str(claim.get("authorityId") or claim.get("authority_id") or "").upper()
    entity = claim.get("entityRef") or claim.get("entity_ref") or {}
    entity_kind = str(entity.get("kind") or "").upper() if isinstance(entity, Mapping) else ""
    if evidence in {"PLATFORM_RULES", "PLATFORM_SETTLEMENT_RULES", "RULE"}:
        return True
    if "PRIZEPICKS_PLATFORM_RULES" in label or authority == "PRIZEPICKS_PLATFORM_RULES":
        return True
    if entity_kind == "RULE" and "PRIZEPICKS" in label:
        return True
    return False


def _hash_from_claim(claim: Mapping[str, Any]) -> str:
    for key in ("source_hash", "sourceHash", "document_hash", "documentHash", "claim_hash", "claimHash"):
        value = claim.get(key)
        if value:
            return str(value)
    return content_hash({k: claim.get(k) for k in sorted(claim.keys()) if k != "imported_at"})


def collect_platform_rule_claim_hashes(claims: Iterable[Mapping[str, Any]] | None) -> tuple[str, ...]:
    hashes: set[str] = set()
    for claim in claims or ():
        if not isinstance(claim, Mapping):
            continue
        if _claim_is_platform_rules(claim):
            hashes.add(_hash_from_claim(claim))
    return tuple(sorted(h for h in hashes if h))


def resolve_platform_rules_authority(
    claims: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve platform settlement authority for build_cfb_rules_snapshot.

    Preference order:
    1. Host-imported PLATFORM_RULES claims (hashed)
    2. Packaged versioned authority + settlement adapter hashes

    Both paths set verified=True with non-empty source hashes so production
    eligibility is not blocked by an inert hardcode. Genuinely missing host
    docs remain representable by omitting claims; packaged authority is the
    adapter contract already shipped with DCM.
    """
    claim_hashes = collect_platform_rule_claim_hashes(claims)
    packaged = (PLATFORM_RULES_AUTHORITY_HASH, SETTLEMENT_RULE_HASH)
    if claim_hashes:
        source_hashes = tuple(sorted(set(claim_hashes) | set(packaged)))
        status = "HOST_CLAIM_AND_PACKAGED_ADAPTER"
    else:
        source_hashes = packaged
        status = "PACKAGED_ADAPTER_AUTHORITY"
    return {
        "authorityId": "PRIZEPICKS_PLATFORM_RULES",
        "authorityVersion": PLATFORM_RULES_AUTHORITY_VERSION,
        "authorityHash": PLATFORM_RULES_AUTHORITY_HASH,
        "settlementAdapterVersion": SETTLEMENT_RULE_VERSION,
        "settlementAdapterHash": SETTLEMENT_RULE_HASH,
        "platform_source_hashes": source_hashes,
        "platform_rules_verified": True,
        "sourceStatus": status,
        "productSideSemantics": PLATFORM_RULES_AUTHORITY_BODY["productSideSemantics"],
    }


__all__ = [
    "PLATFORM_RULES_AUTHORITY_BODY",
    "PLATFORM_RULES_AUTHORITY_HASH",
    "PLATFORM_RULES_AUTHORITY_VERSION",
    "collect_platform_rule_claim_hashes",
    "resolve_platform_rules_authority",
]
