"""Run-scoped cutoff bypass never changes the production default."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.research.claims import claim_record
from dcm.research.test_mode import cutoff_enforced, load_test_mode, production_eligible
from dcm.research.temporal import TemporalLeakError


CUTOFF = "2026-09-08T18:34:52.067Z"
AFTER = "2026-09-10T19:59:05Z"


def test_default_mode_enforces_cutoff_and_claim_bypass_is_marked():
    with pytest.raises(TemporalLeakError, match="TEMPORAL_LEAK"):
        claim_record(
            source_id="NFL_OFFICIAL",
            url="https://www.nfl.com/games/patriots-at-seahawks-2026-reg-1",
            published_at=AFTER,
            observed_at=AFTER,
            forecast_cutoff=CUTOFF,
            semantic_scope="EVENT",
            scope_id="162474",
            claim_type="event_context",
            claim_value={"status": "FINAL"},
            reliability=0.95,
            freshness=0.0,
        )

    claim = claim_record(
        source_id="NFL_OFFICIAL",
        url="https://www.nfl.com/games/patriots-at-seahawks-2026-reg-1",
        published_at=AFTER,
        observed_at=AFTER,
        forecast_cutoff=CUTOFF,
        semantic_scope="EVENT",
        scope_id="162474",
        claim_type="event_context",
        claim_value={"status": "FINAL"},
        reliability=0.95,
        freshness=0.0,
        enforce_cutoff=False,
    )
    assert claim["testOnlyCutoffBypass"] is True
    assert claim["productionEligible"] is False


def test_run_policy_is_bound_and_fail_closed(tmp_path: Path):
    assert cutoff_enforced(tmp_path) is True
    assert production_eligible(tmp_path) is True
    (tmp_path / "test_mode.json").write_text(
        json.dumps(
            {
                "schema": "pillars_dcm.research_test_mode.v1",
                "runId": tmp_path.name,
                "cutoffBypass": True,
                "testOnlyCutoffBypass": True,
                "productionEligible": False,
                "predictiveClaim": "NONE",
                "reason": "historical integration test only",
            }
        ),
        encoding="utf-8",
    )
    assert cutoff_enforced(tmp_path) is False
    assert production_eligible(tmp_path) is False
    bad = json.loads((tmp_path / "test_mode.json").read_text(encoding="utf-8"))
    bad["runId"] = "OTHER_RUN"
    (tmp_path / "test_mode.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="TEST_MODE_INVALID"):
        load_test_mode(tmp_path)
