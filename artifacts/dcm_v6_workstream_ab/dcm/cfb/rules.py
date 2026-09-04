"""Separated CFB statistical and platform-settlement authority snapshot.

The model may use a statistical ledger without treating it as proof of a
particular platform's administrative or payout rules.  Until a dated,
authoritative platform snapshot is supplied, this artifact is explicitly
non-production and blocks production-root certification.
"""
from __future__ import annotations

from typing import Any, Iterable

from dcm.contracts.hashes import content_hash
from dcm.cfb.markets import ACTIVE_CFB_MARKETS, MARKET_CONTRACTS
from dcm.platform.prizepicks.settlement import SETTLEMENT_RULE_HASH, SETTLEMENT_RULE_VERSION


RULES_SCHEMA = "pillars_dcm.cfb_authority_rules_snapshot.v1"
SETTLEMENT_STATES = (
    "MORE", "LESS", "TIE", "DNP", "REBOOT", "VOID", "POSTPONED", "CORRECTED",
    "CANCELLED", "UNKNOWN_PLATFORM_RULE",
)


def build_cfb_rules_snapshot(
    *,
    as_of: str,
    statistical_source_hashes: Iterable[str] = (),
    platform_source_hashes: Iterable[str] = (),
    platform_rules_verified: bool = False,
) -> dict[str, Any]:
    mappings = []
    for market in ACTIVE_CFB_MARKETS:
        contract = dict(MARKET_CONTRACTS.get(market) or {})
        mappings.append({
            "market": market,
            "unit": contract.get("unit"),
            "period": "FULL_GAME",
            "overtime": "INCLUDE_FULL_GAME_IF_OFFICIAL_STAT_VALUE_INCLUDES_OVERTIME",
            "directionStates": ["MORE", "LESS"],
            "pushPolicy": contract.get("push"),
            "statisticalIdentity": contract.get("settlement"),
            "platformSettlementStateSet": list(SETTLEMENT_STATES),
            "verified": bool(platform_rules_verified),
        })
    body: dict[str, Any] = {
        "schema": RULES_SCHEMA,
        "snapshotAsOf": str(as_of),
        "statisticalAuthority": {
            "authorityId": "CFB_STATISTICAL_LEDGER",
            "sourceHashes": sorted({str(value) for value in statistical_source_hashes if value}),
            "role": "official/statistical facts and primitive stat identity",
            "mayAuthorize": ["statistical_value", "event_identity", "participant_identity"],
            "mayNotAuthorize": ["platform_payout", "administrative_void", "reboot", "leaderboard_return"],
        },
        "platformSettlementAuthority": {
            "authorityId": "PRIZEPICKS_PLATFORM_RULES",
            "sourceHashes": sorted({str(value) for value in platform_source_hashes if value}),
            "adapterVersion": SETTLEMENT_RULE_VERSION,
            "adapterHash": SETTLEMENT_RULE_HASH,
            "role": "administrative and economic settlement semantics",
            "verified": bool(platform_rules_verified and platform_source_hashes),
            "mayAuthorize": ["MORE", "LESS", "TIE", "DNP", "REBOOT", "VOID", "POSTPONED", "CORRECTED"],
        },
        "marketMappings": mappings,
        "activeMarketCount": len(mappings),
        "allActiveMarketsMapped": len(mappings) == len(ACTIVE_CFB_MARKETS),
        "sourceStatus": "VERIFIED" if platform_rules_verified and platform_source_hashes else "EXTERNAL_RULES_REQUIRED",
        "productionEligible": bool(platform_rules_verified and platform_source_hashes and mappings),
        "blockers": [] if platform_rules_verified and platform_source_hashes else ["PLATFORM_RULES_SNAPSHOT_REQUIRED"],
        "rule": "stats_authority_is_distinct_from_platform_settlement_authority",
    }
    body["contentHash"] = content_hash({key: value for key, value in body.items() if key != "contentHash"})
    return body


__all__ = ["RULES_SCHEMA", "SETTLEMENT_STATES", "build_cfb_rules_snapshot"]
