from __future__ import annotations

from pathlib import Path

import pytest

from dcm.ingest.har import ingest_har
from dcm.runner import SOFTWARE, main, run_dcm
from dcm.runtime.cutoff import HARDCODED_STALE_CUTOFF, CutoffRequired, derive_cutoff_from_capture
from dcm.version import ExactVersionMismatch, resolve_requested_version

ROOT = Path(__file__).resolve().parents[1]
COMPACT = ROOT / "fixtures" / "sanitized_live_har" / "prizepicks_compact.har"
REPO = Path(__file__).resolve().parents[3]


def test_version_mismatch_refuses_to_run(tmp_path: Path):
    rc = main([
        "--synthetic",
        "--research", "fixture",
        "--cutoff", "2026-08-29T16:00:00Z",
        "--version", "9.9.9-not-this-build",
        "--out", str(tmp_path / "out"),
        "--workspace", str(tmp_path),
    ])
    assert rc == 2
    with pytest.raises(ExactVersionMismatch):
        resolve_requested_version("9.9.9-not-this-build")


def test_version_exact_software_and_short_alias():
    full = resolve_requested_version(SOFTWARE)
    assert full["defaulted"] is False
    assert full["resolved"] == SOFTWARE
    short = resolve_requested_version("6.0.0")
    assert short["resolved"] == SOFTWARE
    omitted = resolve_requested_version(None)
    assert omitted["defaulted"] is True
    assert omitted["resolved"] == SOFTWARE


def test_missing_cutoff_without_derive_flag_fails(tmp_path: Path):
    rc = main([
        "--synthetic",
        "--research", "fixture",
        "--out", str(tmp_path / "out"),
        "--workspace", str(tmp_path),
    ])
    assert rc == 2


def test_cutoff_from_capture_uses_har_started(tmp_path: Path):
    raw = COMPACT.read_bytes()
    ing = ingest_har(raw, raw_bytes=raw)
    derived = derive_cutoff_from_capture(ing)
    assert derived
    assert derived != HARDCODED_STALE_CUTOFF
    result = run_dcm(
        input_path=COMPACT,
        forecast_cutoff=None,
        cutoff_from_capture=True,
        output_root=tmp_path / "RUNS",
        research="fixture",
        workspace=tmp_path,
        account_only=True,
    )
    dest = Path(result["dest"])
    import json
    board = json.loads((dest / "board.json").read_text())
    assert board["forecastCutoff"] == derived


def test_cutoff_from_capture_preserves_fractional_capture_end():
    """The captured board must not be rejected by its own derived cutoff."""
    ingest = {
        "captureStart": "2026-09-05T21:23:38.615Z",
        "captureEnd": "2026-09-05T21:24:07.344Z",
        "rows": [],
    }
    assert derive_cutoff_from_capture(ingest) == "2026-09-05T21:24:07.344Z"


def test_explicit_cutoff_used(tmp_path: Path):
    explicit = "2026-08-29T16:00:00Z"
    result = run_dcm(
        input_path=COMPACT,
        forecast_cutoff=explicit,
        cutoff_from_capture=True,
        output_root=tmp_path / "RUNS",
        research="fixture",
        workspace=tmp_path,
        account_only=True,
    )
    import json
    board = json.loads((Path(result["dest"]) / "board.json").read_text())
    assert board["forecastCutoff"] == explicit


def test_stale_hardcoded_cutoff_gone_from_cli():
    runner = (ROOT / "dcm" / "runner.py").read_text(encoding="utf-8")
    har_run = (ROOT / "dcm" / "runtime" / "har_run.py").read_text(encoding="utf-8")
    assert 'default="2026-08-28T00:00:00Z"' not in runner
    assert 'default="2026-08-28T00:00:00Z"' not in har_run
    ui_run = REPO / "src" / "lib" / "dcm" / "python-run.ts"
    ui_console = REPO / "src" / "components" / "dcm" / "operator-console.tsx"
    if ui_run.is_file():
        src = ui_run.read_text(encoding="utf-8")
        assert "2026-08-28T00:00:00Z" not in src
        assert "2026-08-28T23:59:59Z" not in src
    if ui_console.is_file():
        src = ui_console.read_text(encoding="utf-8")
        assert 'useState("2026-08-28T23:59:59Z")' not in src
        assert 'useState("2026-08-28T00:00:00Z")' not in src
