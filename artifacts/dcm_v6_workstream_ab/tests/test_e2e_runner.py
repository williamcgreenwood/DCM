"""E2E runner acceptance Tests A–J. Additive; does not retire WSAB_BASELINE_46."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.identity.resolve import resolve_row
from dcm.ingest.har import ingest_har
from dcm.learning.sidecar import mutate_forecast
from dcm.model.distributions import from_worlds
from dcm.model.grade import grade
from dcm.model.worlds import sample_basketball, simulate_player_worlds, value_from_stats
from dcm.research.claims import claim_record
from dcm.research.temporal import TemporalLeakError, assert_not_after_cutoff
from dcm.runner import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE, run_dcm
from dcm.runtime.checkpoint import load_checkpoint
from dcm.runtime.dag import Dag
from dcm.sports.baseball.pa import PRODUCTION_STATE, conservation as mlb_conservation
from dcm.sports.basketball.minimal import basketball_conservation

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "synthetic_har.json"
CUTOFF = "2026-08-29T00:00:00Z"


def _synthetic_har(rows: list[dict]) -> dict:
    return {
        "_pillars": {"kind": "SYNTHETIC_HAR", "note": "generated-test"},
        "log": {
            "version": "1.2",
            "creator": {"name": "pillars-test", "version": "1"},
            "entries": [
                {
                    "startedDateTime": "2026-08-28T16:00:00.000Z",
                    "request": {
                        "method": "GET",
                        "url": "https://api.prizepicks.com/projections",
                        "headers": [{"name": "Accept", "value": "application/json"}],
                    },
                    "response": {
                        "status": 200,
                        "headers": [{"name": "Content-Type", "value": "application/json"}],
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({"data": rows}),
                        },
                    },
                }
            ],
        },
    }


def _row(**kwargs) -> dict:
    base = {
        "projectionId": "p0",
        "sportFamily": "basketball",
        "league": "NBA",
        "eventId": "E1",
        "eventLabel": "A @ B",
        "playerId": "P1",
        "playerName": "Player One",
        "teamId": "AAA",
        "team": "AAA",
        "opponent": "BBB",
        "market": "pts",
        "marketLabel": "Points",
        "line": 20.5,
        "side": "MORE",
        "offeredHigher": True,
        "offeredLower": True,
        "modifier": "STANDARD",
        "boardId": "FULL_GAME",
        "productType": "PLAYER_PICKS",
        "role": "G",
    }
    base.update(kwargs)
    return base


def test_a_synthetic_smoke(tmp_path: Path):
    result = run_dcm(
        input_path=None,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path,
        synthetic=True,
        research="fixture",
    )
    assert result["runState"] in {"COMPLETE_FROZEN", "COMPLETE_WITH_UNSUPPORTED_ROWS", "EMPTY_CARD_COMPLETE", "RESEARCHED_MODELED_CARD", "RESEARCHED_MODELED_TOP25"}
    dest = Path(result["dest"])
    for name in (
        "board.json",
        "research_requests.json",
        "evidence/claims.json",
        "top25_ranked.json",
        "top25_qualified.json",
        "strict_card.json",
        "production_certified_card.json",
        "directional_passes.json",
        "frozen_forecast.json",
        "run_integrity.json",
        "checkpoint.json",
        "full_population.jsonl",
    ):
        assert (dest / name).is_file(), name
    integ = result["integrity"]
    assert integ["learningRevision"] == "LR000000"
    assert integ["predictiveClaim"] == "NONE"
    assert integ["optimizedDcm60Claim"] is False
    assert integ["hostPerformanceCertified"] is False
    assert integ["chatgptOperable"] is True
    assert integ["rawRows"] == 6
    assert integ["accounting"]["goblin_rows"] == 1
    board = json.loads((dest / "board.json").read_text())
    assert board["accounting"]["raw_projection_rows"] == 6
    card = json.loads((dest / "strict_card.json").read_text())
    assert all(p["modifier"] != "GOBLIN" for p in card)
    freeze = json.loads((dest / "frozen_forecast.json").read_text())
    assert freeze["v5Decoder"] == "NOT_MOUNTED"
    assert freeze["productionCertified"] is False
    assert freeze["notProductionRootCertified"] is True
    assert freeze["executionMode"] == "RESEARCHED_MODELED"
    certified = json.loads((dest / "production_certified_card.json").read_text())
    assert certified == []
    if freeze["cardSize"] == 0:
        assert freeze.get("emptyCardReason") in {"EMPTY_NO_PLAYABLES", "EMPTY_RESEARCH_INCOMPLETE", "EMPTY_PORTFOLIO_CONSTRAINT"}


def test_b_real_har_sanitized_fixture_is_supplied():
    live = Path(__file__).resolve().parents[1] / "fixtures" / "sanitized_live_har" / "prizepicks_compact.har"
    assert live.is_file(), "sanitized live HAR fixture missing"
    from dcm.ingest.har import ingest_har
    ing = ingest_har(live.read_bytes(), raw_bytes=live.read_bytes())
    assert ing["rows"], "compact live HAR must parse projections"
    assert ing["adapter"] == "PRIZEPICKS_JSONAPI"


def test_c_thousand_row_board_accounts_every_row(tmp_path: Path):
    rows = []
    for i in range(250):
        rows.append(_row(projectionId=f"nba{i}", playerId=f"N{i}", playerName=f"Nba {i}", eventId=f"NBA_{i // 10}", market="pts"))
    for i in range(250):
        rows.append(
            _row(
                projectionId=f"nfl{i}",
                sportFamily="gridiron",
                league="NFL",
                playerId=f"F{i}",
                playerName=f"Nfl {i}",
                eventId=f"NFL_{i // 10}",
                market="pass_yds",
                marketLabel="Passing Yards",
                line=250.5,
                role="QB",
            )
        )
    for i in range(200):
        rows.append(
            _row(
                projectionId=f"soc{i}",
                sportFamily="soccer",
                league="EPL",
                playerId=f"S{i}",
                playerName=f"Soc {i}",
                eventId="EPL_X",
                market="shots",
                marketLabel="Shots",
                line=2.5,
            )
        )
    for i in range(150):
        rows.append(_row(projectionId=f"gob{i}", playerId=f"G{i}", playerName=f"Gob {i}", modifier="GOBLIN", line=12.5))
    for i in range(150):
        rows.append(
            _row(
                projectionId=f"mlb{i}",
                sportFamily="baseball",
                league="MLB",
                playerId=f"M{i}",
                playerName=f"Mlb {i}",
                eventId="MLB_X",
                market="hits_runs_rbi",
                marketLabel="Hits+Runs+RBIs",
                line=0.5,
                role="BAT",
            )
        )
    assert len(rows) == 1000
    har = _synthetic_har(rows)
    path = tmp_path / "big.har.json"
    path.write_text(json.dumps(har), encoding="utf-8")
    result = run_dcm(input_path=path, forecast_cutoff=CUTOFF, output_root=tmp_path / "out", research="fixture")
    classified = result["classified"]
    assert len(classified) == 1000
    allowed = {"MODELED", "UNSUPPORTED", "UNRESOLVED", "EXCLUDED_GOBLIN"}
    states = {c["state"] for c in classified}
    assert states <= allowed
    assert all(c["state"] in allowed for c in classified)
    assert sum(1 for c in classified if c["state"] == "EXCLUDED_GOBLIN") == 150
    assert sum(1 for c in classified if c["state"] == "UNSUPPORTED") == 200
    assert sum(1 for c in classified if c["state"] == "UNRESOLVED") == 150
    assert sum(1 for c in classified if c["state"] == "MODELED") == 500


def test_d_line_change_invalidates_descendants_not_research():
    dag = Dag(
        cutoff=CUTOFF,
        config_hash="cfg",
        schema_version="PHASE_BC_SCHEMA_V1_2026-08-25",
        source_versions={"har": "aaa", "parser": "v", "software": SOFTWARE},
    )
    research = dag.add("EVENT_RESEARCH", "e1")
    dag.complete(research.key, "research-hash")
    hist = dag.add("PLAYER_HISTORY", "p1")
    dag.complete(hist.key, "hist-hash")
    line = dag.add("MARKET_LINE", "m1", parents=[research.key])
    dag.complete(line.key, "line-hash")
    grade_n = dag.add("GRADE", "m1", parents=[line.key])
    dag.complete(grade_n.key, "grade-hash")
    freeze = dag.add("FREEZE", "board", parents=[grade_n.key])
    dag.complete(freeze.key, "freeze-hash")
    hit = dag.invalidate_line_descendants()
    assert dag.nodes[research.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[hist.key].state == "COMPLETE_VERIFIED"
    assert dag.nodes[line.key].state == "INVALIDATED"
    assert dag.nodes[grade_n.key].state == "INVALIDATED"
    assert dag.nodes[freeze.key].state == "INVALIDATED"
    assert research.key not in hit


def test_e_checkpoint_resume_matches_uninterrupted(tmp_path: Path):
    a = run_dcm(input_path=None, forecast_cutoff=CUTOFF, output_root=tmp_path / "a", synthetic=True, research="fixture")
    incomplete = run_dcm(
        input_path=None,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "b",
        synthetic=True,
        research="file",
        evidence_dir=tmp_path / "empty-evidence",
    )
    assert incomplete["runState"] == "INCOMPLETE_CHECKPOINTED"
    manifest = json.loads((Path(incomplete["dest"]) / "input_manifest.json").read_text())
    assert manifest["synthetic"] is True
    assert manifest["sourceMode"] == "SYNTHETIC"
    ck_path = Path(incomplete["dest"]) / "checkpoint.json"
    ck = load_checkpoint(ck_path)
    assert ck["learningRevision"] == LEARNING_REVISION
    resumed = run_dcm(
        input_path=None,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "b",
        research="fixture",
        resume=ck_path,
    )
    assert resumed["runState"] in {"COMPLETE_FROZEN", "COMPLETE_WITH_UNSUPPORTED_ROWS", "EMPTY_CARD_COMPLETE", "RESEARCHED_MODELED_CARD", "RESEARCHED_MODELED_TOP25"}
    assert resumed["integrity"]["frozenForecastHash"] == a["integrity"]["frozenForecastHash"]
    assert resumed["integrity"]["predictiveClaim"] == PREDICTIVE_CLAIM


def test_f_zero_playable_returns_empty_card(tmp_path: Path):
    rows = [
        _row(projectionId="g1", modifier="GOBLIN", playerId="G1"),
        _row(
            projectionId="s1",
            sportFamily="soccer",
            league="EPL",
            market="shots",
            playerId="S1",
            playerName="Saka",
        ),
    ]
    path = tmp_path / "empty.har.json"
    path.write_text(json.dumps(_synthetic_har(rows)), encoding="utf-8")
    result = run_dcm(input_path=path, forecast_cutoff=CUTOFF, output_root=tmp_path / "out", research="fixture")
    assert result["runState"] in {"EMPTY_CARD_COMPLETE", "COMPLETE_WITH_UNSUPPORTED_ROWS", "RESEARCHED_MODELED_CARD", "RESEARCHED_MODELED_TOP25"}
    assert result["integrity"]["cardSize"] == 0
    assert result["card"] == []
    assert result["integrity"]["playable"] == 0
    assert result["integrity"]["productionCertified"] is False
    assert result["integrity"].get("emptyCardReason") in {"EMPTY_NO_PLAYABLES", "EMPTY_RESEARCH_INCOMPLETE"}


def test_g_demon_is_demotion_only():
    std = grade(
        selected_p=0.59,
        lower_bound=0.53,
        demon=False,
        fragility=0.18,
        robustness_area=2.0,
        elasticity=0.1,
        false_sign=0.1,
    )
    demon = grade(
        selected_p=0.59,
        lower_bound=0.53,
        demon=True,
        fragility=0.42,
        robustness_area=0.4,
        elasticity=0.4,
        false_sign=0.3,
    )
    assert std == "PLAYABLE"
    assert demon != "PLAYABLE"
    assert demon in {"LEAN", "PASS", "TRAP"}


def test_h_simplex_push_aware():
    d = from_worlds([1.0, 2.0, 2.0, 3.0], 2.0)
    assert d["pHigher"] == 0.25
    assert d["pLower"] == 0.25
    assert d["pPush"] == 0.5
    assert abs(d["pHigher"] + d["pLower"] + d["pPush"] - 1.0) < 1e-12
    d2 = from_worlds([10.0, 11.0, 12.0], 10.5)
    assert abs(d2["pHigher"] + d2["pLower"] + d2["pPush"] - 1.0) < 1e-12
    assert d2["pLower"] != pytest.approx(1.0 - d2["pHigher"]) or d2["pPush"] == 0.0


def test_i_pra_equals_pts_reb_ast_every_world():
    rng = __import__("random").Random(7)
    for _ in range(32):
        w = sample_basketball(rng, 34.0)
        assert abs(w["pra"] - (w["pts"] + w["reb"] + w["ast"])) < 1e-9
        assert abs(value_from_stats("pra", w) - (w["pts"] + w["reb"] + w["ast"])) < 1e-9
        assert all(r.passed for r in basketball_conservation(w))
    row = _row(market="pra", playerId="TATUM", eventId="NBA_BOS_NYK")
    worlds = simulate_player_worlds(row, n=48, seed="test")
    for w in worlds:
        assert abs(value_from_stats("pra", w) - (w["pts"] + w["reb"] + w["ast"])) < 1e-9


def test_j_unsupported_sport_accounted_not_dropped():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ing = ingest_har(raw, raw_bytes=FIXTURE.read_bytes())
    ids = {r["projectionId"] for r in ing["rows"]}
    assert "s1" in ids
    soccer = next(r for r in ing["rows"] if r["projectionId"] == "s1")
    assert soccer["sportFamily"] == "soccer"


def test_j_cfb_name_is_not_official_player_id():
    row = resolve_row(
        _row(
            sportFamily="gridiron",
            league="CFB",
            playerId="SAYIN_SRC",
            playerName="Julian Sayin",
            market="pass_yds",
        )
    )
    assert row["cfbOfficialNameListed"] is True
    assert row["cfbOfficialPlayerId"] is None
    assert row["playerId"] == "SAYIN_SRC"
    assert row["identityBlocker"] == "CFB_OFFICIAL_PLAYER_ID_ABSENT"


def test_temporal_leak_fails_closed():
    with pytest.raises(TemporalLeakError):
        assert_not_after_cutoff("2026-08-29T00:00:01Z", CUTOFF)
    with pytest.raises(TemporalLeakError):
        claim_record(
            source_id="x",
            url="https://example.invalid",
            published_at="2026-08-29T12:00:00Z",
            observed_at="2026-08-29T12:00:00Z",
            forecast_cutoff=CUTOFF,
            semantic_scope="PLAYER",
            scope_id="p",
            claim_type="box_score",
            claim_value={"pts": 40},
            reliability=0.4,
            freshness=0.1,
        )


def test_corruption_basketball_and_baseball_fail():
    bad = sample_basketball(__import__("random").Random(1), 34.0)
    bad["fgm"] = bad["fga"] + 5
    assert not all(r.passed for r in basketball_conservation(bad))
    mlb = {
        "PA": 4,
        "AB": 4,
        "BB": 0,
        "HBP": 0,
        "SF": 0,
        "SH": 0,
        "SO": 1,
        "H": 9,
        "1B": 1,
        "2B": 0,
        "3B": 0,
        "HR": 0,
        "TB": 1,
    }
    failed = [c["rule_id"] for c in mlb_conservation(mlb) if not c["passed"]]
    assert "H" in failed
    assert PRODUCTION_STATE == "SHADOW_SUPPORTED"


def test_append_only_learning_refuses_mutation(tmp_path: Path):
    with pytest.raises(RuntimeError, match="APPEND_ONLY"):
        mutate_forecast(tmp_path / "frozen_forecast.json")


def test_software_version_does_not_promote_lr():
    assert LEARNING_REVISION == "LR000000"
    assert PREDICTIVE_CLAIM == "NONE"
    assert "E2E" in SOFTWARE
    assert "OPTIMIZED" not in SOFTWARE


def test_resume_rejects_tampered_frozen_model_config(tmp_path: Path):
    incomplete = run_dcm(
        input_path=None,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "tamper",
        synthetic=True,
        research="file",
        evidence_dir=tmp_path / "empty-evidence",
    )
    assert incomplete["runState"] == "INCOMPLETE_CHECKPOINTED"
    dest = Path(incomplete["dest"])
    config_path = dest / "MODEL_CONFIG.json"
    config = json.loads(config_path.read_text())
    config["fastWorlds"] = int(config["fastWorlds"]) + 1
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(RuntimeError, match="MODEL_CONFIG_HASH_MISMATCH_ON_RESUME"):
        run_dcm(
            input_path=None,
            forecast_cutoff=CUTOFF,
            output_root=tmp_path / "tamper",
            research="fixture",
            resume=dest / "checkpoint.json",
        )
