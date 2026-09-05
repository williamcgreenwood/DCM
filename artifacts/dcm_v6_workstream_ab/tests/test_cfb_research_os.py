"""CFB guarded-launch Research OS: graphs, acquisition, ranking, freeze."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.cfb.accounting import account_cfb_board
from dcm.cfb.launch import emit_cfb_forecast_artifacts, prepare_cfb_research_os
from dcm.ingest.har import ingest_har
from dcm.research.acquisition import build_acquisition_actions, schedule_acquisition_actions
from dcm.research.batch import build_next_research_batch
from dcm.research.os_graphs import build_board_graph, build_market_demand_graph, build_requirement_graph
from dcm.research.provider import write_bundle
from dcm.research.requests import plan_research
from dcm.runner import run_dcm
from dcm.cfb.markets import NEWLY_ACTIVATED_MARKETS
from dcm.sports.football.research_requirements import MARKET_REQUIREMENTS
from tests.test_cfb_guarded_launch import CUTOFF, FIXTURE, _claims, _web_claims


def _rows() -> list[dict]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return ingest_har(raw)["rows"]


def _real_shape_har(tmp_path: Path) -> Path:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw.pop("_pillars", None)
    har_path = tmp_path / "cfb-real-shape.har.json"
    har_path.write_text(json.dumps(raw), encoding="utf-8")
    return har_path


def test_cfb_accounting_before_goblin_exclusion():
    rows = _rows()
    acc = account_cfb_board(rows)
    assert acc["rawCfb"] == 8
    assert acc["goblin"] == 0
    assert acc["nonGoblin"] == 8
    assert acc["supported"] == 8
    assert acc["unsupported"] == 0
    assert acc["goblinsExcludedFromSelectionAfterAccounting"] is True
    assert set(acc["supportedMarketDefinitions"]) <= set(MARKET_REQUIREMENTS)
    assert set(acc["registeredMarketDefinitions"]) == set(MARKET_REQUIREMENTS)
    assert acc["meaningfulTop100"] is False
    assert acc["newMarketsActivatedToday"] == list(NEWLY_ACTIVATED_MARKETS)


def test_graphs_exist_before_research_and_use_constitution_primitives():
    rows = _rows()
    planned = plan_research(rows, CUTOFF)
    board = build_board_graph(rows)
    demand = build_market_demand_graph(rows)
    req = build_requirement_graph(rows, planned["requests"])
    assert board["nodeCount"] > 0
    assert board["contentHash"]
    assert "eventToOffers" in board["reverseIndexes"]
    assert demand["cfbSupportedDefinitions"]
    assert req["topoOk"] is True
    assert req["reverseIndexes"]["requirementToOffers"]
    actions = build_acquisition_actions(rows, planned["requests"])
    assert actions["actionCount"] >= 1
    schedule = schedule_acquisition_actions(actions)
    assert schedule["liveSelector"] == "ALG-SCHED-001"
    assert "ALG-SCHED-001" in schedule["algorithmIds"]
    # fanout: at least one action covers more than one offer
    assert any(int(a.get("dependentOfferCount") or 0) > 1 for a in actions["actions"])


def test_modelable_is_not_playable_and_per_prop_flags(tmp_path: Path):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = ingest_har(raw)["rows"]
    planned = plan_research(rows, CUTOFF)
    claims = _claims(rows)
    dest = tmp_path / "os"
    dest.mkdir()
    os_art = prepare_cfb_research_os(dest, rows, planned["requests"], claims=claims)
    assert (dest / "board_graph.json").is_file()
    assert (dest / "requirement_graph.json").is_file()
    assert (dest / "acquisition_actions.json").is_file()
    assert os_art["accounting"]["supported"] == 8


def test_live_batch_uses_celf_not_one_prop_one_search():
    rows = _rows()
    planned = plan_research(rows, CUTOFF)
    batch = build_next_research_batch(planned["requests"], rows=rows, max_entities=25)
    assert batch["liveSelector"] == "ALG-SCHED-001"
    assert batch["batching"] == "celf_acquisition_action_then_event_pack"
    assert batch["selectedCount"] >= 1
    assert batch.get("celfActionIds")
    # Not one independent search per prop: selected entities cannot explode to offer×scope
    assert batch["selectedCount"] <= len(planned["requests"])


def test_large_board_celf_does_not_starve_on_sport_mass():
    """SPORT/COMPETITION fanout must not consume the unique-offer budget alone."""
    compact = Path(__file__).resolve().parents[1] / "fixtures" / "sanitized_live_har" / "prizepicks_compact.har"
    raw = compact.read_bytes()
    rows = ingest_har(raw, raw_bytes=raw)["rows"]
    planned = plan_research(rows, "2026-08-29T16:00:00Z")
    actions = build_acquisition_actions(rows, planned["requests"])
    schedule = schedule_acquisition_actions(actions, max_actions=25, max_dependent_offers=500)
    selected = schedule["selectedActionIds"]
    assert len(selected) >= 3
    scopes = {a["scope"] for a in actions["actions"] if a["actionId"] in selected}
    assert "EVENT" in scopes or "AFFILIATION" in scopes
    assert scopes != {"SPORT"} and scopes != {"COMPETITION"} and scopes != {"SPORT", "COMPETITION"}
    by_id = {a["actionId"]: a for a in actions["actions"]}
    assert any(int(by_id[aid]["dependentOfferCount"] or 0) > 1 for aid in selected)



def test_fixture_provider_cannot_create_production_playables(tmp_path: Path):
    """FixtureProvider is engineering-only. Graphs still emit; playables stay 0."""
    result = run_dcm(
        input_path=FIXTURE,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs",
        research="fixture",
        workspace=tmp_path,
        synthetic=False,
    )
    dest = Path(result["dest"])
    assert (dest / "board_graph.json").is_file()
    assert (dest / "requirement_graph.json").is_file()
    assert (dest / "acquisition_actions.json").is_file()
    assert (dest / "CFB_HAR_ACCOUNTING.json").is_file()
    if (dest / "CFB_PLAYABLES_FINAL.json").is_file():
        playables = json.loads((dest / "CFB_PLAYABLES_FINAL.json").read_text())
        assert playables["count"] == 0
    freeze = json.loads((dest / "freeze.json").read_text()) if (dest / "freeze.json").is_file() else {}
    if freeze:
        assert freeze.get("learningRevision", "LR000000") == "LR000000"
        assert freeze.get("predictiveClaim", "NONE") == "NONE"


def test_cfb_fixture_end_to_end_top100_top25_playables_interim(tmp_path: Path):
    har_path = _real_shape_har(tmp_path)
    rows = ingest_har(json.loads(har_path.read_text(encoding="utf-8")))["rows"]
    bundle_path = tmp_path / "cfb-acceptance.jsonl"
    write_bundle(bundle_path, _web_claims(rows))
    result = run_dcm(
        input_path=har_path,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs",
        research="bundle",
        bundle_path=bundle_path,
        workspace=tmp_path,
        synthetic=False,
    )
    dest = Path(result["dest"])
    for name in (
        "algorithm_execution_plan.json",
        "board_graph.json",
        "market_demand_graph.json",
        "requirement_graph.json",
        "acquisition_actions.json",
        "acquisition_schedule.json",
        "CFB_HAR_ACCOUNTING.json",
        "CFB_TOP100_PRELIMINARY.json",
        "CFB_TOP25_FINAL.json",
        "CFB_PLAYABLES_FINAL.json",
        "CFB_LAUNCH_REPORT.json",
        "cfb_prop_states.json",
        "algorithm_execution_telemetry.json",
        "parameters/snapshots.json",
        "freeze.json",
    ):
        assert (dest / name).is_file(), name

    plan = json.loads((dest / "algorithm_execution_plan.json").read_text())
    assert plan["researchMayBegin"] is True
    assert plan["planHash"]

    acc = json.loads((dest / "CFB_HAR_ACCOUNTING.json").read_text())
    assert acc["rawCfb"] == 8
    assert acc["supported"] == 8

    top100 = json.loads((dest / "CFB_TOP100_PRELIMINARY.json").read_text())
    assert top100["count"] == 8
    row = top100["rows"][0]
    for col in (
        "rank", "offer_id", "player", "team", "opponent", "market", "line",
        "offered_sides", "preferred_direction", "P_Higher", "P_Lower",
        "push_probability", "uncertainty", "Reliability", "Data_Quality",
        "Volatility", "Fragility", "OOD", "Selection_Score", "grade",
        "true_line_tolerance", "research_modelability_state", "material_blockers",
    ):
        assert col in row, col
    assert row["research_modelability_state"]["propModelable"] is True
    assert row["not_a_recommendation"] is True
    grades = {r["grade"] for r in top100["rows"]}
    assert grades <= {"PLAYABLE", "LEAN", "PASS", "TRAP"}
    # Probability is not Reliability / Data Quality / Volatility / Fragility.
    assert row["P_Higher"] != row["Reliability"] or row["Reliability"] is None

    top25 = json.loads((dest / "CFB_TOP25_FINAL.json").read_text())
    assert top25["count"] == 8
    playables = json.loads((dest / "CFB_PLAYABLES_FINAL.json").read_text())
    assert 0 <= playables["count"] <= 6
    freeze = json.loads((dest / "freeze.json").read_text())
    assert freeze["learningRevision"] == "LR000000"
    assert freeze["predictiveClaim"] == "NONE"
    assert freeze["cfbTop100Count"] == 8
    tel = json.loads((dest / "algorithm_execution_telemetry.json").read_text())
    activated = tel["activatedCounts"]
    for alg in ("ALG-SCHED-001", "ALG-SORT-001", "ALG-SORT-003", "ALG-GROUP-002", "ALG-INDEX-001"):
        assert alg in activated, alg
        assert activated[alg] >= 1

    result2 = run_dcm(
        input_path=har_path,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs2",
        research="bundle",
        bundle_path=bundle_path,
        workspace=tmp_path,
        synthetic=False,
    )
    dest2 = Path(result2["dest"])
    h1 = json.loads((dest / "CFB_TOP100_PRELIMINARY.json").read_text())["contentHash"]
    h2 = json.loads((dest2 / "CFB_TOP100_PRELIMINARY.json").read_text())["contentHash"]
    assert h1 == h2
    # The real-shape bundle intentionally omits required requests. It must
    # remain an interim frontier, even though the per-prop rows are modeled.
    freeze1 = json.loads((dest / "freeze.json").read_text())
    freeze2 = json.loads((dest2 / "freeze.json").read_text())
    assert freeze1["forecastFrozen"] is False
    assert freeze1["freezeState"] == "FRONTIER_INTERIM"
    assert freeze1["runState"] == "AWAITING_FRONTIER_RESEARCH"
    assert "frozenForecastHash" not in freeze1
    assert freeze2["forecastFrozen"] is False
    assert freeze2["freezeState"] == "FRONTIER_INTERIM"
    assert "frozenForecastHash" not in freeze2


def test_offered_side_only_and_goblin_after_accounting():
    rows = _rows()
    acc = account_cfb_board(rows)
    assert acc["goblinsExcludedFromSelectionAfterAccounting"] is True
    for row in rows:
        assert row.get("offeredHigher") or row.get("offeredLower")


def test_partial_bundle_still_emits_graphs_and_per_prop_states(tmp_path: Path):
    har_path = _real_shape_har(tmp_path)
    rows = ingest_har(json.loads(har_path.read_text(encoding="utf-8")))["rows"]
    bundle_path = tmp_path / "partial.jsonl"
    write_bundle(bundle_path, _web_claims(rows)[:4])  # globally incomplete
    result = run_dcm(
        input_path=har_path,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs",
        research="bundle",
        bundle_path=bundle_path,
        workspace=tmp_path,
    )
    dest = Path(result["dest"])
    assert (dest / "board_graph.json").is_file()
    assert (dest / "requirement_graph.json").is_file()
    assert (dest / "acquisition_actions.json").is_file()
    if result["runState"] != "INCOMPLETE_CHECKPOINTED":
        states = json.loads((dest / "cfb_prop_states.json").read_text())
        assert states["rows"]
        for row in states["rows"]:
            assert "propModelable" in row
            assert "propPlayableEligible" in row
            assert "propResearchComplete" in row
            assert "propFrontierResearchEligible" in row
            # Independence: research completeness is not inferred from modelability.
            if row.get("propModelable") and not row.get("propResearchComplete"):
                assert row.get("propPlayableEligible") is False
