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
    "CANCELLED", "PARTIAL_RESTART", "UNKNOWN_PLATFORM_RULE",
)

_FIELD_SEMANTICS: dict[str, dict[str, Any]] = {
    "pass_att": {
        "unit": "count",
        "definition": "official forward pass attempts; sacks and scrambles are not pass attempts",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "pass_cmp": {
        "unit": "count",
        "definition": "completed forward passes credited to the passer",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "pass_yds": {
        "unit": "yards",
        "definition": "official passing yards credited to the passer",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "pass_td": {
        "unit": "count",
        "definition": "passing touchdowns credited to the passer",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "interceptions": {
        "unit": "count",
        "definition": "interceptions thrown by the passer",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "rush_att": {
        "unit": "count",
        "definition": "official rushing attempts, including the registered scramble component",
        "identity": "rush_att = designed_rush_att + scramble_att",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "rush_yds": {
        "unit": "yards",
        "definition": "official rushing yards, including the registered scramble component",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "rush_td": {
        "unit": "count",
        "definition": "rushing touchdowns credited to the rusher",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "targets": {
        "unit": "count",
        "definition": "official pass targets credited to the receiver when available",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "receptions": {
        "unit": "count",
        "definition": "completed receptions credited to the receiver",
        "identity": "receptions <= targets when both are recorded",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "rec_yds": {
        "unit": "yards",
        "definition": "official receiving yards credited to the receiver",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "rec_td": {
        "unit": "count",
        "definition": "receiving touchdowns credited to the receiver",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "dropbacks": {
        "unit": "count",
        "definition": "registered quarterback dropbacks",
        "identity": "dropbacks = pass_att + sacks_taken + scramble_att",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "sacks_taken": {
        "unit": "count",
        "definition": "quarterback sacks taken; not a pass attempt",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "scramble_att": {
        "unit": "count",
        "definition": "quarterback scramble attempts",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "fg_made": {
        "unit": "count",
        "definition": "field goals made by the kicker",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "xp_made": {
        "unit": "count",
        "definition": "extra points made by the kicker",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
    "kicking_pts": {
        "unit": "points",
        "definition": "official kicking points credited to the kicker",
        "authority": "CFB_STATISTICAL_LEDGER",
    },
}

_IDENTITY_RULES = {
    "event": "canonical CFB event/game identifier from the statistical ledger; label text is not an identifier",
    "player": "canonical player identifier from the ledger; display name is never a join key",
    "team": "canonical affiliation/team identifier from the ledger; abbreviation is display data",
    "opponent": "canonical opposing affiliation within the same event",
}


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
        source_fields = sorted({
            str(field) for field in (*contract.get("opportunity", ()), *contract.get("efficiency", ()))
            if str(field) in _FIELD_SEMANTICS
        })
        mappings.append({
            "market": market,
            "unit": contract.get("unit"),
            "sourceFields": source_fields,
            "fieldSemantics": {field: _FIELD_SEMANTICS[field] for field in source_fields},
            "period": "FULL_GAME",
            "overtime": "INCLUDE_FULL_GAME_IF_OFFICIAL_STAT_VALUE_INCLUDES_OVERTIME",
            "directionStates": ["MORE", "LESS"],
            "pushPolicy": contract.get("push"),
            "statisticalIdentity": contract.get("settlement"),
            "platformSettlementStateSet": list(SETTLEMENT_STATES),
            "settlementOutcomes": {
                "MORE": "official value greater than line",
                "LESS": "official value less than line",
                "TIE": "official value exactly equals line; platform tie policy applies",
                "DNP": "platform administrative state; never inferred from absent statistics",
                "REBOOT": "platform administrative state; requires platform rule snapshot",
                "VOID": "platform administrative state; requires platform rule snapshot",
                "POSTPONED": "event status; settlement deferred or platform-defined",
                "CANCELLED": "event status; requires platform rule snapshot",
                "PARTIAL_RESTART": "game restart/partial-game handling; requires platform rule snapshot",
                "CORRECTED": "official correction recorded as a new immutable observation",
            },
            "identityRules": dict(_IDENTITY_RULES),
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
            "verified": bool(statistical_source_hashes),
            "sourceStatus": "HASHED_INPUTS_PRESENT" if statistical_source_hashes else "EXTERNAL_STAT_SOURCE_REQUIRED",
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
        "globalFieldSemantics": {key: dict(value) for key, value in sorted(_FIELD_SEMANTICS.items())},
        "identityRules": dict(_IDENTITY_RULES),
        "jurisdictionPolicy": "platform/jurisdiction-specific administrative rules require a dated verified platform snapshot",
        "activeMarketCount": len(mappings),
        "allActiveMarketsMapped": len(mappings) == len(ACTIVE_CFB_MARKETS),
        "sourceStatus": "VERIFIED" if platform_rules_verified and platform_source_hashes else "EXTERNAL_RULES_REQUIRED",
        "statisticalSourceStatus": "HASHED_INPUTS_PRESENT" if statistical_source_hashes else "EXTERNAL_STAT_SOURCE_REQUIRED",
        "productionEligible": bool(platform_rules_verified and platform_source_hashes and mappings),
        "blockers": [] if platform_rules_verified and platform_source_hashes else ["PLATFORM_RULES_SNAPSHOT_REQUIRED"],
        "rule": "stats_authority_is_distinct_from_platform_settlement_authority",
    }
    body["contentHash"] = content_hash({key: value for key, value in body.items() if key != "contentHash"})
    return body


__all__ = ["RULES_SCHEMA", "SETTLEMENT_STATES", "build_cfb_rules_snapshot"]
