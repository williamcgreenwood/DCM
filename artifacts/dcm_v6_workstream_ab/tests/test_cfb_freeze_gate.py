"""Adversarial freeze-gate tests. Fail if semantic contracts are ceremonial."""
from __future__ import annotations

from pathlib import Path

from dcm.cfb.event_worlds import simulate_joint_cfb_event_worlds
from dcm.cfb.frontier import run_frontier_loop
from dcm.cfb.markets import ACTIVE_CFB_MARKETS, cfb_market_execution_matrix
from dcm.cfb.opportunity_ledger import allocate_team_opportunity, estimate_opportunity_share
from dcm.cfb.recompute import recompute_full_bundle
from dcm.cfb.refresh import apply_final_refresh
from dcm.model.parameters import build_parameter_snapshot
from dcm.model.ranking import rank_candidates
from dcm.research.acquisition import build_acquisition_actions
from dcm.research.cache_layers import ResearchCacheCascade
from dcm.research.coverage import evaluate_request
from dcm.research.indexes import BoardIndexes, EvidenceIndexes
from dcm.research.material_facts import facts_to_features, resolve_material_facts
from dcm.research.source_health import (
    CIRCUIT_HALF_OPEN,
    CIRCUIT_OPEN,
    default_cfb_source_health,
    load_cfb_source_health,
    persist_cfb_source_health,
)
from dcm.runtime.drive_catalog import DriveObjectCatalog


def _logs(role: str = "RB", n: int = 8) -> list[dict]:
    out = []
    for i in range(n):
        if role == "QB":
            out.append({
                "pass_att": 32, "pass_cmp": 20, "pass_yds": 260, "pass_td": 2, "interceptions": 1,
                "rush_att": 5, "rush_yds": 18, "rush_td": 0, "snaps": 68, "date": f"2026-08-{10+i:02d}",
            })
        elif role == "RB":
            out.append({
                "rush_att": 16, "rush_yds": 75, "rush_td": 1, "targets": 4, "receptions": 3,
                "rec_yds": 22, "rec_td": 0, "snaps": 40, "date": f"2026-08-{10+i:02d}",
            })
        else:
            out.append({
                "rush_att": 1, "rush_yds": 4, "targets": 8, "receptions": 5, "rec_yds": 68,
                "rec_td": 1, "routes": 28, "snaps": 55, "date": f"2026-08-{10+i:02d}",
            })
    return out


def _cfb_row(role: str = "RB", market: str = "rush_yds", pid: str = "P1") -> dict:
    return {
        "sportFamily": "gridiron", "league": "CFB", "eventId": "E1", "playerId": pid,
        "teamId": "OSU", "opponentId": "MICH", "projectionId": f"pp-{pid}-{market}",
        "market": market, "role": role, "playerName": f"{role} Player",
        "line": 80.0, "offeredHigher": True, "offeredLower": True,
    }


def _claims(row: dict, logs: list[dict], extra_player: dict | None = None) -> list[dict]:
    player = {
        "status": "ACTIVE", "role": row["role"], "game_logs": logs,
        "opportunity": {"support_n": len(logs)}, "efficiency": {"support_n": len(logs)},
        **(extra_player or {}),
    }
    return [
        {"semantic_scope": "SUBJECT", "scope": "SUBJECT", "scope_id": row["playerId"], "claim_type": "PLAYER",
         "claim_value": player, "claim_hash": f"c-{row['playerId']}", "source_id": "FIXTURE", "reliability": 0.9, "freshness": 0.8},
        {"semantic_scope": "AFFILIATION", "scope": "AFFILIATION", "scope_id": row["teamId"], "claim_type": "TEAM",
         "claim_value": {"plays": 70, "pass_rate": 0.55, "pace": 1.0, "pass_defense": 0.98, "rush_defense": 1.02},
         "claim_hash": "c-team", "source_id": "FIXTURE"},
        {"semantic_scope": "EVENT", "scope": "EVENT", "scope_id": row["eventId"], "claim_type": "EVENT",
         "claim_value": {"scheduled_start": "2026-09-06T19:00:00Z", "environment": "outdoor",
                         "pass_defense": 0.98, "rush_defense": 1.02},
         "claim_hash": "c-event", "source_id": "FIXTURE"},
        {"semantic_scope": "MARKET_DEFINITION", "scope": "MARKET_DEFINITION",
         "scope_id": f"prizepicks|CFB|{row['market']}|FULL_GAME", "claim_type": "MARKET_DEFINITION",
         "claim_value": {"definition_verified": True}, "claim_hash": "c-md", "source_id": "FIXTURE"},
        {"semantic_scope": "OFFER", "scope": "OFFER", "scope_id": row["projectionId"], "claim_type": "OFFER",
         "claim_value": {"offer_recorded": True}, "claim_hash": "c-off", "source_id": "FIXTURE"},
    ]


