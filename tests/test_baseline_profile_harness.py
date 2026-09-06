"""Smoke tests for Phase 9 baseline profiler harness (not certification)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmarks" / "baseline" / "profile_baseline.py"


def test_baseline_profiler_smoke(tmp_path: Path):
    out = tmp_path / "baseline"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--smoke",
            "--out",
            str(out),
            "--tag",
            "smoke",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**dict(**__import__("os").environ), "PYTHONPATH": str(ROOT / "src")},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    summary = json.loads(proc.stdout)
    assert summary["ok"] is True
    assert summary["hostPerformanceCertified"] is False
    json_path = Path(summary["json"])
    md_path = Path(summary["markdown"])
    assert json_path.is_file()
    assert md_path.is_file()
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["schema"] == "pillars_dcm.baseline_profile.v1"
    assert report["hostPerformanceCertified"] is False
    assert report["boardSizes"] == [100]
    assert report["worldSizes"] == [64]
    assert report["boardStore"]
    assert report["compact"]
    assert report["eventWorld"]
    assert report["cacheAndDag"]["cacheHits"] >= 0
    assert report["hotspots"]
    assert "Phase 9" in md_path.read_text(encoding="utf-8") or "baseline" in md_path.read_text(encoding="utf-8").lower()


def test_baseline_profiler_importable_helpers():
    # Ensure module imports under package path without executing main.
    import importlib.util

    spec = importlib.util.spec_from_file_location("dcm_baseline_profile", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = mod._synthetic_cfb_rows(10)
    assert len(rows) == 10
    assert rows[0]["league"] == "CFB"
    specs = mod._cfb_team_specs(4)
    assert len(specs) == 4
