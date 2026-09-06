"""HistoricalGapResolver event-sequence contract."""
from dcm.research.historical_gap import resolve_history_gap, stored_event_ids


def test_append_only_missing_events_38_40():
    stored = [str(i) for i in range(1, 38)]
    expected = [str(i) for i in range(1, 41)]
    resolved = resolve_history_gap(
        stored_event_ids=stored,
        expected_completed_event_ids=expected,
    )
    assert resolved["appendEventIds"] == ["38", "39", "40"]
    assert resolved["reuseEventIds"] == stored
    assert resolved["deletedEventIds"] == []
    assert resolved["silentlyDeleted"] is False
    assert resolved["reacquireStored"] is False
    assert resolved["deltaClass"] == "APPEND_MISSING_HISTORY"


def test_unexpected_extra_is_audited_not_deleted():
    resolved = resolve_history_gap(
        stored_event_ids=["1", "2", "ghost"],
        expected_completed_event_ids=["1", "2", "3"],
    )
    assert resolved["appendEventIds"] == ["3"]
    assert resolved["unexpectedExtraEventIds"] == ["ghost"]
    assert "ghost" not in resolved["deletedEventIds"]


def test_stored_event_ids_prefer_eventId():
    logs = [
        {"eventId": "E1", "date": "2026-08-01"},
        {"eventId": "E2", "date": "2026-08-02"},
    ]
    assert stored_event_ids(logs) == ["E1", "E2"]