def test_material_fact_changes_fitted_snapshot_hash_and_role():
    row = _cfb_row("WR", "rec_yds", "WR1")
    logs = _logs("WR")
    claims = _claims(row, logs)
    feats_wr = [{"name": "role", "value": "WR", "scope": "SUBJECT", "scopeId": "WR1", "materialFactHash": "h-wr"}]
    feats_rb = [{"name": "role", "value": "RB", "scope": "SUBJECT", "scopeId": "WR1", "materialFactHash": "h-rb"}]
    snap_wr = build_parameter_snapshot(row, claims, fact_features=feats_wr)
    snap_rb = build_parameter_snapshot(row, claims, fact_features=feats_rb)
    assert snap_wr["parameter_snapshot_hash"] != snap_rb["parameter_snapshot_hash"]
    assert snap_wr["parameters"]["role"] == "WR"
    assert snap_rb["parameters"]["role"] == "RB"
    assert (snap_wr.get("opportunity") or {}).get("rush_att_mean") != (snap_rb.get("opportunity") or {}).get("rush_att_mean") or (
        snap_wr["parameters"].get("rush_att_mean") != snap_rb["parameters"].get("rush_att_mean")
    )


def test_material_status_changes_snapshot_and_availability():
    row = _cfb_row("QB", "pass_yds", "QB1")
    claims = _claims(row, _logs("QB"))
    a = build_parameter_snapshot(row, claims, fact_features=[
        {"name": "status", "value": "ACTIVE", "scope": "SUBJECT", "scopeId": "QB1", "materialFactHash": "s1"}
    ])
    b = build_parameter_snapshot(row, claims, fact_features=[
        {"name": "status", "value": "OUT", "scope": "SUBJECT", "scopeId": "QB1", "materialFactHash": "s2"}
    ])
    assert a["parameter_snapshot_hash"] != b["parameter_snapshot_hash"]
    assert (a.get("availabilityMixture") or {}).get("pPlay") != (b.get("availabilityMixture") or {}).get("pPlay")


def test_lone_rb_uses_shared_residual_event_world():
    specs = [{"row": {"playerId": "RB1", "eventId": "E", "teamId": "T", "role": "RB"},
              "snapshot": {"parameters": {"role": "RB", "rush_att_mean": 14, "support_n": 8}}}]
    joint = simulate_joint_cfb_event_worlds(specs, n=8, seed="lone-rb")
    assert joint["meta"]["allocationMode"] == "JOINT_TEAM"
    assert joint["meta"]["playerCount"] == 1
    assert joint["meta"]["residual"]["rushAttMean"] > 0
    for stats in joint["worlds"]["RB1"]:
        assert stats.get("unmodeled_rush_residual", 0) > 0 or joint["meta"]["residual"]["rushAttMean"] > 0


def test_lone_qb_uses_shared_event_world():
    specs = [{"row": {"playerId": "QB1", "eventId": "E", "teamId": "T", "role": "QB"},
              "snapshot": {"parameters": {"role": "QB", "pass_att_mean": 32, "support_n": 10}}}]
    joint = simulate_joint_cfb_event_worlds(specs, n=6, seed="lone-qb")
    assert joint["meta"]["joint"] is True
    assert joint["meta"]["residual"]["passAttMean"] >= 0
    assert "QB1" in joint["worlds"]


