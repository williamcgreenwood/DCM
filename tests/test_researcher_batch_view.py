from __future__ import annotations

from dcm.chat.research_bridge import _researcher_view


def test_researcher_view_projects_singular_action_identity():
    view = _researcher_view(
        [
            {
                "actionId": "AA_EVENT_1",
                "requestId": "REQ_EVENT_1",
                "scopeId": "1",
                "need": "start_venue_starters_environment",
                "sourceCandidates": ["NFL_OFFICIAL"],
                "context": {"label": "SF @ LA", "league": "NFL", "sportFamily": "gridiron"},
            }
        ],
        [
            {
                "request_id": "REQ_EVENT_1",
                "scope": "EVENT",
                "scope_id": "1",
                "need": "start_venue_starters_environment",
            }
        ],
    )
    assert view == [
        {
            "actionId": "AA_EVENT_1",
            "requestIds": ["REQ_EVENT_1"],
            "displayLabel": "SF @ LA",
            "league": "NFL",
            "sport": "gridiron",
            "eventLabel": "SF @ LA",
            "affiliation": None,
            "opponent": None,
            "requiredFields": ["start_venue_starters_environment"],
            "permittedSources": ["NFL_OFFICIAL"],
        }
    ]
