"""Write canonical universal research artifacts plus legacy compatibility views."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dcm.ml.feature_store import persist_feature_store
from dcm.research.dependency_graph import build_research_dependency_graph
from dcm.research.entity_graph import build_entity_graph
from dcm.research.entity_packets import build_entity_packets
from dcm.research.evidence_graph import build_evidence_graph
from dcm.research.player_offer_set import build_player_offer_sets, player_offer_sets_document
from dcm.research.player_packet import build_packets_for_offer_sets, packets_document
from dcm.research.population import (
    build_legacy_research_population_manifest,
    build_research_population_manifest,
)
from dcm.research.staged import stage_research
from dcm.research.subject_offer_set import build_subject_offer_sets, subject_offer_sets_document
from dcm.research.universal_plan import build_universal_host_research_plan
from dcm.sports.common.contract import contract_registry_document


def _write(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def emit_offer_sets_and_manifest(
    dest: Path,
    rows: list[dict[str, Any]],
    *,
    planned: dict[str, Any] | None = None,
    cutoff: str = "",
    research_shadow: bool = False,
) -> dict[str, Any]:
    # Canonical universal grouping.
    subject_sets = build_subject_offer_sets(rows)
    subject_doc = _write(
        Path(dest) / "subject_offer_sets.json",
        subject_offer_sets_document(subject_sets),
    )
    manifest = build_research_population_manifest(
        rows, planned=planned, cutoff=cutoff, research_shadow=research_shadow
    )
    man_doc = _write(Path(dest) / "research_population_manifest.json", manifest)
    dependency_graph = _write(
        Path(dest) / "research_dependency_graph.json",
        build_research_dependency_graph(subject_sets, population=manifest),
    )
    universal_plan = _write(
        Path(dest) / "universal_host_research_plan.json",
        build_universal_host_research_plan(manifest, subject_offer_sets=subject_sets),
    )
    sport_plugin_contracts = _write(
        Path(dest) / "sport_plugin_contract_registry.json",
        contract_registry_document(validate_imports=True),
    )

    # Transitional compatibility artifacts for existing basketball/gridiron
    # research/model consumers. They are projections of the canonical layer.
    legacy_sets = build_player_offer_sets(rows)
    legacy_offer_doc = _write(
        Path(dest) / "player_offer_sets.json",
        player_offer_sets_document(legacy_sets),
    )
    legacy_manifest = _write(
        Path(dest) / "research_population_manifest_legacy.json",
        build_legacy_research_population_manifest(
            rows, planned=planned, cutoff=cutoff, research_shadow=research_shadow
        ),
    )
    return {
        "subjectOfferSets": subject_sets,
        "subjectOfferSetsDoc": subject_doc,
        "researchDependencyGraph": dependency_graph,
        "universalHostResearchPlan": universal_plan,
        "sportPluginContracts": sport_plugin_contracts,
        "offerSets": legacy_sets,
        "offerSetsDoc": legacy_offer_doc,
        "manifest": man_doc,
        "legacyManifest": legacy_manifest,
    }


def emit_packets_and_graph(
    dest: Path,
    *,
    offer_sets: list[dict[str, Any]],
    claims: list[dict[str, Any]] | None = None,
    cutoff: str = "",
    population: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packets = build_packets_for_offer_sets(offer_sets, claims=claims or [], as_of=cutoff)
    pack_doc = _write(Path(dest) / "player_research_packets.json", packets_document(packets))
    graph = build_evidence_graph(claims or [], offer_sets, packets)
    graph_doc = _write(Path(dest) / "evidence_graph.json", graph)
    entities = build_entity_packets(offer_sets, claims=claims or [], as_of=cutoff, population=population)
    _write(
        Path(dest) / "team_research_packets.json",
        {
            "schema": entities["schema"],
            **{
                k: entities[k]
                for k in ("teamPacketCount", "thinTeamPackets", "reuseRule", "teams", "contentHash")
                if k in entities
            },
        },
    )
    _write(
        Path(dest) / "event_research_packets.json",
        {
            "schema": "pillars_dcm.event_research_packets.v1",
            "eventPacketCount": entities["eventPacketCount"],
            "events": entities["events"],
            "contentHash": entities["contentHash"],
        },
    )
    _write(
        Path(dest) / "opponent_research_packets.json",
        {
            "schema": "pillars_dcm.opponent_research_packets.v1",
            "opponentPacketCount": entities["opponentPacketCount"],
            "opponents": entities["opponents"],
            "reuseRule": entities["reuseRule"],
            "contentHash": entities["contentHash"],
        },
    )
    _write(Path(dest) / "entity_research_packets.json", entities)
    entity_graph = build_entity_graph(
        offer_sets,
        team_packets=entities.get("teams") or [],
        event_packets=entities.get("events") or [],
        opponent_packets=entities.get("opponents") or [],
        player_packets=packets,
        population=population,
    )
    entity_doc = _write(Path(dest) / "entity_graph.json", entity_graph)
    staged = stage_research(packets, offer_sets)
    staged_doc = _write(Path(dest) / "staged_research.json", staged)
    feature_manifest = persist_feature_store(
        Path(dest),
        packets,
        offer_sets,
        cutoff,
        team_packets=entities.get("teams") or [],
        pass_b_packets=staged.get("packetsPassB") or [],
    )
    return {
        "packets": packets,
        "packetsDoc": pack_doc,
        "graph": graph_doc,
        "featureStore": feature_manifest,
        "entityPackets": entities,
        "entityGraph": entity_doc,
        "staged": staged_doc,
        "teamPackets": entities.get("teams") or [],
        "eventPackets": entities.get("events") or [],
        "opponentPackets": entities.get("opponents") or [],
    }


def emit_player_centric_research(
    dest: Path,
    rows: list[dict[str, Any]],
    *,
    planned: dict[str, Any] | None = None,
    claims: list[dict[str, Any]] | None = None,
    cutoff: str = "",
    research_shadow: bool = False,
) -> dict[str, Any]:
    """Backward-compatible entrypoint; universal artifacts are emitted first."""
    first = emit_offer_sets_and_manifest(
        dest, rows, planned=planned, cutoff=cutoff, research_shadow=research_shadow
    )
    second = emit_packets_and_graph(
        dest,
        offer_sets=first["offerSets"],
        claims=claims,
        cutoff=cutoff,
        population=first.get("manifest"),
    )
    return {**first, **second}
