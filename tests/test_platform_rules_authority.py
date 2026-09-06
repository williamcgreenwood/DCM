"""Platform rules authority must not hardcode verified=False without hashes."""

from __future__ import annotations

from dcm.cfb.rules import build_cfb_rules_snapshot
from dcm.platform.prizepicks.platform_rules_authority import (
    PLATFORM_RULES_AUTHORITY_HASH,
    PLATFORM_RULES_AUTHORITY_VERSION,
    collect_platform_rule_claim_hashes,
    resolve_platform_rules_authority,
)
from dcm.platform.prizepicks.settlement import SETTLEMENT_RULE_HASH


def test_packaged_authority_verifies_without_host_claims() -> None:
    resolved = resolve_platform_rules_authority([])
    assert resolved["platform_rules_verified"] is True
    assert PLATFORM_RULES_AUTHORITY_HASH in resolved["platform_source_hashes"]
    assert SETTLEMENT_RULE_HASH in resolved["platform_source_hashes"]
    assert resolved["authorityVersion"] == PLATFORM_RULES_AUTHORITY_VERSION
    snap = build_cfb_rules_snapshot(
        as_of="2026-09-06T15:30:00Z",
        platform_source_hashes=resolved["platform_source_hashes"],
        platform_rules_verified=resolved["platform_rules_verified"],
    )
    assert snap["productionEligible"] is True
    assert "PLATFORM_RULES_SNAPSHOT_REQUIRED" not in snap["blockers"]
    assert snap["platformSettlementAuthority"]["verified"] is True


def test_host_platform_rules_claim_hashes_merge() -> None:
    claims = [
        {
            "evidenceType": "PLATFORM_RULES",
            "sourceLabel": "PRIZEPICKS_PLATFORM_RULES",
            "source_hash": "abc123host",
            "entityRef": {"kind": "RULE", "id": "prizepicks:platform_settlement"},
        }
    ]
    hashes = collect_platform_rule_claim_hashes(claims)
    assert hashes == ("abc123host",)
    resolved = resolve_platform_rules_authority(claims)
    assert "abc123host" in resolved["platform_source_hashes"]
    assert PLATFORM_RULES_AUTHORITY_HASH in resolved["platform_source_hashes"]
    assert resolved["sourceStatus"] == "HOST_CLAIM_AND_PACKAGED_ADAPTER"


def test_non_platform_claims_ignored() -> None:
    claims = [{"evidenceType": "BOX_SCORE", "source_hash": "zzz", "sourceLabel": "ESPN"}]
    assert collect_platform_rule_claim_hashes(claims) == ()
    resolved = resolve_platform_rules_authority(claims)
    assert resolved["sourceStatus"] == "PACKAGED_ADAPTER_AUTHORITY"