def test_kicker_remains_isolated():
    specs = [
        {"row": {"playerId": "QB", "eventId": "E", "role": "QB"}, "snapshot": {"parameters": {"role": "QB", "pass_att_mean": 30}}},
        {"row": {"playerId": "K", "eventId": "E", "role": "K"}, "snapshot": {"parameters": {"role": "K", "fg_att_mean": 2}}},
    ]
    joint = simulate_joint_cfb_event_worlds(specs, n=6, seed="kicker")
    assert joint["meta"]["kickerIsolated"] is True
    for stats in joint["worlds"]["K"]:
        assert stats["rush_att"] == 0
        assert stats["targets"] == 0


def test_starter_qb_not_blindly_capped_at_92():
    player = {"playerId": "QB1", "role": "QB", "starter": "starter",
              "params": {"pass_att_mean": 34.0, "support_n": 10}}
    est = estimate_opportunity_share(player, pool="pass", team_total=35)
    assert est["method"] == "ROLE_EPOCH_LOGS"
    assert est["fallback"] is False
    assert est["estimatedShare"] > 0.92
    alloc = allocate_team_opportunity([player], team_pass_att=35, team_rush_att=30, team_targets=35)
    assert alloc["shareEstimates"][0]["pass"]["estimatedShare"] > 0.92
    assert alloc["playerPassAtt"][0] + alloc["residualPassAtt"] == 35


def test_conservation_holds_with_residuals():
    players = [
        {"playerId": "RB1", "role": "RB", "params": {"rush_att_mean": 16.0, "support_n": 8}},
        {"playerId": "WR1", "role": "WR", "params": {"targets_mean": 8.0, "support_n": 8}},
    ]
    alloc = allocate_team_opportunity(players, team_pass_att=30, team_rush_att=40, team_targets=30)
    assert sum(alloc["playerRushAtt"]) + alloc["residualRushAtt"] == 40
    assert sum(alloc["playerTargets"]) + alloc["residualTargets"] == 30


def test_material_refresh_rebuild_keys_and_full_bundle_can_flip_direction():
    rec = {
        "row": {"playerId": "QB1", "eventId": "E1", "teamId": "T", "line": 220.0, "market": "pass_yds",
                "offeredHigher": True, "offeredLower": True, "sportFamily": "gridiron", "league": "CFB",
                "injury": "ACTIVE", "projectionId": "o1"},
        "selectedSide": "MORE",
        "selectedP": 0.7,
        "grade": "LEAN",
        "_worldValues": [250.0] * 8,
        "parameterSnapshot": {"data_quality": 0.8, "ood_risk": 0.1, "synthetic": False,
                              "opportunity": {"support_n": 8}, "efficiency": {"support_n": 8}},
        "evidenceSafeP": 0.7,
        "lowerBound": 0.55,
    }
    facts = resolve_material_facts([
        {"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "INJURY",
         "claim_value": {"injury": "QUESTIONABLE"}, "authority": "OFFICIAL",
         "observed_at": "2026-09-01T00:00:00Z"},
    ])
    out = apply_final_refresh([rec], facts=facts, cutoff="2026-09-03T00:00:00Z")
    assert out["modeled"][0]["needsWorldRebuild"] is True
    assert "QB1" in out["report"]["rebuildPlayerIds"]
    low = dict(rec)
    low["_worldValues"] = [100.0] * 8
    recomputed = recompute_full_bundle(low)
    assert recomputed["selectedSide"] == "LESS"
    assert recomputed["directionFlipped"] is True
    assert recomputed["evidenceSafeP"] is not None
    assert recomputed["selectionScore"] is not None


def test_material_refresh_can_change_ranking():
    a = {
        "row": {"projectionId": "a", "playerId": "A", "eventId": "E", "line": 10.0, "market": "rush_yds",
                "offeredHigher": True, "offeredLower": False, "sportFamily": "gridiron", "league": "CFB"},
        "selectedSide": "MORE", "_worldValues": [80.0] * 16,
        "parameterSnapshot": {"data_quality": 0.95, "ood_risk": 0.02, "synthetic": False,
                              "opportunity": {"support_n": 12}, "efficiency": {"support_n": 12}},
    }
    b = {
        "row": {"projectionId": "b", "playerId": "B", "eventId": "E", "line": 10.0, "market": "rush_yds",
                "offeredHigher": True, "offeredLower": False, "sportFamily": "gridiron", "league": "CFB"},
        "selectedSide": "MORE", "_worldValues": [8.0] * 8 + [12.0] * 8,
        "parameterSnapshot": {"data_quality": 0.95, "ood_risk": 0.02, "synthetic": False,
                              "opportunity": {"support_n": 12}, "efficiency": {"support_n": 12}},
    }
    ra = recompute_full_bundle(a)
    rb = recompute_full_bundle(b)
    ranked = rank_candidates([ra, rb], top_k=2, seed="refresh-rank")
    assert ranked[0]["row"]["projectionId"] == "a"
    a2 = dict(ra)
    a2["_worldValues"] = [2.0] * 16
    a2 = recompute_full_bundle(a2)
    ranked2 = rank_candidates([a2, dict(rb)], top_k=2, seed="refresh-rank")
    assert ranked2[0]["row"]["projectionId"] == "b"


