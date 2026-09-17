from __future__ import annotations

from dcm.chat.har_only_controller import build_capture_diff
from dcm.runtime.capture_authority import build_capture_authority, capture_gate_status


def _claim(*, line: float, direction: str, status: str = "SCHEDULED", body: str = "h1") -> dict:
    return {
        "claimId": f"claim-{line}-{direction}",
        "claimHash": f"hash-{line}-{direction}-{body}",
        "leagueId": "NFL",
        "eventId": "event-1",
        "subjectId": "player-1",
        "marketId": "market-1",
        "proposition": "RECEPTIONS",
        "periodLabel": "FULL_GAME",
        "line": line,
        "direction": direction,
        "eventStatus": status,
        "sourceBodyHash": body,
    }


def test_capture_authority_is_operator_controlled(tmp_path):
    har = tmp_path / "capture.har"
    har.write_text("{}", encoding="utf-8")
    authority = build_capture_authority([har])
    assert authority["status"] == "ACCEPTED"
    assert authority["replacementCaptureRequired"] is False
    assert capture_gate_status(authority) == "PASS"


def test_capture_diff_uses_internal_order_and_preserves_insights():
    captures = [
        {"captureId": "later", "sha256": "later-sha", "sportHint": "NFL", "captureStart": "2026-09-17T04:00:00Z"},
        {"captureId": "earlier", "sha256": "earlier-sha", "sportHint": "NFL", "captureStart": "2026-09-16T08:00:00Z"},
    ]
    diff = build_capture_diff(
        captures,
        [
            [_claim(line=4.5, direction="HIGHER", body="old")],
            [_claim(line=5.5, direction="LOWER", body="new")],
        ],
    )
    assert diff["temporalOrdering"] == "HAR_INTERNAL_STARTED_DATETIME"
    assert diff["filenameTimestampUsedForOrdering"] is False
    assert diff["pairs"][0]["laterResearchUsable"] is True
    assert diff["pairs"][0]["laterProductionForecastUsable"] is False
    assert diff["pairs"][0]["laterForecastBlocker"] == "OFFER_REVALIDATION_UNAVAILABLE"
