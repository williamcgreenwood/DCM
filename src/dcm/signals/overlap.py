"""Semantic identity and overlap grouping for signal operators."""
from __future__ import annotations

import hashlib
import json

from dcm.signals.contracts import SignalOperatorSpec


def semantic_signature(spec: SignalOperatorSpec) -> str:
    payload = {
        "family": spec.family.strip().lower(),
        "stage": spec.stage.value,
        "sports": sorted(set(spec.sports)),
        "competitions": sorted(set(spec.competitions)),
        "markets": sorted(set(spec.market_definitions)),
        "scopes": sorted(set(spec.semantic_scopes)),
        "inputs": sorted(
            (v.name.strip().lower(), v.unit.strip().lower(), v.dimension.strip().lower(), v.temporal_class)
            for v in spec.required_inputs
        ),
        "outputs": sorted(
            (v.name.strip().lower(), v.unit.strip().lower(), v.dimension.strip().lower())
            for v in spec.outputs
        ),
        "transformation": spec.transformation_id.strip().lower(),
        "evidenceLineageClass": sorted(
            (v.claim_type.strip().upper(), v.freshness_policy.strip().lower())
            for v in spec.evidence_requirements
        ),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def resolved_overlap_group(spec: SignalOperatorSpec, signature: str) -> str:
    return spec.overlap_group.strip() or f"SEMANTIC:{signature[:16]}"
