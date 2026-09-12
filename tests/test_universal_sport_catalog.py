from __future__ import annotations

import pytest

from dcm.contracts.universal_entities import SubjectType
from dcm.ingest.markets import map_league
from dcm.research.subject_offer_set import canonical_subject_fields
from dcm.research.classify import accounting_classify, research_disposition
from dcm.sports.common.catalog import PROFILES, normalize_sport_id, require_sport_profile


def test_research_os_declared_sport_families_have_profiles():
    assert set(PROFILES) == {
        "australian_rules", "baseball", "basketball", "combat", "cricket",
        "darts", "esports", "golf", "gridiron", "handball", "hockey",
        "lacrosse", "motorsport", "racket", "rugby", "soccer", "volleyball",
    }
    for profile in PROFILES.values():
        assert profile.event_structure
        assert profile.segment_structure
        assert profile.opportunity_resources
        assert profile.world_kind.endswith("World")
        assert profile.harvest_strategy


@pytest.mark.parametrize(
    ("alias", "canonical"),
    (("football", "gridiron"), ("F1", "motorsport"), ("boxing", "combat"),
     ("tennis", "racket"), ("AFL", "australian_rules"), ("lax", "lacrosse")),
)
def test_sport_aliases_are_deterministic(alias: str, canonical: str):
    assert normalize_sport_id(alias) == canonical
    assert require_sport_profile(alias).sport_id == canonical


@pytest.mark.parametrize(
    ("league", "expected"),
    (("FIBA", ("FIBA", "basketball")), ("MLS", ("MLS", "soccer")),
     ("F1", ("F1", "motorsport")), ("PDC", ("PDC", "darts")),
     ("AFL", ("AFL", "australian_rules")), ("PLL", ("PLL", "lacrosse"))),
)
def test_ingest_maps_declared_competitions_without_fuzzy_guessing(league, expected):
    assert map_league(league) == expected


def test_subject_type_defaults_follow_sport_profile_without_fabricating_player():
    driver = canonical_subject_fields({
        "playerId": "D1", "playerName": "Driver", "sportFamily": "F1",
        "league": "F1", "eventId": "R1",
    })
    fighter = canonical_subject_fields({
        "playerId": "F1", "playerName": "Fighter", "sportFamily": "boxing",
        "league": "BOXING", "eventId": "B1",
    })
    assert driver["sportId"] == "motorsport"
    assert driver["subjectType"] == SubjectType.DRIVER.value
    assert fighter["sportId"] == "combat"
    assert fighter["subjectType"] == SubjectType.FIGHTER.value


def test_unknown_sport_profile_still_fails_closed():
    with pytest.raises(LookupError, match="SPORT_PROFILE_UNSUPPORTED"):
        require_sport_profile("made_up_sport")


def test_known_research_only_sport_is_researchable_but_never_modeled():
    row = {
        "projectionId": "MLS-1", "playerId": "P1", "playerName": "Player",
        "sportFamily": "soccer", "league": "MLS", "eventId": "E1",
        "market": "shots", "line": 2.5, "modifier": "STANDARD",
        "offeredHigher": True, "offeredLower": True, "status": "pre_game",
    }
    assert research_disposition(row, research_shadow=False) == (False, "shadow")
    assert research_disposition(row, research_shadow=True) == (True, "shadow")
    assert accounting_classify(row) == ("UNSUPPORTED", "RESEARCH_ONLY_NOT_SELECTABLE")
