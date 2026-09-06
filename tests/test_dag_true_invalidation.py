"""True dependency invalidation: ID-scoped descendants, research-stable line changes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.chat.state import write_json
from dcm.runtime.dag import (
    RESEARCH_STABLE,
    Dag,
    DagFrozenError,
)


CUTOFF = "2026-09-06T12:00:00Z"


def _dag() -> Dag:
    return Dag(
        cutoff=CUTOFF,
        config_hash="true-descendant",
        schema_version="v1",
        source_versions={"parser": "test"},
    )


def test_reverse_adjacency_indexes_are_deterministic():
    dag = _dag()
    claim = dag.add("EVIDENCE_CLAIM", "c1")
    dag.complete(claim.key, "c1")
    p1 = dag.ensure_offer_lineage(claim_keys=[claim.key], offer_id="o1", event_id="e1")
    p2 = dag.ensure_offer_lineage(claim_keys=[claim.key], offer_id="o2", event_id="e2")
    idx = dag.reverse_adjacency_indexes()
    assert claim.key in idx["children"]
    kids = idx["children"][claim.key]
    assert kids == sorted(kids)
    assert "FACT" in idx["byType"]
    assert "FEATURE" in idx["byType"]
    assert "PARAMETER" in idx["byType"]
    assert p1.key in idx["byIdentity"]["o1"]
    assert p2.key in idx["byIdentity"]["o2"]
    assert any(e.startswith("FACT->FEATURE") for e in idx["typeEdges"])
    snap = dag.snapshot()
    assert "children" in snap
    assert snap["indexes"]["byType"]["GRADE"]


def test_invalidate_bfs_only_touches_actual_descendants():
    dag = _dag()
    claim = dag.add("EVIDENCE_CLAIM", "c1")
    dag.complete(claim.key, "c1")
    touch = dag.ensure_offer_lineage(claim_keys=[claim.key], offer_id="touch", event_id="e-touch")
    other = dag.ensure_offer_lineage(claim_keys=[claim.key], offer_id="other", event_id="e-other")
    hit = dag.invalidate([touch.key], include_roots=True)
    assert touch.key in hit
    # fact/feature are ancestors, not descendants — must survive
    for n in dag.nodes.values():
        if n.identity in {"fact:touch", "feature:touch"} or (
            n.node_type in {"FACT", "FEATURE"} and "touch" in n.identity
        ):
            assert n.state == "COMPLETE_VERIFIED"
    # descendants of touch PARAMETER
    worlds = [n for n in dag.nodes.values() if n.node_type == "EVENT_WORLDS" and n.identity == "e-touch"][0]
    grade = [n for n in dag.nodes.values() if n.node_type == "GRADE" and n.identity == "touch"][0]
    rank = [n for n in dag.nodes.values() if n.node_type == "RANK" and n.identity == "touch"][0]
    assert worlds.key in hit and worlds.state == "INVALIDATED"
    assert grade.key in hit and grade.state == "INVALIDATED"
    assert rank.key in hit and rank.state == "INVALIDATED"
    # unrelated lineage intact
    assert dag.nodes[other.key].state == "COMPLETE_VERIFIED"
    other_g = [n for n in dag.nodes.values() if n.node_type == "GRADE" and n.identity == "other"][0]
    other_w = [n for n in dag.nodes.values() if n.node_type == "EVENT_WORLDS" and n.identity == "e-other"][0]
    assert other_g.state == "COMPLETE_VERIFIED"
    assert other_w.state == "COMPLETE_VERIFIED"
    assert other_g.key not in hit


def test_line_change_preserves_historical_research_and_unrelated_grades():
    dag = _dag()
    hist = dag.add("SUBJECT_HISTORY", "QB1")
    dag.complete(hist.key, "hist")
    player = dag.add("PLAYER_HISTORY", "QB1")
    dag.complete(player.key, "ph")
    line = dag.add("MARKET_LINE", "offer-line", parents=[hist.key])
    dag.complete(line.key, "line")
    grade = dag.add("GRADE", "offer-line", parents=[line.key])
    dag.complete(grade.key, "g")
    # Unrelated offer grade with no line parent — must survive ID-scoped line invalidation
    unrelated = dag.add("GRADE", "offer-other")
    dag.complete(unrelated.key, "go")
    unrelated_param = dag.add("PARAMETER", "offer-other")
    dag.complete(unrelated_param.key, "po")
    hit = dag.invalidate_line_descendants()
    assert line.key in hit
    assert grade.key in hit
    assert dag.nodes[hist.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[player.key].state == "COMPLETE_VERIFIED"
    assert hist.key not in hit
    assert player.key not in hit
    assert dag.nodes[unrelated.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[unrelated_param.key].state == "COMPLETE_VERIFIED"
    assert unrelated.key not in hit


def test_role_change_invalidates_only_affected_role_lineage():
    dag = _dag()
    role_a = dag.add("ROLE", "QB1@TEAM_A")
    dag.complete(role_a.key, "ra")
    param_a = dag.add("PARAMETER", "offer-a", parents=[role_a.key])
    dag.complete(param_a.key, "pa")
    world_a = dag.add("EVENT_WORLDS", "event-a", parents=[param_a.key])
    dag.complete(world_a.key, "wa")
    grade_a = dag.add("GRADE", "offer-a", parents=[param_a.key, world_a.key])
    dag.complete(grade_a.key, "ga")

    role_b = dag.add("ROLE", "QB2@TEAM_B")
    dag.complete(role_b.key, "rb")
    param_b = dag.add("PARAMETER", "offer-b", parents=[role_b.key])
    dag.complete(param_b.key, "pb")
    world_b = dag.add("EVENT_WORLDS", "event-b", parents=[param_b.key])
    dag.complete(world_b.key, "wb")
    grade_b = dag.add("GRADE", "offer-b", parents=[param_b.key, world_b.key])
    dag.complete(grade_b.key, "gb")

    hit = dag.invalidate_role_lineage([role_a.key])
    assert role_a.key in hit
    assert param_a.key in hit
    assert world_a.key in hit
    assert grade_a.key in hit
    assert dag.nodes[role_b.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[param_b.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[world_b.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[grade_b.key].state == "COMPLETE_VERIFIED"
    assert grade_b.key not in hit


def test_weather_invalidates_only_relevant_event_descendants():
    dag = _dag()
    weather = dag.add("WEATHER", "stadium-x")
    dag.complete(weather.key, "wx")
    world_x = dag.add("EVENT_WORLDS", "event-x", parents=[weather.key])
    dag.complete(world_x.key, "wxw")
    grade_x = dag.add("GRADE", "offer-x", parents=[world_x.key])
    dag.complete(grade_x.key, "gx")

    world_y = dag.add("EVENT_WORLDS", "event-y")
    dag.complete(world_y.key, "wy")
    grade_y = dag.add("GRADE", "offer-y", parents=[world_y.key])
    dag.complete(grade_y.key, "gy")

    hit = dag.invalidate_environment_lineage([weather.key])
    assert weather.key in hit
    assert world_x.key in hit
    assert grade_x.key in hit
    assert dag.nodes[world_y.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[grade_y.key].state == "COMPLETE_VERIFIED"
    assert grade_y.key not in hit


def test_freeze_rejects_backward_invalidate():
    dag = _dag()
    param = dag.add("PARAMETER", "o1")
    dag.complete(param.key, "p")
    port = dag.ensure_portfolio_link(grade_or_rank_keys=[param.key])
    dag.mark_freeze(portfolio_key=port.key)
    assert dag.is_frozen()
    with pytest.raises(DagFrozenError):
        dag.invalidate([param.key])
    with pytest.raises(DagFrozenError):
        dag.invalidate_types(["PARAMETER"])
    # Reloaded snapshot stays frozen
    reloaded = Dag.from_snapshot(dag.snapshot())
    assert reloaded.is_frozen()
    with pytest.raises(DagFrozenError):
        reloaded.invalidate([param.key])


def test_legacy_invalidate_types_still_coarse_but_spares_research_stable():
    dag = _dag()
    hist = dag.add("SUBJECT_HISTORY", "QB1")
    dag.complete(hist.key, "h")
    p1 = dag.add("PARAMETER", "a")
    dag.complete(p1.key, "a")
    p2 = dag.add("PARAMETER", "b")
    dag.complete(p2.key, "b")
    hit = dag.invalidate_for_delta("APPEND_MISSING_HISTORY")
    assert p1.key in hit and p2.key in hit
    assert hist.key not in hit
    assert dag.nodes[hist.key].state == "COMPLETE_VERIFIED"
    assert hist.node_type in RESEARCH_STABLE


def test_from_snapshot_roundtrip_preserves_children(tmp_path: Path):
    dag = _dag()
    claim = dag.add("EVIDENCE_CLAIM", "c")
    dag.complete(claim.key, "c")
    param = dag.ensure_offer_lineage(claim_keys=[claim.key], offer_id="o", event_id="e")
    path = tmp_path / "runtime_dag.json"
    write_json(path, dag.snapshot())
    loaded = Dag.from_snapshot(json.loads(path.read_text(encoding="utf-8")))
    assert loaded.children_map()[claim.key]
    hit = loaded.invalidate([param.key])
    assert param.key in hit
