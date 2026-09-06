"""P0 research efficiency: classify first, then deep-research only eligibles."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from dcm.ingest.board import freeze_board
from dcm.ingest.har import ingest_har
from dcm.research.classify import research_disposition
from dcm.research.host_plan import build_host_research_plan
from dcm.research.requests import build_requests, plan_research
from dcm.runner import run_dcm

ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "dcm_v6_workstream_ab"
FULL = ROOT / "fixtures" / "sanitized_live_har" / "prizepicks_20260829.sanitized.har"
CUTOFF = "2026-08-29T16:00:00Z"


def _board():
    ing = ingest_har(FULL.read_bytes(), raw_bytes=FULL.read_bytes())
    board = freeze_board(ing, mount={"state": "ABSENT_IN_THIS_WORKSPACE"}, cutoff=CUTOFF, asof_policy="account_capture")
    return board


def test_full_har_research_plan_far_below_legacy_20k():
    board = _board()
    assert len(board["rows"]) == 11113
    planned = plan_research(board["rows"], CUTOFF, research_shadow=False)
    requests = planned["requests"]
    assert len(requests) < 18528
    # ~609 model-capable non-MLB props plus shared SPORT/EVENT/TEAM/MARKET_DEFINITION
    assert planned["eligible_prop_count"] < 1200
    assert planned["eligible_prop_count"] >= 400
    assert len(requests) < 4000
    assert planned["legacy_market_emitted"] is False
    assert not any(r["scope"] == "MARKET" for r in requests)
    scopes = Counter(r["scope"] for r in requests)
    assert set(scopes) <= {
        "SPORT",
        "COMPETITION",
        "EVENT",
        "ENVIRONMENT",
        "AFFILIATION",
        "SUBJECT",
        "COUNTERPARTY",
        "MARKET_DEFINITION",
        "OFFER",
    }
    assert "PLAYER" not in scopes
    assert "TEAM" not in scopes
    assert "SUBJECT" in scopes
    assert "AFFILIATION" in scopes
    # hierarchy, not alphabetical
    ranks = [r["hierarchy_rank"] for r in requests]
    assert ranks == sorted(ranks)

    skipped = planned["skipped"]
    assert skipped["goblin"] == 1849
    assert skipped["unsupported_sport"] >= 3000
    assert skipped["live_or_in_progress"] >= 1
    assert skipped["side_unknown"] >= 1000
    assert skipped["shadow"] >= 1000
    assert skipped["shadow_researched"] == 0

    offer_ids = {r["scope_id"] for r in requests if r["scope"] == "OFFER"}
    by_id = {r["projectionId"]: r for r in board["rows"]}
    for pid in offer_ids:
        row = by_id[pid]
        deep, klass = research_disposition(row, research_shadow=False)
        assert deep, (pid, klass)
        assert klass in {"model_eligible", "shadow"}
        assert row.get("modifier") != "GOBLIN"
        assert row.get("league") != "MLB"
        assert not (row.get("isLive") or row.get("status") in {"in_progress", "suspended"})
        assert row.get("offeredHigher") or row.get("offeredLower")

    plan = build_host_research_plan(
        requests,
        skipped=skipped,
        entity_graph=planned["entity_graph"],
        unique_scopes=planned["unique_scopes"],
        eligible_prop_count=planned["eligible_prop_count"],
    )
    assert plan["orientation"] == "BUNDLE"
    assert plan["oneFilePerRequest"] is False
    assert plan["bundleFile"] == "evidence_bundle.jsonl"
    assert "outputFile" not in plan
    assert all("outputFile" not in t for t in plan["tasks"])
    assert plan["skippedClasses"]["goblin"] == 1849
    assert plan["entityGraph"]["sports"]


def test_mlb_shadow_research_opt_in():
    board = _board()
    off = plan_research(board["rows"], CUTOFF, research_shadow=False)
    on = plan_research(board["rows"], CUTOFF, research_shadow=True)
    assert on["eligible_prop_count"] > off["eligible_prop_count"]
    assert on["skipped"]["shadow_researched"] >= 1000
    mlb_offers = [
        r for r in on["requests"]
        if r["scope"] == "OFFER" and str(r.get("definition_id") or "").startswith("prizepicks|MLB|")
    ]
    assert mlb_offers
    assert not any(
        str(r.get("definition_id") or "").startswith("prizepicks|MLB|")
        for r in off["requests"]
        if r["scope"] == "OFFER"
    )


def test_account_only_writes_bundle_oriented_plan(tmp_path: Path):
    result = run_dcm(
        input_path=FULL,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "RUNS",
        research="file",
        workspace=tmp_path,
        account_only=True,
    )
    dest = Path(result["dest"])
    reqs = json.loads((dest / "research_requests.json").read_text())
    plan = json.loads((dest / "host_research_plan.json").read_text())
    assert 0 < len(reqs) < 18528
    assert plan["orientation"] == "BUNDLE"
    assert plan["skippedClasses"]["goblin"] == 1849
