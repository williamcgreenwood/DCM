from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.ingest.har import ingest_har
from dcm.model.distributions import from_worlds
from dcm.model.parameters import build_parameter_snapshot
from dcm.model.worlds import simulate_player_worlds, value_from_stats
from dcm.research.claims import claim_record
from dcm.research.classify import market_definition_id
from dcm.research.population import build_research_population_manifest
from dcm.research.requests import plan_research
from dcm.research.provider import write_bundle
from dcm.learning.postgame import settle_run
from dcm.runner import run_dcm

FIXTURE = Path(__file__).resolve().parents[1] / "artifacts" / "dcm_v6_workstream_ab" / "fixtures" / "cfb_guarded_launch_har.json"
CUTOFF = "2026-09-02T18:00:00Z"


def _claim(scope: str, scope_id: str, value: dict) -> dict:
    return claim_record(
        source_id="FIXTURE_CFB_GUARDED_LAUNCH",
        url="fixture://cfb-guarded-launch",
        published_at=CUTOFF,
        observed_at=CUTOFF,
        forecast_cutoff=CUTOFF,
        semantic_scope=scope,
        scope_id=scope_id,
        claim_type="acceptance_fixture",
        claim_value=value,
        reliability=0.70,
        freshness=1.0,
    )


QB_LOGS = [
    {"date": "2025-09-01", "gs": 1, "snaps": 70, "pass_att": 31, "pass_cmp": 20, "pass_yds": 248, "rush_att": 7, "rush_yds": 32, "sacks_taken": 2, "scramble_att": 4},
    {"date": "2025-09-08", "gs": 1, "snaps": 72, "pass_att": 34, "pass_cmp": 23, "pass_yds": 281, "rush_att": 8, "rush_yds": 39, "sacks_taken": 2, "scramble_att": 5},
    {"date": "2025-09-15", "gs": 1, "snaps": 68, "pass_att": 29, "pass_cmp": 18, "pass_yds": 226, "rush_att": 6, "rush_yds": 26, "sacks_taken": 3, "scramble_att": 4},
    {"date": "2026-08-29", "gs": 1, "snaps": 69, "pass_att": 32, "pass_cmp": 21, "pass_yds": 264, "rush_att": 7, "rush_yds": 35, "sacks_taken": 2, "scramble_att": 4},
]
RB_LOGS = [
    {"date": "2025-09-01", "gs": 1, "snaps": 48, "rush_att": 16, "rush_yds": 84, "routes": 12, "targets": 3, "receptions": 2, "rec_yds": 18},
    {"date": "2025-09-08", "gs": 1, "snaps": 51, "rush_att": 18, "rush_yds": 101, "routes": 13, "targets": 4, "receptions": 3, "rec_yds": 27},
    {"date": "2025-09-15", "gs": 1, "snaps": 46, "rush_att": 15, "rush_yds": 73, "routes": 11, "targets": 2, "receptions": 2, "rec_yds": 15},
    {"date": "2026-08-29", "gs": 1, "snaps": 50, "rush_att": 17, "rush_yds": 92, "routes": 12, "targets": 3, "receptions": 2, "rec_yds": 20},
]
WR_LOGS = [
    {"date": "2025-09-01", "gs": 1, "snaps": 59, "routes": 31, "targets": 8, "receptions": 5, "rec_yds": 71, "rush_att": 1, "rush_yds": 4},
    {"date": "2025-09-08", "gs": 1, "snaps": 62, "routes": 33, "targets": 9, "receptions": 6, "rec_yds": 88, "rush_att": 0, "rush_yds": 0},
    {"date": "2025-09-15", "gs": 1, "snaps": 57, "routes": 30, "targets": 7, "receptions": 4, "rec_yds": 63, "rush_att": 1, "rush_yds": 6},
    {"date": "2026-08-29", "gs": 1, "snaps": 61, "routes": 32, "targets": 8, "receptions": 5, "rec_yds": 79, "rush_att": 0, "rush_yds": 0},
]


def _claims(rows: list[dict]) -> list[dict]:
    claims = [
        _claim("EVENT", "CFB_TEST_1", {
            "event_context": True,
            "scheduled_start": "2026-09-05T23:00:00Z",
            "venue": "Fixture Stadium",
            "surface": "grass",
            "weather": {"wind_mph": 7, "precipitation": 0},
            "spread": -17.5,
            "game_total": 55.5,
        }),
        _claim("AFFILIATION", "AAA", {
            "affiliation_context": True,
            "team_context": True,
            "plays": 72,
            "pass_rate": 0.55,
            "rush_rate": 0.45,
            "pace": 1.02,
            "depth": {"QB": "QB1", "RB": "RB1", "WR": "WR1"},
            "injury_cluster": False,
        }),
        _claim("COUNTERPARTY", "BBB", {
            "counterparty_context": True,
            "team_context": True,
            "plays": 69,
            "pace": 1.0,
            "pass_defense": 0.98,
            "rush_defense": 1.01,
            "depth": {},
            "injury_cluster": False,
        }),
        _claim("SUBJECT", "QB1", {
            "status": "ACTIVE", "role": "QB", "game_logs": QB_LOGS,
            "opportunity": {"support_n": len(QB_LOGS)}, "efficiency": {"support_n": len(QB_LOGS)},
        }),
        _claim("SUBJECT", "RB1", {
            "status": "ACTIVE", "role": "RB", "game_logs": RB_LOGS,
            "opportunity": {"support_n": len(RB_LOGS)}, "efficiency": {"support_n": len(RB_LOGS)},
        }),
        _claim("SUBJECT", "WR1", {
            "status": "ACTIVE", "role": "WR", "game_logs": WR_LOGS,
            "opportunity": {"support_n": len(WR_LOGS)}, "efficiency": {"support_n": len(WR_LOGS)},
        }),
    ]
    for row in rows:
        claims.append(_claim("MARKET_DEFINITION", market_definition_id(row), {"definition_verified": True}))
        claims.append(_claim("OFFER", str(row["projectionId"]), {"offer_recorded": True}))
    return claims


