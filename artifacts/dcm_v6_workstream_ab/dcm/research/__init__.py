"""Public research namespace with lazy exports.

Research packets import model adapters and the model package imports feature
metadata.  Keeping this convenience namespace lazy removes a package-level
cycle without changing callers such as ``from dcm.research import collect``.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "claim_record": ("dcm.research.claims", "claim_record"),
    "dedupe": ("dcm.research.claims", "dedupe"),
    "build_entity_graph": ("dcm.research.entity_graph", "build_entity_graph"),
    "build_entity_packets": ("dcm.research.entity_packets", "build_entity_packets"),
    "build_event_research_packet": ("dcm.research.entity_packets", "build_event_research_packet"),
    "build_opponent_research_packet": ("dcm.research.entity_packets", "build_opponent_research_packet"),
    "build_team_research_packet": ("dcm.research.entity_packets", "build_team_research_packet"),
    "build_evidence_graph": ("dcm.research.evidence_graph", "build_evidence_graph"),
    "attach_runtime_lineage": ("dcm.research.evidence_graph", "attach_runtime_lineage"),
    "trace_selection": ("dcm.research.evidence_graph", "trace_selection"),
    "trace_runtime_lineage": ("dcm.research.evidence_graph", "trace_runtime_lineage"),
    "build_player_offer_sets": ("dcm.research.player_offer_set", "build_player_offer_sets"),
    "build_player_research_packet": ("dcm.research.player_packet", "build_player_research_packet"),
    "build_research_population_manifest": ("dcm.research.population", "build_research_population_manifest"),
    "BundleProvider": ("dcm.research.provider", "BundleProvider"),
    "FileProvider": ("dcm.research.provider", "FileProvider"),
    "FixtureProvider": ("dcm.research.provider", "FixtureProvider"),
    "collect": ("dcm.research.provider", "collect"),
    "write_bundle": ("dcm.research.provider", "write_bundle"),
    "build_requests": ("dcm.research.requests", "build_requests"),
    "TemporalLeakError": ("dcm.research.temporal", "TemporalLeakError"),
    "assert_not_after_cutoff": ("dcm.research.temporal", "assert_not_after_cutoff"),
    "filter_claims": ("dcm.research.temporal", "filter_claims"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module = import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value
