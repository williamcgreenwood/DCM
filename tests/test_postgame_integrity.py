from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.learning.postgame import settle_run
from dcm.runner import run_dcm

CUTOFF = "2026-08-29T00:00:00Z"


def _make_run(tmp_path: Path) -> Path:
    result = run_dcm(
        input_path=None,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs",
        synthetic=True,
        research="fixture",
        workspace=tmp_path / "workspace",
    )
    return Path(result["dest"])


def test_postgame_verifies_frozen_run_and_hashes_outcome_source(tmp_path: Path):
    run_dir = _make_run(tmp_path)
    outcomes = tmp_path / "outcomes.json"
    outcomes.write_text('{"outcomes": []}\n', encoding="utf-8")
    result = settle_run(run_dir, outcomes)
    assert result["summary"]["frozenRunVerified"] is True
    assert result["summary"]["platformSettlementComputed"] is False
    assert len(result["summary"]["outcomesSha256"]) == 64


def test_postgame_rejects_tampered_full_population(tmp_path: Path):
    run_dir = _make_run(tmp_path)
    pop = run_dir / "full_population.jsonl"
    rows = [json.loads(line) for line in pop.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    rows[0]["line"] = float(rows[0].get("line") or 0.0) + 1.0
    pop.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    outcomes = tmp_path / "outcomes.json"
    outcomes.write_text('{"outcomes": []}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="FROZEN_FORECAST_SEMANTIC_HASH_MISMATCH"):
        settle_run(run_dir, outcomes)


def test_postgame_rejects_tampered_hash_sidecar(tmp_path: Path):
    run_dir = _make_run(tmp_path)
    (run_dir / "frozen_forecast.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    outcomes = tmp_path / "outcomes.json"
    outcomes.write_text('{"outcomes": []}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="FROZEN_FORECAST_SIDECAR_HASH_MISMATCH"):
        settle_run(run_dir, outcomes)
