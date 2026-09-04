"""Adversarial semantic-completion tests. Fail if algorithms are ceremonial."""
from __future__ import annotations

from pathlib import Path

from dcm.algorithms.telemetry import AlgorithmTelemetry, ceremonial_violations
from dcm.cfb.event_worlds import simulate_joint_cfb_event_worlds
from dcm.cfb.markets import ACTIVE_CFB_MARKETS, cfb_market_execution_matrix
from dcm.cfb.opportunity_ledger import allocate_team_opportunity
from dcm.cfb.refresh import apply_final_refresh
from dcm.research.cache_layers import ResearchCacheCascade
from dcm.research.indexes import BoardIndexes
from dcm.research.material_facts import facts_to_features, resolve_material_facts
from dcm.research.source_health import CIRCUIT_HALF_OPEN, CIRCUIT_OPEN, default_cfb_source_health


def test_ceremonial_violations_detect_sample_queries():
    tel = AlgorithmTelemetry()
    tel.record(
        "ALG-SEARCH-010",
        problem_class="FUZZY_MATCH",
        producer="sample",
        consumer="launch",
        phase="QUERIED",
        downstream_used=False,
    )
    snap = tel.snapshot()
    assert snap["ceremonialViolations"]
    assert snap["activatedCounts"] == {}
    tel2 = AlgorithmTelemetry()
    tel2.record(
        "ALG-SORT-001",
        problem_class="FINAL_RANK",
        producer="rank",
        consumer="runner",
        phase="EXECUTED",
        downstream_used=True,
    )
    assert ceremonial_violations(tel2.snapshot()["executions"]) == []
    assert "ALG-SORT-001" in tel2.snapshot()["activatedCounts"]


def test_launch_source_does_not_sample_query_indexes():
    src = Path(__file__).resolve().parents[1] / "dcm" / "cfb" / "launch.py"
    text = src.read_text(encoding="utf-8")
    assert "query_retrieval_cascade" not in text
    assert "rows[:8]" not in text
    assert "rows[:4]" not in text
    assert "isotonic_regression(" not in text
    assert "split_conformal(" not in text
    assert "zscore_ood(" not in text


def test_exact_identity_skips_fuzzy():
    rows = [
        {"projectionId": "o1", "playerName": "John Smith", "team": "A", "market": "pass_yds",
         "sportFamily": "gridiron", "league": "CFB", "eventId": "E", "playerId": "P1", "teamId": "A"},
        {"projectionId": "o2", "playerName": "Jane Doe", "team": "B", "market": "rush_yds",
         "sportFamily": "gridiron", "league": "CFB", "eventId": "E", "playerId": "P2", "teamId": "B"},
    ]
    idx = BoardIndexes(rows)
    identity = idx.resolve_identities()
    assert identity["exactCount"] == 2
    assert identity["skippedFuzzy"] == 2
    assert identity["fuzzyCount"] == 0
    assert identity["cascadeCount"] == 0
    snap = idx.telemetry.snapshot()
    skipped = [r for r in snap["executions"] if r.get("phase") == "SKIPPED_NOT_APPLICABLE"]
    assert any(r["algorithm_id"] == "ALG-SEARCH-010" for r in skipped)
    idx.close()


def test_lone_rb_does_not_absorb_team_rush():
    players = [{"playerId": "RB1", "role": "RB", "params": {"rush_att_mean": 18.0}}]
    alloc = allocate_team_opportunity(players, team_pass_att=30, team_rush_att=40, team_targets=30)
    assert alloc["playerRushAtt"][0] <= int(round(0.55 * 40))
    assert alloc["residualRushAtt"] > 0
    assert alloc["playerRushAtt"][0] + alloc["residualRushAtt"] == 40


def test_kicker_gets_zero_rush_and_targets():
    players = [
        {"playerId": "QB1", "role": "QB", "params": {"pass_att_mean": 32.0, "rush_att_mean": 5.0}},
        {"playerId": "K1", "role": "K", "params": {"fg_att_mean": 2.0}},
    ]
    alloc = allocate_team_opportunity(players, team_pass_att=35, team_rush_att=38, team_targets=35)
    assert alloc["playerRushAtt"][1] == 0
    assert alloc["playerTargets"][1] == 0
    assert alloc["playerPassAtt"][1] == 0
    assert alloc["kickerIsolated"] is True


def test_two_rbs_share_and_leave_residual():
    players = [
        {"playerId": "RB1", "role": "RB", "params": {"rush_att_mean": 16.0}},
        {"playerId": "RB2", "role": "RB", "params": {"rush_att_mean": 10.0}},
    ]
    alloc = allocate_team_opportunity(players, team_pass_att=28, team_rush_att=42, team_targets=28)
    assert sum(alloc["playerRushAtt"]) < 42
    assert alloc["residualRushAtt"] > 0
    assert sum(alloc["playerRushAtt"]) + alloc["residualRushAtt"] == 42


