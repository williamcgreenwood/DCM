"""CFB reference-implementation tests. Positive and negative. No vacuous asserts."""
from __future__ import annotations

from pathlib import Path

from dcm.algorithms.execution_plan import build_har_algorithm_execution_plan
from dcm.algorithms.ml_families import empirical_bayes_shrink, isotonic_regression, split_conformal, zscore_ood
from dcm.cfb.champion import select_champion, select_cfb_champions
from dcm.cfb.coextract import (
    FULL_STRUCTURED_PAGE_WHEN_CHEAP,
    fanout_acceptance,
    harvest_structured_page,
)
from dcm.cfb.har_delta import classify_board_delta
from dcm.cfb.markets import (
    ACTIVE_CFB_MARKETS,
    NEWLY_ACTIVATED_MARKETS,
    canonicalize_cfb_market,
    classify_raw_market_label,
    inventory_raw_labels,
)
from dcm.ingest.markets import map_stat
from dcm.learning.registry import propose_promotion
from dcm.model.gridiron_models import GridironEfficiencyModel, GridironOpportunityModel, TeamEventModel
from dcm.research.readiness import evaluate_research_os_readiness, require_research_may_begin
from dcm.selection.portfolio import _composite_conflict
from dcm.sports.football.projection import _eval_formula
from dcm.sports.football.registry import lookup_market
from dcm.sports.common.plugin import PRODUCTION, selection_state


def test_exact_aliases_normalize_to_same_market():
    assert canonicalize_cfb_market("pass_attempts") == "pass_att"
    assert canonicalize_cfb_market("pass_completions") == "pass_cmp"
    assert canonicalize_cfb_market("pass_comp") == "pass_cmp"
    assert canonicalize_cfb_market("rush_atts") == "rush_att"
    assert canonicalize_cfb_market("recs") == "receptions"
    assert canonicalize_cfb_market("Player Touchdowns") == "rush_rec_td"
    assert canonicalize_cfb_market("passing yards") == "pass_yds"
    assert map_stat("Pass Comp")[0] == "pass_cmp"
    assert map_stat("recs")[0] == "receptions"
    assert map_stat("rush atts")[0] == "rush_att"
    alias = classify_raw_market_label("pass_attempts")
    assert alias["class"] == "EXACT_ALIAS_EXISTING_MARKET"
    assert alias["canonical"] == "pass_att"


def test_longest_play_is_genuine_unsupported_not_alias():
    for raw in ("Longest Reception", "longest rec", "longest_rush", "longest pass"):
        row = classify_raw_market_label(raw)
        assert row["class"] == "UNSUPPORTED_BY_DESIGN"
        assert row["canonical"] == ""
        assert "play-level" in row["reason"]
    assert map_stat("Longest Reception")[0] == "longest_reception"


def test_inventory_covers_active_and_unsupported():
    labels = [
        "Passing Yards", "Pass TDs", "Player Touchdowns", "Kicking Points",
        "Targets", "Fantasy Score", "Longest Reception", "Tackles",
    ]
    inv = inventory_raw_labels(labels)
    assert set(inv["activeMarketDefinitions"]) == set(ACTIVE_CFB_MARKETS)
    assert "pass_td" in NEWLY_ACTIVATED_MARKETS
    by = inv["byClass"]
    assert "Passing Yards" in by.get("EXACT_ALIAS_EXISTING_MARKET", []) + by.get("SUPPORTED_IMPLEMENTED", [])
    assert any("Longest" in x for x in by.get("UNSUPPORTED_BY_DESIGN", []))


def test_kicking_pts_formula_parses_multiplication():
    values = {"fg_made": 2.0, "xp_made": 3.0}
    assert abs(_eval_formula("3 * fg_made + xp_made", values) - 9.0) < 1e-12
    assert abs(_eval_formula("pass_yds + rush_yds", {"pass_yds": 10.0, "rush_yds": 4.0}) - 14.0) < 1e-12


def test_kicking_pts_project_from_ledger():
    from dcm.sports.football.registry import CFB_LEAGUE

    definition = lookup_market(CFB_LEAGUE, "kicking_pts")
    assert definition is not None
    assert definition.formula
    assert abs(_eval_formula(definition.formula, {"fg_made": 2.0, "xp_made": 1.0}) - 7.0) < 1e-9


