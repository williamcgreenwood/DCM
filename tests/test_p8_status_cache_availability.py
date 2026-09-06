"""P8 adapters, cache, ESPN status, official schedule, availability mixture."""
from __future__ import annotations

from dcm.model.availability import availability_mixture
from dcm.model.worlds import simulate_player_worlds
from dcm.research.adapters.espn_status import ESPNStatusAdapter, canonicalize_status
from dcm.research.adapters.official_league import OfficialWNBAAdapter
from dcm.research.cache import ResearchCache, cache_identity
from dcm.research.entity_packets import build_event_research_packet
from dcm.research.lineup import build_lineup_effects
from dcm.research.provider import FixtureProvider, collect


ASOF = "2026-08-30T12:00:00Z"


def test_espn_status_maps_questionable_and_rest_out():
    payload = {
        "injuries": [
            {"player": "DeWanna Bonner", "team": "ATL", "status": "Questionable", "comment": "Rest"},
            {"player": "A'ja Wilson", "team": "LVA", "status": "Active"},
            {"id": "x", "displayName": "Injured Star", "status": "Out"},
        ]
    }
    recs = ESPNStatusAdapter(retrieved_at=ASOF).normalize({
        "url": "https://www.espn.com/wnba/injuries",
        "json": payload,
        "retrievedAt": ASOF,
        "publishedAt": ASOF,
    })
    by_name = {r["fields"]["playerName"]: r["fields"]["status"] for r in recs}
    assert by_name["DeWanna Bonner"] == "QUESTIONABLE"
    assert by_name["A'ja Wilson"] == "ACTIVE"
    assert by_name["Injured Star"] == "OUT"
    assert canonicalize_status("game time decision") == "QUESTIONABLE"
    assert canonicalize_status("???") == "UNKNOWN"


def test_official_wnba_schedule_marks_started_event():
    payload = {
        "games": [
            {
                "gameId": "E1",
                "status": "scheduled",
                "start": "2026-08-30T21:30:00Z",
                "venue": "College Park Center",
                "home": "DAL",
                "away": "CON",
            },
            {
                "gameId": "MINATL",
                "status": "in_progress",
                "start": "2026-08-30T17:00:00Z",
                "venue": "State Farm Arena",
                "home": "ATL",
                "away": "MIN",
            },
        ]
    }
    recs = OfficialWNBAAdapter(retrieved_at=ASOF).normalize({
        "url": "https://www.wnba.com/schedule",
        "json": payload,
        "retrievedAt": ASOF,
        "league": "WNBA",
    })
    by_id = {r["fields"]["eventId"]: r["fields"]["gameStatus"] for r in recs}
    assert by_id["E1"] == "SCHEDULED"
    assert by_id["MINATL"] == "IN_PROGRESS"
    packet = build_event_research_packet(
        event_id="MINATL", as_of=ASOF, league="WNBA", official_json=payload,
    )
    assert "EVENT_STATUS_IN_PROGRESS" in packet["flags"]
    assert packet["gameStatus"] == "IN_PROGRESS"


def test_research_cache_respects_as_of_not_wall_clock():
    cache = ResearchCache()
    ident = cache_identity(
        source_id="BASKETBALL_REFERENCE",
        adapter_version="br-html-1",
        as_of="2026-08-30T12:00:00Z",
        entity="PAIGE",
        kind="PLAYER_GAME_LOG",
    )
    cache.put(ident, {"logs": [1, 2, 3]}, published_at="2026-08-29T00:00:00Z")
    assert cache.get(ident, as_of="2026-08-30T12:00:00Z")["logs"] == [1, 2, 3]
    late = cache_identity(
        source_id="ESPN",
        adapter_version="espn-status-1",
        as_of="2026-08-30T12:00:00Z",
        entity="BONNER",
        kind="STATUS",
    )
    cache.put(late, {"status": "OUT"}, published_at="2026-08-30T19:00:00Z")
    assert cache.get(late, as_of="2026-08-30T12:00:00Z") is None
    assert late["longevity"] == "SHORT_LIVED"
    assert ident["longevity"] == "LONG_LIVED"


def test_availability_mixture_blocks_questionable_records_probable():
    q = availability_mixture("QUESTIONABLE")
    assert q["excessiveUncertainty"] is True
    assert q["playableBlockedByMixture"] is True
    assert 0.0 < q["pPlay"] < 1.0
    p = availability_mixture("PROBABLE")
    assert p["pPlay"] > 0.8
    assert p["playableBlockedByMixture"] is False
    out = availability_mixture("OUT")
    assert out["playableBlockedByMixture"] is True
    effects = build_lineup_effects([
        {"label": "without X", "rawEffect": 0.25, "minutes": 40},
        {"label": "empty"},
    ])
    assert effects["priorUsedAsResearch"] is False
    assert effects["usableCount"] == 1


def test_collect_cache_hits_on_second_pass():
    cutoff = ASOF
    reqs = [{
        "request_id": "REQ_T_DAL",
        "scope": "TEAM",
        "scope_id": "DAL",
        "need": "pace_matchup",
        "forecast_cutoff": cutoff,
    }]
    cache = ResearchCache()
    provider = FixtureProvider(cutoff)
    first = collect(reqs, provider, cache=cache)
    assert first["cacheHits"] == 0
    assert first["claims"]
    second = collect(reqs, provider, cache=cache)
    assert second["cacheHits"] >= 1
    assert len(second["claims"]) >= 1


def test_questionable_mixture_produces_sit_worlds_and_stays_playable_blocked():
    q = availability_mixture("QUESTIONABLE")
    assert q["playableBlockedByMixture"] is True
    row = {
        "projectionId": "p1", "sportFamily": "basketball", "league": "WNBA",
        "eventId": "E1", "teamId": "DAL", "playerId": "BONNER", "market": "pts",
        "boardId": "FULL_GAME", "line": 6.5, "role": "F",
    }
    snap = {
        "parameters": {"minutes_mean": 28.0, "minutes_sd": 3.0, "family": "basketball"},
        "availabilityMixture": q,
        "status": "QUESTIONABLE",
        "blocker": "PLAYER_STATUS_UNCERTAIN",
    }
    worlds = simulate_player_worlds(row, n=64, seed="mix-test", parameter_snapshot=snap)
    sit = [w for w in worlds if w.get("_availabilityState") == "SIT" or float(w.get("minutes") or 0) == 0.0]
    play = [w for w in worlds if float(w.get("minutes") or 0) > 0.0]
    assert sit, "QUESTIONABLE must emit sit worlds"
    assert play, "QUESTIONABLE still models play worlds for diagnostics"
    assert q["pSit"] > 0.2


def test_active_does_not_mix_sit_worlds():
    row = {
        "projectionId": "p1", "sportFamily": "basketball", "league": "WNBA",
        "eventId": "E1", "teamId": "DAL", "playerId": "PAIGE", "market": "pts",
        "boardId": "FULL_GAME", "line": 21.5, "role": "G",
    }
    snap = {
        "parameters": {"minutes_mean": 32.0, "minutes_sd": 2.0, "family": "basketball"},
        "availabilityMixture": availability_mixture("ACTIVE"),
        "status": "ACTIVE",
    }
    worlds = simulate_player_worlds(row, n=32, seed="active-nomix", parameter_snapshot=snap)
    assert all(float(w.get("minutes") or 0) > 0.0 for w in worlds)
    assert not any(w.get("_availabilityState") == "SIT" for w in worlds)
