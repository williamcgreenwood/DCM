"""Checkpoint → evidence_bundle.jsonl → --resume --research bundle → snapshots → model → freeze."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.research.claims import claim_record
from dcm.research.provider import write_bundle
from dcm.runner import run_dcm

ROOT = Path(__file__).resolve().parents[1]
COMPACT = ROOT / "fixtures" / "sanitized_live_har" / "prizepicks_compact.har"
CUTOFF = "2026-08-29T16:00:00Z"


def _frozen_claim(req: dict) -> dict:
    scope = req["scope"]
    if scope == "SPORT":
        value = {"distribution_family": "count", "overtime": "INCLUDE_FULL_GAME", "rules_or_distribution_context": True}
    elif scope == "EVENT":
        value = {
            "event_context": True,
            "starters_known": True,
            "environment": "indoor",
            "scheduled_start": "2026-08-28T23:00:00Z",
            "venue": "test-arena",
            "surface": "wood",
        }
    elif scope == "TEAM":
        value = {
            "team_context": True,
            "pace_multiplier": 1.0,
            "matchup_efficiency_multiplier": 1.0,
            "injury_cluster": False,
            "plays": 65,
        }
    elif scope == "PLAYER":
        value = {
            "status": "ACTIVE",
            "role": "starter",
            "opportunity": {"support_n": 3, "minutes_mean": 30.0},
            "efficiency": {"support_n": 3},
            "role_epoch_logs": [
                {"minutes": 28, "fga": 12, "pass_att": 30, "role": "starter"},
                {"minutes": 31, "fga": 14, "pass_att": 32, "role": "starter"},
                {"minutes": 29, "fga": 11, "pass_att": 28, "role": "bench"},
            ],
        }
    elif scope == "MARKET_DEFINITION":
        value = {"definition_verified": True}
    else:
        value = {"offer_recorded": True, "line": req.get("line")}
    return claim_record(
        source_id="TEST_FROZEN_OFFICIAL",
        url="https://www.wnba.com/test-frozen-bundle",
        published_at="2026-08-28T00:00:00Z",
        observed_at="2026-08-28T12:00:00Z",
        forecast_cutoff=str(req["forecast_cutoff"]),
        semantic_scope=scope,
        scope_id=str(req["scope_id"]),
        claim_type=str(req["need"]),
        claim_value=value,
        reliability=0.8,
        freshness=0.7,
    )


def test_checkpoint_bundle_resume_validate_snapshot_model_freeze(tmp_path: Path):
    first = run_dcm(
        input_path=COMPACT,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "RUNS",
        research="file",
        evidence_dir=tmp_path / "empty-evidence",
        workspace=tmp_path,
    )
    assert first["runState"] == "INCOMPLETE_CHECKPOINTED"
    dest = Path(first["dest"])
    requests = json.loads((dest / "research_requests.json").read_text())
    assert requests
    claims = [_frozen_claim(req) for req in requests]
    bundle_path = dest / "evidence_bundle.jsonl"
    write_bundle(bundle_path, claims)
    resumed = run_dcm(
        input_path=COMPACT,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "RUNS",
        research="bundle",
        bundle_path=bundle_path,
        resume=dest / "checkpoint.json",
        workspace=tmp_path,
    )
    assert resumed["runState"] in {
        "COMPLETE_FROZEN",
        "COMPLETE_WITH_UNSUPPORTED_ROWS",
        "EMPTY_CARD_COMPLETE",
        "RESEARCHED_MODELED_CARD",
        "RESEARCHED_MODELED_TOP25",
    }
    assert (dest / "parameters" / "snapshots.json").is_file()
    snaps = json.loads((dest / "parameters" / "snapshots.json").read_text())
    assert snaps
    freeze = json.loads((dest / "freeze.json").read_text())
    assert freeze["learningRevision"] == "LR000000"
    assert freeze["predictiveClaim"] == "NONE"
    assert freeze["researchComplete"] is True
    assert freeze["productionCertified"] is False
    assert freeze["executionMode"] == "RESEARCHED_MODELED"
    assert (dest / "frozen_forecast.json").is_file()
    assert json.loads((dest / "production_certified_card.json").read_text()) == []
    assert (dest / "top25_ranked.json").is_file()