def test_frontier_required_cannot_freeze():
    modeled = [{"row": {"projectionId": "o1", "league": "CFB", "market": "pass_yds"},
                "grade": "LEAN", "selectedP": 0.62, "rank": 3,
                "research_modelability_state": {"propFrontierResearchEligible": True}}]
    loop = run_frontier_loop(
        modeled,
        unresolved_actions=3,
        host_required=True,
        actions={"actions": [{"actionId": "AA_SUBJECT_P", "offerIds": ["o1"], "dependentOfferCount": 1,
                              "pSuccess": 0.9, "authority": 0.9, "cost": 1.0, "freshness": 0.8}]},
    )
    assert loop["top25"]["final"] is False
    assert loop["loop"]["stopReason"] == "EXTERNAL_HOST_REQUIRED"
    assert loop["top25"]["name"] == "CFB_TOP25_INTERIM"


def test_frontier_hash_change_increments_pass():
    modeled = [{"row": {"projectionId": "o1", "league": "CFB", "market": "pass_yds"}, "grade": "PASS", "selectedP": 0.5, "rank": 10}]
    loop = run_frontier_loop(modeled, snapshot_hash_before="aaa", snapshot_hash_after="bbb")
    assert loop["loop"]["frontierPassCount"] == 1
    assert loop["loop"]["snapshotChanged"] is True
    assert loop["passState"]["passIncremented"] is True
    assert loop["passState"]["ParameterSnapshotHashBefore"] == "aaa"
    assert loop["passState"]["ParameterSnapshotHashAfter"] == "bbb"


def test_unrelated_evidence_does_not_increment_pass():
    modeled = [{"row": {"projectionId": "o1", "league": "CFB", "market": "pass_yds"}, "grade": "PASS", "selectedP": 0.5, "rank": 10}]
    loop = run_frontier_loop(
        modeled,
        evidence_imported=True,
        snapshot_hash_before="aaa",
        snapshot_hash_after="aaa",
        world_hash_before="w",
        world_hash_after="w",
        feature_hash_before="f",
        feature_hash_after="f",
    )
    assert loop["loop"]["frontierPassCount"] == 0
    assert loop["loop"]["evidenceImportedIgnoredUnlessMaterial"] is True


def test_status_evidence_does_not_satisfy_game_history():
    request = {
        "request_id": "R1", "scope": "SUBJECT", "scope_id": "QB1",
        "need": "GAME_HISTORY", "sportFamily": "gridiron", "league": "CFB", "market": "pass_yds",
    }
    status_claims = [{
        "semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "STATUS",
        "claim_value": {"status": "ACTIVE"},
    }]
    verdict = evaluate_request(request, status_claims)
    assert verdict["complete"] is False
    assert "ROLE_COMPARABLE_GAME_LOGS_MIN_3" in verdict["missing"] or "PLAYER_ROLE" in verdict["missing"]
    evidence = EvidenceIndexes(status_claims)
    actions = build_acquisition_actions(
        [{"projectionId": "o1", "playerId": "QB1", "league": "CFB", "sportFamily": "gridiron", "market": "pass_yds",
          "eventId": "E", "teamId": "T"}],
        [request],
        evidence=evidence,
    )
    incomplete_ids = {rid for act in actions["actions"] for rid in (act.get("requirementIds") or [])}
    assert "R1" in incomplete_ids or actions["completeRequirementCount"] == 0
    # STATUS-only evidence must not complete the GAME_HISTORY/SUBJECT requirement.
    assert actions["completeRequirementCount"] == 0
    evidence.close()