def test_efficiency_fits_td_int_kicking_from_logs():
    logs = [
        {"pass_att": 30, "pass_cmp": 18, "pass_yds": 240, "pass_td": 2, "interceptions": 1,
         "rush_att": 8, "rush_yds": 40, "rush_td": 1, "targets": 0, "receptions": 0, "rec_yds": 0},
        {"pass_att": 28, "pass_cmp": 17, "pass_yds": 210, "pass_td": 1, "interceptions": 0,
         "rush_att": 6, "rush_yds": 22, "rush_td": 0, "targets": 0, "receptions": 0, "rec_yds": 0},
    ]
    eff = GridironEfficiencyModel().fit(logs, league="CFB", role="QB", pass_defense=1.0, rush_defense=1.0)
    assert 0 < eff["pass_td_rate"] < 0.2
    assert 0 <= eff["int_rate"] < 0.15
    assert eff["shrinkage"]["method"] == "empirical_bayes_shrink"
    opp = GridironOpportunityModel().fit(logs, league="CFB", role="QB")
    assert "logSupport" in opp
    assert opp["logSupport"]["pass_att_n"] >= 1
    kick_logs = [{"fg_att": 2, "fg_made": 1, "xp_att": 3, "xp_made": 3}]
    k_opp = GridironOpportunityModel().fit(kick_logs, league="CFB", role="K")
    assert k_opp["opportunity_from"] == "kicking_attempts"
    assert k_opp["fg_att_mean"] > 0
    k_eff = GridironEfficiencyModel().fit(kick_logs, league="CFB", role="K")
    assert k_eff["fg_rate"] > 0
    team = TeamEventModel().fit({"plays": 70}, {"scheduled_start": "2026-09-03T00:00:00Z"}, {}, league="CFB", market="kicking_pts")
    assert team["playableBlocker"] is None
    blocked = TeamEventModel().fit({"plays": 70}, {}, {}, league="CFB", market="pass_td")
    assert blocked["playableBlocker"] == "OPPONENT_PASS_DEFENSE"


def test_empirical_bayes_and_stdlib_ml_primitives():
    assert abs(empirical_bayes_shrink(1.0, 0, 0.5, 8) - 0.5) < 1e-12
    shrunk = empirical_bayes_shrink(0.8, 4, 0.5, 8)
    assert 0.5 < shrunk < 0.8
    iso = isotonic_regression([0.1, 0.4, 0.9], [0.2, 0.1, 0.8])
    assert iso == sorted(iso) or iso[0] <= iso[-1]
    assert split_conformal([0.1, 0.2, 0.4]) > 0
    assert zscore_ood(10.0, [1.0, 2.0, 1.5, 2.5]) > 1.0


def test_research_may_begin_false_until_readiness(tmp_path: Path):
    plan = build_har_algorithm_execution_plan({"n_offers": 8})
    assert plan.research_may_begin is False
    body = evaluate_research_os_readiness(
        board_graph=None,
        market_demand_graph=None,
        requirement_graph=None,
        indexes_meta=None,
        reused_evidence_scopes=None,
        acquisition_actions=None,
    )
    assert body["researchMayBegin"] is False
    assert "BOARD_GRAPH_INVALID" in body["blockers"]
    try:
        require_research_may_begin(tmp_path)
        raise AssertionError("expected RESEARCH_MAY_BEGIN_DENIED")
    except RuntimeError as exc:
        assert "RESEARCH_MAY_BEGIN_DENIED" in str(exc)


def test_har_delta_line_only_reuses_history():
    prev = [{"projectionId": "a", "playerId": "P1", "eventId": "E1", "teamId": "T", "market": "pass_yds", "line": 220, "side": "MORE"}]
    curr = [{"projectionId": "a", "playerId": "P1", "eventId": "E1", "teamId": "T", "market": "pass_yds", "line": 225, "side": "MORE"}]
    delta = classify_board_delta(prev, curr)
    assert delta["refreshCurrentContext"] == 1
    assert delta["rows"][0]["lineOnly"] is True
    assert delta["rows"][0]["disposition"] == "REFRESH_CURRENT_CONTEXT"
    new = classify_board_delta(prev, [{"projectionId": "b", "playerId": "P2", "eventId": "E2", "teamId": "X", "market": "rush_yds", "line": 80}])
    assert new["newEntity"] == 1