def test_joint_worlds_residual_and_kicker_isolation():
    specs = [
        {"row": {"playerId": "RB", "eventId": "E", "role": "RB"}, "snapshot": {"parameters": {"role": "RB", "rush_att_mean": 14}}},
        {"row": {"playerId": "K", "eventId": "E", "role": "K"}, "snapshot": {"parameters": {"role": "K", "fg_att_mean": 2}}},
    ]
    joint = simulate_joint_cfb_event_worlds(specs, n=6, seed="residual")
    assert joint["meta"]["allocationMode"] == "JOINT_TEAM"
    assert joint["meta"]["kickerIsolated"] is True
    assert joint["meta"]["residual"]["rushAttMean"] > 0
    for stats in joint["worlds"]["K"]:
        assert stats["rush_att"] == 0
        assert stats["targets"] == 0


def test_material_fact_hash_includes_values():
    a = resolve_material_facts([
        {"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "STATUS", "claim_value": "ACTIVE", "authority": "OFFICIAL"},
    ])
    b = resolve_material_facts([
        {"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "STATUS", "claim_value": "OUT", "authority": "OFFICIAL"},
    ])
    assert a["contentHash"] != b["contentHash"]
    feats = facts_to_features(a)
    assert feats
    post = resolve_material_facts(
        [{"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "STATUS", "claim_value": "OUT",
          "authority": "OFFICIAL", "observed_at": "2026-09-04T00:00:00Z"}],
        cutoff="2026-09-03T12:00:00Z",
    )
    assert post["excludedPostCutoff"] == 1
    assert post["factCount"] == 0


def test_source_health_open_skipped_half_open_and_cfb_adapter():
    health = default_cfb_source_health()
    ids = {s["sourceId"] for s in health.snapshot()["sources"]}
    assert "CFB_SPORTS_REFERENCE" in ids
    assert "CFB_PFR" not in ids
    adapters = {s["adapter"] for s in health.snapshot()["sources"]}
    assert "college_football_reference" in adapters
    assert "pro_football_reference" not in adapters
    for _ in range(3):
        health.record_failure("CFB_SPORTS_REFERENCE", reason="timeout")
    assert health._state["CFB_SPORTS_REFERENCE"]["circuitState"] == CIRCUIT_OPEN
    assert health._state["CFB_SPORTS_REFERENCE"]["openUntil"]
    routed = health.route(claim_type="SUBJECT", sport="CFB")
    assert "CFB_SPORTS_REFERENCE" not in routed
    assert "WEB_SEARCH" in routed or "CFB_STATUS" in routed
    health._state["CFB_SPORTS_REFERENCE"]["openUntil"] = "2000-01-01T00:00:00+00:00"
    health._refresh_circuit(health._state["CFB_SPORTS_REFERENCE"])
    assert health._state["CFB_SPORTS_REFERENCE"]["circuitState"] == CIRCUIT_HALF_OPEN
    health.record_success("CFB_SPORTS_REFERENCE")
    assert health._state["CFB_SPORTS_REFERENCE"]["circuitState"] == "CLOSED"


def test_cache_does_not_self_put_get_requests(tmp_path: Path):
    cascade = ResearchCacheCascade(tmp_path)
    cascade.put("SUBJECT", "QB1", {"claim_type": "game_line", "claim_value": {"pass_yds": 240}, "observed_at": "2026-09-01T00:00:00Z"})
    rec, layer = cascade.get("SUBJECT", "QB1")
    assert rec is not None
    assert layer in {"L0", "L1", "L2"}
    miss, miss_layer = cascade.get("SUBJECT", "MISSING")
    assert miss is None
    assert miss_layer == "L6"
    asof, l4 = cascade.get_asof("SUBJECT", "QB1", "2026-09-02T00:00:00Z")
    assert asof is not None
    assert l4 == "L4"
    snap = cascade.snapshot()
    assert snap["misses"] >= 1
    cascade.close()


def test_line_only_refresh_does_not_rebuild_worlds():
    modeled = [{
        "row": {"playerId": "QB1", "eventId": "E1", "line": 220.0, "market": "pass_yds"},
        "selectedSide": "MORE",
        "selectedP": 0.6,
        "grade": "LEAN",
        "_worldValues": [200.0] * 4 + [250.0] * 4,
        "lowerBound": 0.4,
        "fragility": 0.1,
        "falseSignRisk": 0.1,
        "evidenceSafeP": 0.6,
    }]
    rebuilt = {"n": 0}

    def resim(rec):
        rebuilt["n"] += 1
        return rec.get("_worldValues")

    out = apply_final_refresh(
        modeled,
        claims=[{"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_value": {"line": 225.0}, "observed_at": "2026-09-01T00:00:00Z"}],
        cutoff="2026-09-03T00:00:00Z",
        resimulate=resim,
    )
    assert out["report"]["lineOnlyCount"] == 1
    assert out["report"]["materialStateCount"] == 0
    assert rebuilt["n"] == 0
    assert out["modeled"][0]["needsWorldRebuild"] is False


def test_material_refresh_rebuilds_worlds():
    modeled = [{
        "row": {"playerId": "QB1", "eventId": "E1", "line": 220.0, "market": "pass_yds", "injury": "ACTIVE"},
        "selectedSide": "MORE",
        "selectedP": 0.6,
        "grade": "LEAN",
        "_worldValues": [220.0] * 8,
        "lowerBound": 0.4,
        "fragility": 0.1,
        "falseSignRisk": 0.1,
        "evidenceSafeP": 0.6,
    }]
    rebuilt = {"n": 0}

    def resim(rec):
        rebuilt["n"] += 1
        return [100.0] * 8

    out = apply_final_refresh(
        modeled,
        claims=[{"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_value": {"injury": "QUESTIONABLE"}, "observed_at": "2026-09-01T00:00:00Z"}],
        cutoff="2026-09-03T00:00:00Z",
        resimulate=resim,
    )
    assert out["report"]["materialStateCount"] == 1
    assert out["modeled"][0]["needsWorldRebuild"] is True
    assert rebuilt["n"] == 1
    assert out["modeled"][0]["_worldValues"][0] == 100.0


def test_frontier_does_not_increment_on_generic_evidence():
    from dcm.cfb.frontier import run_frontier_loop

    modeled = [{"row": {"projectionId": "o1", "league": "CFB", "market": "pass_yds"}, "grade": "PASS", "selectedP": 0.5, "rank": 10}]
    loop = run_frontier_loop(modeled, evidence_imported=True, unresolved_actions=0)
    assert loop["loop"]["frontierPassCount"] == 0
    assert loop["loop"]["evidenceImportedIgnoredUnlessMaterial"] is True
    assert loop["top25"]["final"] is True
    assert loop["loop"]["stopReason"] in {"NO_MATERIAL_FRONTIER_REQUIREMENTS", "NO_POSITIVE_EVSI_ACTION", "FRONTIER_STABLE"}


def test_isotonic_conformal_inactive_at_lr000000(tmp_path: Path):
    from dcm.cfb.launch import emit_cfb_forecast_artifacts

    dest = tmp_path / "ml"
    dest.mkdir()
    modeled = [{"row": {"league": "CFB", "market": "pass_yds", "projectionId": "o1"}, "grade": "PASS", "selectedP": 0.55, "selectionScore": 0.4}]
    emit_cfb_forecast_artifacts(dest, modeled=modeled, qualified=[], classified=modeled)
    body = (dest / "cfb_ml_primitives.json").read_text(encoding="utf-8")
    assert "INACTIVE_ZERO_ELIGIBLE_SETTLEMENTS" in body
    assert "INACTIVE_INSUFFICIENT_CALIBRATION_DATA" in body
    champs = (dest / "cfb_champion_challenger.json").read_text(encoding="utf-8")
    assert "SHADOW_DIAGNOSTIC" in champs
    tel = (dest / "algorithm_execution_telemetry.json")
    # emit does not persist telemetry file; check matrix instead
    matrix = cfb_market_execution_matrix()
    assert matrix["allActiveComplete"] is True
    assert set(matrix["active"]) == set(ACTIVE_CFB_MARKETS)
    assert not matrix["demoted"]


def test_prepare_has_no_ceremonial_violations(tmp_path: Path):
    import json

    from dcm.cfb.launch import persist_algorithm_telemetry, prepare_cfb_research_os
    from dcm.ingest.har import ingest_har
    from dcm.research.requests import plan_research
    from tests.test_cfb_guarded_launch import CUTOFF, FIXTURE

    rows = ingest_har(json.loads(FIXTURE.read_text(encoding="utf-8")))["rows"]
    planned = plan_research(rows, CUTOFF)
    dest = tmp_path / "os"
    dest.mkdir()
    art = prepare_cfb_research_os(dest, rows, planned["requests"], claims=[])
    snap = persist_algorithm_telemetry(dest, art["telemetry"])
    assert snap["ceremonialViolations"] == []
    health = json.loads((dest / "source_health.json").read_text())
    ids = [s["sourceId"] for s in health["sources"]]
    assert "CFB_SPORTS_REFERENCE" in ids
    assert "CFB_PFR" not in ids
    co = json.loads((dest / "cfb_coextraction.json").read_text())
    assert co["status"] == "NO_ACQUIRED_STRUCTURED_PAGE"
    actions = json.loads((dest / "acquisition_actions.json").read_text())
    assert actions["actions"]
    assert actions["actions"][0].get("sourceCandidates")