def test_exact_id_does_not_query_bloom_composite_sqlite():
    rows = [
        {"projectionId": "o1", "playerName": "John Smith", "team": "A", "market": "pass_yds",
         "sportFamily": "gridiron", "league": "CFB", "eventId": "E", "playerId": "P1", "teamId": "A"},
    ]
    idx = BoardIndexes(rows)
    identity = idx.resolve_identities()
    assert identity["exactCount"] == 1
    snap = idx.telemetry.snapshot()
    queried = [r for r in snap["executions"] if r.get("phase") == "QUERIED"]
    assert not any(r["algorithm_id"] == "ALG-INDEX-009" and r.get("producer", "").endswith("might_have_offer") for r in queried)
    assert not any("lookup_composite" in str(r.get("producer") or "") for r in queried)
    assert not any("sqlite_event_offers" in str(r.get("producer") or "") for r in queried)
    idx.close()


def test_l5_semantic_to_content_address(tmp_path: Path):
    catalog = DriveObjectCatalog(tmp_path)
    cascade = ResearchCacheCascade(tmp_path, drive=catalog)
    cascade.put("SUBJECT", "QB1", {"claim_type": "game_line", "claim_value": {"pass_yds": 240},
                                   "claim_hash": "digest-qb1", "observed_at": "2026-09-01T00:00:00Z"},
                claim_type="game_line")
    catalog.persist(tmp_path)
    cascade.clear_ephemeral()
    rec, layer = cascade.get("SUBJECT", "QB1", claim_type="game_line")
    assert layer == "L5"
    assert rec is not None
    assert rec.get("claim_value", {}).get("pass_yds") == 240
    empty = ResearchCacheCascade(tmp_path, drive=None)
    miss, miss_layer = empty.get("SUBJECT", "QB1", claim_type="game_line")
    assert miss is None
    assert miss_layer == "L6"
    cascade.close()
    empty.close()


def test_source_health_zero_success_stays_zero(tmp_path: Path):
    health = default_cfb_source_health()
    for _ in range(3):
        health.record_failure("CFB_SPORTS_REFERENCE", reason="timeout")
    assert health.success_probability("CFB_SPORTS_REFERENCE") == 0.0
    persist_cfb_source_health(health, tmp_path)
    loaded = load_cfb_source_health(tmp_path)
    assert loaded.success_probability("CFB_SPORTS_REFERENCE") == 0.0
    assert loaded.success_probability("CFB_SPORTS_REFERENCE") != 0.85


def test_open_source_changes_routing_and_celf_gain():
    from dcm.research.acquisition import build_acquisition_actions as build

    rows = [{"projectionId": "o1", "playerId": "P1", "league": "CFB", "sportFamily": "gridiron",
             "market": "pass_yds", "eventId": "E", "teamId": "T"}]
    reqs = [{"request_id": "R-EVENT", "scope": "EVENT", "scope_id": "E", "eventId": "E",
             "dependent_offer_ids": ["o1"]}]
    healthy = default_cfb_source_health()
    sick = default_cfb_source_health()
    for _ in range(3):
        sick.record_failure("CFB_OFFICIAL_GAMEBOOK", reason="timeout")
    assert sick._state["CFB_OFFICIAL_GAMEBOOK"]["circuitState"] == CIRCUIT_OPEN
    a_ok = build(rows, reqs, source_health=healthy)
    a_bad = build(rows, reqs, source_health=sick)
    ev_ok = next(x for x in a_ok["actions"] if x["scope"] == "EVENT")
    ev_bad = next(x for x in a_bad["actions"] if x["scope"] == "EVENT")
    assert ev_ok["sourceId"] != ev_bad["sourceId"] or ev_ok["expectedGain"] != ev_bad["expectedGain"]
    assert ev_ok["sourceId"] == "CFB_OFFICIAL_GAMEBOOK"
    assert ev_bad["sourceId"] != "CFB_OFFICIAL_GAMEBOOK"
    assert float(ev_bad["expectedGain"]) <= float(ev_ok["expectedGain"])