def test_coextract_fanout_one_page_many_entities():
    rows = [
        {"league": "CFB", "eventId": "E1", "teamId": "A", "opponentId": "B", "playerId": "QB1", "projectionId": "o1", "market": "pass_yds"},
        {"league": "CFB", "eventId": "E1", "teamId": "A", "opponentId": "B", "playerId": "RB1", "projectionId": "o2", "market": "rush_yds"},
        {"league": "CFB", "eventId": "E1", "teamId": "A", "opponentId": "B", "playerId": "WR1", "projectionId": "o3", "market": "rec_yds"},
    ]
    page = {
        "eventId": "E1",
        "teams": ["A", "B"],
        "players": [
            {"playerId": "QB1", "pass_yds": 240},
            {"playerId": "RB1", "rush_yds": 90},
            {"playerId": "WR1", "rec_yds": 70},
        ],
    }
    harvested = harvest_structured_page(page, rows, policy=FULL_STRUCTURED_PAGE_WHEN_CHEAP)
    assert harvested["boardSubjectHits"] == 3
    assert harvested["fanout"] >= 3
    assert harvested["claimCount"] >= 3
    fan = fanout_acceptance({"actionCount": 1, "actions": [{"dependentOfferCount": 3}]}, [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}])
    assert fan["onePropOneSearch"] is False
    assert fan["accepted"] is True


def test_champion_portable_and_gpu_rejected():
    champ = select_champion("pass_yds", role="QB", sample_n=2)
    assert champ["gpuRequired"] is False
    assert champ["supportRegime"] == "SMALL_SAMPLE"
    champ2 = select_champion("pass_yds", role="QB", sample_n=12, benchmark={
        "candidates": [{"algorithmId": "ALG-ML-TABULAR-006", "family": "XGBoost", "gpuOnly": True, "logLoss": 0.01}],
    })
    assert champ2["algorithmId"] != "ALG-ML-TABULAR-006"
    modeled = [{"row": {"league": "CFB", "market": "pass_td", "role": "QB"}, "parameterSnapshot": {"opportunity": {"support_n": 3}}}]
    table = select_cfb_champions(modeled)
    assert table["learningRevision"] == "LR000000"
    assert table["predictiveClaim"] == "NONE"
    assert "pass_td" in table["markets"]


def test_portfolio_combo_constraints():
    assert _composite_conflict({"rush_td"}, "rush_rec_td") is True
    assert _composite_conflict({"fg_made"}, "kicking_pts") is True
    assert _composite_conflict({"pass_yds"}, "receptions") is False


def test_learning_firewall_stays_lr000000(tmp_path: Path):
    proposal = propose_promotion(tmp_path / "learning_registry.json", "ghost.challenger")
    assert proposal["status"] == "BLOCKED"
    assert proposal["lrUnchanged"] == "LR000000"
    assert proposal["predictiveClaimUnchanged"] == "NONE"
    assert proposal["autoPromote"] is False


def test_plugin_activates_new_markets():
    for market in NEWLY_ACTIVATED_MARKETS:
        assert selection_state("gridiron", "CFB", market) == PRODUCTION
    assert selection_state("gridiron", "CFB", "def_tackles") != PRODUCTION


