"""EvidenceGraph: typed nodes/edges and selection → source URL trace."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.research.claims import claim_record
from dcm.research.evidence_graph import NODE_TYPES, build_evidence_graph, trace_selection
from dcm.research.player_offer_set import build_player_offer_sets
from dcm.research.player_packet import build_packets_for_offer_sets
from dcm.runner import run_dcm


CUTOFF = "2026-08-30T12:00:00Z"
PAIGE_URL = "https://www.basketball-reference.com/wnba/players/b/bueckpa01w/gamelog/2026/"


def test_graph_trace_from_fake_selection_to_claim_url():
    claim = claim_record(
        source_id="BASKETBALL_REFERENCE",
        url=PAIGE_URL,
        published_at="2026-08-29T00:00:00Z",
        observed_at="2026-08-29T01:00:00Z",
        forecast_cutoff=CUTOFF,
        semantic_scope="PLAYER",
        scope_id="PAIGE",
        claim_type="game_logs",
        claim_value={"status": "ACTIVE", "role": "starter", "game_logs": [{"minutes": 32, "pts": 21}] * 3,
                     "opportunity": {"support_n": 3}, "efficiency": {"support_n": 3}},
        reliability=0.8,
        freshness=0.9,
    )
    rows = [{
        "projectionId": "pp-pts",
        "playerId": "PAIGE",
        "playerName": "Paige Bueckers",
        "sportFamily": "basketball",
        "league": "WNBA",
        "team": "DAL",
        "teamId": "DAL",
        "opponent": "CON",
        "eventId": "E1",
        "eventLabel": "DAL vs CON",
        "eventStartTime": "2026-08-30T21:30:00Z",
        "market": "pts",
        "line": 21.5,
        "modifier": "STANDARD",
        "offeredHigher": True,
        "offeredLower": True,
        "boardId": "FULL_GAME",
    }]
    sets = build_player_offer_sets(rows)
    packets = build_packets_for_offer_sets(sets, claims=[claim], as_of=CUTOFF)
    graph = build_evidence_graph([claim], sets, packets)
    assert graph["schema"] == "pillars_dcm.evidence_graph.v1"
    assert graph["contentHash"]
    types = {n["type"] for n in graph["nodes"]}
    for needed in NODE_TYPES:
        # NormalizedStat present because packet has logs
        assert needed in types, needed
    edge_types = {e["type"] for e in graph["edges"]}
    assert "supports" in edge_types
    assert "derived_from" in edge_types
    assert "applies_to" in edge_types
    traced = trace_selection(graph, {"projectionId": "pp-pts"})
    assert traced["resolved"] is True
    assert traced["sourceUrl"] == PAIGE_URL
    assert "Offer" in traced["nodeTypes"]
    assert "SourceDocument" in traced["nodeTypes"]


def test_fixture_runner_writes_graph_structures(tmp_path: Path):
    result = run_dcm(
        input_path=None,
        forecast_cutoff="2026-08-29T00:00:00Z",
        output_root=tmp_path,
        synthetic=True,
        research="fixture",
    )
    dest = Path(result["dest"])
    for name in (
        "player_offer_sets.json",
        "research_population_manifest.json",
        "player_research_packets.json",
        "evidence_graph.json",
    ):
        assert (dest / name).is_file(), name
    graph = json.loads((dest / "evidence_graph.json").read_text())
    assert graph["nodeCount"] >= 1
    assert "contentHash" in graph
    packets = json.loads((dest / "player_research_packets.json").read_text())
    assert packets["packetCount"] >= 1