def test_half_open_is_one_trial():
    health = default_cfb_source_health()
    for sid in ("CFB_OFFICIAL_GAMEBOOK", "CFB_SPORTS_REFERENCE", "CFB_STATUS"):
        for _ in range(3):
            health.record_failure(sid, reason="timeout")
        health._state[sid]["openUntil"] = "2000-01-01T00:00:00+00:00"
        health._refresh_circuit(health._state[sid])
        assert health._state[sid]["circuitState"] == CIRCUIT_HALF_OPEN
    routed = health.route(claim_type="SUBJECT", sport="CFB")
    half = [s for s in routed if health._state[s]["circuitState"] == CIRCUIT_HALF_OPEN]
    assert len(half) <= 1


def test_market_execution_matrix_not_hardcoded_and_all_active():
    src = Path(__file__).resolve().parents[1] / "dcm" / "cfb" / "markets.py"
    text = src.read_text(encoding="utf-8")
    assert '"championProducer": True' not in text
    assert '"ParameterSnapshot": True' not in text
    assert '"EventWorldPrimitive": True' not in text
    matrix = cfb_market_execution_matrix()
    assert matrix["provenFromRuntime"] is True
    assert set(matrix["active"]) == set(ACTIVE_CFB_MARKETS)
    assert matrix["allActiveComplete"] is True
    assert not matrix["demoted"]
    assert len(matrix["rows"]) == 19
    for row in matrix["rows"]:
        assert all(row["stages"].values()), row


def test_runner_uses_joint_cfb_for_one_player():
    src = Path(__file__).resolve().parents[1] / "dcm" / "runner.py"
    text = src.read_text(encoding="utf-8")
    assert "use_joint_cfb = family == \"gridiron\" and league == \"CFB\" and len(group) >= 2" not in text
    assert "bool(str(row.get(\"eventId\") or \"\"))" in text


def test_incremental_research_os_skips_static_rebuild(tmp_path: Path):
    from dcm.cfb.launch import prepare_cfb_research_os

    rows = [_cfb_row("QB", "pass_yds", "QB1")]
    reqs = [{"request_id": "R1", "scope": "EVENT", "scope_id": "E1", "eventId": "E1"}]
    dest = tmp_path / "os"
    dest.mkdir()
    first = prepare_cfb_research_os(dest, rows, reqs, claims=[])
    assert first["staticReused"] is False
    second = prepare_cfb_research_os(dest, rows, reqs, claims=[])
    assert second["staticReused"] is True
    assert second["dynamicReused"] is True
    assert second["actionsReused"] is True
    assert (dest / "research_os_state.json").is_file()
    third = prepare_cfb_research_os(dest, rows, reqs, claims=[], frontier_offer_ids_set={"o1"})
    assert third["staticReused"] is True
    assert third["dynamicReused"] is True
    assert third["actionsReused"] is False


def test_warm_reuse_hits_l5_after_ephemeral_clear(tmp_path: Path):
    catalog = DriveObjectCatalog(tmp_path)
    cascade = ResearchCacheCascade(tmp_path, drive=catalog)
    cascade.put("EVENT", "E1", {"claim_type": "EVENT", "claim_value": {"scheduled_start": "x"},
                                "observed_at": "2026-09-01T00:00:00Z"}, claim_type="EVENT")
    catalog.persist(tmp_path)
    cascade.clear_ephemeral()
    rec, layer = cascade.get("EVENT", "E1", claim_type="EVENT")
    assert rec is not None
    assert layer == "L5"
    snap = cascade.snapshot()
    assert snap["hits"]["L5"] >= 1
    cascade.close()


def test_facts_hash_to_feature_hash_chain():
    a = resolve_material_facts([
        {"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "STATUS", "claim_value": "ACTIVE", "authority": "OFFICIAL"},
    ])
    b = resolve_material_facts([
        {"semantic_scope": "SUBJECT", "scope_id": "QB1", "claim_type": "STATUS", "claim_value": "OUT", "authority": "OFFICIAL"},
    ])
    assert a["contentHash"] != b["contentHash"]
    fa, fb = facts_to_features(a), facts_to_features(b)
    assert fa and fb
    assert fa[0]["materialFactHash"] != fb[0]["materialFactHash"]
    assert fa[0]["contentHash"] != fb[0]["contentHash"]
    assert fa[0]["name"] == "status"