def test_cfb_guarded_launch_har_to_probability_fixture():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ingested = ingest_har(raw)
    rows = ingested["rows"]
    assert len(rows) == 8
    assert all(row["league"] == "CFB" for row in rows)

    planned = plan_research(rows, CUTOFF)
    population = build_research_population_manifest(rows, planned=planned, cutoff=CUTOFF)
    assert population["eligibleOfferCount"] == 8
    assert population["subjectOfferSetCount"] == 3
    assert population["uniqueCounts"]["events"] == 1
    assert population["uniqueCounts"]["subjects"] == 3

    claims = _claims(rows)
    modeled = 0
    for row in rows:
        snap = build_parameter_snapshot(row, claims)
        assert snap["minimum_model_support"] is True
        assert snap["model_support"]["modelable"] is True
        worlds = simulate_player_worlds(
            row,
            n=256,
            seed="CFB_GUARDED_ACCEPTANCE",
            parameter_snapshot=snap,
        )
        values = [value_from_stats(row["market"], world) for world in worlds]
        dist = from_worlds(values, float(row["line"]))
        assert abs(dist["pHigher"] + dist["pLower"] + dist["pPush"] - 1.0) < 1e-9
        assert 0.0 <= dist["pHigher"] <= 1.0
        assert 0.0 <= dist["pLower"] <= 1.0
        modeled += 1
    assert modeled == 8


def _web_claims(rows: list[dict]) -> list[dict]:
    out = []
    for claim in _claims(rows):
        out.append(claim_record(
            source_id="TEST_CFB_WEB_ACCEPTANCE",
            url="https://example.com/cfb-guarded-launch-source",
            published_at=CUTOFF,
            observed_at=CUTOFF,
            forecast_cutoff=CUTOFF,
            semantic_scope=str(claim["semantic_scope"]),
            scope_id=str(claim["scope_id"]),
            claim_type="cfb_guarded_launch_web_fixture",
            claim_value=claim["claim_value"],
            reliability=0.80,
            freshness=1.0,
        ))
    return out


def test_real_cfb_partial_global_bundle_does_not_checkpoint_supported_rows(tmp_path: Path):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw.pop("_pillars", None)  # exercise the real/non-synthetic HAR branch
    har_path = tmp_path / "cfb-real-shape.har.json"
    har_path.write_text(json.dumps(raw), encoding="utf-8")

    rows = ingest_har(raw)["rows"]
    bundle_path = tmp_path / "cfb-partial-evidence.jsonl"
    write_bundle(bundle_path, _web_claims(rows))

    result = run_dcm(
        input_path=har_path,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs",
        research="bundle",
        bundle_path=bundle_path,
        workspace=tmp_path,
    )
    assert result["runState"] != "INCOMPLETE_CHECKPOINTED"
    classified = result["classified"]
    modeled = [r for r in classified if r["state"] in {"MODELED", "MODELED_DIAGNOSTIC"}]
    assert len(modeled) == 8
    assert all(r.get("blocker") != "RESEARCH_INCOMPLETE" for r in modeled)
    partial = json.loads((Path(result["dest"]) / "research_partial.json").read_text())
    assert partial["state"] == "PARTIAL_RESEARCH_CONTINUE_CFB_PER_PROP"
    assert partial["missingRequestIds"], "test bundle must remain globally incomplete"


def test_interim_frontier_has_no_frozen_semantics_or_settlement_eligibility(tmp_path: Path):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw.pop("_pillars", None)
    har_path = tmp_path / "cfb-interim.har.json"
    har_path.write_text(json.dumps(raw), encoding="utf-8")
    rows = ingest_har(raw)["rows"]
    bundle_path = tmp_path / "cfb-interim-evidence.jsonl"
    write_bundle(bundle_path, _web_claims(rows))

    result = run_dcm(
        input_path=har_path,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs",
        research="bundle",
        bundle_path=bundle_path,
        workspace=tmp_path,
    )
    dest = Path(result["dest"])
    freeze = json.loads((dest / "freeze.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((dest / "checkpoint.json").read_text(encoding="utf-8"))
    hashes = json.loads((dest / "hashes.json").read_text(encoding="utf-8"))
    assert freeze["forecastFrozen"] is False
    assert freeze["freezeState"] == "FRONTIER_INTERIM"
    assert result["runState"] == "AWAITING_FRONTIER_RESEARCH"
    assert (dest / "frontier_checkpoint.json").is_file()
    assert not (dest / "frozen_forecast.json").exists()
    assert not (dest / "frozen_forecast.sha256").exists()
    assert "frozenForecastHash" not in hashes
    assert "frozenForecastHash" not in checkpoint
    assert checkpoint["pending"] == ["FRONTIER_RESEARCH"]
    outcomes = tmp_path / "outcomes.json"
    outcomes.write_text('{"outcomes": []}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="FORECAST_NOT_FROZEN"):
        settle_run(dest, outcomes)
