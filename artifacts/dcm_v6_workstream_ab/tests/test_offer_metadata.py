from dcm.research.coverage import coverage_report
from dcm.research.offer_metadata import recover_offer_metadata


def _request(pid):
    return {"scope": "OFFER", "scope_id": pid, "request_id": "REQ_" + pid, "need": "line_sides_modifier"}


def test_recovery_uses_har_row_and_never_infers_inverse_side():
    rows = [{
        "projectionId": "p1", "eventId": "e1", "market": "pass_yds", "statTypeRaw": "Passing Yards",
        "line": 250.5, "modifier": "STANDARD", "boardId": "FULL_GAME",
        "offeredHigher": True, "offeredLower": False, "sourceSnapshotTime": "2026-09-05T09:00:00Z",
        "sourceBodyHash": "body-hash",
    }]
    result = recover_offer_metadata(rows, [_request("p1"), _request("missing")], cutoff="2026-09-05T12:00:00Z")
    assert result["recovered"] == 1
    assert result["unresolved"][0]["reason"] == "OFFER_NOT_IN_ASOF_BOARD"
    claim = result["claims"][0]
    assert claim["claim_value"]["offered_higher"] is True
    assert claim["claim_value"]["offered_lower"] is False
    assert coverage_report([_request("p1")], result["claims"])["complete"]


def test_recovery_marks_missing_sides_explicitly():
    rows = [{
        "projectionId": "p2", "sourceSnapshotTime": "2026-09-05T09:00:00Z",
        "offeredHigher": False, "offeredLower": False,
    }]
    result = recover_offer_metadata(rows, [_request("p2")], cutoff="2026-09-05T12:00:00Z")
    assert result["recovered"] == 0
    assert result["unresolved"][0]["reason"] == "UNRESOLVED_PLATFORM_METADATA:OFFERED_SIDE_MISSING"
