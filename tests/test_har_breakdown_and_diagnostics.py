"""Structural HAR profiling and sanitized runtime diagnostics tests."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.research.har_breakdown import build_har_breakdown, safe_parse_har
from dcm.runtime.diagnostics import build_diagnostics, write_diagnostics


def _har() -> dict:
    body = {
        "data": [
            {"id": "event-1", "event_id": "event-1", "scheduled_start": "2026-09-08T19:00:00Z", "home_team": "H", "away_team": "A"},
            {"id": "event-2", "event_id": "event-2", "scheduled_start": "2026-09-08T20:00:00Z", "home_team": "J", "away_team": "B"},
        ]
    }
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "test", "version": "1"},
            "entries": [
                {
                    "startedDateTime": "2026-09-08T18:00:00Z",
                    "time": 1,
                    "request": {
                        "method": "GET",
                        "url": "https://example.test/events?token=must-not-persist",
                        "headers": [{"name": "Authorization", "value": "Bearer secret-value"}],
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {"mimeType": "application/json", "text": json.dumps(body)},
                    },
                }
            ],
        }
    }


def test_har_breakdown_is_whole_capture_safe_and_reproducible(tmp_path: Path):
    path = tmp_path / "capture.har"
    path.write_text(json.dumps(_har()), encoding="utf-8")
    parsed = safe_parse_har(path)
    assert parsed["entryCount"] == 1
    first = build_har_breakdown(path, run_id="RUN", output_path=tmp_path / "first.json")
    second = build_har_breakdown(path, run_id="RUN", output_path=tmp_path / "second.json")
    assert first["receipt"] == second["receipt"]
    assert first["breakdown"]["privacy"]["rawUrlsPersisted"] is False
    assert first["breakdown"]["privacy"]["rawBodiesPersisted"] is False
    assert first["breakdown"]["privacy"]["secretHeaderCount"] >= 1
    assert first["breakdown"]["recordDigest"]
    encoded = (tmp_path / "first.json").read_text(encoding="utf-8")
    assert "secret-value" not in encoded
    assert "example.test" not in encoded


def test_diagnostics_redact_secrets_urls_and_keep_recovery_metadata(tmp_path: Path):
    try:
        raise RuntimeError("token=private-token https://private.example/path")
    except RuntimeError as exc:
        payload = build_diagnostics(
            command="research-batch",
            exit_code=1,
            failure_code="SOURCE_RATE_LIMITED",
            exc=exc,
            context={"apiToken": "secret", "url": "https://private.example/path", "affectedIds": ["AA_1"]},
        )
    path = tmp_path / "diagnostics.json"
    saved = write_diagnostics(path, payload)
    encoded = path.read_text(encoding="utf-8")
    assert saved["failureCode"] == "SOURCE_RATE_LIMITED"
    assert saved["exception"]["message"] != "token=private-token https://private.example/path"
    assert "private-token" not in encoded
    assert "private.example" not in encoded
    assert saved["recoveryCommand"]
    assert saved["contentHash"]