def test_hold_playable_demotes_conflict():
    from dcm.research.material_facts import apply_hold_playable, hold_playable_scope_ids, resolve_material_facts

    claims = [
        {"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "STATUS", "claim_value": "ACTIVE", "authority": "REPUTABLE_REPORTING", "freshness": 0.4, "source_id": "s1"},
        {"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "STATUS", "claim_value": "QUESTIONABLE", "authority": "SEARCH_FALLBACK", "freshness": 0.9, "source_id": "s2"},
    ]
    facts = resolve_material_facts(claims)
    hold = hold_playable_scope_ids(facts)
    assert "QB1" in hold
    rec = apply_hold_playable(
        {"row": {"playerId": "QB1", "eventId": "E1"}, "grade": "PLAYABLE", "modeledPlayable": True, "productionSelectable": True},
        hold,
    )
    assert rec["grade"] == "LEAN"
    assert rec["modeledPlayable"] is False
    assert rec["blocker"] == "MATERIAL_FACT_CONFLICT"
    safe = apply_hold_playable({"row": {"playerId": "RB1"}, "grade": "PLAYABLE", "modeledPlayable": True}, hold)
    assert safe["grade"] == "PLAYABLE"


def test_governed_role_epoch_executes_ewma_cusum_page_hinkley():
    from dcm.research.role_epoch import governed_change_points

    series = [10.0] * 12 + [40.0] * 12
    body = governed_change_points(series)
    assert body["greedy"][0] == 0
    assert 12 in body["greedy"]
    assert len(body["ewma"]) == len(series)
    assert "ALG-ML-TIME-001" in body["executed"]
    assert "ALG-ML-TIME-002" in body["executed"]
    assert "ALG-ML-TIME-003" in body["executed"]


def test_archive_retry_reconcile_and_drive_catalog(tmp_path: Path):
    from dcm.runtime.archive_receipt import archive_reconcile, archive_retry, build_archive_receipt, persist_archive_receipt
    from dcm.runtime.drive_catalog import BLOCKED_EXTERNAL, DriveObjectCatalog

    dest = tmp_path / "run"
    dest.mkdir()
    (dest / "frozen_forecast.json").write_text('{"frozenForecastHash": "abc"}\n', encoding="utf-8")
    receipt = persist_archive_receipt(dest, build_archive_receipt(dest, hashes={"frozenForecastHash": "abc", "harSha256": "h"}))
    assert receipt["remoteFailureInvalidatesForecast"] is False
    retried = archive_retry(dest)
    assert retried["retried"] is True
    recon = archive_reconcile(dest)
    assert recon["hashesMatch"] is True
    assert recon["localFallbackLegal"] is True
    cat = DriveObjectCatalog(dest)
    digest = cat.put("deadbeef", {"kind": "HAR_OFFER"})
    ident = cat.identify(digest)
    assert ident["present"] is True
    fetched = cat.fetch(digest)
    assert fetched["status"] == "NOT_CONFIGURED"
    assert fetched["blocked"] == BLOCKED_EXTERNAL


def test_retrieval_cascade_queries_rrf_mmr_lsh():
    from dcm.research.indexes import BoardIndexes

    rows = [
        {"projectionId": "o1", "playerName": "John Smith", "team": "A", "market": "pass_yds", "sportFamily": "gridiron", "league": "CFB", "eventId": "E", "playerId": "P1"},
        {"projectionId": "o2", "playerName": "Jon Smith", "team": "A", "market": "rush_yds", "sportFamily": "gridiron", "league": "CFB", "eventId": "E", "playerId": "P2"},
    ]
    idx = BoardIndexes(rows)
    out = idx.query_retrieval_cascade("John Smith")
    assert "rrf" in out
    assert "mmr" in out
    assert "lshHits" in out
    bits = idx.requirement_bitmaps([{"request_id": "r1", "dependent_offer_ids": ["o1", "o2"]}])
    assert bits["r1"] == 2
    idx.close()


def test_failure_class_identity_and_stale():
    from dcm.learning.failure_class import classify_failure

    ident = classify_failure(predicted_side="MORE", outcome="LOSS", snapshot_fields={"blocker": "IDENTITY_ALIAS"})
    assert ident["failureClass"] == "identity"
    stale = classify_failure(predicted_side="MORE", outcome="LOSS", snapshot_fields={"reason": "STALE evidence"})
    assert stale["failureClass"] == "stale_evidence"


def test_joint_cfb_event_worlds_emit_allocation_mode():
    from dcm.cfb.event_worlds import simulate_joint_cfb_event_worlds

    specs = [
        {"row": {"playerId": "QB", "eventId": "E", "role": "QB", "market": "pass_yds"}, "snapshot": {"parameters": {"role": "QB", "pass_att_mean": 30, "completion_rate": 0.6, "ypa": 7.0}}},
        {"row": {"playerId": "WR", "eventId": "E", "role": "WR", "market": "rec_yds"}, "snapshot": {"parameters": {"role": "WR", "routes_mean": 8, "target_rate": 0.25, "catch_rate": 0.6}}},
    ]
    joint = simulate_joint_cfb_event_worlds(specs, n=8, seed="test")
    assert joint["meta"]["allocationMode"] == "JOINT_TEAM"
    assert "identities" in joint["meta"]["conservation"]
    assert len(joint["worlds"]["QB"]) == 8
    assert len(joint["worlds"]["WR"]) == 8
