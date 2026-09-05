"""Constitution hashes are sidecar identity, not forecast-semantic fields."""
from __future__ import annotations

from dcm.runtime.freeze import _CONTEXT_FIELDS, forecast_hash_payload


def test_forecast_hash_payload_omits_constitution_fields():
    payload = forecast_hash_payload(
        {
            "runId": "r",
            "dcmVersion": "6.0.0",
            "learningRevision": "LR000000",
            "schemaId": "s",
            "schemaHash": "h",
            "modelConfigHash": "m",
            "calibrationStateHash": "c",
            "harSha256": "a" * 64,
            "forecastCutoff": "2026-09-03T00:00:00Z",
            "boardHash": "b",
            "algorithmConstitutionSha256": "should-not-appear",
            "algorithmRegistrySha256": "should-not-appear",
        },
        [],
        [],
        [],
    )
    assert "algorithmConstitutionSha256" not in _CONTEXT_FIELDS
    assert "algorithmRegistrySha256" not in _CONTEXT_FIELDS
    assert "algorithmConstitutionSha256" not in payload
    assert "algorithmRegistrySha256" not in payload
    assert payload["learningRevision"] == "LR000000"
