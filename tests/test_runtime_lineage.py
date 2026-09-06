"""Feature → State → Parameter → Simulation → Selection → Settlement lineage."""
from __future__ import annotations

from pathlib import Path

from dcm.model.participation import ParticipationModel
from dcm.research.claims import claim_record
from dcm.research.evidence_graph import (
    attach_runtime_lineage,
    build_evidence_graph,
    trace_runtime_lineage,
)
from dcm.research.player_offer_set import build_player_offer_sets
from dcm.research.player_packet import build_packets_for_offer_sets
from dcm.runtime.dag import Dag


CUTOFF = "2026-08-30T12:00:00Z"


def _claim():
    return claim_record(
        source_id="BASKETBALL_REFERENCE",
        url="https://www.basketball-reference.com/wnba/players/b/bueckpa01w/gamelog/2026/",
        published_at="2026-08-29T00:00:00Z",
        observed_at="2026-08-29T01:00:00Z",
        forecast_cutoff=CUTOFF,
        semantic_scope="SUBJECT",
        scope_id="PAIGE",
        claim_type="HISTORICAL_PERFORMANCE",
        claim_value={
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": [{"minutes": 32, "pts": 21, "fga": 14, "date": "2026-08-20"}] * 3,
            "opportunity": {"support_n": 3},
            "efficiency": {"support_n": 3},
        },
        reliability=0.8,
        freshness=0.9,
    )


def test_runtime_lineage_attaches_feature_parameter_simulation_selection():
    claim = _claim()
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
    snap_hash = "snap" + "0" * 60
    runtime = attach_runtime_lineage(
        graph,
        features=[{
            "entity": "PAIGE",
            "eventId": "E1",
            "featureName": "minutes_l5",
            "family": "PARTICIPATION",
            "asOf": CUTOFF,
            "sourceHashes": [claim["source_hash"]],
            "claimHashes": [claim["claim_hash"]],
        }],
        snapshots=[{
            "playerId": "PAIGE",
            "eventId": "E1",
            "market": "pts",
            "parameter_snapshot_hash": snap_hash,
            "evidence_hashes": [claim["claim_hash"]],
            "participation": {"unit": "minutes", "mean": 31.0, "source": "LOGS", "inputHash": "part1"},
            "parameters": {"opportunityInputHash": "opp1", "efficiencyInputHash": "eff1"},
            "role_epoch": {"support_n": 3},
            "layers": {"lineage": {"opportunityInputHash": "opp1", "efficiencyInputHash": "eff1"}},
        }],
        evaluations=[{
            "row": rows[0],
            "projectionId": "pp-pts",
            "parameterSnapshot": {"parameter_snapshot_hash": snap_hash},
            "grade": "PLAYABLE",
            "pHigher": 0.61,
            "pLower": 0.37,
        }],
        selections=[{"projectionId": "pp-pts", "grade": "PLAYABLE", "selectedSide": "MORE"}],
        run_id="RUN1",
        forecast_cutoff=CUTOFF,
    )
    types = {n["type"] for n in runtime["nodes"]}
    for needed in (
        "Feature", "RoleState", "ParticipationState", "OpportunityState",
        "EfficiencyState", "ParameterSnapshot", "Simulation", "PropEvaluation",
        "Selection", "Forecast",
    ):
        assert needed in types, needed
    traced = trace_runtime_lineage(runtime, {"projectionId": "pp-pts"})
    assert traced["hasParameterSnapshot"] is True
    assert traced["hasSimulation"] is True
    assert "Selection" in traced["runtimeNodeTypes"]


def test_settlement_lineage_does_not_use_hit_to_rewrite_research():
    graph = build_evidence_graph([], [], [])
    runtime = attach_runtime_lineage(
        graph,
        selections=[{"projectionId": "pp-pts", "grade": "PLAYABLE"}],
        settlements=[{
            "projectionId": "pp-pts",
            "settlement": "WIN",
            "frozenForecastHash": "abc",
        }],
        run_id="RUN1",
        frozen_forecast_hash="abc",
    )
    types = {n["type"] for n in runtime["nodes"]}
    assert "Settlement" in types
    assert "LearningObservation" in types
    learn = next(n for n in runtime["nodes"] if n["type"] == "LearningObservation")
    assert learn["doesNotDecideResearchReuse"] is True
    assert learn["futureOnly"] is True


def test_runtime_lineage_emits_operational_nodes_and_edge_provenance():
    graph = attach_runtime_lineage(
        build_evidence_graph([], [], []),
        evaluations=[{
            "projectionId": "pp-1",
            "row": {"projectionId": "pp-1", "eventId": "E1"},
            "worldCount": 8,
            "pHigher": .6,
            "pLower": .3,
            "pPush": .1,
        }],
        selections=[{"projectionId": "pp-1", "selectedSide": "MORE", "grade": "LEAN"}],
        run_id="RUN1",
        forecast_cutoff=CUTOFF,
        runtime_context={
            "codeVersion": "6.0.0-test",
            "harSha256": "h" * 64,
            "inputHashes": ["h" * 64],
            "rows": [{"projectionId": "pp-1", "eventId": "E1", "market": "pass_yds", "line": 250}],
            "requests": [{"request_id": "REQ1", "scope": "OFFER", "scope_id": "pp-1", "need": "line_sides_modifier"}],
            "signalEvaluations": [{
                "projectionId": "pp-1", "operatorId": "CFB_SUPPORT_CONTEXT_V1",
                "outputHash": "s" * 64, "lifecycleState": "ACTIVE_FEATURE",
                "consumers": ["dcm.ml.feature_store.signal_evaluation_feature_records"],
            }],
        },
    )
    types = {node["type"] for node in graph["nodes"]}
    for needed in (
        "Run", "Job", "InputDataset", "HAROffer", "ResearchRequirement", "AcquisitionAction",
        "EventWorld", "ProbabilityBundle", "Decision", "Portfolio", "FrozenForecast", "SignalEvaluation",
    ):
        assert needed in types, needed
    required_edge_fields = set(graph["provenanceContract"]["edgeFields"])
    assert all(required_edge_fields <= set(edge) for edge in graph["edges"])
    assert graph["provenanceContract"]["rawBytesIncluded"] is False


def test_dag_line_change_preserves_subject_history():
    dag = Dag(cutoff=CUTOFF, config_hash="c", schema_version="v", source_versions={})
    hist = dag.add("SUBJECT_HISTORY", "PAIGE")
    dag.complete(hist.key, "h1")
    line = dag.add("MARKET_LINE", "pp-pts", parents=[hist.key])
    dag.complete(line.key, "l1")
    hit = dag.invalidate_line_descendants()
    assert line.key in hit
    assert dag.nodes[hist.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[line.key].state == "INVALIDATED"
    more = dag.invalidate_for_delta("APPEND_MISSING_HISTORY")
    assert hist.key not in more


def test_participation_is_independent_of_efficiency():
    logs = [{"minutes": 30, "fga": 12, "pts": 18} for _ in range(5)]
    part = ParticipationModel().fit(logs, family="basketball", league="WNBA")
    assert part["unit"] == "minutes"
    assert part["mean"] > 0
    assert part["source"] in {"LOGS", "PRIOR"}
    assert "inputHash" in part
    snaps = [{"snaps": 60, "pass_att": 32} for _ in range(5)]
    g = ParticipationModel().fit(snaps, family="gridiron", league="NFL", role="QB")
    assert g["unit"] == "snaps"
