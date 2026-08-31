"""Host-native public contracts. Python remains the only probability engine."""
from __future__ import annotations

HOST_COMMANDS = (
    "doctor",
    "prepare",
    "next-research",
    "evidence-import",
    "coverage",
    "forecast",
    "report",
    "resume",
    "audit",
    "archive",
    "settle",
)

REQUIRED_PREPARE_ARTIFACTS = (
    "run_manifest.json",
    "board.json",
    "accounting.json",
    "subject_offer_sets.json",
    "research_population_manifest.json",
    "research_dependency_graph.json",
    "sport_plugin_contract_registry.json",
    "evidence_coverage.json",
    "host_state.json",
)

HOST_STATE_SCHEMA = "pillars_dcm.host_state.v1"
CHAT_RESULT_SCHEMA = "pillars_dcm.chat_result.v1"
OBSERVATION_SCHEMA = "pillars_dcm.host_observation.v1"
