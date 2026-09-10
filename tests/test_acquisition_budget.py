from __future__ import annotations

from dcm.research.acquisition import schedule_acquisition_actions


def _action(action_id: str, *, offer_count: int, event_id: str) -> dict[str, object]:
    return {
        "actionId": action_id,
        "scope": "EVENT",
        "scopeId": event_id,
        "eventId": event_id,
        "sourceFamily": "event_schedule_venue_status",
        "sourceId": "NFL_OFFICIAL",
        "requirementIds": [f"REQ_{action_id}"],
        "offerIds": [f"OFFER_{i}" for i in range(offer_count)],
        "dependentOfferCount": offer_count,
        "weight": 1.0,
        "cost": 1.0,
        "expectedGain": 1.0,
    }


def test_single_oversized_action_is_not_admitted_to_packet():
    schedule = schedule_acquisition_actions(
        {
            "actions": [
                _action("AA_BIG", offer_count=251, event_id="BIG"),
                _action("AA_OK", offer_count=2, event_id="OK"),
            ]
        },
        max_actions=8,
        max_dependent_offers=250,
    )

    assert "AA_BIG" not in schedule["selectedActionIds"]
    assert "AA_OK" in schedule["selectedActionIds"]
    assert schedule["dependentOfferBudgetUsed"] <= 250
    assert all(batch["dependentOfferCount"] <= 250 for batch in schedule["packedBatches"])
